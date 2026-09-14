# OfficeCLI Installation & Setup Guide

Tome uses **OfficeCLI** as its document compilation engine to assemble Markdown chapter files into styled Microsoft Word (`.docx`) books with running headers, footers, and typography.

OfficeCLI compiles OpenXML documents directly without requiring Microsoft Office, LibreOffice, or external runtime interpreters.

---

## 1. Automatic Download & Configuration

When you run `tome docx`, `tome run`, or `tome translate`, Tome automatically checks for an available `officecli` binary:

1. Checks the system `PATH` for an installed `officecli` executable.
2. Checks the local project directory `bin/officecli` (or `bin/officecli.exe` on Windows).
3. If not found, Tome detects the current operating system and architecture, downloads the latest release binary from GitHub, places it in `bin/`, and sets execute permissions automatically.

---

## 2. Manual Installation

If your environment is air-gapped, behind a firewall, or requires manual binary verification, install OfficeCLI manually:

### Linux (x86_64)
```bash
mkdir -p bin
curl -L -o bin/officecli https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.145/officecli-linux-x64
chmod +x bin/officecli
```

### Linux (ARM64 / aarch64)
```bash
mkdir -p bin
curl -L -o bin/officecli https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.145/officecli-linux-arm64
chmod +x bin/officecli
```

### macOS (Apple Silicon / arm64)
```bash
mkdir -p bin
curl -L -o bin/officecli https://github.com/iOfficeAI/OfficeCLI/releases/latest/download/officecli-mac-arm64
chmod +x bin/officecli
xattr -d com.apple.quarantine bin/officecli 2>/dev/null || true
```

### macOS (Intel / x86_64)
```bash
mkdir -p bin
curl -L -o bin/officecli https://github.com/iOfficeAI/OfficeCLI/releases/latest/download/officecli-mac-x64
chmod +x bin/officecli
xattr -d com.apple.quarantine bin/officecli 2>/dev/null || true
```

### Windows (x64)
```powershell
New-Item -ItemType Directory -Force -Path bin
Invoke-WebRequest -Uri "https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.145/officecli-win-x64.exe" -OutFile "bin/officecli.exe"
```

---

## 3. Verifying Installation

Verify that the binary operates correctly:

```bash
bin/officecli --version
```

Output:
```text
officecli version 1.0.145
```

---

## 4. Fonts Management

OfficeCLI binds typography based on the fonts available to your operating system or local files provided in `fonts/`:

- **Default Font Directory**: Place `.ttf` or `.otf` files directly inside the project's `fonts/` directory:
  - `fonts/B-Nazanin.ttf` (Eastern serif typeface)
  - `fonts/Vazirmatn.ttf` (Eastern sans-serif typeface)
  - `fonts/Times.ttf` (Western serif typeface)
- **Automatic Fallback**: If a requested font is not found locally, Tome registers the font name as a system typeface inside the document styles, allowing target systems to render it with installed system fonts.

---

## 5. Troubleshooting

- **Permission Denied (`EACCES`)**: Run `chmod +x bin/officecli` to grant execute permissions.
- **Missing Shared Libraries**: On minimal Linux containers (Alpine/Debian Slim), ensure `libc6` or `glibc` is available.
- **Headless Environments**: OfficeCLI requires no display server (X11 or Wayland) and runs cleanly in headless Docker containers and systemd services.
