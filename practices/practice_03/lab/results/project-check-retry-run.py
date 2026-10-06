"""Retry only questions 2 and 3 after preparing the offline ripgrep dependency."""
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
DEPENDENCY = Path('/tmp/opencode/ripgrep-dependency/rg')


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def save(path, payload, mode='w'):
    with path.open(mode) as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def worker(index):
    assert index in (2, 3)
    assert json.loads((RESULTS / 'project-check-ripgrep-offline.json').read_text())['success']
    question = [line.split('. ', 1)[1] for line in (LAB / 'QUESTIONS.md').read_text().splitlines()
                if line[:1].isdigit()][index - 1]
    sandbox = Path(tempfile.mkdtemp(prefix=f'project-check-q{index}-retry1-', dir='/tmp/opencode'))
    shutil.copytree(DEMO, sandbox / 'demo', ignore=shutil.ignore_patterns('__pycache__'))
    spec = importlib.util.spec_from_file_location('isolated_read_check', RESULTS / 'read-check-2-run.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.RESULTS = RESULTS
    runner.LAB = sandbox
    runner.DEMO = sandbox / 'demo'
    runner.PREFIX = f'project-check-q{index}-retry1'
    runner.STATE.update(question=question, sandbox_files=hashes(sandbox / 'demo'),
                        original_demo_sha256=hashes(DEMO), references_transmitted=False,
                        dependency={'binary': str(DEPENDENCY), 'sha256': hashlib.sha256(DEPENDENCY.read_bytes()).hexdigest(),
                                    'prepared_before_network_disabled': True,
                                    'offline_verification': 'project-check-ripgrep-offline.json'})
    os.environ['PATH'] = str(DEPENDENCY.parent) + ':' + os.environ['PATH']
    popen = subprocess.Popen

    def isolated_popen(command, *args, **kwargs):
        if command[:2] == ['opencode', 'run']:
            command = list(command)
            command[-1] = question
            command[command.index('--title') + 1] = runner.PREFIX
            runner.STATE['command'] = command
            runner.save()
            assert shutil.which('rg', path=kwargs['env']['PATH']) == str(DEPENDENCY)
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


def batch():
    path = RESULTS / 'project-check-retry-batch.json'
    state = {'status': 'running', 'question_indices': [2, 3], 'demo_sha256_before': hashes(DEMO),
             'old_results_sha256_before': {k: v for k, v in hashes(RESULTS).items()
                                           if '-retry' not in k}, 'runs': []}
    save(path, state, 'x')
    for index in (2, 3):
        print(f'Retry question {index}', flush=True)
        process = subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()), '--worker', str(index)])
        result_path = RESULTS / f'project-check-q{index}-retry1-verification.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        state['runs'].append({'question': index, 'worker_exit_code': process.returncode,
                              'sessionID': result.get('sessionID'), 'status': result.get('status'),
                              'answer': result.get('answer'), 'run_seconds': result.get('run_seconds')})
        save(path, state)
        if process.returncode:
            state['status'] = 'failed'
            break
    else:
        state['status'] = 'completed'
    state['demo_sha256_after'] = hashes(DEMO)
    state['demo_unchanged'] = state['demo_sha256_before'] == state['demo_sha256_after']
    after = hashes(RESULTS)
    state['old_results_unchanged'] = all(after.get(k) == v for k, v in state['old_results_sha256_before'].items())
    save(path, state)
    print(json.dumps(state['runs'], ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(int(sys.argv[2]))
    else:
        batch()
