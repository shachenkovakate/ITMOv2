# Фича A: unsubscribe

Прочитаны AGENTS.md, docs/requirements.md, test_service.py и evidence/README.md.
Skill notify-mini-check загружен реальным вызовом инструмента skill.

## Наблюдаемые результаты

1. Реальные MCP-вызовы: `" Ann "` → `Ann`; `"   "` → `empty name`.
2. До реализации добавлены шесть тестов: успешная отписка, неизвестное имя,
   повтор, пробелы вокруг имени, пустая строка/пробелы, сохранность других подписчиков.
3. После правки тестов hook автоматически вызвал `sh scripts/check.sh`.
   В ответе apply_patch агент получил `[notify-mini-check hook]`, код 1,
   `Ran 9 tests`, `FAILED (errors=7)` и AttributeError об отсутствии unsubscribe.
   Все три исходных теста subscribe прошли. Два subTest пустого имени дали две ошибки.
4. Реализован unsubscribe: strip, ValueError("empty name"), удаление существующего
   имени с True, неизвестное имя и повтор с False. Subscribe сохранён.
5. После правки service.py hook вернул в ответе apply_patch код 0, 9 тестов, OK.
6. Отдельно выполнена команда из загруженного skill:
   `python3 .opencode/skills/notify-mini-check/scripts/check.py`.
   Получен JSON: command `sh scripts/check.sh`, exit_code 0, ok true, 9 тестов, OK.

Краткие события и полный вывод отдельной проверки skill — в feature-a-events.json.
Эти записи отражают состоявшиеся вызовы текущей сессии.
Исходные evidence не перезаписывались; штатный hook дописывает hook-events.jsonl.
Фича B, контракт, runner, третья практика и reflection.md не изменялись.
Commit не выполнялся.
