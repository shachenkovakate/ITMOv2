# Notify Mini: передача результата практики 4

## Состояние проекта

Фичи A и B реализованы и приняты. Исходный subscribe сохранён.
Сервис использует стандартную библиотеку Python; подписчики хранятся
в существующем множестве subscribers в памяти. Всего 14 unittest-тестов:
3 для subscribe, 6 для unsubscribe и 5 для list_subscribers.

A сохранена в коммите d6baa5f на practice_04. B реализована в отдельном
worktree ITMOv2-p4-b на practice_04_b от этого коммита.
Следующий этап передачи: коммит B и fast-forward объединение в practice_04
с повторной проверкой объединённого проекта. Этот документ не выдаёт
планируемые операции Git за уже выполненные; их результат будет показан
в ответе агента и доступен в git log.

## Требования

Источник контракта — requirements.md; правила стиля — style-guide.md.

- subscribe(name): strip, добавление в множество, ответ {"subscribed": True};
  повтор не создаёт дубликат, пустое имя вызывает ValueError("empty name").
- unsubscribe(name): strip, удаление существующего имени с ответом
  {"unsubscribed": True}; неизвестное имя и повтор дают
  {"unsubscribed": False}; пустое имя вызывает ValueError("empty name").
- list_subscribers(): новый список в стандартном порядке строк Python;
  пустое хранилище даёт []; изменение списка не меняет хранилище;
  результат отражает текущее состояние после подписки и отписки.

Контракт и runner не изменены. Практика 3 и reflection.md не изменены.

## Проверка

Из каталога practices/practice_04/project:

```sh
sh scripts/check.sh
```

Отдельный запуск skill notify-mini-check:

```sh
python3 .opencode/skills/notify-mini-check/scripts/check.py
```

Ожидаемый успешный результат: 14 тестов, OK, exit code 0.
Skill дополнительно выводит JSON с exit_code: 0 и ok: true.

## Подтверждения реальных событий

- A: evidence/feature-a.md и evidence/feature-a-events.json.
  В исходном evidence/hook-events.jsonl записи 4 и 5 подтверждают
  ожидаемое падение до A и успешные 9 тестов после реализации.
- B: evidence/feature-b-red.md — сначала добавлены пять тестов;
  автоматический hook вернул exit code 1, 14 тестов и пять AttributeError
  из-за отсутствующей list_subscribers. Исходные девять тестов прошли.
- B: evidence/feature-b-green.json — успешный автоматический hook после
  реализации и отдельный фактический запуск команды загруженного skill:
  exit code 0, 14 тестов, OK. Загрузка skill подтверждена вызовом functions.skill
  в сессии B; запуск — вызовом functions.bash и сохранённым JSON результата.
- Hook: .opencode/plugins/notify-mini-check.js запускает runner после правок
  через write/edit/apply_patch. Реальные результаты возвращены агенту
  с меткой [notify-mini-check hook] и дописаны в evidence/hook-events.jsonl.
  Старые подтверждения не заменены.
- MCP: evidence/mcp-protocol-calls.json содержит реальные initialize,
  tools/list и tools/call локального notify-mini-name через stdio.
  " Ann " возвращает Ann; пробелы и пустая строка — empty name;
  нестроковые значения — name must be a string. evidence/feature-a.md
  также фиксирует вызовы MCP в сессии A. Для B новых MCP-вызовов не было;
  подтверждение относится к ранее выполненным вызовам, а не наличию конфигурации.

## Отдельный review

После реализации B вызван read-only subagent explore через functions.task.
Task ID: ses_eed9e6f5affeg442mnbnI8b04H, завершён успешно.
Отчёт — evidence/feature-b-review.md. Все пять критериев B соблюдены,
subscribe и A сохранены, scope проверен. Обязательных исправлений
и существенных необязательных замечаний нет. Reviewer файлы не менял
и оценивал тесты по сохранённым результатам, без нового запуска.

## Что осталось для сдачи

- Сохранить коммит B и выполнить только fast-forward merge в practice_04;
  повторно проверить 14 тестов в исходном репозитории (операции текущей передачи).
- Студентке самостоятельно заполнить reflection.md по реальному опыту работы.
- Передать материалы практики по правилам курса; push — только после отдельного
  поручения. Worktree сохраняется.
