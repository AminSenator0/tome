# macOS Setup & Operation Guide

Tome is fully supported on macOS, optimized for both **Apple Silicon** (M1, M2, M3, M4 series with Metal / MPS hardware acceleration) and **Intel Macs** (x86_64).

---

## 1. Quickstart & Prerequisites

### 1.1 Homebrew Prerequisites
If you do not have Homebrew installed, install it from [brew.sh](https://brew.sh). Then install Python 3.11 and LibreOffice:

```bash
# Install Python 3.11 and LibreOffice for PDF compilation
brew install python@3.11
brew install --cask libreoffice
```

### 1.2 Repository Setup & Virtual Environment
```bash
# Clone or navigate into the repository
cd book

# Create and activate virtual environment using Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate

# Install Tome and all dependencies
pip install --upgrade pip
pip install -e .
```

Once installed, the `tome` command is automatically symlinked into your user executable paths (`~/.local/bin`, `~/bin`, or Homebrew bin). Ensure `~/.local/bin` or `~/bin` is in your shell `PATH`:

```bash
# For zsh (default on macOS):
echo 'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 2. OfficeCLI Automatic Binary Management

Tome uses **OfficeCLI** for compiling Markdown chapters into styled Microsoft Word (`.docx`) books.

### Automatic Detection & Architecture Matching
When compiling books (`tome docx` or `tome run`), Tome automatically:
1. Detects your hardware architecture:
   - **Apple Silicon (M1/M2/M3/M4)**: Downloads `officecli-mac-arm64`.
   - **Intel Mac**: Downloads `officecli-mac-x64`.
2. Verifies binary compatibility:
   - If a project folder was transferred from Linux containing an ELF Linux binary in `bin/officecli`, Tome detects the format mismatch, removes the incompatible binary, and automatically downloads the native macOS Mach-O executable.
3. Automatically clears macOS Gatekeeper quarantine (`xattr -d com.apple.quarantine bin/officecli`) to prevent security dialog popups.

### Manual Verification
```bash
bin/officecli --version
```
Output:
```text
officecli version 1.0.147
```

---

## 3. Apple Silicon Hardware Acceleration (MPS)

When extracting entities, character personas, and world taxonomies with GLiNER:
- Tome automatically detects Apple Silicon and binds to PyTorch Metal Performance Shaders (`mps` device).
- If any particular model layer is unsupported by the Metal backend, Tome provides an automatic graceful fallback to multi-threaded CPU inference without crashing.
- OpenMP multi-library conflict guards (`KMP_DUPLICATE_LIB_OK=TRUE`) are automatically configured to prevent crashes with duplicate OpenMP dylibs.

---

## 4. LibreOffice on macOS

Tome automatically discovers LibreOffice across standard macOS locations:
- `/Applications/LibreOffice.app/Contents/MacOS/soffice`
- `~/Applications/LibreOffice.app/Contents/MacOS/soffice`
- `/opt/homebrew/bin/soffice`
- `/usr/local/bin/soffice`

You do **not** need to manually configure environment variables or add symlinks for LibreOffice to convert `.docx` manuscripts into `.pdf`.

---

## 5. System Fonts & Typography

Tome supports local project fonts in `fonts/` as well as native macOS system font directories:
- `/Library/Fonts`
- `/System/Library/Fonts`
- `/System/Library/Fonts/Supplemental` (Times New Roman, Arial, Georgia, etc.)
- `~/Library/Fonts` (user-installed fonts)

You can specify Persian/Eastern fonts (such as `Vazirmatn.ttf` or `B Nazanin`) and Western fonts in `tome.json` or pass them via CLI `--eastern-font` and `--western-font`.

---

## 6. Running as a 24/7 Background Service (`launchd`)

On macOS, Tome integrates directly with Apple's native **launchd** service daemon via LaunchAgents.

### Install & Start Background Service
```bash
tome web service install --host 127.0.0.1 --port 8000
```
This generates and loads `~/Library/LaunchAgents/com.tome.web.plist`, starting the web platform and API in the background.

### Check Service Status
```bash
tome web service status
```

### Stop & Uninstall Service
```bash
tome web service uninstall
```

---

## 7. Terminal & TUI on macOS

The interactive Terminal User Interface (`tome` with no arguments) runs seamlessly in:
- **Terminal.app** (macOS default)
- **iTerm2**
- **Warp**
- **Ghostty**, **Alacritty**, and **Kitty**

Keybindings:
- `Ctrl + C` or `Ctrl + Q`: Cleanly quit TUI.
- Mouse / Trackpad scrolling is supported across all tabbed views.
