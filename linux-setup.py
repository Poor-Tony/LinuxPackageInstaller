#!/usr/bin/env python3
"""
Install a personal Linux desktop software set across common distributions.

The implementation lives in the linux_setup package so the entry point stays
small and each installer area can be maintained independently.
"""

from __future__ import annotations

from linux_setup.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
