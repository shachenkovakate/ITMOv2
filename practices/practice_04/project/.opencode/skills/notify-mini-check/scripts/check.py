#!/usr/bin/env python3
"""Structured wrapper around the project's canonical check."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[4]
    try:
        run = subprocess.run(
            ["sh", "scripts/check.sh"], cwd=root, capture_output=True, text=True
        )
        result = {"command": "sh scripts/check.sh", "exit_code": run.returncode,
                  "stdout": run.stdout, "stderr": run.stderr,
                  "ok": run.returncode == 0}
    except OSError as error:
        result = {"command": "sh scripts/check.sh", "exit_code": 127,
                  "stdout": "", "stderr": str(error), "ok": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
