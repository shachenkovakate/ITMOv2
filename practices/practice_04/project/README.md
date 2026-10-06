# Notify Mini — практика 4

Отдельная копия учебного сервиса из практики 3. Требования двух фич — docs/requirements.md. Фичи A (`unsubscribe`) и B (`list_subscribers`) реализованы и приняты; исходный `subscribe` сохранён. Все 14 тестов проходят.

Правила агента — `AGENTS.md`, стиль проекта — `docs/style-guide.md`.
Фича B реализована в отдельном worktree на ветке `practice_04_b` от коммита A.
Состояние проекта и материалы для сдачи — `docs/HANDOFF.md`.

Проверка из этого каталога: `sh scripts/check.sh`.

Рабочую сессию OpenCode запускать из этого каталога. `evidence/` содержит реальные действия агента, вызовы skill/MCP и результаты hook. В `evidence/hook-events.jsonl` запись 4 подтверждает FAIL до реализации A, запись 5 — PASS после неё; `feature-a-events.json` — краткое сопоставление, а не замена исходного журнала. Рефлексия студентки оформляется после работы по её сообщениям, не придумывается заранее.

Подтверждения B: `evidence/feature-b-red.md`, `evidence/feature-b-green.json`
и `evidence/feature-b-review.md`. Отдельный read-only review выполнен subagent
`explore`; обязательных исправлений не выявлено.
