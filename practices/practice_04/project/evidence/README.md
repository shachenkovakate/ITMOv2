# Notify Mini — подготовка среды

## Фактические результаты

- Прочитаны `AGENTS.md`, `docs/requirements.md`, `test_service.py`.
- Выполнен `sh scripts/check.sh`: код 0, три теста, `OK`.
- Установленный OpenCode: **1.18.34**.
- В новом процессе инструмент `skill` успешно загрузил `notify-mini-check`,
  затем инструмент `bash` выполнил скрипт skill. JSON содержит код 0 и вывод тестов.
- Подключён локальный MCP `notify-mini-name`. Реальные вызовы через OpenCode:
  `{"name":" Ann "}` → `Ann`; `{"name":"   "}` → ошибка `empty name`.
- Дополнительные stdio MCP-вызовы подтвердили ошибки для `""`, `42`, `null`, `[]`.
- После **каждого** из реальных инструментов `apply_patch`, `write`, `edit`
  автоматически выполнен `sh scripts/check.sh`, код 0. Вывод включён в ответ
  инструмента агенту, а не только в отдельный лог.

## Назначение компонентов

**Skill** — инструкция для повторяемой проверки по запросу. Скрипт skill оборачивает
канонический runner и возвращает `command`, `exit_code`, `stdout`, `stderr`, `ok`.

**MCP** — отдельный локальный процесс, предоставляющий агенту инструмент проверки
имени по JSON-RPC/stdio. Он обрезает края строки и сообщает ошибки входа через
`isError: true`; состояние приложения не используется.

**Hook** — автоматическая проверка после успешной правки через инструменты
`write`, `edit`, `apply_patch`. Использует `tool.execute.after` OpenCode 1.18.34,
изменяет `output.output` и сохраняет результат в `hook-events.jsonl`.

## Где находятся подтверждения

| Файл | Содержание |
| --- | --- |
| `baseline-check.json` | Реальный запуск исходного runner |
| `skill-discovery.json` | Обнаружение проектного skill новым процессом |
| `opencode-tool-events-retry.json` | Успешная загрузка skill, запуск скрипта, MCP-вызовы, apply_patch с выводом hook |
| `opencode-write-edit-events.json` | Реальные write/edit с результатом hook в ответах |
| `hook-events.jsonl` | Три автоматических запуска runner |
| `mcp-connection.json` | `opencode mcp list`: connected |
| `mcp-protocol-calls.json` | Запросы и ответы stdio MCP, включая неверные типы |
| `opencode-api.md` | Проверка API установленного runtime |
| `errors.json` | Отсутствие rg, бинарный Read и skill в старой сессии |
| `model-error.json` | Ошибка HTTP 400 для неподдерживаемой модели |
| `opencode-tool-events.json` | Первоначальные ошибки разрешений apply_patch |

Первоначальная проверка правок была отклонена, поскольку OpenCode сопоставляет
разрешения apply_patch с путями относительно git worktree. В повторном запуске
разрешён путь `practices/practice_04/project/evidence/*`, после чего hook сработал.
Это разрешение задано только через окружение проверочного процесса.

OpenCode выбирает apply_patch для GPT-моделей, write/edit — для остальных.
Поэтому все три ветки проверены двумя свежими процессами.

## Повторение

```sh
python3 .opencode/skills/notify-mini-check/scripts/check.py
python3 evidence/verify_mcp.py
python3 evidence/verify_environment.py
python3 evidence/verify_environment.py opencode/big-pickle
```

Проверочные сессии используют настроенного провайдера OpenCode; ключи не
копируются в проект. Сохраняются только события инструментов и очищенные ошибки,
без внутренних рассуждений и HTTP-заголовков.

## Ограничения и состояние

Контракт — `docs/requirements.md`; runner — `sh scripts/check.sh`.
Python-компоненты используют стандартную библиотеку. Подписчики остаются в памяти.
Перед будущими фичами обязателен цикл «тест → ожидаемое падение → реализация → успех»;
перед B нужно прочитать style guide и работать в отдельном worktree после коммита A.

Подготовлены только среда и подтверждения. `service.py`, `test_service.py`, контракт,
runner и третья практика не изменялись; commit не выполнялся, `reflection.md`
не заполнялся. OpenCode автоматически создал локальные служебные зависимости
в `.opencode/`; framework приложения не добавлялся.

Текущую интерактивную сессию нужно закрыть и запустить OpenCode заново из проекта,
чтобы она загрузила skill, MCP и plugin. Свежие проверочные процессы уже применили их.
