# Проверка API установленного OpenCode

Фактически выполнены `opencode --version`, `opencode debug info` и чтение
`package.json` установленного пакета: версия **1.18.34**.
Исполняемый файл: `/home/kate/.npm-global/lib/node_modules/opencode-ai/bin/opencode.exe`.

Встроенный runtime исследован командой `strings` с фильтрацией Python.
Подтверждён вызов после выполнения встроенного инструмента:

```js
yield*i.trigger("tool.execute.after",{tool:k.id,sessionID:H.sessionID,callID:H.callID,args:b},V)
```

`V` — результат инструмента с полями `title`, `metadata`, `output` и возможными
`attachments`. Поэтому plugin изменяет **`output.output`** на месте,
а не возвращает строку как результат callback.

Также подтверждена фильтрация инструментов по модели:

```js
let F=D.modelID.includes("gpt-")&&!D.modelID.includes("oss")&&!D.modelID.includes("gpt-4");
if(A.id===xr.id)return F;
if(A.id===Hr.id||A.id===vr.id)return!F;
```

Здесь `xr` — apply_patch, `Hr` — edit, `vr` — write. Для GPT-сессии используются
реальные вызовы apply_patch, для проверки write/edit — отдельная сессия с моделью,
для которой runtime предоставляет эти инструменты.

Plugin `.opencode/plugins/notify-mini-check.js` обнаруживается новым процессом
автоматически. Его фактическое применение подтверждается ответом инструмента
в `opencode-tool-events-retry.json` и журналом `hook-events.jsonl`.
