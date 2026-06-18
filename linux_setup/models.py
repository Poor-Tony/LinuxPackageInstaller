from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


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


@dataclass(frozen=True)
class App:
    key: str
    label: str
    category: str
    installed: Callable[[SystemInfo], bool]
    install: Callable[[SystemInfo], None]
    default_selected: bool = True
