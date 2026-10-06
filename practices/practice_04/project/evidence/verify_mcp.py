"""Actual stdio MCP requests, including inputs rejected by the tool schema."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    process = subprocess.Popen(["python3", ".opencode/mcp/subscriber_name.py"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    records = []
    try:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "notify-mini-evidence", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        for index, name in enumerate([" Ann ", "   ", "", 42, None, []], 3):
            requests.append({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                "params": {"name": "check_subscriber_name", "arguments": {"name": name}}})
        for request in requests:
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(process.stdout.readline()) if "id" in request else None
            records.append({"request": request, "response": response})
        results = [record["response"]["result"] for record in records if
                   record["request"]["method"] == "tools/call"]
        assert results[0] == {"content": [{"type": "text", "text": "Ann"}], "isError": False}
        assert all(result["isError"] for result in results[1:])
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    value = {"transport": "MCP JSON-RPC over stdio", "server_exit_code": process.returncode,
             "records": records}
    (ROOT / "evidence" / "mcp-protocol-calls.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
