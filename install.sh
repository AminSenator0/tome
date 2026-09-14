#!/usr/bin/env bash
# ==============================================================================
# Tome Automated Installer & Environment Bootstrapper
# Supports: macOS (Apple Silicon M1/M2/M3/M4 & Intel) & Linux (Ubuntu/Debian/VPS)
# Fully idempotent: skips already installed components and recovers from errors.
# ==============================================================================
set -Eeuo pipefail

# ------------------------------------------------------------------------------
# Formatting & Colors
# ------------------------------------------------------------------------------
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
MAGENTA="\033[0;35m"
DIM="\033[2m"
RESET="\033[0m"

log_info()    { echo -e "${CYAN}‣${RESET} $*"; }
log_success() { echo -e "${GREEN}✓${RESET} $*"; }
log_warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
log_step()    { echo -e "\n${BOLD}${MAGENTA}==>${RESET} ${BOLD}$*${RESET}"; }
log_skip()    { echo -e "${DIM}[SKIP]${RESET} $*"; }

error_handler() {
    local exit_code=$1
    local line_no=$2
    echo -e "\n${BOLD}${RED}✖ Error encountered on line ${line_no} (Exit code: ${exit_code})${RESET}"
    echo -e "${YELLOW}Please review the error message above or refer to SETUP_COMMANDS.txt for manual execution.${RESET}\n"
    exit "${exit_code}"
}
trap 'error_handler $? $LINENO' ERR

# ------------------------------------------------------------------------------
# STEP 0: Location & Environment Detection
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}              TOME UNIVERSAL AUTOMATED INSTALLER & ENVIRONMENT BOOTSTRAPPER   ${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64|amd64) ARCH_NORMALIZED="x64" ;;
    arm64|aarch64) ARCH_NORMALIZED="arm64" ;;
    *) ARCH_NORMALIZED="$ARCH" ;;
esac

echo -e "• Target Directory:  ${CYAN}${SCRIPT_DIR}${RESET}"
echo -e "• Operating System:  ${CYAN}${OS}${RESET}"
echo -e "• CPU Architecture:  ${CYAN}${ARCH} (${ARCH_NORMALIZED})${RESET}"

# Privilege & Sudo Detection
IS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=true
fi

if [ "$OS" = "darwin" ] && [ "$IS_ROOT" = true ]; then
    echo -e "\n${BOLD}${RED}ERROR: Do not run this installer with sudo on macOS!${RESET}"
    echo -e "Homebrew and macOS user tools require normal user privileges."
    echo -e "Please execute without sudo: ${BOLD}./install.sh${RESET}\n"
    exit 1
fi

SUDO_CMD=""
if [ "$OS" = "linux" ] && [ "$IS_ROOT" = false ]; then
    if command -v sudo &>/dev/null; then
        SUDO_CMD="sudo"
    fi
fi

can_run_sudo() {
    if [ "$IS_ROOT" = true ]; then
        return 0
    fi
    if [ -n "$SUDO_CMD" ]; then
        if sudo -n true 2>/dev/null; then
            return 0
        fi
        if [ -t 0 ] && [ -n "${TERM:-}" ]; then
            return 0
        fi
    fi
    return 1
}

# ------------------------------------------------------------------------------
# STEP 1: Platform-Specific System Bootstrapping
# ------------------------------------------------------------------------------
if [ "$OS" = "darwin" ]; then
    log_step "[1/9] Checking macOS Developer Tools & Homebrew..."

    # 1.1 Apple Command Line Tools
    if xcode-select -p &>/dev/null; then
        log_skip "Apple Command Line Tools already installed ($(xcode-select -p))."
    else
        log_info "Installing Apple Command Line Tools..."
        xcode-select --install 2>/dev/null || true
        if [ -t 0 ]; then
            echo -e "${YELLOW}Please click 'Install' on the popup dialog if prompted.${RESET}"
            until xcode-select -p &>/dev/null; do
                sleep 3
            done
        fi
        log_success "Apple Command Line Tools configured."
    fi

    # 1.2 Homebrew
    BREW_BIN=""
    if [ "$ARCH" = "arm64" ] && [ -f "/opt/homebrew/bin/brew" ]; then
        BREW_BIN="/opt/homebrew/bin/brew"
    elif [ -f "/usr/local/bin/brew" ]; then
        BREW_BIN="/usr/local/bin/brew"
    elif command -v brew &>/dev/null; then
        BREW_BIN="$(command -v brew)"
    fi

    if [ -n "$BREW_BIN" ]; then
        log_skip "Homebrew is already installed (${BREW_BIN})."
    else
        log_info "Homebrew not found. Installing official Homebrew..."
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ "$ARCH" = "arm64" ] && [ -f "/opt/homebrew/bin/brew" ]; then
            BREW_BIN="/opt/homebrew/bin/brew"
        else
            BREW_BIN="/usr/local/bin/brew"
        fi
    fi

    eval "$("${BREW_BIN}" shellenv)"

    # Persist Homebrew in shell profiles
    for shell_rc in "$HOME/.zprofile" "$HOME/.zshrc"; do
        if [ ! -f "$shell_rc" ] || ! grep -q "brew shellenv" "$shell_rc"; then
            echo "eval \"\$(${BREW_BIN} shellenv)\"" >> "$shell_rc"
            log_info "Added Homebrew environment to ${shell_rc}"
        fi
    done
    log_success "Homebrew active and configured."

elif [ "$OS" = "linux" ]; then
    log_step "[1/9] Checking Linux System Dependencies..."

    MISSING_PKGS=()
    for pkg_cmd in curl git; do
        if ! command -v "$pkg_cmd" &>/dev/null; then
            MISSING_PKGS+=("$pkg_cmd")
        fi
    done

    if [ ${#MISSING_PKGS[@]} -eq 0 ] && command -v python3 &>/dev/null; then
        log_skip "Core system tools (curl, git, python3) are already installed."
    else
        if can_run_sudo; then
            log_info "Installing missing system packages via package manager (${MISSING_PKGS[*]:-})..."
            if command -v apt-get &>/dev/null; then
                $SUDO_CMD apt-get update -y || true
                $SUDO_CMD apt-get install -y "${MISSING_PKGS[@]}" python3-venv python3-pip build-essential || true
            elif command -v dnf &>/dev/null; then
                $SUDO_CMD dnf install -y "${MISSING_PKGS[@]}" python3-pip gcc || true
            fi
            log_success "Linux system dependencies installed."
        else
            log_warn "System package installation skipped (running without sudo). Proceeding with user-space tools..."
        fi
    fi
fi

# ------------------------------------------------------------------------------
# STEP 2: Core Tool Verification (Git, Python, uv, LibreOffice)
# ------------------------------------------------------------------------------
log_step "[2/9] Verifying Core Tools (Git, Python 3.11, Astral uv, LibreOffice)..."

# 2.1 Git
if command -v git &>/dev/null; then
    log_skip "Git is available ($(git --version))."
elif [ "$OS" = "darwin" ]; then
    brew install git
    log_success "Git installed via Homebrew."
fi

# 2.2 Python 3.11+
PYTHON_TARGET=""
if command -v python3.11 &>/dev/null; then
    PYTHON_TARGET="$(command -v python3.11)"
    log_skip "Python 3.11 is available (${PYTHON_TARGET})."
elif [ "$OS" = "darwin" ]; then
    log_info "Installing Python 3.11 via Homebrew..."
    brew install python@3.11
    PYTHON_TARGET="$(brew --prefix python@3.11)/bin/python3.11"
    log_success "Python 3.11 installed."
elif command -v python3 &>/dev/null; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' &>/dev/null; then
        PYTHON_TARGET="$(command -v python3)"
        log_skip "Python $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")') found at ${PYTHON_TARGET}."
    else
        PYTHON_TARGET="3.11"
    fi
fi

# 2.3 Astral uv
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/bin:$PATH"

if command -v uv &>/dev/null; then
    log_skip "Astral uv is available ($(uv --version))."
elif [ "$OS" = "darwin" ] && command -v brew &>/dev/null; then
    log_info "Installing Astral uv via Homebrew..."
    brew install uv || curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    log_success "Astral uv installed."
else
    log_info "Installing Astral uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    log_success "Astral uv installed."
fi

# 2.4 LibreOffice (for DOCX -> PDF conversion)
if [ "$OS" = "darwin" ]; then
    if [ -d "/Applications/LibreOffice.app" ] || [ -d "$HOME/Applications/LibreOffice.app" ] || command -v soffice &>/dev/null; then
        log_skip "LibreOffice is already installed."
    else
        log_info "Installing LibreOffice for macOS (PDF compiler)..."
        brew install --cask libreoffice 2>/dev/null || log_warn "LibreOffice cask skipped. You can manually install it anytime."
        log_success "LibreOffice setup complete."
    fi
elif [ "$OS" = "linux" ]; then
    if command -v soffice &>/dev/null || command -v libreoffice &>/dev/null; then
        log_skip "LibreOffice is already installed."
    elif [ "$IS_ROOT" = true ] || sudo -n true 2>/dev/null; then
        log_info "Installing LibreOffice for Linux PDF conversion..."
        if command -v apt-get &>/dev/null; then
            $SUDO_CMD apt-get install -y libreoffice || true
        elif command -v dnf &>/dev/null; then
            $SUDO_CMD dnf install -y libreoffice || true
        fi
    else
        log_skip "LibreOffice not installed (optional for direct PDF export). DOCX generation works natively via OfficeCLI."
    fi
fi

# ------------------------------------------------------------------------------
# STEP 3: Isolated Virtual Environment (.venv) Setup
# ------------------------------------------------------------------------------
log_step "[3/9] Configuring Virtual Environment (.venv)..."

VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_PY="${VENV_DIR}/bin/python"

VENV_VALID=false
if [ -x "${VENV_PY}" ]; then
    if "${VENV_PY}" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" &>/dev/null 2>&1; then
        VENV_VALID=true
    fi
fi

if [ "$VENV_VALID" = true ]; then
    log_skip "Virtual environment (.venv) already exists and is healthy ($("${VENV_PY}" --version))."
else
    log_info "Creating fresh virtual environment..."
    rm -rf "${VENV_DIR}"
    if command -v uv &>/dev/null; then
        uv venv --python 3.11 "${VENV_DIR}" 2>/dev/null || uv venv "${VENV_DIR}"
    elif [ -n "$PYTHON_TARGET" ] && [ -x "$PYTHON_TARGET" ]; then
        "$PYTHON_TARGET" -m venv "${VENV_DIR}"
    else
        python3 -m venv "${VENV_DIR}"
    fi
    log_success "Created virtual environment at ${VENV_DIR}"
fi

# ------------------------------------------------------------------------------
# STEP 4: Install Tome & Core Python Dependencies
# ------------------------------------------------------------------------------
log_step "[4/9] Installing Tome Packages & Dependencies..."

DEPS_READY=false
if "${VENV_PY}" -c "import importlib.metadata; importlib.metadata.version('tome')" &>/dev/null 2>&1; then
    DEPS_READY=true
fi

if [ "$DEPS_READY" = true ]; then
    log_skip "Tome and core dependencies are already installed."
else
    log_info "Installing Python dependencies (using Astral uv for maximum speed)..."
    if command -v uv &>/dev/null; then
        VIRTUAL_ENV="${VENV_DIR}" uv pip install -e .
    else
        "${VENV_PY}" -m pip install --upgrade pip
        "${VENV_PY}" -m pip install -e .
    fi
    log_success "All dependencies installed successfully."
fi

# ------------------------------------------------------------------------------
# STEP 5: Register 'tome' Command Globally in PATH & Shell Profiles
# ------------------------------------------------------------------------------
log_step "[5/9] Registering 'tome' Command in System & User PATH..."

"${VENV_PY}" -m tome.cli.main install-cli

export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
if [ "$OS" = "darwin" ] && [ -d "/opt/homebrew/bin" ]; then
    export PATH="/opt/homebrew/bin:$PATH"
fi

if command -v tome &>/dev/null; then
    log_success "'tome' command is active in current session ($(command -v tome))."
else
    log_info "'tome' executable linked to ~/.local/bin/tome. Open a new terminal session or run 'source ~/.zshrc' to activate."
fi

# ------------------------------------------------------------------------------
# STEP 6: Pre-download & Cache GLiNER NLP Model
# ------------------------------------------------------------------------------
log_step "[6/9] Verifying GLiNER Named-Entity Recognition Model..."

LOCAL_MODEL_FOUND=false
DETECTED_MODEL_DIR=""

for test_dir in \
    "${SCRIPT_DIR}/models/gliner_medium-v2.1" \
    "${SCRIPT_DIR}/models/urchade/gliner_medium-v2.1" \
    "${PWD}/models/gliner_medium-v2.1" \
    "${PWD}/models/urchade/gliner_medium-v2.1"; do
    if [ -d "$test_dir" ] && ([ -f "$test_dir/model.safetensors" ] || [ -f "$test_dir/pytorch_model.bin" ] || [ -f "$test_dir/config.json" ]); then
        LOCAL_MODEL_FOUND=true
        DETECTED_MODEL_DIR="$test_dir"
        break
    fi
done

HF_CACHE_DIR="$HOME/.cache/huggingface/hub/models--urchade--gliner_medium-v2.1"

if [ "$LOCAL_MODEL_FOUND" = true ]; then
    log_skip "GLiNER model detected in local directory (${DETECTED_MODEL_DIR}). Using existing offline weights (0 MB downloaded)."
elif [ -d "$HF_CACHE_DIR/snapshots" ] && [ -n "$(ls -A "$HF_CACHE_DIR/snapshots" 2>/dev/null)" ]; then
    log_skip "GLiNER model (urchade/gliner_medium-v2.1) is already cached in HuggingFace cache (${HF_CACHE_DIR})."
else
    log_info "Downloading GLiNER model for offline named-entity extraction..."
    "${VENV_PY}" -m tome.cli.main setup-model
    log_success "GLiNER model downloaded and cached."
fi

# ------------------------------------------------------------------------------
# STEP 7: Initialize & Verify OfficeCLI for Architecture
# ------------------------------------------------------------------------------
log_step "[7/9] Verifying Native OfficeCLI Binary..."

OFFICECLI_BIN="${SCRIPT_DIR}/bin/officecli"
OFFICECLI_VALID=false

if [ -x "${OFFICECLI_BIN}" ]; then
    if "${VENV_PY}" -c "from pathlib import Path; from tome.core.docx import is_compatible_officecli_binary; exit(0 if is_compatible_officecli_binary(Path('${OFFICECLI_BIN}')) else 1)" &>/dev/null 2>&1; then
        OFFICECLI_VALID=true
    fi
fi

if [ "$OFFICECLI_VALID" = true ]; then
    log_skip "OfficeCLI binary already installed and verified for ${OS} (${ARCH_NORMALIZED})."
else
    log_info "Downloading native OfficeCLI binary for ${OS} (${ARCH_NORMALIZED})..."
    "${VENV_PY}" -c "from tome.core.docx import find_officecli; print('OfficeCLI ready at:', find_officecli())"
    log_success "OfficeCLI initialized."
fi

if [ -x "${OFFICECLI_BIN}" ]; then
    OFFICECLI_VERSION="$("${OFFICECLI_BIN}" --version 2>/dev/null || echo 'officecli verified')"
    log_success "${OFFICECLI_VERSION}"
fi

# ------------------------------------------------------------------------------
# STEP 8: Verify Configuration (tome.json)
# ------------------------------------------------------------------------------
log_step "[8/9] Checking Configuration File (tome.json)..."

if [ -f "${SCRIPT_DIR}/tome.json" ]; then
    log_skip "Configuration file tome.json already exists."
else
    if [ -f "${SCRIPT_DIR}/tome.example.json" ]; then
        cp "${SCRIPT_DIR}/tome.example.json" "${SCRIPT_DIR}/tome.json"
        log_success "Created tome.json from template."
    else
        "${VENV_PY}" -c "from tome.config import TomeConfig; TomeConfig().save_config(Path('tome.json'))"
        log_success "Generated default tome.json."
    fi
    echo -e "${YELLOW}Note: Remember to update 'api_key' in tome.json with your LLM provider credentials.${RESET}"
fi

# ------------------------------------------------------------------------------
# STEP 9: Final Health Verification & Ready Banner
# ------------------------------------------------------------------------------
log_step "[9/9] Running Final Health Verification..."

"${VENV_PY}" -m tome.cli.main --help >/dev/null

echo -e "\n${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}               🎉 TOME IS FULLY INSTALLED AND READY TO USE!                   ${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}\n"

echo -e "${BOLD}Installation Summary:${RESET}"
echo -e "  • ${BOLD}Operating System:${RESET}   ${OS} (${ARCH_NORMALIZED})"
echo -e "  • ${BOLD}Python Environment:${RESET} ${VENV_DIR} ($("${VENV_PY}" --version))"
echo -e "  • ${BOLD}Tome Command:${RESET}       $(command -v tome 2>/dev/null || echo "${HOME}/.local/bin/tome")"
echo -e "  • ${BOLD}OfficeCLI Status:${RESET}   ${OFFICECLI_BIN} (Native ${OS} binary verified)"
echo -e "  • ${BOLD}Config File:${RESET}        ${SCRIPT_DIR}/tome.json"
echo -e "  • ${BOLD}Default User:${RESET}       khorshid / 1382\n"

echo -e "${BOLD}Quickstart Commands (Run from ANY terminal window):${RESET}"
echo -e "  1. ${CYAN}tome tui${RESET}               Launch the interactive Terminal UI"
echo -e "  2. ${CYAN}tome web${RESET}               Launch Web Platform & REST API (http://127.0.0.1:8000)"
echo -e "  3. ${CYAN}tome run \"book.epub\" -t${RESET} Run full pipeline (Extract, Translate, Compile DOCX)"
if [ "$OS" = "darwin" ]; then
    echo -e "  4. ${CYAN}tome service install${RESET}   Run 24/7 background service via native macOS launchd"
else
    echo -e "  4. ${CYAN}sudo tome service install${RESET} Run 24/7 background service via Linux systemd"
fi
echo ""
