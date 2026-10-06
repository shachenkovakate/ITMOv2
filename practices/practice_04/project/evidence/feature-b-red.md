# Фича B: проверка до реализации

Ветка: practice_04_b, отдельный worktree ITMOv2-p4-b.
Начальное рабочее дерево было чистым. Прочитаны AGENTS.md,
docs/requirements.md, docs/style-guide.md, service.py и test_service.py.
Skill notify-mini-check загружен фактическим вызовом functions.skill.

Сначала через apply_patch добавлен ListSubscribersTest с пятью тестами:
пустое хранилище, порядок строк Python (регистр и кириллица), повторная
подписка с нормализацией пробелов, независимость нового списка, совместный
сценарий subscribe/unsubscribe с неизвестным именем и опустошением хранилища.
На момент проверки list_subscribers в service.py отсутствовала.

## Фактический результат автоматического hook после правки тестов

Событие: tool.execute.after; инструмент: apply_patch.
Команда: sh scripts/check.sh; exit_code: 1; signal: null; stdout: пустой.

```text
test_duplicate (test_service.ListSubscribersTest.test_duplicate) ... ERROR
test_empty (test_service.ListSubscribersTest.test_empty) ... ERROR
test_independent_list (test_service.ListSubscribersTest.test_independent_list) ... ERROR
test_sorted (test_service.ListSubscribersTest.test_sorted) ... ERROR
test_subscribe_and_unsubscribe (test_service.ListSubscribersTest.test_subscribe_and_unsubscribe) ... ERROR
test_duplicate (test_service.SubscribeTest.test_duplicate) ... ok
test_empty (test_service.SubscribeTest.test_empty) ... ok
test_subscribe (test_service.SubscribeTest.test_subscribe) ... ok
test_empty (test_service.UnsubscribeTest.test_empty) ... ok
test_preserves_other_subscribers (test_service.UnsubscribeTest.test_preserves_other_subscribers) ... ok
test_repeat (test_service.UnsubscribeTest.test_repeat) ... ok
test_surrounding_spaces (test_service.UnsubscribeTest.test_surrounding_spaces) ... ok
test_unknown (test_service.UnsubscribeTest.test_unknown) ... ok
test_unsubscribe (test_service.UnsubscribeTest.test_unsubscribe) ... ok

Ran 14 tests in 0.002s
FAILED (errors=5)
```

Каждая из пяти ошибок — AttributeError:
`module 'service' has no attribute 'list_subscribers'`.
Полные traceback выданы в ответе apply_patch и автоматически дописаны hook
в evidence/hook-events.jsonl. Старые записи не заменены.
