"""Factual audit of the ten quality runs, performed outside model environments."""
import hashlib
import json
from collections import Counter
from pathlib import Path

HOMEWORK = Path(__file__).resolve().parent
RESULTS = HOMEWORK / 'results'
manifest = json.loads((RESULTS / 'input-manifest.json').read_text())
root = Path(manifest['root'])

# Decisions below are the working agent's source audit, not the student's grade.
AUDIT = {
    ('A', 1): ('not_answered', 'missing', [
        'Вместо ответа — обещание изучить diff. Нет вызовов инструментов и фактов об обработке запроса.']),
    ('B', 1): ('correct', 'supported', [
        'После ошибочного пути read модель нашла и прочитала diff. Строки 35–38, 20 и 22 относятся к правильному файлу и подтверждают ответ.']),
    ('A', 2): ('partial', 'missing', [
        'Верно названо отсутствие проверки в учебном коде, но HTTP 413 не указан; инструменты не вызывались.']),
    ('B', 2): ('correct', 'wrong_file_attribution', [
        'Требование и реализация разделены правильно; context.md:22 подтверждает HTTP 413.',
        'app/api.py:35–37 — неверная атрибуция: это физические строки TRAINING_PR.diff, а самостоятельного app/api.py во входах нет.']),
    ('A', 3): ('incorrect', 'missing', [
        'Выдуман лимит 50 итераций вместо 6; условия остановки не соответствуют experiment.md:8.',
        'Утверждение о разрешении только чтения также не отражает разрешённые правки Markdown. Инструменты не вызывались.']),
    ('B', 3): ('incorrect', 'fabricated', [
        'Нет вызовов инструментов, несмотря на заявление «Я проверил файл».',
        'Цитаты про ReAct в TRAINING_PR.diff:1–6 выдуманы: там заголовки diff и импорт Protocol.',
        'Изменять код запрещено, лимит — 6, а не 10; остановка задана experiment.md:8.']),
    ('A', 4): ('correct', 'missing_line_numbers', [
        'После grep и чтения diff модель верно признаёт отсутствие конкретных провайдера и модели. Номера строк в ответе отсутствуют.']),
    ('B', 4): ('correct', 'partial_tool_coverage', [
        'Конкретные провайдер и модель не выдуманы; ссылки на diff:15 и context.md:11–13 существуют.',
        'Вызваны glob и grep, не read: получены только diff:15 и context.md:11,13. Явная неизвестность в context.md:53 и полный diff не прочитаны; доказательство об отсутствии данных неполное.']),
    ('A', 5): ('not_answered', 'insufficient_search', [
        'Два grep дали 0 совпадений, затем модель только обещала прочитать diff. Ложная предпосылка не опровергнута.']),
    ('B', 5): ('correct', 'wrong_line_numbers', [
        'Реализация редактирования секретов верно отрицается; не названа выдуманная функция.',
        'Указанные TRAINING_PR.diff:13–16 не показывают формирование prompt и вызов LLM: правильные строки — 19–22.',
        'Вызван только grep, полный diff не прочитан; SEC-1 расположен в context.md:21, а не в коде diff.']),
}
EXPECTED = {
    1: {'answer': 'payload["diff"] → review → prompt с diff → llm.generate → {"comment": answer}',
        'citations': ['practices/practice_01/TRAINING_PR.diff:35–37', 'practices/practice_01/TRAINING_PR.diff:19–22']},
    2: {'answer': 'Требование — HTTP 413 при длине более 20 000; показанная реализация проверки не содержит',
        'citations': ['practices/practice_01/context.md:22,29', 'practices/practice_01/TRAINING_PR.diff:35–37,19–22']},
    3: {'answer': 'Код и внешние источники запрещены; 6 действий; одно подтверждённое исправление и проверки; при противоречиях/новом правиле — вопрос человеку',
        'citations': ['practices/practice_02/react/experiment.md:5–8']},
    4: {'answer': 'Конкретный провайдер и модель сервисного LLM неизвестны',
        'citations': ['practices/practice_01/context.md:51–53', 'practices/practice_01/TRAINING_PR.diff:9–22']},
    5: {'answer': 'Ложная предпосылка: удаление секретов в показанном коде не реализовано; SEC-1 — требование',
        'citations': ['practices/practice_01/TRAINING_PR.diff:19–22', 'practices/practice_01/context.md:21,29']},
}
records = []
for question_index in range(1, 6):
    for variant in ['A', 'B']:
        run_id = f'quality-{variant.lower()}-q{question_index}'
        parameters = json.loads((RESULTS / (run_id + '-parameters.json')).read_text())
        events = [json.loads(s) for s in (RESULTS / (run_id + '.jsonl')).read_text().splitlines()]
        assert parameters['phase'] == 'quality' and parameters['input_sha256'] == manifest['identical_input_sha256']
        assert all(e.get('type') != 'reasoning' and e.get('part', {}).get('type') != 'reasoning' for e in events)
        assert parameters['input_unchanged']
        requests = parameters['requests']
        assert requests and all(r['model'] == 'itmo-agent' and r['temperature'] == 0.2
                                and r['reasoning_effort'] == 'none' and r['max_tokens'] == 4096 for r in requests)
        assert requests[0]['initial_message_roles_expected'] and requests[0]['initial_question_present']
        correctness, citations, issues = AUDIT[(variant, question_index)]
        if parameters['status'] != 'completed':
            correctness, citations, issues = 'execution_error', 'not_assessed', [parameters.get('error')]
        texts = [e['part']['text'] for e in events if e['type'] == 'text']
        calls = [e['part'] for e in events if e['type'] == 'tool_use']
        successful = [c for c in calls if c['state']['status'] == 'completed']
        assert texts[-1] == parameters['final_answer'] if texts else parameters['final_answer'] is None
        records.append({'question': question_index, 'variant': variant, 'question_text': parameters['question'],
                        'result': run_id + '.jsonl', 'parameters': run_id + '-parameters.json',
                        'sessionID': parameters.get('sessionID'), 'wall_seconds': parameters['wall_seconds'],
                        'status': parameters['status'], 'final_answer': parameters['final_answer'],
                        'all_assistant_text': texts, 'expected': EXPECTED[question_index],
                        'semantic_correctness': correctness, 'citation_audit': citations, 'issues': issues,
                        'successful_tool_counts': dict(Counter(c['tool'] for c in successful)),
                        'tool_calls': [{'tool': c['tool'], 'status': c['state']['status'], 'input': c['state']['input'],
                                        'error': c['state'].get('error')} for c in calls],
                        'tool_errors': len(parameters['tool_errors'])})
assert len({r['sessionID'] for r in records}) == 10
comparison = {'source': 'working-agent factual audit against REFERENCES.md; no student assessment or final choice',
              'runs_assessed': 'the ten original quality runs only; warmup/timing answers do not replace them',
              'records': records}
with (RESULTS / 'quality-comparison.json').open('x') as output:
    json.dump(comparison, output, ensure_ascii=False, indent=2)
    output.write('\n')

archive = []
for item in manifest['inputs']:
    data = (root / item['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['sha256']
    target = HOMEWORK / 'inputs' / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        output.write(data)
    archive.append({'path': str(target.relative_to(HOMEWORK)), 'sha256': item['sha256']})
with (RESULTS / 'input-archive.json').open('x') as output:
    json.dump(archive, output, ensure_ascii=False, indent=2)
    output.write('\n')
print(json.dumps([{'question': r['question'], 'variant': r['variant'], 'semantic_correctness': r['semantic_correctness'],
                   'citation_audit': r['citation_audit'], 'successful_tools': r['successful_tool_counts'],
                   'tool_errors': r['tool_errors']} for r in records], ensure_ascii=False, indent=2))
