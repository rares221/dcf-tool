"""Create or update the repository's GitHub labels from .github/labels.json using the GitHub CLI.

Run once after creating the repository (and again whenever labels.json changes):

    python scripts/sync_labels.py            # needs the `gh` CLI, logged in with `gh auth login`
    python scripts/sync_labels.py --dry-run  # print the commands without running them
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LABELS_FILE = Path(__file__).resolve().parents[1] / ".github" / "labels.json"


def build_commands(labels: list[dict]) -> list[list[str]]:
    """One `gh label create ... --force` command per label (--force updates a label that already exists)."""
    return [
        ["gh", "label", "create", l["name"], "--color", l["color"], "--description", l["description"], "--force"]
        for l in labels
    ]


def main(argv: list[str]) -> int:
    commands = build_commands(json.loads(LABELS_FILE.read_text(encoding="utf-8")))
    for cmd in commands:
        if "--dry-run" in argv:
            print(" ".join(f'"{part}"' if " " in part else part for part in cmd))
            continue
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(("ok    " if result.returncode == 0 else "FAILED") + " " + cmd[3])
        if result.returncode != 0:
            print("      " + result.stderr.strip())
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
