"""Первый локальный запрос; сохраняет только ответ и измеренные метрики."""
import json
import time
import urllib.request
from pathlib import Path

payload = {"model": "qwen3.5:9b", "messages": [{"role": "user", "content": "Объясни разницу между моделью и сервером двумя предложениями"}], "stream": False, "think": False, "options": {"num_ctx": 4096, "num_predict": 256, "temperature": 0.2, "seed": 42}}
started = time.perf_counter()
record = {"endpoint": "http://localhost:11434/api/chat", "request": payload}
try:
    req = urllib.request.Request(record["endpoint"], data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        answer = json.load(response)
    answer.get("message", {}).pop("thinking", None)
    record["response"] = answer
    record["load_seconds"] = answer.get("load_duration", 0) / 1e9
    record["total_seconds"] = answer.get("total_duration", 0) / 1e9
    duration = answer.get("eval_duration", 0) / 1e9
    record["decode_tokens_per_second"] = answer.get("eval_count", 0) / duration if duration else None
except Exception as exc:
    record["error"] = str(exc)
record["wall_seconds"] = time.perf_counter() - started
with Path(__file__).with_name("first-request.json").open("x", encoding="utf-8") as out:
    json.dump(record, out, ensure_ascii=False, indent=2)
print(json.dumps(record, ensure_ascii=False, indent=2))
