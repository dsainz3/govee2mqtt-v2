#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]

PYPROJECT = REPO_ROOT / "python" / "pyproject.toml"
PY_INIT = REPO_ROOT / "python" / "src" / "govee2mqtt_v2" / "__init__.py"
ADDON_CONFIG = REPO_ROOT / "addon-v2" / "config.yaml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


VERSION_RE = re.compile(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")\s*$')
INIT_RE = re.compile(r'^(__version__\s*=\s*")(\d+\.\d+\.\d+)(")\s*$')
ADDON_RE = re.compile(r'^(version:\s*")(\d+\.\d+\.\d+)(")\s*$')


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _bump_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _update_version_line(content: str, pattern: re.Pattern[str], new_version: str) -> str:
    lines = content.splitlines()
    updated = False
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        lines[idx] = f"{match.group(1)}{new_version}{match.group(3)}"
        updated = True
        break
    if not updated:
        raise ValueError("Version line not found")
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _read_current_version() -> str:
    for line in _read(PYPROJECT).splitlines():
        match = VERSION_RE.match(line)
        if match:
            return match.group(2)
    raise ValueError("Version not found in pyproject.toml")


def _update_changelog(new_version: str) -> None:
    content = _read(CHANGELOG)
    if f"## {new_version}" in content:
        return

    lines = content.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            insert_at = idx
            break
    entry = [
        f"## {new_version}",
        "",
        "- Automated version bump.",
        "",
    ]
    new_lines = lines[:insert_at] + entry + lines[insert_at:]
    _write(CHANGELOG, "\n".join(new_lines) + "\n")


def main() -> int:
    current = _read_current_version()
    new_version = _bump_patch(current)

    _write(PYPROJECT, _update_version_line(_read(PYPROJECT), VERSION_RE, new_version))
    _write(PY_INIT, _update_version_line(_read(PY_INIT), INIT_RE, new_version))
    _write(ADDON_CONFIG, _update_version_line(_read(ADDON_CONFIG), ADDON_RE, new_version))
    _update_changelog(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
