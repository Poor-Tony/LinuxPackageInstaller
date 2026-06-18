from __future__ import annotations

from typing import Callable

from .models import SystemInfo
from .native_packages import NATIVE_ITEMS, manager_install, native_packages_for
from .utils import command_exists, command_ok, run

FLATHUB_REMOTE = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def flatpak_installed(app_id: str) -> Callable[[SystemInfo], bool]:
    return lambda _system: command_ok(["flatpak", "info", app_id])


def install_flatpak(app_id: str) -> Callable[[SystemInfo], None]:
    def installer(_system: SystemInfo) -> None:
        ensure_flathub()
        run(["flatpak", "install", "-y", "flathub", app_id])

    return installer


def ensure_flathub() -> None:
    if not command_exists("flatpak"):
        raise RuntimeError("flatpak is not installed.")
    remotes = run(
        ["flatpak", "remotes", "--columns=name"], capture=True, check=False
    ).stdout
    if "flathub" not in remotes.split():
        run(
            ["flatpak", "remote-add", "--if-not-exists", "flathub", FLATHUB_REMOTE],
            sudo=True,
        )


def flathub_configured(_system: SystemInfo) -> bool:
    if not command_exists("flatpak"):
        return False
    remotes = run(
        ["flatpak", "remotes", "--columns=name"], capture=True, check=False
    ).stdout
    return "flathub" in remotes.split()


def install_flatpak_and_flathub(system: SystemInfo) -> None:
    flatpak_item = NATIVE_ITEMS["flatpak"]
    packages = native_packages_for(system, flatpak_item)
    missing_flatpak = not command_exists("flatpak")
    if missing_flatpak:
        manager_install(system, packages)
    ensure_flathub()
