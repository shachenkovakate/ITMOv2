# Воспроизведение домашнего эксперимента

Проверка уже сохранённых результатов без генерации и без зависимости от временного worktree:

```bash
python3 practices/practice_03/homework/verify_results.py --check
make test
```

Для нового запуска нужны Python 3.10+, curl, tar, Ollama 0.34.4, OpenCode 1.18.34 и скачанные веса. Из корня репозитория (bash; в Fish команды окружения выполнить через `bash`):

```bash
ollama list
ollama create itmo-agent -f practices/practice_03/lab/Modelfile.agent
mkdir -p /tmp/opencode/ripgrep-dependency
curl --fail --location https://github.com/BurntSushi/ripgrep/releases/download/15.1.0/ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz -o /tmp/opencode/ripgrep.tar.gz
printf '%s\n' '1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599  /tmp/opencode/ripgrep.tar.gz' | sha256sum --check
tar -xzf /tmp/opencode/ripgrep.tar.gz --strip-components=1 -C /tmp/opencode/ripgrep-dependency ripgrep-15.1.0-x86_64-unknown-linux-musl/rg
export ITMO_RIPGREP=/tmp/opencode/ripgrep-dependency/rg
export ITMO_RESULTS_DIR="$(mktemp -d /tmp/itmo-homework-results-XXXXXX)"
```

Тег в реестре может обновиться. Для точного повторения сравнить `ollama list`/`ollama show` с digest в `results/environment.json`; команда pull не гарантирует прежние веса. Старые результаты сохраняются, новая серия пишется в отдельный `ITMO_RESULTS_DIR`.

Запуск новой серии:

```bash
python3 practices/practice_03/homework/run_experiment.py --prepare-only
python3 -u practices/practice_03/homework/run_experiment.py
```

Первый этап проверяет покрытие всех ссылок из `REFERENCES.md` тремя входными фрагментами, сохраняет их хеши и создаёт отдельный тестовый worktree. Генерации модели на этом этапе нет. Второй этап проверяет, что загруженные конфигурации отличаются только prompt, и выполняет:

1. 10 независимых качественных запусков, в порядке A1, B1, A2, B2 … A5, B5.
2. Два отдельных прогрева вопросом №1 — для A и B; они исключаются из замеров.
3. Шесть независимых измерений вопроса №1: A1, B1, A2, B2, A3, B3.

Все вопросы берутся дословно из `QUESTIONS.md`. Лимиты одинаковы: 4096 выходных токенов, 8 шагов агента, 600 секунд на запуск; timeout локального наблюдающего прокси — 295 секунд ожидания. Прокси не меняет тело запроса и подтверждает `reasoning_effort="none"`, temperature=0.2, модель и лимит ответа. Подключения только локальные; плагины и MCP отключены.

Подготовленная зависимость: `/tmp/opencode/ripgrep-dependency/rg`. Источник и SHA-256 записаны в `../lab/results/project-check-ripgrep-setup.json`; offline-проверка — в `project-check-ripgrep-offline.json` того же каталога. Runner добавляет этот каталог в PATH перед отключением внешних подключений.

`results/quality-{a,b}-q{1..5}.jsonl` содержит фактические ответы и CLI-события, сохраняемые построчно с flush/fsync; события reasoning исключаются. `*-parameters.json` хранит тексты ответа, инструментальные результаты, время и параметры; `*-http.jsonl` — наблюдения фактических запросов без содержимого сообщений. Ошибки процесса/API сохраняются в `*-error.json`, ошибки инструментов — в CLI-событиях и `tool_errors`. Ошибочные ответы не заменяются эталонами.

`results/speed.json` содержит по три времени и медиану в секундах. Метрика — `time.perf_counter()` от запуска процесса OpenCode до его завершения: это время всей агентной задачи, включая чтение и генерацию, а не скорость модели в токенах/с. Медиана вычисляется для трёх завершившихся без ошибки процесса сессий; это не означает три правильных ответа. Качество проверяется отдельно.

`results/input-manifest.json` подтверждает полноту входов. `results/resolved-config-{a,b}.json` — реальные загруженные конфигурации. `results/run-state.json` хранит независимые sessionID, ход серии и проверку неизменности исходников, прежних результатов и согласованных вопросов/prompt.

`analyze_results.py` сохраняет фактическое сопоставление рабочего агента с эталонами в `results/quality-comparison.json` и архивирует ровно три входных фрагмента в `inputs/`. Это аудит сохранённых основных ответов, без повторного запуска модели; решения об ошибках основаны на проверенных строках исходников. `verify_results.py` проверяет все 18 записей, независимость сессий, HTTP-параметры, медианы, отсутствие reasoning-событий и неизменность исходных данных; итог — `results/verification.json` и `results/environment.json`.

Runner отказывается перезаписывать существующую серию. Эталоны, отчёт, прежние ответы и этот документ не входят в тестовый worktree. Оценка студентки и окончательный выбор конфигурации в рамках этого запуска не записываются.

Новая серия требует отдельной проверки качества по REFERENCES.md. Скрипты analyze_results.py и verify_results.py проверяют исходную сохранённую серию; они не оценивают автоматически другие ответы. Старые эталоны содержат пометку о состоянии до эксперимента — итог и выбор студентки находятся в REPORT.md.
