from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def main() -> None:
    run([sys.executable, "-m", "alembic", "upgrade", "head"])
    run([sys.executable, "scripts/db/seed_local_data.py"])


if __name__ == "__main__":
    main()
