from __future__ import annotations

import os
from typing import Callable

from .models import SystemInfo
from .native_packages import NATIVE_ITEMS, manager_install, native_packages_for
from .utils import command_exists, run

FLATHUB_REMOTE = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def flatpak_command_ok(args: list[str]) -> bool:
    try:
        return run(args, check=False, capture=True).returncode == 0
    except FileNotFoundError:
        return False


def target_flatpak_user() -> str | None:
    user = os.environ.get("SUDO_USER") if os.geteuid() == 0 else None
    if user and user != "root":
        return user
    return None


def user_flatpak_command_ok(args: list[str]) -> bool:
    user = target_flatpak_user()
    if user:
        return flatpak_command_ok(["sudo", "-H", "-u", user, *args])
    return flatpak_command_ok(args)


def flatpak_app_installed(app_id: str) -> bool:
    if not command_exists("flatpak"):
        return False
    return (
        flatpak_command_ok(["flatpak", "info", "--system", app_id])
        or user_flatpak_command_ok(["flatpak", "info", "--user", app_id])
        or flatpak_command_ok(["flatpak", "info", app_id])
    )


def flatpak_remotes(args: list[str]) -> set[str]:
    try:
        result = run(args, capture=True, check=False)
    except FileNotFoundError:
        return set()
    if result.returncode != 0:
        return set()
    return set(result.stdout.split())


def user_flatpak_remotes(args: list[str]) -> set[str]:
    user = target_flatpak_user()
    if user:
        return flatpak_remotes(["sudo", "-H", "-u", user, *args])
    return flatpak_remotes(args)


def flathub_remote_configured() -> bool:
    if not command_exists("flatpak"):
        return False
    remotes = (
        flatpak_remotes(["flatpak", "remotes", "--system", "--columns=name"])
        | user_flatpak_remotes(["flatpak", "remotes", "--user", "--columns=name"])
        | flatpak_remotes(["flatpak", "remotes", "--columns=name"])
    )
    return "flathub" in remotes


def flatpak_installed(app_id: str) -> Callable[[SystemInfo], bool]:
    return lambda _system: flatpak_app_installed(app_id)


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
    return flathub_remote_configured()


def install_flatpak_and_flathub(system: SystemInfo) -> None:
    flatpak_item = NATIVE_ITEMS["flatpak"]
    packages = native_packages_for(system, flatpak_item)
    missing_flatpak = not command_exists("flatpak")
    if missing_flatpak:
        manager_install(system, packages)
    ensure_flathub()
