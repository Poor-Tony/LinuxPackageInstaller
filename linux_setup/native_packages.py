from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import SystemInfo
from .utils import command_exists, run


@dataclass(frozen=True)
class NativePackage:
    label: str
    commands: tuple[str, ...]
    packages: dict[str, tuple[str, ...]]
    required: bool = True

    def installed(self, _system: SystemInfo) -> bool:
        if not self.commands:
            return False
        return all(command_exists(command) for command in self.commands)


def manager_install(system: SystemInfo, packages: list[str]) -> None:
    packages = [pkg for pkg in packages if pkg]
    if not packages:
        return
    if system.package_manager == "apt":
        run(["apt", "update"], sudo=True)
        run(["apt", "install", "-y", *packages], sudo=True)
    elif system.package_manager == "dnf":
        run(["dnf", "install", "-y", *packages], sudo=True)
    elif system.package_manager == "pacman":
        run(["pacman", "-Syu", "--needed", "--noconfirm", *packages], sudo=True)
    elif system.package_manager == "zypper":
        run(["zypper", "--non-interactive", "install", *packages], sudo=True)
    else:
        raise RuntimeError("No supported package manager found.")


def native_packages_for(system: SystemInfo, item: NativePackage) -> list[str]:
    family_packages = item.packages.get(system.family, ())
    manager_packages = item.packages.get(system.package_manager, ())
    return list(manager_packages or family_packages)


def install_native(item: NativePackage) -> Callable[[SystemInfo], None]:
    def installer(system: SystemInfo) -> None:
        packages = native_packages_for(system, item)
        if not packages:
            raise RuntimeError(
                f"No package mapping for {item.label} on {system.distro_name}."
            )
        manager_install(system, packages)

    return installer


NATIVE_ITEMS: dict[str, NativePackage] = {
    "flatpak": NativePackage(
        "Flatpak + Flathub",
        ("flatpak",),
        {
            "debian": ("flatpak",),
            "fedora": ("flatpak",),
            "arch": ("flatpak",),
            "opensuse": ("flatpak",),
        },
    ),
    "firefox": NativePackage(
        "Firefox",
        ("firefox",),
        {
            "debian": ("firefox",),
            "fedora": ("firefox",),
            "arch": ("firefox",),
            "opensuse": ("MozillaFirefox",),
        },
    ),
    "thunderbird": NativePackage(
        "Thunderbird",
        ("thunderbird",),
        {
            "debian": ("thunderbird",),
            "fedora": ("thunderbird",),
            "arch": ("thunderbird",),
            "opensuse": ("MozillaThunderbird",),
        },
    ),
    "ghostty": NativePackage(
        "Ghostty",
        ("ghostty",),
        {
            "debian": ("ghostty",),
            "fedora": ("ghostty",),
            "arch": ("ghostty",),
            "opensuse": ("ghostty",),
        },
    ),
    "alacritty": NativePackage(
        "Alacritty",
        ("alacritty",),
        {
            "debian": ("alacritty",),
            "fedora": ("alacritty",),
            "arch": ("alacritty",),
            "opensuse": ("alacritty",),
        },
    ),
    "zsh": NativePackage(
        "ZSH",
        ("zsh",),
        {
            "debian": ("zsh",),
            "fedora": ("zsh",),
            "arch": ("zsh",),
            "opensuse": ("zsh",),
        },
    ),
    "oh-my-zsh": NativePackage(
        "Oh My Zsh",
        (),
        {},
        required=False,
    ),
    "yubikey": NativePackage(
        "YubiKey support",
        ("ykman", "ykpersonalize", "pamu2fcfg"),
        {
            "debian": (
                "yubikey-manager",
                "yubikey-personalization",
                "pcscd",
                "scdaemon",
                "libpam-yubico",
                "libpam-u2f",
                "pamu2fcfg",
                "opensc",
            ),
            "fedora": (
                "yubikey-manager",
                "yubikey-personalization",
                "pcsc-lite",
                "pcsc-lite-ccid",
                "pam-u2f",
                "opensc",
            ),
            "arch": (
                "yubikey-manager",
                "yubikey-personalization",
                "pcsclite",
                "ccid",
                "pam-u2f",
                "opensc",
            ),
            "opensuse": (
                "yubikey-manager",
                "yubikey-personalization",
                "pcsc-lite",
                "pcsc-ccid",
                "pam_u2f",
                "opensc",
            ),
        },
    ),
    "steam": NativePackage(
        "Steam",
        ("steam",),
        {
            "debian": ("steam-installer",),
            "fedora": ("steam",),
            "arch": ("steam",),
            "opensuse": ("steam",),
        },
    ),
    "neovim": NativePackage(
        "Neovim",
        ("nvim",),
        {
            "debian": ("neovim",),
            "fedora": ("neovim",),
            "arch": ("neovim",),
            "opensuse": ("neovim",),
        },
    ),
    "github-cli": NativePackage(
        "GitHub CLI",
        ("gh",),
        {
            "debian": ("gh",),
            "fedora": ("gh",),
            "arch": ("github-cli",),
            "opensuse": ("gh",),
        },
    ),
}
