# Linux Setup

A small dependency-free Python CLI for setting up fresh Linux desktop installs.

It targets:

- Ubuntu
- Fedora
- CachyOS
- EndeavourOS
- openSUSE Tumbleweed

It detects the current distribution, package manager, kernel and desktop session,
prints which configured packages are already installed, then lets you choose the
remaining packages to install. All remaining packages are selected by default.

## Included Software

Native package manager:

- Flatpak with Flathub remote
- Firefox
- Thunderbird
- Ghostty
- Alacritty
- ZSH, with `chsh` to make it the default shell when selected
- Oh My Zsh, using a native package where available and the official installer
  as a fallback
- YubiKey packages and `pcscd`

Flathub:

- Microsoft Edge
- Zed Editor
- Spotify
- Bitwarden

Native installers:

- Visual Studio Code
- JetBrains Toolbox

## Usage

Run after installing the OS and signing in to the normal desktop user account:

```sh
python3 linux-setup.py
```

Preview detection and package status without installing anything:

```sh
python3 linux-setup.py --dry-run
```

Install all remaining configured software without prompting:

```sh
python3 linux-setup.py --yes
```

During interactive selection:

- Press Enter or type `all` to install everything remaining.
- Type `none` to install nothing.
- Type selections like `1,3,5-8` to install specific entries.

## Notes

Some package availability depends on the distribution release and enabled
repositories. For example, Ghostty is listed as a native package, but older
distribution releases may not provide it in their default repositories.
