"""Capture only observable tool events; never persist model reasoning or credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence"


def save(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def check():
    run = subprocess.run(["sh", "scripts/check.sh"], cwd=ROOT, capture_output=True, text=True)
    save("baseline-check.json", {"command": "sh scripts/check.sh", "exit_code": run.returncode,
                                "stdout": run.stdout, "stderr": run.stderr})
    skills = subprocess.run(["opencode", "debug", "skill"], cwd=ROOT, capture_output=True, text=True)
    save("skill-discovery.json", {"exit_code": skills.returncode,
        "skills": [s for s in json.loads(skills.stdout) if s["name"] == "notify-mini-check"]})
    mcp = subprocess.run(["opencode", "mcp", "list"], cwd=ROOT, capture_output=True, text=True)
    save("mcp-connection.json", {"command": "opencode mcp list", "exit_code": mcp.returncode,
                                 "stdout": mcp.stdout, "stderr": mcp.stderr})


def session(model="openai/gpt-6.1-sol"):
    prompt = """Verify only the Notify Mini environment. No features, no commits, no reflection.
First read AGENTS.md, docs/requirements.md and test_service.py.
Call the skill tool with name notify-mini-check, then actually run the Python script it specifies.
Call the connected MCP check_subscriber_name tool with name ' Ann ' and then name '   '.
The second call must return a tool error; retain it and continue.
Verify the after-edit hook using three actual tool calls on evidence/hook-probe.txt only:
1. write content 'hook probe: write\n' with write;
2. edit it to 'hook probe: edit\n' with edit;
3. apply_patch to change it to 'hook probe: apply_patch\n'.
Do not substitute bash file writes. Each result should include [notify-mini-check hook].
If any of those tools is unavailable, report it explicitly. Do not change any other files.
Summarize observed tool outcomes, without reasoning."""
    if model == "opencode/big-pickle":
        prompt = """Verify the Notify Mini after-edit hook only. First read AGENTS.md,
docs/requirements.md and test_service.py. Do not implement features or make commits.
Use the write tool to create evidence/hook-write-edit.txt containing 'hook probe: write\n'.
Then use read and the edit tool to replace 'hook probe: write' with 'hook probe: edit'.
Do not write any other files, do not use bash writes or apply_patch.
Observe [notify-mini-check hook] and test output in both tool responses.
Finish with a concise summary of actual results."""
    command = ["opencode", "run", "--format", "json", "-m", model, prompt]
    env = dict(os.environ)
    # Session-only boundary for the verification, not a permanent global permission change.
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": {
        "edit": {"*": "deny", "evidence/*": "allow", "practices/practice_04/project/evidence/*": "allow", str(EVIDENCE / "*"): "allow"},
        "bash": {"*": "deny", "python3 .opencode/skills/notify-mini-check/scripts/check.py": "allow"}
    }})
    try:
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=240)
        raw = run.stdout
        code = run.returncode
    except subprocess.TimeoutExpired as error:
        raw = error.stdout or ""
        if isinstance(raw, bytes):
            raw = raw.decode(errors="replace")
        code = 124
    events = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        # Explicit allowlist: no reasoning events, session exports, or headers.
        if event.get("type") == "tool_use":
            part = event.get("part", {})
            state = part.get("state", {})
            events.append({"type": "tool_use", "tool": part.get("tool"),
                "status": state.get("status"), "input": state.get("input"),
                "output": state.get("output"), "error": state.get("error")})
        elif event.get("type") == "error":
            error = event.get("error", {})
            data = error.get("data", {})
            events.append({"type": "error", "name": error.get("name"),
                           "message": data.get("message"), "status_code": data.get("statusCode")})
    result = {"command": f"opencode run --format json -m {model} <verification prompt>",
              "exit_code": code, "events": events}
    destination = "opencode-tool-events.json" if not (EVIDENCE / "opencode-tool-events.json").exists() else "opencode-tool-events-retry.json"
    if model == "opencode/big-pickle":
        destination = "opencode-write-edit-events.json"
    save(destination, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        check()
    session(sys.argv[1] if len(sys.argv) > 1 else "openai/gpt-6.1-sol")
