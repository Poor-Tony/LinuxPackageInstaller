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
- Steam
- Neovim
- ONLYOFFICE Desktop Editors
- GitHub CLI

Flathub:

- Microsoft Edge
- Zed Editor
- Spotify
- Bitwarden
- Mullvad Browser
- Brave Browser
- Logseq
- KeePassXC
- AusweisApp

Native installers:

- Visual Studio Code
- JetBrains Toolbox
- Ollama
- Pi Agent
- opencode
- Hermes Agent
- Claude Code
- Codex CLI

Ollama, Pi Agent, opencode, Hermes Agent, Claude Code and Codex CLI are opt-in
entries. They are shown in the selection list but are not selected when pressing
Enter or when using `--yes`.

## Usage

Run after installing the OS and signing in to the normal desktop user account:

```sh
python3 linux-setup.py
```

Preview detection and package status without installing anything:

```sh
python3 linux-setup.py --dry-run
```

Install all default-selected remaining configured software without prompting:

```sh
python3 linux-setup.py --yes
```

During interactive selection:

- Press Enter to install the default selection.
- Type `all` to install everything remaining, including opt-in entries.
- Type `none` to install nothing.
- Type selections like `1,3,5-8` to install specific entries.

## Notes

Some package availability depends on the distribution release and enabled
repositories. For example, Ghostty is listed as a native package, but older
distribution releases may not provide it in their default repositories.
