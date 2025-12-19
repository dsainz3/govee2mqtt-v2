#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess


def _git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = result.stdout.strip()
    return [line for line in output.splitlines() if line]


def _changed_files() -> list[str]:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF")
    to_ref = os.getenv("PRE_COMMIT_TO_REF")
    if from_ref and to_ref:
        return _git("diff", "--name-only", f"{from_ref}..{to_ref}")

    staged = _git("diff", "--name-only", "--cached")
    if staged:
        return staged

    return _git("diff", "--name-only")


def main() -> int:
    changed = _changed_files()
    if not changed:
        return 0

    if "CHANGELOG.md" in changed:
        return 0

    print("CHANGELOG.md must be updated when any files change.")
    print("Changed files:")
    for path in changed:
        print(f" - {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
