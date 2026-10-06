#!/usr/bin/env python3
"""Local MCP server over newline-delimited JSON-RPC stdio; standard library only."""
import json
import sys


def handle(request):
    method = request.get("method")
    if "id" not in request:
        return None
    response = {"jsonrpc": "2.0", "id": request["id"]}
    if method == "initialize":
        result = {"protocolVersion": request.get("params", {}).get(
            "protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
            "serverInfo": {"name": "notify-mini-name", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": "check_subscriber_name",
            "description": "Trim a nonempty subscriber name; reject empty names and non-string types.",
            "inputSchema": {"type": "object", "properties": {
                "name": {"type": "string"}}, "required": ["name"],
                "additionalProperties": False}}]}
    elif method == "tools/call":
        params = request.get("params", {})
        if params.get("name") != "check_subscriber_name":
            response["error"] = {"code": -32602, "message": "unknown tool"}
            return response
        name = params.get("arguments", {}).get("name")
        error = "name must be a string" if not isinstance(name, str) else (
            "empty name" if not name.strip() else None)
        result = {"content": [{"type": "text", "text": error or name.strip()}],
                  "isError": error is not None}
    else:
        response["error"] = {"code": -32601, "message": "method not found"}
        return response
    response["result"] = result
    return response


def main():
    for line in sys.stdin:
        try:
            response = handle(json.loads(line))
        except (ValueError, TypeError, AttributeError) as error:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": str(error)}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
