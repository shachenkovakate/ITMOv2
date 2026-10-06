---
name: notify-mini-check
description: Use when checking Notify Mini or verifying its edits; runs scripts/check.sh and returns structured test output and exit code.
---

# Notify Mini check

Run from the Notify Mini project directory:

```sh
python3 .opencode/skills/notify-mini-check/scripts/check.py
```

The script runs the unchanged `sh scripts/check.sh` in the project directory.
It prints JSON with `command`, `exit_code`, `stdout`, `stderr`, and `ok`,
and exits with the check's exit code. Report failures with their actual output.
Do not implement features or change the contract or runner as part of a check.
