"""Five isolated sessions using the unchanged, successful read-check-2 runner."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
RESULTS = Path(__file__).resolve().parent
LAB = RESULTS.parent
DEMO = LAB / 'demo'
PREFIX = 'project-check'


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def questions():
    lines = (LAB / 'QUESTIONS.md').read_text().splitlines()
    return [line.split('. ', 1)[1] for line in lines if line[:1].isdigit()]


def save(path, payload, mode='w'):
    with path.open(mode) as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def worker(index):
    question = questions()[index - 1]
    # No reference answers, report, history or results are copied here.
    sandbox = Path(tempfile.mkdtemp(prefix=f'project-check-q{index}-', dir='/tmp/opencode'))
    shutil.copytree(DEMO, sandbox / 'demo', ignore=shutil.ignore_patterns('__pycache__'))
    spec = importlib.util.spec_from_file_location('isolated_read_check', RESULTS / 'read-check-2-run.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.RESULTS = RESULTS
    runner.LAB = sandbox
    runner.DEMO = sandbox / 'demo'
    runner.PREFIX = f'{PREFIX}-q{index}'
    runner.STATE['question'] = question
    runner.STATE['sandbox_files'] = hashes(sandbox / 'demo')
    runner.STATE['original_demo_sha256'] = hashes(DEMO)
    runner.STATE['references_transmitted'] = False
    popen = subprocess.Popen

    def isolated_popen(command, *args, **kwargs):
        if command[:2] == ['opencode', 'run']:
            command = list(command)
            command[-1] = question
            command[command.index('--title') + 1] = runner.PREFIX
            runner.STATE['command'] = command
            runner.save()
        return popen(command, *args, **kwargs)

    runner.subprocess.Popen = isolated_popen
    try:
        runner.main()
    except Exception as error:
        runner.fail(f'{type(error).__name__}: {error}')
        runner.STATE['status'] = 'failed'
        runner.save()
    finally:
        runner.subprocess.Popen = popen
    raise SystemExit(0 if runner.STATE['status'] == 'completed' else 1)


def batch(start=1):
    suffix = '-remaining' if start > 1 else ''
    path = RESULTS / f'{PREFIX}{suffix}-batch.json'
    original = hashes(DEMO)
    old_results = {k: v for k, v in hashes(RESULTS).items() if not k.startswith(PREFIX)}
    state = {'status': 'running', 'questions': questions(), 'demo_sha256_before': original,
             'old_results_sha256_before': old_results, 'runs': []}
    save(path, state, 'x')
    for index, question in enumerate(questions(), 1):
        if index < start:
            continue
        print(f'Question {index}: {question}', flush=True)
        process = subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()), '--worker', str(index)])
        result_path = RESULTS / f'{PREFIX}-q{index}-verification.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        state['runs'].append({'question': index, 'worker_exit_code': process.returncode,
                              'sessionID': result.get('sessionID'), 'status': result.get('status'),
                              'answer': result.get('answer'), 'run_seconds': result.get('run_seconds')})
        save(path, state)
    state['status'] = 'completed_with_errors' if any(r['worker_exit_code'] for r in state['runs']) else 'completed'
    state['demo_sha256_after'] = hashes(DEMO)
    state['demo_unchanged'] = state['demo_sha256_before'] == state['demo_sha256_after']
    after = hashes(RESULTS)
    state['old_results_unchanged'] = all(after.get(k) == v for k, v in old_results.items())
    save(path, state)
    print(json.dumps(state['runs'], ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(int(sys.argv[2]))
    elif sys.argv[1:] == ['--remaining']:
        batch(start=3)
    else:
        batch()
