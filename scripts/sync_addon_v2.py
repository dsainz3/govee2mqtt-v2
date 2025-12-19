#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
ADDON_APP_ROOT = REPO_ROOT / "addon-v2" / "app"


def _sync_file(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def _sync_tree(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def main() -> int:
    _sync_file(PYTHON_ROOT / "pyproject.toml", ADDON_APP_ROOT / "pyproject.toml")
    _sync_file(PYTHON_ROOT / "README.md", ADDON_APP_ROOT / "README.md")
    _sync_tree(PYTHON_ROOT / "src", ADDON_APP_ROOT / "src")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
