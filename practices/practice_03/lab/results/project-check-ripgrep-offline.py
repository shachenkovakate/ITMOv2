"""Verify the very Ripgrep.glob/grep backend used by OpenCode's leaf tools."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

results = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix='ripgrep-offline-', dir='/tmp/opencode'))
demo = root / 'demo'
shutil.copytree(results.parent / 'demo', demo, ignore=shutil.ignore_patterns('__pycache__'))
for name in ['home', 'config', 'data', 'cache', 'state']:
    (root / name).mkdir()
config = json.loads((results / 'read-check-2-config.json').read_text())
config['provider']['ollama']['options']['baseURL'] = 'http://127.0.0.1:11434/v1'
config['agent']['local-guide']['prompt'] = (demo / 'repo-system.txt').read_text()
config_path = root / 'opencode.json'
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
env = {'PATH': '/tmp/opencode/ripgrep-dependency:' + os.environ['PATH'],
       'LANG': 'C.UTF-8', 'HOME': str(root / 'home'),
       **{f'XDG_{name.upper()}_HOME': str(root / name) for name in ['config', 'data', 'cache', 'state']},
       'OPENCODE_CONFIG': str(config_path), 'OPENCODE_DISABLE_PROJECT_CONFIG': '1',
       'OPENCODE_PURE': '1', 'OPENCODE_DISABLE_DEFAULT_PLUGINS': '1',
       'OPENCODE_DISABLE_AUTOUPDATE': '1', 'OPENCODE_DISABLE_MODELS_FETCH': '1',
       'OPENCODE_DISABLE_LSP_DOWNLOAD': '1', 'OPENCODE_DISABLE_CLAUDE_CODE': '1',
       'OPENCODE_DISABLE_EXTERNAL_SKILLS': '1', 'npm_config_offline': 'true',
       'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
       'ALL_PROXY': 'http://127.0.0.1:9', 'NO_PROXY': 'localhost,127.0.0.1,::1'}
env.update({k.lower(): v for k, v in list(env.items()) if k.endswith('_PROXY')})
record = {'environment': env, 'cwd': str(demo), 'binary': shutil.which('rg', path=env['PATH']),
          'backend': 'OpenCode 1.18.34 Ripgrep.glob and Ripgrep.grep (shared with glob/grep tools)',
          'source': 'https://raw.githubusercontent.com/anomalyco/opencode/v1.18.34/packages/opencode/src/cli/cmd/debug/ripgrep.ts',
          'checks': []}
for tool, arguments in [('glob', ['files', '--glob', '*.py']), ('grep', ['search', 'subscribers', '--glob', '*.py'])]:
    command = ['opencode', 'debug', 'rg', *arguments, '--pure', '--print-logs']
    result = subprocess.run(command, cwd=demo, env=env, capture_output=True, text=True, timeout=120)
    record['checks'].append({'backend_method': tool, 'command': command, 'exit_code': result.returncode,
                             'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode:
        break
record['success'] = len(record['checks']) == 2 and all(c['exit_code'] == 0 for c in record['checks'])
record['external_downloads_observed'] = any('downloading ripgrep' in c['stderr'] for c in record['checks'])
if record['success']:
    record['glob_expected_files_found'] = set(record['checks'][0]['stdout'].splitlines()) == {'service.py', 'test_service.py'}
    rows = json.loads(record['checks'][1]['stdout'])
    record['grep_expected_line_found'] = any(r['entry']['path'] == 'service.py' and r['line'] == 1 and r['text'].strip() == 'subscribers = set()' for r in rows)
    record['success'] = record['glob_expected_files_found'] and record['grep_expected_line_found'] and not record['external_downloads_observed']
with (results / 'project-check-ripgrep-offline.json').open('x') as output:
    json.dump(record, output, ensure_ascii=False, indent=2)
    output.write('\n')
print(json.dumps({k: record[k] for k in ['success', 'binary', 'checks', 'external_downloads_observed']}, ensure_ascii=False, indent=2))
raise SystemExit(0 if record['success'] else 1)
