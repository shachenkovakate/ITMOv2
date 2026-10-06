"""One isolated run; observe unmodified HTTP requests and durably save CLI events."""
import hashlib
import http.client
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RESULTS = Path(__file__).resolve().parent
LAB = RESULTS.parent
DEMO = LAB / 'demo'
PREFIX = 'read-check-2'
LOCK = threading.Lock()
FAILED = threading.Event()
START = time.perf_counter()
STATE = {'status': 'preparing', 'requests': [], 'events': 0, 'read_calls': 0, 'answer': ''}


def hashes():
    return {str(p.relative_to(DEMO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEMO.rglob('*') if p.is_file()}


def save():
    STATE['wall_seconds'] = round(time.perf_counter() - START, 3)
    path = RESULTS / f'{PREFIX}-verification.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def write_line(output, value):
    output.write(json.dumps(value, ensure_ascii=False) + '\n')
    output.flush()
    os.fsync(output.fileno())


def fail(message):
    with LOCK:
        if not FAILED.is_set():
            STATE['error'] = message
            FAILED.set()
            with (RESULTS / f'{PREFIX}-error.json').open('x') as output:
                json.dump({'error': message, 'wall_seconds': round(time.perf_counter() - START, 3)}, output, ensure_ascii=False, indent=2)
                output.write('\n')
                output.flush()
                os.fsync(output.fileno())
            save()
            print('ERROR:', message, flush=True)


class Observer(BaseHTTPRequestHandler):
    # Forward bytes unchanged. Only request metadata is persisted, never messages.
    def log_message(self, *args):
        pass

    def do_POST(self):
        connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=295)
        try:
            body = self.rfile.read(int(self.headers['Content-Length']))
            payload = json.loads(body)
            observed = {'path': self.path, 'model': payload.get('model'),
                        'reasoning_effort': payload.get('reasoning_effort'),
                        'temperature': payload.get('temperature'), 'stream': payload.get('stream'),
                        'max_tokens': payload.get('max_tokens'),
                        'message_roles': [m['role'] for m in payload.get('messages', [])],
                        'message_characters': sum(len(json.dumps(m, ensure_ascii=False)) for m in payload.get('messages', [])),
                        'tools': [t['function']['name'] for t in payload.get('tools', [])],
                        'sessionID': self.headers.get('x-opencode-session-id'),
                        'user_agent': self.headers.get('User-Agent'),
                        'wall_seconds': round(time.perf_counter() - START, 3)}
            with LOCK:
                write_line(HTTP_LOG, {'type': 'request', **observed})
                STATE['requests'].append(observed)
                save()
            if self.path != '/v1/chat/completions' or observed['reasoning_effort'] != 'none':
                raise ValueError('OpenCode did not send reasoning_effort=none to /v1/chat/completions')
            if observed['model'] != 'itmo-agent' or observed['temperature'] != 0.2:
                raise ValueError('Unexpected model or temperature in actual HTTP request')
            if set(observed['tools']) - {'read', 'glob', 'grep', 'invalid'}:
                raise ValueError('Unexpected tool advertised in HTTP request')
            print('HTTP request verified: reasoning_effort=none, temperature=0.2;', observed['tools'], flush=True)
            request_start = time.perf_counter()
            headers = {k: v for k, v in self.headers.items() if k.lower() not in {'host', 'connection', 'content-length'}}
            connection.request('POST', self.path, body=body, headers=headers)
            response = connection.getresponse()
            with LOCK:
                write_line(HTTP_LOG, {'type': 'response_headers', 'status': response.status,
                                     'header_seconds': round(time.perf_counter() - request_start, 3)})
            if response.status >= 400:
                raise RuntimeError(f'Ollama HTTP {response.status}: {response.read().decode()}')
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'text/event-stream'))
            self.end_headers()
            self.wfile.flush()
            for line in iter(response.readline, b''):
                self.wfile.write(line)
                self.wfile.flush()
            with LOCK:
                write_line(HTTP_LOG, {'type': 'response_end', 'request_seconds': round(time.perf_counter() - request_start, 3)})
        except (BrokenPipeError, ConnectionResetError) as error:
            if not FAILED.is_set():
                fail(f'{type(error).__name__}: {error}')
        except Exception as error:
            fail(f'{type(error).__name__}: {error}')
        finally:
            connection.close()


def stdout_reader(process):
    with (RESULTS / f'{PREFIX}.jsonl').open('x') as output:
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                fail(f'CLI returned invalid JSON: {error}')
                return
            if event.get('type') == 'reasoning' or event.get('part', {}).get('type') == 'reasoning':
                continue
            write_line(output, event)
            part = event.get('part', {})
            with LOCK:
                STATE['events'] += 1
                STATE['sessionID'] = event.get('sessionID', STATE.get('sessionID'))
                if event.get('type') == 'tool_use' and part.get('tool') == 'read':
                    STATE['read_calls'] += 1
                    STATE.setdefault('reads', []).append(part.get('state'))
                if event.get('type') == 'text':
                    STATE['answer'] += part.get('text', '')
                save()
            print('CLI:', event.get('type'), part.get('tool', ''), flush=True)
            if event.get('type') == 'error' or part.get('state', {}).get('status') == 'error':
                fail(event)
                return


def stderr_reader(process):
    with (RESULTS / f'{PREFIX}-stderr.log').open('x') as output:
        for line in process.stderr:
            output.write(line)
            output.flush()
            os.fsync(output.fileno())
            if 'level=ERROR' in line or 'stream error' in line:
                fail(line.strip())


def main():
    global HTTP_LOG
    if (RESULTS / f'{PREFIX}-verification.json').exists():
        raise SystemExit('Existing attempt will not be overwritten')
    STATE['demo_sha256_before'] = hashes()
    isolation = Path(tempfile.mkdtemp(prefix='read-check-2-', dir='/tmp/opencode'))
    for name in ['home', 'config', 'data', 'cache', 'state']:
        (isolation / name).mkdir()
    STATE['isolation_directory'] = str(isolation)
    STATE['opencode_version'] = subprocess.check_output(['opencode', '--version'], text=True).strip()
    STATE['configuration_sources'] = [
        'https://raw.githubusercontent.com/anomalyco/opencode/v1.18.34/packages/opencode/src/session/llm/request.ts',
        'https://raw.githubusercontent.com/anomalyco/opencode/v1.18.34/packages/opencode/src/provider/transform.ts',
        'https://opencode.ai/config.json',
    ]
    server = ThreadingHTTPServer(('127.0.0.1', 0), Observer)
    config = json.loads((DEMO / 'opencode.json').read_text())
    config.update(enabled_providers=['ollama'], default_agent='local-guide', plugin=[], mcp={},
                  share='disabled', autoupdate=False, snapshot=False, lsp=False, formatter=False)
    config['provider']['ollama']['options']['baseURL'] = f'http://127.0.0.1:{server.server_port}/v1'
    model = config['provider']['ollama']['models']['itmo-agent']
    model['options'] = {'reasoningEffort': 'none'}
    model['temperature'] = True
    config['agent']['local-guide']['temperature'] = 0.2
    config['agent']['local-guide']['prompt'] = '{file:' + str(DEMO / 'repo-system.txt') + '}'
    config_path = RESULTS / f'{PREFIX}-opencode.json'
    with config_path.open('x') as output:
        json.dump(config, output, ensure_ascii=False, indent=2)
        output.write('\n')
    env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'HOME': str(isolation / 'home'),
           **{f'XDG_{name.upper()}_HOME': str(isolation / name) for name in ['config', 'data', 'cache', 'state']},
           'OPENCODE_CONFIG': str(config_path), 'OPENCODE_DISABLE_PROJECT_CONFIG': '1',
           'OPENCODE_PURE': '1', 'OPENCODE_DISABLE_DEFAULT_PLUGINS': '1',
           'OPENCODE_DISABLE_AUTOUPDATE': '1', 'OPENCODE_DISABLE_MODELS_FETCH': '1',
           'OPENCODE_DISABLE_LSP_DOWNLOAD': '1', 'OPENCODE_DISABLE_CLAUDE_CODE': '1',
           'OPENCODE_DISABLE_EXTERNAL_SKILLS': '1', 'npm_config_offline': 'true',
           'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
           'ALL_PROXY': 'http://127.0.0.1:9', 'NO_PROXY': 'localhost,127.0.0.1,::1'}
    env.update({k.lower(): v for k, v in list(env.items()) if k.endswith('_PROXY')})
    STATE['environment'] = env
    save()
    debug = subprocess.run(['opencode', 'debug', 'config', '--pure'], cwd=DEMO, env=env,
                           capture_output=True, text=True, timeout=120)
    with (RESULTS / f'{PREFIX}-config.json').open('x') as output:
        output.write(debug.stdout)
    if debug.returncode:
        fail(debug.stderr)
        return
    resolved = json.loads(debug.stdout)
    assert resolved['provider']['ollama']['models']['itmo-agent']['options']['reasoningEffort'] == 'none'
    assert resolved['agent']['local-guide']['permission'] == {'*': 'deny', 'read': 'allow', 'glob': 'allow', 'grep': 'allow'}
    assert resolved['provider']['ollama']['models']['itmo-agent']['limit']['context'] == 65536
    assert resolved['enabled_providers'] == ['ollama'] and not resolved['mcp'] and not resolved['plugin']
    HTTP_LOG = (RESULTS / f'{PREFIX}-http.jsonl').open('x')
    threading.Thread(target=server.serve_forever, daemon=True).start()
    command = ['opencode', 'run', '--dir', 'demo', '--agent', 'local-guide', '--model', 'ollama/itmo-agent',
               '--format', 'json', '--pure', '--print-logs', '--title', 'read-check-2',
               'Прочитай README.md инструментом read. Назови команду тестирования со ссылкой на файл']
    STATE.update(command=command, cwd=str(LAB), status='running')
    save()
    process = subprocess.Popen(command, cwd=LAB, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1, start_new_session=True)
    STATE['pid'] = process.pid
    save()
    threads = [threading.Thread(target=reader, args=(process,), daemon=True) for reader in [stdout_reader, stderr_reader]]
    for thread in threads:
        thread.start()
    run_start = time.perf_counter()
    while process.poll() is None:
        if FAILED.wait(0.2) or time.perf_counter() - run_start > 600:
            if not FAILED.is_set():
                fail('Read-check exceeded 600 seconds')
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            break
    process.wait()
    for thread in threads:
        thread.join(timeout=5)
    if process.returncode and not FAILED.is_set():
        fail(f'CLI exit code {process.returncode}')
    STATE.update(exit_code=process.returncode, run_seconds=round(time.perf_counter() - run_start, 3),
                 status='failed' if FAILED.is_set() else 'completed', demo_sha256_after=hashes())
    STATE['demo_unchanged'] = STATE['demo_sha256_before'] == STATE['demo_sha256_after']
    ps = subprocess.run(['ollama', 'ps'], capture_output=True, text=True)
    STATE['ollama_ps'] = ps.stdout
    save()
    server.shutdown()
    print(json.dumps({k: STATE.get(k) for k in ['status', 'run_seconds', 'read_calls', 'answer', 'error', 'ollama_ps', 'demo_unchanged']}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        fail(f'{type(error).__name__}: {error}')
        STATE['status'] = 'failed'
        save()
