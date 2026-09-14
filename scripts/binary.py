import subprocess
import sys
import time


def build_standalone_binary() -> None:
    start_time = time.perf_counter()

    excludes = [
        "tensorboard",
        "torch.utils.tensorboard",
        "torch.distributed",
        "matplotlib",
        "scipy",
        "PIL",
        "cv2",
        "IPython",
        "tkinter",
    ]

    platform_name = "macOS" if sys.platform == "darwin" else ("Windows" if sys.platform == "win32" else "Linux")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "tome",
        "--clean",
    ]

    if sys.platform != "darwin":
        cmd.append("--strip")

    for exc in excludes:
        cmd.extend(["--exclude-module", exc])

    cmd.append("src/tome/cli/main.py")

    print(f"Building lightweight {platform_name} standalone binary for Tome...")
    subprocess.check_call(cmd)

    duration = round(time.perf_counter() - start_time, 2)
    print(f"Binary build completed successfully in {duration}s -> dist/tome")


if __name__ == "__main__":
    build_standalone_binary()
