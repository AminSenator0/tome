# Production VPS Deployment Checklist & Guide

This guide outlines best practices for deploying Tome on a Linux Virtual Private Server (VPS) for headless, automated book processing.

---

## 1. Pre-Deployment Checklist

- [ ] **Python Runtime**: Python 3.11+ installed.
- [ ] **System Dependencies**: `build-essential`, `libgl1` (for PDF rendering), `curl`.
- [ ] **Binary Setup**: OfficeCLI binary downloaded to `bin/` or installed globally.
- [ ] **Font Assets**: Eastern and Western TTF fonts placed in `fonts/` (e.g. `B-Nazanin.ttf`, `Vazirmatn.ttf`, `Times.ttf`).
- [ ] **API Access**: AvalAI API key generated and tested.
- [ ] **Network & Proxy**: SOCKS5 / HTTP proxy configured if deploying from an IP with restricted egress.
- [ ] **Storage**: Minimum 10 GB free disk space for raw PDFs, GLiNER model weights, and output artifacts.

---

## 2. Server Installation Steps

### 2.1 System Packages
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv curl libgl1
```

### 2.2 Repository Setup & Virtual Environment
```bash
git clone https://github.com/your-org/tome.git /opt/tome
cd /opt/tome
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 2.3 OfficeCLI Installation
Tome automatically downloads OfficeCLI if not present, or you can install it manually:
```bash
mkdir -p bin
curl -L -o bin/officecli https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.145/officecli-linux-x64
chmod +x bin/officecli
```

### 2.4 Fonts Setup
Place required fonts in the `fonts/` directory:
```bash
mkdir -p fonts
# Copy B-Nazanin.ttf, Vazirmatn.ttf, Times.ttf into fonts/
```

---

## 3. Configuration (`tome.json`)

Create `/opt/tome/tome.json` with production settings:
```json
{
  "llm_base_url": "https://api.avalai.ir/v1",
  "llm_api_key": "aa-YOUR_AVALAI_API_KEY",
  "llm_model": "qwen3.8-flash",
  "llm_timeout": 300,
  "stream_response": true,
  "proxy_enabled": false,
  "proxy_type": "socks5",
  "proxy_host": "127.0.0.1",
  "proxy_port": 10808,
  "target_language": "Persian",
  "persian_nlp": true,
  "compile_docx": true,
  "eastern_font": "B-Nazanin.ttf",
  "western_font": "Times.ttf",
  "log_retention_days": 14
}
```

---

## 4. Systemd Service Setup

To run the Tome REST API as a background daemon:

Create `/etc/systemd/system/tome.service`:
```ini
[Unit]
Description=Tome Manuscript Processing API Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/tome
Environment="PATH=/opt/tome/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/tome/.venv/bin/uvicorn tome.api.routes:app --host 0.0.0.0 --port 8000 --workers 2

Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tome
sudo systemctl start tome
sudo systemctl status tome
```

---

## 5. Reverse Proxy with Nginx (Optional)

```nginx
server {
    listen 80;
    server_name tome.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
        proxy_connect_timeout 60s;
    }
}
```
