"""Проверка локального API в отдельном network namespace без внешних интерфейсов."""
import json, os, subprocess, tempfile, time, urllib.request
from pathlib import Path
root = Path(__file__).resolve().parent
output = root / 'audit/offline.json'
if output.exists():
    raise SystemExit('Результат уже существует')
subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
env = dict(os.environ, OLLAMA_NO_CLOUD='1', OLLAMA_HOST='127.0.0.1:11434',
           OLLAMA_MODELS='/usr/share/ollama/.ollama/models',
           HOME=tempfile.mkdtemp(prefix='itmo-offline-home-'), OLLAMA_NUM_PARALLEL='1')
record = {'method': 'unshare -Urn: separate network namespace, loopback only',
          'interfaces': subprocess.check_output(['ip', '-j', 'address'], text=True),
          'OLLAMA_NO_CLOUD': '1', 'weights': env['OLLAMA_MODELS']}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with (root / 'audit/offline-server.log').open('x') as log:
    server = subprocess.Popen(['ollama', 'serve'], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                with opener.open('http://127.0.0.1:11434/api/tags', timeout=2) as r:
                    record['tags'] = json.load(r)
                break
            except Exception:
                if server.poll() is not None: raise RuntimeError('Ollama server exited')
                time.sleep(.2)
        else: raise RuntimeError('Server did not start')
        payload = {'model': 'qwen3.5:9b', 'stream': False, 'think': False,
                   'messages': [{'role':'user','content':'Объясни разницу между моделью и сервером двумя предложениями'}],
                   'options': {'num_ctx':4096,'num_predict':256,'temperature':.2,'seed':42}}
        record['request'] = payload
        start = time.perf_counter()
        req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        with opener.open(req, timeout=300) as r:
            record['http_status'] = r.status
            record['response'] = json.load(r)
        record['response'].get('message',{}).pop('thinking',None)
        record['wall_seconds'] = time.perf_counter()-start
        record['success'] = bool(record['response'].get('message',{}).get('content'))
    except Exception as exc:
        record['error'] = str(exc)
        record['success'] = False
    finally:
        server.terminate()
        try: server.wait(timeout=10)
        except subprocess.TimeoutExpired: server.kill(); server.wait()
with output.open('x') as f: json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in record.items() if k not in ['tags','request','interfaces']},ensure_ascii=False,indent=2))
