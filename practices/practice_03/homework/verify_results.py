"""Verify recorded execution facts without running the model again."""
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

homework = Path(__file__).resolve().parent
repo = homework.parents[2]
results = homework / 'results'
state = json.loads((results / 'run-state.json').read_text())
manifest = json.loads((results / 'input-manifest.json').read_text())
speed = json.loads((results / 'speed.json').read_text())
comparison = json.loads((results / 'quality-comparison.json').read_text())
digest = lambda data: hashlib.sha256(data).hexdigest()

assert state['status'] in ['completed', 'completed_with_errors']
assert len(state['runs']) == 18
assert Counter(r['phase'] for r in state['runs']) == {'quality': 10, 'warmup': 2, 'timing': 6}
assert len({r['sessionID'] for r in state['runs']}) == 18
assert manifest['coverage_complete'] and len(manifest['reference_coverage']) == 12
assert not manifest['references_copied'] and not manifest['report_copied'] and not manifest['previous_answers_copied']
config_a = json.loads((results / 'resolved-config-a.json').read_text())
config_b = json.loads((results / 'resolved-config-b.json').read_text())
config_a['agent']['local-guide'].pop('prompt')
config_b['agent']['local-guide'].pop('prompt')
assert config_a == config_b
assert config_a['enabled_providers'] == ['ollama'] and not config_a['plugin'] and not config_a['mcp']
assert config_a['agent']['local-guide']['permission'] == {'*': 'deny', 'read': 'allow', 'glob': 'allow', 'grep': 'allow', 'external_directory': 'deny'}
assert config_a['agent']['local-guide']['steps'] == 8
assert config_a['provider']['ollama']['models']['itmo-agent']['limit'] == {'context': 65536, 'output': 4096}

initial_system_hashes = {'A': set(), 'B': set()}
events_count = 0
tool_errors = 0
for run in state['runs']:
    parameters = json.loads((results / (run['id'] + '-parameters.json')).read_text())
    assert parameters['status'] == run['status']
    assert parameters['input_sha256'] == state['inputs'] and parameters['input_unchanged']
    assert parameters['question'] == state['questions'][parameters['question_index'] - 1]
    assert '--continue' not in parameters['command'] and '--session' not in parameters['command']
    assert parameters['question_index'] == 1 if parameters['phase'] in ['warmup', 'timing'] else True
    assert '65536' in parameters['ollama_ps'] and '100% CPU' in parameters['ollama_ps']
    events = [json.loads(s) for s in (results / (run['id'] + '.jsonl')).read_text().splitlines()]
    assert all(e['type'] != 'reasoning' and e.get('part', {}).get('type') != 'reasoning' for e in events)
    assert all(e.get('part', {}).get('tokens', {}).get('reasoning', 0) == 0 for e in events)
    assert len(events) == parameters['events']
    events_count += len(events)
    tool_errors += len(parameters['tool_errors'])
    assert parameters['requests']
    first = parameters['requests'][0]
    assert first['initial_message_roles_expected'] and first['initial_question_present']
    initial_system_hashes[parameters['variant']].add(first['system_sha256'])
    for request in parameters['requests']:
        assert request['model'] == 'itmo-agent' and request['reasoning_effort'] == 'none'
        assert request['temperature'] == 0.2 and request['max_tokens'] == 4096
        assert request['configured_prompt_present'] and not set(request['tools']) - {'read', 'glob', 'grep', 'invalid'}
    stderr = (results / (run['id'] + '-stderr.log')).read_text()
    assert 'downloading ripgrep' not in stderr and 'ripgrep execution failed' not in stderr
    for tool in parameters['tool_calls']:
        inputs = tool['state']['input']
        target = inputs.get('filePath') or inputs.get('path')
        if target:
            path = Path(target) if Path(target).is_absolute() else Path(state['input_root']) / target
            assert path.resolve().is_relative_to(Path(state['input_root']))
    if parameters['status'] == 'error':
        assert (results / (run['id'] + '-error.json')).exists()

for variant in ['A', 'B']:
    measured = [r for r in state['runs'] if r['phase'] == 'timing' and r['variant'] == variant]
    assert len(measured) == 3
    assert speed['variants'][variant]['wall_seconds'] == [r['wall_seconds'] for r in measured]
    successful = [r['wall_seconds'] for r in measured if r['status'] == 'completed']
    expected_median = round(statistics.median(successful), 3) if len(successful) == 3 else None
    assert speed['variants'][variant]['median_seconds'] == expected_median
assert speed['unit'] == 'seconds' and speed['warmups_excluded']
assert len(comparison['records']) == 10
assert all(digest((repo / path).read_bytes()) == value for path, value in state['source_sha256_before'].items())
old_root = repo / 'practices/practice_03/lab/results'
old_hashes = {str(p.relative_to(old_root)): digest(p.read_bytes()) for p in old_root.rglob('*') if p.is_file()}
assert all(old_hashes.get(k) == v for k, v in state['old_results_sha256_before'].items())
assert all(digest((homework / name).read_bytes()) == value for name, value in state['accepted_plan_sha256'].items())
for item in manifest['inputs']:
    assert digest((homework / 'inputs' / item['path']).read_bytes()) == item['sha256']
    # Архив inputs/ является переносимым доказательством; /tmp не требуется.

verification = {'quality_sessions': 10, 'warmup_sessions': 2, 'timing_sessions': 6, 'unique_sessions': 18,
                'all_reference_citations_covered': True, 'only_prompt_differs_in_config': True,
                'initial_system_sha256_by_variant': {v: sorted(h) for v, h in initial_system_hashes.items()},
                'first_system_stable_within_each_variant': all(len(h) == 1 for h in initial_system_hashes.values()),
                'initial_history_contains_only_system_and_current_question': True,
                'actual_http_parameters_verified': True, 'all_runtime_contexts': 65536,
                'processor': '100% CPU', 'reasoning_text_events_saved': 0,
                'events_saved': events_count, 'tool_errors_saved': tool_errors,
                'ripgrep_downloads_observed': False, 'inputs_identical_and_unchanged': True,
                'source_materials_unchanged': True, 'previous_results_unchanged': True,
                'accepted_questions_references_prompts_unchanged': True,
                'median_seconds': {v: speed['variants'][v]['median_seconds'] for v in ['A', 'B']},
                'timing_note': 'Process success is not answer correctness: timing-a-q1-r1 did not answer the question; r2/r3 did.'}
if '--check' in sys.argv:
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    raise SystemExit(0)
with (results / 'verification.json').open('x') as output:
    json.dump(verification, output, ensure_ascii=False, indent=2)
    output.write('\n')
environment = {'versions': state['versions'], 'model': state['model'], 'ollama_show': state['ollama_show'],
               'hardware_source': '../../REPORT.md#окружение', 'runtime_placement': '100% CPU',
               'runtime_context': 65536, 'runtime_size': '8.7 GB', 'ripgrep_sha256': state['ripgrep_sha256']}
with (results / 'environment.json').open('x') as output:
    json.dump(environment, output, ensure_ascii=False, indent=2)
    output.write('\n')
print(json.dumps(verification, ensure_ascii=False, indent=2))
print('Model:', state['model']['name'], state['model']['digest'], state['model']['details'])
