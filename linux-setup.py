#!/usr/bin/env python3
"""
Install a personal Linux desktop software set across common distributions.

The script intentionally depends only on the Python standard library so it can
run on a freshly installed desktop system.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

APP_NAME = "Linux Setup"
SUPPORTED_DISTROS = {
    "ubuntu": "Ubuntu",
    "fedora": "Fedora",
    "cachyos": "CachyOS",
    "endeavouros": "EndeavourOS",
    "opensuse-tumbleweed": "openSUSE Tumbleweed",
    "opensuse": "openSUSE",
}

FLATHUB_REMOTE = "https://dl.flathub.org/repo/flathub.flatpakrepo"


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
        env=env,
    )


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def command_ok(args: list[str]) -> bool:
    try:
        return run(args, check=False, capture=True).returncode == 0
    except FileNotFoundError:
        return False


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


@dataclass(frozen=True)
class SystemInfo:
    distro_id: str
    distro_name: str
    id_like: list[str]
    version: str
    desktop: str
    package_manager: str

    @property
    def family(self) -> str:
        ids = [self.distro_id, *self.id_like]
        if any(item in ids for item in ("arch", "cachyos", "endeavouros")):
            return "arch"
        if any(item in ids for item in ("fedora", "rhel")):
            return "fedora"
        if any(item in ids for item in ("ubuntu", "debian")):
            return "debian"
        if any(item.startswith("opensuse") or item == "suse" for item in ids):
            return "opensuse"
        return "unknown"


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


@dataclass(frozen=True)
class App:
    key: str
    label: str
    category: str
    installed: Callable[[SystemInfo], bool]
    install: Callable[[SystemInfo], None]
    default_selected: bool = True


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


def ensure_npm(system: SystemInfo) -> None:
    if command_exists("npm"):
        return
    manager_install(system, ["npm"])


def command_installed(command: str) -> Callable[[SystemInfo], bool]:
    return lambda _system: command_exists(command)


def local_bin_command_installed(command: str) -> Callable[[SystemInfo], bool]:
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


def install_shell_script(url: str, filename: str, shell: str = "sh") -> None:
    with tempfile.TemporaryDirectory() as tmp:
        installer = Path(tmp) / filename
        print(f"Downloading {url}")
        download_file(url, installer)
        run([shell, str(installer)])


def install_standalone_script(
    url: str, filename: str, shell: str = "sh"
) -> Callable[[SystemInfo], None]:
    def installer(_system: SystemInfo) -> None:
        install_shell_script(url, filename, shell=shell)

    return installer


def install_npm_global(package: str) -> Callable[[SystemInfo], None]:
    def installer(system: SystemInfo) -> None:
        ensure_npm(system)
        run(["npm", "install", "-g", package], sudo=True)

    return installer


def install_ollama(_system: SystemInfo) -> None:
    install_shell_script("https://ollama.com/install.sh", "install-ollama.sh")


def vscode_installed(_system: SystemInfo) -> bool:
    return command_exists("code")


def install_vscode(system: SystemInfo) -> None:
    if system.family == "debian":
        manager_install(system, ["wget", "gpg", "apt-transport-https"])
        run(["install", "-d", "-m", "0755", "/etc/apt/keyrings"], sudo=True)
        with urllib.request.urlopen(
            "https://packages.microsoft.com/keys/microsoft.asc", timeout=30
        ) as response:
            key = response.read()
        proc = subprocess.run(
            ["gpg", "--dearmor"], input=key, stdout=subprocess.PIPE, check=True
        )
        temp_key = Path(tempfile.gettempdir()) / "packages.microsoft.gpg"
        temp_key.write_bytes(proc.stdout)
        run(
            [
                "install",
                "-o",
                "root",
                "-g",
                "root",
                "-m",
                "0644",
                str(temp_key),
                "/etc/apt/keyrings/packages.microsoft.gpg",
            ],
            sudo=True,
        )
        repo = "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main\n"
        temp_repo = Path(tempfile.gettempdir()) / "vscode.list"
        temp_repo.write_text(repo, encoding="utf-8")
        run(
            [
                "install",
                "-o",
                "root",
                "-g",
                "root",
                "-m",
                "0644",
                str(temp_repo),
                "/etc/apt/sources.list.d/vscode.list",
            ],
            sudo=True,
        )
        manager_install(system, ["code"])
    elif system.family == "fedora":
        run(
            ["rpm", "--import", "https://packages.microsoft.com/keys/microsoft.asc"],
            sudo=True,
        )
        repo = textwrap.dedent(
            """\
            [code]
            name=Visual Studio Code
            baseurl=https://packages.microsoft.com/yumrepos/vscode
            enabled=1
            autorefresh=1
            type=rpm-md
            gpgcheck=1
            gpgkey=https://packages.microsoft.com/keys/microsoft.asc
            """
        )
        temp_repo = Path(tempfile.gettempdir()) / "vscode.repo"
        temp_repo.write_text(repo, encoding="utf-8")
        run(
            [
                "install",
                "-o",
                "root",
                "-g",
                "root",
                "-m",
                "0644",
                str(temp_repo),
                "/etc/yum.repos.d/vscode.repo",
            ],
            sudo=True,
        )
        manager_install(system, ["code"])
    elif system.family == "opensuse":
        run(
            ["rpm", "--import", "https://packages.microsoft.com/keys/microsoft.asc"],
            sudo=True,
        )
        run(
            [
                "zypper",
                "--non-interactive",
                "addrepo",
                "https://packages.microsoft.com/yumrepos/vscode",
                "vscode",
            ],
            sudo=True,
        )
        manager_install(system, ["code"])
    else:
        install_flatpak("com.vscodium.codium")(system)


def toolbox_installed(_system: SystemInfo) -> bool:
    return (
        command_exists("jetbrains-toolbox")
        or Path.home()
        .joinpath(".local/share/JetBrains/Toolbox/bin/jetbrains-toolbox")
        .exists()
    )


def jetbrains_toolbox_download_url() -> str:
    api_url = "https://data.services.jetbrains.com/products/releases?code=TBA&latest=true&type=release"
    machine = platform.machine().lower()
    download_key = "linuxARM64" if machine in ("aarch64", "arm64") else "linux"
    with urllib.request.urlopen(api_url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    releases = data.get("TBA") or []
    if not releases:
        raise RuntimeError(
            "JetBrains Toolbox release metadata did not contain a release."
        )
    download = releases[0].get("downloads", {}).get(download_key, {})
    link = download.get("link")
    if not link:
        raise RuntimeError(
            f"JetBrains Toolbox release metadata did not contain a {download_key} download."
        )
    return link


def install_jetbrains_toolbox(_system: SystemInfo) -> None:
    if _system.family == "debian":
        manager_install(_system, ["libfuse2"])

    url = jetbrains_toolbox_download_url()
    install_dir = Path.home() / ".local" / "share" / "JetBrains" / "Toolbox"
    bin_dir = install_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "jetbrains-toolbox.tar.gz"
        print(f"Downloading {url}")
        download_file(url, archive)
        run(["tar", "-xzf", str(archive), "-C", tmp])
        candidates = [p for p in Path(tmp).rglob("jetbrains-toolbox") if p.is_file()]
        if not candidates:
            raise RuntimeError(
                "Could not find jetbrains-toolbox binary in downloaded archive."
            )
        target = bin_dir / "jetbrains-toolbox"
        shutil.copy2(candidates[0], target)
        target.chmod(0o755)
    link = Path.home() / ".local" / "bin" / "jetbrains-toolbox"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(bin_dir / "jetbrains-toolbox")
    print(f"Installed JetBrains Toolbox to {link}")


def install_hermes_agent(_system: SystemInfo) -> None:
    install_shell_script(
        "https://hermes-agent.nousresearch.com/install.sh",
        "install-hermes.sh",
        shell="bash",
    )


def zsh_installed(_system: SystemInfo) -> bool:
    return command_exists("zsh")


def install_zsh_and_default(system: SystemInfo) -> None:
    install_native(NATIVE_ITEMS["zsh"])(system)
    make_zsh_default()


def make_zsh_default() -> None:
    zsh = shutil.which("zsh")
    if not zsh:
        raise RuntimeError("zsh was not found after installation.")
    current_shell = os.environ.get("SHELL", "")
    if Path(current_shell).name == "zsh":
        return
    shells = (
        Path("/etc/shells").read_text(encoding="utf-8")
        if Path("/etc/shells").exists()
        else ""
    )
    if zsh not in shells:
        run(["sh", "-c", f"printf '%s\\n' '{zsh}' >> /etc/shells"], sudo=True)
    run(["chsh", "-s", zsh, os.environ.get("USER", "")], sudo=True)


def oh_my_zsh_installed(_system: SystemInfo) -> bool:
    return Path.home().joinpath(".oh-my-zsh").exists()


def install_oh_my_zsh(system: SystemInfo) -> None:
    if not command_exists("zsh"):
        install_zsh_and_default(system)
    packages = native_packages_for(system, NATIVE_ITEMS["oh-my-zsh"])
    if packages:
        manager_install(system, packages)
    if not oh_my_zsh_installed(system):
        manager_install(system, ["git"])
        env = os.environ.copy()
        env["RUNZSH"] = "no"
        env["CHSH"] = "no"
        url = (
            "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
        )
        with tempfile.TemporaryDirectory() as tmp:
            installer = Path(tmp) / "install-oh-my-zsh.sh"
            print(f"Downloading {url}")
            download_file(url, installer)
            run(
                ["sh", str(installer)],
                check=True,
                capture=False,
                input_text=None,
                env=env,
            )


def install_yubikey_services(system: SystemInfo) -> None:
    install_native(NATIVE_ITEMS["yubikey"])(system)
    if command_exists("systemctl"):
        run(["systemctl", "enable", "--now", "pcscd"], sudo=True, check=False)


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


def apps() -> list[App]:
    return [
        App(
            "flatpak",
            "Flatpak + Flathub",
            "native",
            flathub_configured,
            install_flatpak_and_flathub,
        ),
        App(
            "firefox",
            "Firefox",
            "native",
            NATIVE_ITEMS["firefox"].installed,
            install_native(NATIVE_ITEMS["firefox"]),
        ),
        App(
            "thunderbird",
            "Thunderbird",
            "native",
            NATIVE_ITEMS["thunderbird"].installed,
            install_native(NATIVE_ITEMS["thunderbird"]),
        ),
        App(
            "ghostty",
            "Ghostty",
            "native",
            NATIVE_ITEMS["ghostty"].installed,
            install_native(NATIVE_ITEMS["ghostty"]),
        ),
        App(
            "alacritty",
            "Alacritty",
            "native",
            NATIVE_ITEMS["alacritty"].installed,
            install_native(NATIVE_ITEMS["alacritty"]),
        ),
        App(
            "zsh",
            "ZSH + default shell",
            "native",
            zsh_installed,
            install_zsh_and_default,
        ),
        App(
            "oh-my-zsh",
            "Oh My Zsh",
            "native/script",
            oh_my_zsh_installed,
            install_oh_my_zsh,
        ),
        App(
            "yubikey",
            "YubiKey support",
            "native",
            NATIVE_ITEMS["yubikey"].installed,
            install_yubikey_services,
        ),
        App(
            "steam",
            "Steam",
            "native",
            NATIVE_ITEMS["steam"].installed,
            install_native(NATIVE_ITEMS["steam"]),
        ),
        App(
            "neovim",
            "Neovim",
            "native",
            NATIVE_ITEMS["neovim"].installed,
            install_native(NATIVE_ITEMS["neovim"]),
        ),
        App(
            "onlyoffice",
            "ONLYOFFICE Desktop Editors",
            "flathub",
            flatpak_installed("org.onlyoffice.desktopeditors"),
            install_flatpak("org.onlyoffice.desktopeditors"),
        ),
        App(
            "github-cli",
            "GitHub CLI",
            "native",
            NATIVE_ITEMS["github-cli"].installed,
            install_native(NATIVE_ITEMS["github-cli"]),
        ),
        App(
            "edge",
            "Microsoft Edge",
            "flathub",
            flatpak_installed("com.microsoft.Edge"),
            install_flatpak("com.microsoft.Edge"),
        ),
        App(
            "zed",
            "Zed Editor",
            "flathub",
            flatpak_installed("dev.zed.Zed"),
            install_flatpak("dev.zed.Zed"),
        ),
        App(
            "spotify",
            "Spotify",
            "flathub",
            flatpak_installed("com.spotify.Client"),
            install_flatpak("com.spotify.Client"),
        ),
        App(
            "bitwarden",
            "Bitwarden",
            "flathub",
            flatpak_installed("com.bitwarden.desktop"),
            install_flatpak("com.bitwarden.desktop"),
        ),
        App(
            "mullvad-browser",
            "Mullvad Browser",
            "flathub",
            flatpak_installed("net.mullvad.MullvadBrowser"),
            install_flatpak("net.mullvad.MullvadBrowser"),
        ),
        App(
            "brave",
            "Brave Browser",
            "flathub",
            flatpak_installed("com.brave.Browser"),
            install_flatpak("com.brave.Browser"),
        ),
        App(
            "logseq",
            "Logseq",
            "flathub",
            flatpak_installed("com.logseq.Logseq"),
            install_flatpak("com.logseq.Logseq"),
        ),
        App(
            "keepassxc",
            "KeePassXC",
            "flathub",
            flatpak_installed("org.keepassxc.KeePassXC"),
            install_flatpak("org.keepassxc.KeePassXC"),
        ),
        App(
            "ausweisapp",
            "AusweisApp",
            "flathub",
            flatpak_installed("de.bund.ausweisapp.ausweisapp2"),
            install_flatpak("de.bund.ausweisapp.ausweisapp2"),
        ),
        App(
            "nextcloud",
            "Nextcloud Desktop Client",
            "flathub",
            flatpak_installed("com.nextcloud.desktopclient.nextcloud"),
            install_flatpak("com.nextcloud.desktopclient.nextcloud"),
        ),
        App(
            "vscode",
            "Visual Studio Code",
            "native installer",
            vscode_installed,
            install_vscode,
        ),
        App(
            "jetbrains-toolbox",
            "JetBrains Toolbox",
            "native installer",
            toolbox_installed,
            install_jetbrains_toolbox,
        ),
        App(
            "uv",
            "uv",
            "native installer",
            local_bin_command_installed("uv"),
            install_standalone_script(
                "https://astral.sh/uv/install.sh", "install-uv.sh"
            ),
        ),
        App(
            "ruff",
            "Ruff",
            "native installer",
            local_bin_command_installed("ruff"),
            install_standalone_script(
                "https://astral.sh/ruff/install.sh", "install-ruff.sh"
            ),
        ),
        App(
            "ty",
            "ty",
            "native installer",
            local_bin_command_installed("ty"),
            install_standalone_script(
                "https://astral.sh/ty/install.sh", "install-ty.sh"
            ),
        ),
        App(
            "ollama",
            "Ollama",
            "native installer",
            command_installed("ollama"),
            install_ollama,
            default_selected=False,
        ),
        App(
            "pi-agent",
            "Pi Agent",
            "native installer",
            command_installed("pi"),
            install_npm_global("@earendil-works/pi-coding-agent"),
            default_selected=False,
        ),
        App(
            "opencode",
            "opencode",
            "native installer",
            command_installed("opencode"),
            install_npm_global("opencode-ai"),
            default_selected=False,
        ),
        App(
            "hermes-agent",
            "Hermes Agent",
            "native installer",
            command_installed("hermes"),
            install_hermes_agent,
            default_selected=False,
        ),
        App(
            "claude-code",
            "Claude Code",
            "native installer",
            command_installed("claude"),
            install_npm_global("@anthropic-ai/claude-code"),
            default_selected=False,
        ),
        App(
            "codex-cli",
            "Codex CLI",
            "native installer",
            command_installed("codex"),
            install_npm_global("@openai/codex"),
            default_selected=False,
        ),
    ]


def print_header(system: SystemInfo) -> None:
    print()
    print(c(f" {APP_NAME} ", Color.BOLD + Color.CYAN))
    print(c("-" * 64, Color.DIM))
    print(f"{c('Distro: ', Color.BOLD)}{system.distro_name}")
    print(f"{c('Desktop:', Color.BOLD)} {system.desktop}")
    print(f"{c('Kernel: ', Color.BOLD)}{platform.release()} ({platform.machine()})")
    print(f"{c('Manager:', Color.BOLD)} {system.package_manager}")
    print(c("-" * 64, Color.DIM))


def print_status(installed: list[App], pending: list[App]) -> None:
    if installed:
        print(c("\nAlready installed", Color.GREEN))
        for app in installed:
            status = app.category + (", opt-in" if not app.default_selected else "")
            print(
                f"  {c('[ok]', Color.GREEN)} {app.label} {c('[' + status + ']', Color.DIM)}"
            )
    else:
        print(c("\nAlready installed: none from this list", Color.YELLOW))
    if pending:
        print(c("\nRemaining", Color.YELLOW))
        for index, app in enumerate(pending, 1):
            status = app.category + (", opt-in" if not app.default_selected else "")
            print(f"  {index:>2}. {app.label} {c('[' + status + ']', Color.DIM)}")
    else:
        print(c("\nEverything from the configured list is installed.", Color.GREEN))


def parse_selection(selection: str, count: int) -> list[int]:
    text = selection.strip().lower()
    if text == "":
        return []
    if text in ("all", "a"):
        return list(range(count))
    if text in ("none", "n"):
        return []
    selected: set[int] = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            selected.update(range(start - 1, end))
        else:
            selected.add(int(part) - 1)
    invalid = [item + 1 for item in selected if item < 0 or item >= count]
    if invalid:
        raise ValueError(f"Invalid selection: {invalid}")
    return sorted(selected)


def choose_apps(pending: list[App], assume_yes: bool = False) -> list[App]:
    if not pending:
        return []
    default_apps = [app for app in pending if app.default_selected]
    if assume_yes:
        return default_apps
    print()
    print("Select packages to install.")
    print(
        c(
            "Enter = default selection, 'all' = all including opt-in, 'none' = none, examples: 1,3,5-8",
            Color.DIM,
        )
    )
    while True:
        try:
            selection = input(c("Install selection [default]: ", Color.BOLD))
            if selection.strip() == "":
                return default_apps
            indexes = parse_selection(selection, len(pending))
            return [pending[index] for index in indexes]
        except (ValueError, IndexError) as exc:
            print(c(f"{exc}. Try again.", Color.RED))


def install_selected(system: SystemInfo, selected: list[App]) -> int:
    if not selected:
        print(c("\nNo packages selected.", Color.YELLOW))
        return 0
    failures: list[tuple[str, str]] = []
    print()
    for index, app in enumerate(selected, 1):
        print(
            c(
                f"[{index}/{len(selected)}] Installing {app.label}",
                Color.BOLD + Color.BLUE,
            )
        )
        try:
            app.install(system)
        except Exception as exc:  # noqa: BLE001 - report and continue with the rest.
            failures.append((app.label, str(exc)))
            print(c(f"Failed: {app.label}: {exc}", Color.RED))
    if failures:
        print(c("\nCompleted with failures", Color.YELLOW))
        for label, reason in failures:
            print(f"  {c('[!]', Color.YELLOW)} {label}: {reason}")
        return 1
    print(c("\nAll selected packages installed.", Color.GREEN))
    return 0


def supported_warning(system: SystemInfo) -> None:
    if system.family == "unknown":
        print(
            c(
                "Warning: this distribution is not mapped to a supported package manager.",
                Color.YELLOW,
            )
        )
    elif system.distro_id not in SUPPORTED_DISTROS and not set(
        system.id_like
    ).intersection(SUPPORTED_DISTROS):
        print(
            c(
                f"Warning: {system.distro_name} is not one of the explicitly targeted distributions.",
                Color.YELLOW,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a personal desktop software set on Linux."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="install default-selected remaining packages without prompting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="detect and print status without installing",
    )
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        print("This installer is intended to run on Linux.", file=sys.stderr)
        return 2

    system = detect_system()
    print_header(system)
    supported_warning(system)

    installed: list[App] = []
    pending: list[App] = []
    for app in apps():
        if app.installed(system):
            installed.append(app)
        else:
            pending.append(app)

    print_status(installed, pending)
    if args.dry_run:
        return 0
    selected = choose_apps(pending, assume_yes=args.yes)
    return install_selected(system, selected)


if __name__ == "__main__":
    raise SystemExit(main())
