import os
import shutil
import subprocess
import sys
from pathlib import Path


def generate_systemd_unit(
    exec_path: str,
    work_dir: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    user: str | None = None,
) -> str:
    user_line = f"User={user}\n" if user and user != "root" else ""
    return f"""[Unit]
Description=Tome Web Platform & Publishing Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
{user_line}WorkingDirectory={work_dir}
ExecStart={exec_path} web --host {host} --port {port}
Restart=always
RestartSec=5s
KillMode=process
TimeoutStopSec=30
StandardOutput=append:{work_dir}/logs/web/service.log
StandardError=append:{work_dir}/logs/web/service.log
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""


def generate_launchd_plist(
    exec_args: list[str],
    work_dir: str,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> str:
    full_args = exec_args + ["web", "--host", host, "--port", str(port)]
    args_xml = "".join(f"        <string>{a}</string>\n" for a in full_args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tome.web</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}    </array>
    <key>WorkingDirectory</key>
    <string>{work_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{work_dir}/logs/web/service.log</string>
    <key>StandardErrorPath</key>
    <string>{work_dir}/logs/web/service.log</string>
</dict>
</plist>
"""


def install_service(
    host: str = "0.0.0.0",
    port: int = 8000,
    system_wide: bool = True,
) -> tuple[bool, str]:
    if sys.platform not in ("linux", "darwin"):
        return False, "Background service registration is only supported on Linux (systemd) and macOS (launchd)."

    work_dir = str(Path.cwd().resolve())
    logs_web = Path(work_dir) / "logs" / "web"
    logs_web.mkdir(parents=True, exist_ok=True)

    exec_path = shutil.which("tome")

    if sys.platform == "darwin":
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist_path = plist_dir / "com.tome.web.plist"

        exec_args = [exec_path] if exec_path else [sys.executable, "-m", "tome.cli.main"]
        content = generate_launchd_plist(exec_args=exec_args, work_dir=work_dir, host=host, port=port)
        try:
            plist_path.write_text(content, encoding="utf-8")
            subprocess.run(["launchctl", "unload", "-w", str(plist_path)], capture_output=True, check=False)
            res = subprocess.run(["launchctl", "load", "-w", str(plist_path)], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, f"Tome macOS service registered and started via launchd at {plist_path}"
            return True, f"Tome macOS launchd service plist written to {plist_path} (load exit code: {res.returncode})"
        except Exception as exc:
            return False, f"Failed to install macOS launchd service: {exc}"

    if not exec_path:
        exec_path = f"{sys.executable} -m tome.cli.main"

    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False

    if is_root and system_wide:
        unit_path = Path("/etc/systemd/system/tome.service")
        content = generate_systemd_unit(
            exec_path=exec_path,
            work_dir=work_dir,
            host=host,
            port=port,
            user=os.environ.get("SUDO_USER") or "root",
        )
        try:
            unit_path.write_text(content, encoding="utf-8")
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "--now", "tome.service"], check=True)
            return True, f"Tome 24/7 service successfully registered and started at {unit_path}"
        except Exception as exc:
            return False, f"Failed to install system-wide service: {exc}"
    else:
        user_dir = Path.home() / ".config" / "systemd" / "user"
        user_dir.mkdir(parents=True, exist_ok=True)
        unit_path = user_dir / "tome.service"
        content = generate_systemd_unit(
            exec_path=exec_path,
            work_dir=work_dir,
            host=host,
            port=port,
            user=None,
        )
        try:
            unit_path.write_text(content, encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", "--now", "tome.service"], check=True)
            return True, f"Tome user service successfully registered and started at {unit_path}"
        except Exception as exc:
            return False, f"Failed to install user service: {exc}. Run with sudo for system-wide service."


def service_status() -> tuple[bool, str]:
    if sys.platform == "darwin":
        res = subprocess.run(["launchctl", "list", "com.tome.web"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return True, f"Tome launchd service is active:\n{res.stdout}"
        return False, "Tome launchd service is not loaded (com.tome.web)."

    if sys.platform != "linux":
        return False, "Service status check is only supported on Linux (systemd) and macOS (launchd)."

    res = subprocess.run(["systemctl", "status", "tome.service"], capture_output=True, text=True, check=False)
    if res.returncode == 0 or "Active:" in res.stdout:
        return True, res.stdout

    res_user = subprocess.run(
        ["systemctl", "--user", "status", "tome.service"], capture_output=True, text=True, check=False
    )
    return res_user.returncode == 0, res_user.stdout or res_user.stderr


def uninstall_service() -> tuple[bool, str]:
    if sys.platform == "darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.tome.web.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", "-w", str(plist_path)], capture_output=True, check=False)
            try:
                plist_path.unlink()
            except Exception as exc:
                return False, f"Failed to remove plist file: {exc}"
            return True, "Tome macOS launchd service unloaded and unregistered."
        return True, "No active Tome launchd service found."

    if sys.platform != "linux":
        return False, "Service uninstallation is only supported on Linux (systemd) and macOS (launchd)."

    errors = []
    for cmd in [
        ["systemctl", "stop", "tome.service"],
        ["systemctl", "disable", "tome.service"],
        ["systemctl", "--user", "stop", "tome.service"],
        ["systemctl", "--user", "disable", "tome.service"],
    ]:
        try:
            subprocess.run(cmd, capture_output=True, check=False)
        except Exception as exc:
            errors.append(str(exc))

    for p in [Path("/etc/systemd/system/tome.service"), Path.home() / ".config" / "systemd" / "user" / "tome.service"]:
        if p.exists():
            try:
                p.unlink()
            except Exception as exc:
                errors.append(str(exc))

    return True, "Tome 24/7 service stopped and unregistered."
