from __future__ import annotations

import os
from pathlib import Path

from .models import SystemInfo
from .utils import command_exists

SUPPORTED_DISTROS = {
    "ubuntu": "Ubuntu",
    "fedora": "Fedora",
    "cachyos": "CachyOS",
    "endeavouros": "EndeavourOS",
    "opensuse-tumbleweed": "openSUSE Tumbleweed",
    "opensuse": "openSUSE",
}


def read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def detect_desktop() -> str:
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or os.environ.get("GDMSESSION")
        or ""
    )
    normalized = desktop.lower()
    if "gnome" in normalized:
        return "GNOME"
    if "kde" in normalized or "plasma" in normalized:
        return "KDE Plasma"
    if "mango" in normalized:
        return "MangoWM"
    if "niri" in normalized:
        return "Niri"
    if "hyprland" in normalized:
        return "Hyprland"
    return desktop or "Unknown"


def detect_system() -> SystemInfo:
    release = read_os_release()
    distro_id = release.get("ID", "").lower()
    id_like = release.get("ID_LIKE", "").lower().split()
    distro_name = release.get("PRETTY_NAME") or SUPPORTED_DISTROS.get(
        distro_id, distro_id or "Unknown"
    )
    package_manager = detect_package_manager(distro_id, id_like)
    return SystemInfo(
        distro_id=distro_id,
        distro_name=distro_name,
        id_like=id_like,
        version=release.get("VERSION_ID", ""),
        desktop=detect_desktop(),
        package_manager=package_manager,
    )


def detect_package_manager(distro_id: str, id_like: list[str]) -> str:
    ids = [distro_id, *id_like]
    if any(
        item in ids for item in ("arch", "cachyos", "endeavouros")
    ) and command_exists("pacman"):
        return "pacman"
    if any(item in ids for item in ("fedora", "rhel")) and command_exists("dnf"):
        return "dnf"
    if any(item in ids for item in ("ubuntu", "debian")) and command_exists("apt"):
        return "apt"
    if any(
        item.startswith("opensuse") or item == "suse" for item in ids
    ) and command_exists("zypper"):
        return "zypper"
    for manager in ("apt", "dnf", "pacman", "zypper"):
        if command_exists(manager):
            return manager
    return "unknown"
