from __future__ import annotations

import getpass
import json
import os
import platform
import pwd
import shutil
import subprocess
import tempfile
import textwrap
import urllib.request
from pathlib import Path
from typing import Callable

from .flatpak import install_flatpak
from .models import SystemInfo
from .native_packages import (
    NATIVE_ITEMS,
    install_native,
    manager_install,
    native_packages_for,
)
from .utils import Color, c, command_exists, download_file, run


def ensure_npm(system: SystemInfo) -> None:
    if command_exists("npm"):
        return
    manager_install(system, ["npm"])


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

    print(
        "Initializing JetBrains Toolbox to create necessary links (start menu, autostart, etc.)..."
    )
    subprocess.Popen(["./bin/jetbrains-toolbox"], cwd=install_dir)


def install_hermes_agent(_system: SystemInfo) -> None:
    install_shell_script(
        "https://hermes-agent.nousresearch.com/install.sh",
        "install-hermes.sh",
        shell="bash",
    )


def target_login_user() -> str:
    user = os.environ.get("SUDO_USER") if os.geteuid() == 0 else None
    if not user or user == "root":
        user = os.environ.get("USER") or getpass.getuser()
    if not user:
        raise RuntimeError("Could not determine which user's shell to change.")
    return user


def login_shell(user: str) -> str:
    try:
        return pwd.getpwnam(user).pw_shell
    except KeyError as exc:
        raise RuntimeError(f"User does not exist: {user}") from exc


def zsh_is_default_for_target_user() -> bool:
    if not command_exists("zsh"):
        return False
    return Path(login_shell(target_login_user())).name == "zsh"


def zsh_installed(_system: SystemInfo) -> bool:
    return zsh_is_default_for_target_user()


def install_zsh_and_default(system: SystemInfo) -> None:
    if not command_exists("zsh"):
        install_native(NATIVE_ITEMS["zsh"])(system)
    make_zsh_default()


def make_zsh_default() -> None:
    zsh = shutil.which("zsh")
    if not zsh:
        raise RuntimeError("zsh was not found after installation.")
    user = target_login_user()
    if Path(login_shell(user)).name == "zsh":
        return
    shells = (
        Path("/etc/shells").read_text(encoding="utf-8")
        if Path("/etc/shells").exists()
        else ""
    )
    if zsh not in shells.splitlines():
        run(["tee", "-a", "/etc/shells"], sudo=True, input_text=f"{zsh}\n")

    chsh_result = run(["chsh", "-s", zsh, user], sudo=True, check=False)
    if Path(login_shell(user)).name != "zsh" and command_exists("usermod"):
        run(["usermod", "--shell", zsh, user], sudo=True)

    new_shell = login_shell(user)
    if Path(new_shell).name != "zsh":
        raise RuntimeError(
            f"Could not change {user}'s login shell to {zsh}. "
            f"chsh exited with {chsh_result.returncode}; current login shell is {new_shell}."
        )
    print(
        c(
            f"Changed {user}'s login shell to {zsh}. Log out and back in for it to take effect.",
            Color.GREEN,
        )
    )


def oh_my_zsh_installed(_system: SystemInfo) -> bool:
    return Path.home().joinpath(".oh-my-zsh").exists()


def install_oh_my_zsh(system: SystemInfo) -> None:
    if not command_exists("zsh"):
        install_zsh_and_default(system)
    packages = native_packages_for(system, NATIVE_ITEMS["oh-my-zsh"])
    if packages:
        manager_install(system, packages)
    if not oh_my_zsh_installed(system):
        manager_install(system, ["git", "curl"])
        env = os.environ.copy()
        env["RUNZSH"] = "no"
        env["CHSH"] = "no"
        url = (
            "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
        )
        print(f"Installing Oh My Zsh from {url}")
        run(
            ["sh", "-c", f"curl -fsSL {url} | sh"],
            check=True,
            capture=False,
            env=env,
        )


def install_yubikey_services(system: SystemInfo) -> None:
    install_native(NATIVE_ITEMS["yubikey"])(system)
    if command_exists("systemctl"):
        run(["systemctl", "enable", "--now", "pcscd"], sudo=True, check=False)
