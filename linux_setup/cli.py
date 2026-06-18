from __future__ import annotations

import argparse
import platform
import sys

from .models import App, SystemInfo
from .system import SUPPORTED_DISTROS, detect_system
from .utils import Color, c

APP_NAME = "Linux Setup"


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

    from .app_catalog import apps

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
