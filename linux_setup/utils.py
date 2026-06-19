from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"


def use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text: str, color: str) -> str:
    if not use_color():
        return text
    return f"{color}{text}{Color.RESET}"


HOST_COMMAND_ENV_REMOVE = {
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "GI_TYPELIB_PATH",
    "GIO_EXTRA_MODULES",
    "GTK_PATH",
    "QT_PLUGIN_PATH",
}


def host_command_env(env: dict[str, str] | None = None) -> dict[str, str]:
    cleaned = (env or os.environ).copy()
    for name in HOST_COMMAND_ENV_REMOVE:
        cleaned.pop(name, None)
    return cleaned


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    sudo: bool = False,
    input_text: str | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = args
    if sudo and os.geteuid() != 0:
        cmd = ["sudo", *args]
    if not capture:
        print(c("$ ", Color.DIM) + " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        cwd=cwd,
        env=host_command_env(env),
    )


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def command_ok(args: list[str]) -> bool:
    try:
        return run(args, check=False, capture=True).returncode == 0
    except FileNotFoundError:
        return False


def command_installed(command: str):
    return lambda _system: command_exists(command)


def local_bin_command_installed(command: str):
    return lambda _system: (
        command_exists(command)
        or Path.home().joinpath(".local", "bin", command).exists()
    )


def download_file(url: str, dest: Path) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        dest.write_bytes(response.read())
