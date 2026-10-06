"""Run the accepted experiment once; never overwrite an earlier result.

Only three source excerpts are placed in the model's standalone worktree.
References and results stay outside it. The observer forwards HTTP bytes unchanged.
"""
import hashlib
import http.client
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOMEWORK = Path(__file__).resolve().parent
REPO = HOMEWORK.parents[2]
RESULTS = Path(os.environ.get('ITMO_RESULTS_DIR', str(HOMEWORK / 'results'))).resolve()
RESULTS.mkdir(parents=True, exist_ok=True)
RG = Path(os.environ.get('ITMO_RIPGREP', '/tmp/opencode/ripgrep-dependency/rg'))
INPUTS = {'practices/practice_01/TRAINING_PR.diff': 42,
          'practices/practice_01/context.md': 58,
          'practices/practice_02/react/experiment.md': 8}
LOCK = threading.RLock()
CURRENT = None
STATE = {'status': 'preparing', 'runs': []}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hashes(root):
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}


def save(path, value, exclusive=False):
    if exclusive:
        with path.open('x') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        return
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)


def save_state():
    save(RESULTS / 'run-state.json', STATE)


def line(output, event):
    output.write(json.dumps(event, ensure_ascii=False) + '\n')
    output.flush()
    os.fsync(output.fileno())


def save_run(ctx):
    save(RESULTS / (ctx['record']['id'] + '-parameters.json'), ctx['record'])


def error(ctx, message):
    with LOCK:
        if not ctx['failed'].is_set():
            ctx['failed'].set()
            ctx['record']['error'] = message
            save(RESULTS / (ctx['record']['id'] + '-error.json'), {'error': message}, exclusive=True)
            save_run(ctx)
            print(ctx['record']['id'], 'ERROR', str(message)[:500], flush=True)


class Observer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        ctx = CURRENT
        connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=295)
        started = time.perf_counter()
        try:
            body = self.rfile.read(int(self.headers['Content-Length']))
            payload = json.loads(body)
            observed = {'type': 'request', 'path': self.path, 'model': payload.get('model'),
                        'temperature': payload.get('temperature'),
                        'reasoning_effort': payload.get('reasoning_effort'),
                        'max_tokens': payload.get('max_tokens'), 'stream': payload.get('stream'),
                        'tools': [t['function']['name'] for t in payload.get('tools', [])],
                        'message_roles': [m['role'] for m in payload.get('messages', [])],
                        'message_characters': sum(len(json.dumps(m, ensure_ascii=False)) for m in payload.get('messages', [])),
                        'sessionID': self.headers.get('x-opencode-session-id'),
                        'user_agent': self.headers.get('User-Agent')}
            system = [m['content'] for m in payload.get('messages', []) if m['role'] == 'system']
            observed['system_sha256'] = digest(json.dumps(system, ensure_ascii=False).encode())
            observed['configured_prompt_present'] = any(ctx['prompt'].strip() in s for s in system if isinstance(s, str))
            observed['source_prompt_sha256'] = digest(ctx['prompt'].encode())
            if not ctx['record']['requests']:
                users = [m['content'] for m in payload['messages'] if m['role'] == 'user']
                observed['initial_question_present'] = any(ctx['record']['question'] in json.dumps(u, ensure_ascii=False) for u in users)
                observed['initial_message_roles_expected'] = observed['message_roles'] == ['system', 'user']
            with LOCK:
                line(ctx['http'], observed)
                ctx['record']['requests'].append(observed)
                save_run(ctx)
            assert self.path == '/v1/chat/completions'
            assert observed['model'] == 'itmo-agent' and observed['temperature'] == 0.2
            assert observed['reasoning_effort'] == 'none' and observed['max_tokens'] == 4096
            assert observed['configured_prompt_present']
            assert not set(observed['tools']) - {'read', 'glob', 'grep', 'invalid'}
            if len(ctx['record']['requests']) == 1:
                assert observed['initial_question_present'] and observed['initial_message_roles_expected']
            headers = {k: v for k, v in self.headers.items() if k.lower() not in {'host', 'connection', 'content-length'}}
            connection.request('POST', self.path, body=body, headers=headers)
            response = connection.getresponse()
            with LOCK:
                line(ctx['http'], {'type': 'response_headers', 'status': response.status,
                                   'header_seconds': round(time.perf_counter() - started, 3)})
            if response.status >= 400:
                raise RuntimeError(f'Ollama HTTP {response.status}: {response.read().decode()}')
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'text/event-stream'))
            self.end_headers()
            self.wfile.flush()
            for chunk in iter(response.readline, b''):
                self.wfile.write(chunk)
                self.wfile.flush()
            with LOCK:
                line(ctx['http'], {'type': 'response_end', 'request_seconds': round(time.perf_counter() - started, 3)})
        except Exception as failure:
            if not ctx['failed'].is_set():
                error(ctx, f'{type(failure).__name__}: {failure}')
        finally:
            connection.close()


def stdout_reader(process, ctx):
    with (RESULTS / (ctx['record']['id'] + '.jsonl')).open('x') as output:
        for raw in process.stdout:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as failure:
                error(ctx, f'Invalid CLI JSON: {failure}')
                return
            part = event.get('part', {})
            if event.get('type') == 'reasoning' or part.get('type') == 'reasoning':
                ctx['record']['reasoning_events_excluded'] += 1
                continue
            line(output, event)
            with LOCK:
                record = ctx['record']
                record['events'] += 1
                if event.get('sessionID'):
                    record['sessionID'] = event['sessionID']
                if event['type'] == 'text':
                    record['assistant_text'].append(part['text'])
                    record['final_answer'] = part['text']
                if event['type'] == 'tool_use':
                    tool = {'tool': part['tool'], 'state': part['state'], 'callID': part['callID']}
                    record['tool_calls'].append(tool)
                    if part['state']['status'] == 'error':
                        record['tool_errors'].append(tool)
                save_run(ctx)
            print(record['id'], event['type'], part.get('tool', ''), flush=True)
            if event['type'] == 'error':
                error(ctx, event)
                return


def stderr_reader(process, ctx):
    with (RESULTS / (ctx['record']['id'] + '-stderr.log')).open('x') as output:
        for raw in process.stderr:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
            if 'level=ERROR' in raw or 'stream error' in raw:
                error(ctx, raw.strip())


def environment(variant, root, server):
    isolation = Path(tempfile.mkdtemp(prefix='session-', dir=root.parent / 'sessions'))
    for name in ['home', 'config', 'data', 'cache', 'state']:
        (isolation / name).mkdir()
    env = {'PATH': str(RG.parent) + ':' + os.environ['PATH'], 'LANG': 'C.UTF-8',
           'HOME': str(isolation / 'home'),
           **{f'XDG_{name.upper()}_HOME': str(isolation / name) for name in ['config', 'data', 'cache', 'state']},
           'OPENCODE_CONFIG': str(HOMEWORK / f'config-{variant.lower()}.json'),
           'OPENCODE_CONFIG_CONTENT': json.dumps({'provider': {'ollama': {'options': {'baseURL': f'http://127.0.0.1:{server.server_port}/v1'}}}}),
           'OPENCODE_DISABLE_PROJECT_CONFIG': '1', 'OPENCODE_PURE': '1',
           'OPENCODE_DISABLE_DEFAULT_PLUGINS': '1', 'OPENCODE_DISABLE_AUTOUPDATE': '1',
           'OPENCODE_DISABLE_MODELS_FETCH': '1', 'OPENCODE_DISABLE_LSP_DOWNLOAD': '1',
           'OPENCODE_DISABLE_CLAUDE_CODE': '1', 'OPENCODE_DISABLE_EXTERNAL_SKILLS': '1',
           'npm_config_offline': 'true', 'HTTP_PROXY': 'http://127.0.0.1:9',
           'HTTPS_PROXY': 'http://127.0.0.1:9', 'ALL_PROXY': 'http://127.0.0.1:9',
           'NO_PROXY': 'localhost,127.0.0.1,::1'}
    env.update({k.lower(): v for k, v in list(env.items()) if k.endswith('_PROXY')})
    return env


def execute(run_id, variant, question_index, phase, root, server, prompts, questions):
    global CURRENT
    env = environment(variant, root, server)
    record = {'id': run_id, 'phase': phase, 'variant': variant, 'question_index': question_index,
              'question': questions[question_index - 1], 'status': 'running',
              'prompt_sha256': digest(prompts[variant].encode()), 'input_sha256': hashes(root),
              'cwd': str(root), 'environment': env, 'requests': [], 'events': 0,
              'assistant_text': [], 'final_answer': None, 'tool_calls': [], 'tool_errors': [],
              'reasoning_events_excluded': 0, 'header_timeout_seconds': 295,
              'run_timeout_seconds': 600, 'output_limit_tokens': 4096, 'steps': 8}
    command = ['opencode', 'run', '--dir', str(root), '--agent', 'local-guide',
               '--model', 'ollama/itmo-agent', '--format', 'json', '--pure', '--print-logs',
               '--title', 'homework-experiment', record['question']]
    record['command'] = command
    ctx = {'record': record, 'prompt': prompts[variant], 'failed': threading.Event(),
           'http': (RESULTS / (run_id + '-http.jsonl')).open('x')}
    CURRENT = ctx
    STATE['current'] = run_id
    STATE['phase'] = phase
    STATE['runs'].append(record)
    save_run(ctx)
    save_state()
    started = time.perf_counter()
    print('START', run_id, flush=True)
    process = subprocess.Popen(command, cwd=root, env=env, text=True, bufsize=1,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    record['pid'] = process.pid
    readers = [threading.Thread(target=f, args=(process, ctx), daemon=True) for f in [stdout_reader, stderr_reader]]
    for reader in readers:
        reader.start()
    while process.poll() is None:
        if ctx['failed'].wait(0.2) or time.perf_counter() - started > 600:
            if not ctx['failed'].is_set():
                error(ctx, 'Run exceeded 600 seconds')
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            break
    process.wait()
    record['wall_seconds'] = round(time.perf_counter() - started, 3)
    for reader in readers:
        reader.join(timeout=5)
    if process.returncode and not ctx['failed'].is_set():
        error(ctx, f'CLI exited with code {process.returncode}')
    if not record['final_answer'] and not ctx['failed'].is_set():
        error(ctx, 'CLI finished without an assistant answer')
    record.update(exit_code=process.returncode, status='error' if ctx['failed'].is_set() else 'completed',
                  input_unchanged=hashes(root) == record['input_sha256'])
    record['ollama_ps'] = subprocess.run(['ollama', 'ps'], capture_output=True, text=True).stdout
    save_run(ctx)
    save_state()
    print('FINISH', run_id, record['status'], record['wall_seconds'], 's',
          json.dumps(record['final_answer'], ensure_ascii=False), flush=True)
    return record


def local_json(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:11434' + path, timeout=10) as response:
        return json.load(response)


def prepare():
    if (RESULTS / 'run-state.json').exists():
        raise SystemExit('An experiment already exists; refusing to overwrite or rerun it')
    assert RG.is_file() and os.access(RG, os.X_OK)
    STATE['source_sha256_before'] = {f'practices/{name}/{path}': value for name in ['practice_01', 'practice_02']
                                     for path, value in hashes(REPO / 'practices' / name).items()}
    STATE['old_results_sha256_before'] = hashes(REPO / 'practices/practice_03/lab/results')
    STATE['accepted_plan_sha256'] = {name: digest((HOMEWORK / name).read_bytes()) for name in
                                    ['QUESTIONS.md', 'REFERENCES.md', 'prompt-a.txt', 'prompt-b.txt']}
    Path('/tmp/opencode').mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='homework-ab-', dir='/tmp/opencode'))
    root = workspace / 'inputs'
    root.mkdir()
    (workspace / 'sessions').mkdir()
    manifest = {'inputs': [], 'reference_coverage': [], 'references_copied': False,
                'report_copied': False, 'previous_answers_copied': False}
    for path, count in INPUTS.items():
        source = REPO / path
        data = b''.join(source.read_bytes().splitlines(keepends=True)[:count])
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            output.write(data)
        manifest['inputs'].append({'path': path, 'lines': [1, count], 'sha256': digest(data),
                                   'source_sha256': digest(source.read_bytes())})
    references = (HOMEWORK / 'REFERENCES.md').read_text()
    for path, spec in re.findall(r'`(practices/[^`]+?):([0-9,–-]+)`', references):
        assert path in INPUTS
        for part in spec.split(','):
            endpoints = re.split('[–-]', part)
            start, end = int(endpoints[0]), int(endpoints[-1])
            assert 1 <= start <= end <= INPUTS[path]
        manifest['reference_coverage'].append({'path': path, 'lines': spec, 'covered': True})
    assert len(manifest['reference_coverage']) >= 12
    assert set(hashes(root)) == set(INPUTS)
    # A standalone worktree makes external_directory=deny effective for every tool.
    subprocess.run(['git', 'init', '--quiet', str(root)], check=True, capture_output=True)
    manifest.update(root=str(root), identical_input_sha256=hashes(root), coverage_complete=True)
    save(RESULTS / 'input-manifest.json', manifest, exclusive=True)
    STATE['input_root'] = str(root)
    STATE['inputs'] = hashes(root)
    STATE['versions'] = {name: subprocess.check_output(command, text=True).strip() for name, command in
                         [('opencode', ['opencode', '--version']), ('ollama', ['ollama', '--version']),
                          ('ripgrep', [str(RG), '--version'])]}
    STATE['ripgrep_sha256'] = digest(RG.read_bytes())
    tags = local_json('/api/tags')['models']
    STATE['model'] = next(m for m in tags if m['name'] in ['itmo-agent', 'itmo-agent:latest'])
    STATE['ollama_show'] = subprocess.check_output(['ollama', 'show', 'itmo-agent'], text=True)
    prompts = {variant: (HOMEWORK / f'prompt-{variant.lower()}.txt').read_text() for variant in ['A', 'B']}
    questions = [line.split('. ', 1)[1] for line in (HOMEWORK / 'QUESTIONS.md').read_text().splitlines()
                 if re.match(r'^[1-5]\. ', line)]
    assert len(questions) == 5
    STATE['questions'] = questions
    save_state()
    return root, prompts, questions


def main():
    state_path = RESULTS / 'run-state.json'
    if state_path.exists():
        prepared = json.loads(state_path.read_text())
        if prepared['status'] != 'prepared':
            raise SystemExit('An experiment already exists; refusing to overwrite or rerun it')
        STATE.update(prepared)
        root = Path(STATE['input_root'])
        prompts = {variant: (HOMEWORK / f'prompt-{variant.lower()}.txt').read_text() for variant in ['A', 'B']}
        questions = STATE['questions']
        assert hashes(root) == STATE['inputs']
        assert all(digest((HOMEWORK / name).read_bytes()) == value for name, value in STATE['accepted_plan_sha256'].items())
    else:
        root, prompts, questions = prepare()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Observer)
    resolved = {}
    for variant in ['A', 'B']:
        env = environment(variant, root, server)
        check = subprocess.run(['opencode', 'debug', 'config', '--pure'], cwd=root, env=env,
                               capture_output=True, text=True, timeout=120)
        save(RESULTS / f'preflight-{variant.lower()}.json', {'exit_code': check.returncode, 'stderr': check.stderr}, exclusive=True)
        assert check.returncode == 0, check.stderr
        resolved[variant] = json.loads(check.stdout)
        save(RESULTS / f'resolved-config-{variant.lower()}.json', resolved[variant], exclusive=True)
        assert resolved[variant]['agent']['local-guide']['prompt'].strip() == prompts[variant].strip()
        clean = json.loads(json.dumps(resolved[variant]))
        clean['agent']['local-guide'].pop('prompt')
        if variant == 'A':
            baseline = clean
        else:
            assert baseline == clean, 'Configuration differs beyond the local-guide prompt'
    STATE['only_prompt_differs'] = True
    STATE['status'] = 'running'
    save_state()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for index in range(1, 6):
        for variant in ['A', 'B']:
            execute(f'quality-{variant.lower()}-q{index}', variant, index, 'quality', root, server, prompts, questions)
    # Separate, unmeasured warmups for both instruction prefixes.
    for variant in ['A', 'B']:
        execute(f'warmup-{variant.lower()}-q1', variant, 1, 'warmup', root, server, prompts, questions)
    for repetition in range(1, 4):
        for variant in ['A', 'B']:
            execute(f'timing-{variant.lower()}-q1-r{repetition}', variant, 1, 'timing', root, server, prompts, questions)
    speed = {'metric': 'wall_seconds: opencode process start to process exit', 'unit': 'seconds',
             'warmups_excluded': True, 'order': ['A1', 'B1', 'A2', 'B2', 'A3', 'B3'], 'variants': {}}
    for variant in ['A', 'B']:
        records = [r for r in STATE['runs'] if r['phase'] == 'timing' and r['variant'] == variant]
        successful = [r['wall_seconds'] for r in records if r['status'] == 'completed']
        speed['variants'][variant] = {'wall_seconds': [r['wall_seconds'] for r in records],
                                      'successful_repetitions': len(successful),
                                      'median_seconds': round(statistics.median(successful), 3) if len(successful) == 3 else None,
                                      'runs': [r['id'] for r in records]}
    save(RESULTS / 'speed.json', speed, exclusive=True)
    STATE['source_unchanged'] = all(digest((REPO / path).read_bytes()) == value for path, value in STATE['source_sha256_before'].items())
    old = hashes(REPO / 'practices/practice_03/lab/results')
    STATE['old_results_unchanged'] = old == STATE['old_results_sha256_before']
    STATE['accepted_plan_unchanged'] = all(digest((HOMEWORK / name).read_bytes()) == value for name, value in STATE['accepted_plan_sha256'].items())
    STATE['inputs_unchanged'] = hashes(root) == STATE['inputs']
    STATE['status'] = 'completed_with_errors' if any(r['status'] == 'error' for r in STATE['runs']) else 'completed'
    STATE.pop('current', None)
    save_state()
    server.shutdown()
    print('DONE', STATE['status'], json.dumps(speed, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--prepare-only']:
            prepare()
            STATE['status'] = 'prepared'
            save_state()
            print('Prepared: three identical input files; all 12 reference citations covered; no model generation.')
        elif not sys.argv[1:]:
            main()
        else:
            raise SystemExit('Usage: run_experiment.py [--prepare-only]')
    except Exception as failure:
        STATE.update(status='fatal_error', error=f'{type(failure).__name__}: {failure}')
        save_state()
        save(RESULTS / 'experiment-error.json', {'error': STATE['error']}, exclusive=True)
        print('FATAL', STATE['error'], flush=True)
        raise
