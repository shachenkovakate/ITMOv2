"""Check the original hook log and scan commit candidates without exposing secrets."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[2]


def verify():
    records = [json.loads(line) for line in
               (ROOT / "evidence/hook-events.jsonl").read_text().splitlines()]
    red, green = records[3], records[4]
    assert red["exit_code"] == 1
    assert "has no attribute 'unsubscribe'" in red["stderr"]
    assert "FAILED (errors=7)" in red["stderr"]
    assert green["exit_code"] == 0
    assert "Ran 9 tests" in green["stderr"] and "\nOK\n" in green["stderr"]
    mapping = json.loads((ROOT / "evidence/feature-a-events.json").read_text())
    assert mapping["source_hook_records"] == {"red_hook": 4, "green_hook": 5}

    candidates = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z",
         "--", "practices/practice_04", "lections/lection_4_AI engineering tools.pdf"],
        cwd=REPO).decode().split("\0")
    patterns = {
        "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        "provider_token": rb"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b",
        "credential_assignment": rb"(?i)[\"']?(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_+/=.-]{16,}[\"']",
        "bearer_token": rb"(?i)\bBearer\s+[A-Za-z0-9_.-]{20,}",
    }
    findings = []
    paths = sorted(set(path for path in candidates if path))
    for path in paths:
        data = (REPO / path).read_bytes()
        for label, pattern in patterns.items():
            if re.search(pattern, data):
                findings.append({"path": path, "pattern": label})
    check = subprocess.run(
        ["python3", ".opencode/skills/notify-mini-check/scripts/check.py"],
        cwd=ROOT, capture_output=True, text=True)
    result = {
        "hook_log": {"path": "evidence/hook-events.jsonl", "fail_record": 4,
                     "pass_record": 5, "verified": True},
        "secret_scan": {"files_scanned": len(paths), "findings": findings,
                        "scope": "Git candidates: practice_04 and lecture 4, including binary files",
                        "patterns": list(patterns)},
        "skill_check": json.loads(check.stdout),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not findings, "Secret-like values found; only paths and pattern labels reported"
    assert check.returncode == 0


if __name__ == "__main__":
    verify()
