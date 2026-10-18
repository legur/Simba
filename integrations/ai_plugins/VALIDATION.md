# Проверка интеграции · 15.10.2026

## Выполнено

- Исходная проверка Python unit-tests 15.10.2026: 14 PASS. Draft dry-run не вызывает сеть; запрет schedule/publish;
  проверка approval/visual status; валидация ID; отсутствие credentials; обработка
  сканера; отключение redirects; извлечение таблиц и source hash.
- Установка в отдельный venv: xberg 1.3.9, ru-humanizer 3.31.4 успешна.
- Реальный Xberg, учебный HTML: извлечена таблица Standard / 1259 EUR, ячейки и
  Markdown совпали с исходником; EXTRACTED_UNVERIFIED и SHA-256 присутствуют.
- Реальный ru-humanizer: учебный before/after с удалением вводной и слова «данный»;
  score 64 → 100; facts.kept=4, lost=[], added=[]; semantic_verified=false.
  Это проверка CLI/JSON-контракта, не оценка качества на постах Leo.
- BulkPublish dry-run: сформированы channelId/mediaFiles/status=draft по OpenAPI;
  сетевой запрос не выполнялся. Doctor сообщает отсутствие credentials.
- Runtime links: AGENTS, Router, META, core, Humanizer и pipeline ссылаются на
  существующий AI_PLUGIN_TOOLS.md. Изменены существующие канонические пути.

## Повторная офлайн-проверка · 18.10.2026

- Python 3.14.3: 17/17 unit-tests PASS. Добавлены регрессии для структурированного
  `BLOCKED` при JSON package с корнем не-объектом и для отклонения каталогов в
  аргументах `scan file` / `--before` до запуска внешнего сканера.
- Полный набор выполнен вне ограниченного sandbox, потому что в sandbox даже
  минимальный `asyncio.run(asyncio.sleep(0))` блокируется при создании локального
  Windows socketpair. В тестах Xberg, scanner и BulkPublish остаются подменёнными;
  внешняя сеть и платные сервисы не вызывались.
- Тестовые временные файлы создавались внутри `integrations/ai_plugins`, чтобы не
  зависеть от запрещённой для записи sandbox Temp. После тестов временные каталоги
  удалены.
- Текущий `doctor`: `xberg` и `ru-humanizer` — `NOT_INSTALLED`, scanner executable —
  `false`, BulkPublish credentials — `false`, publication supported — `false`.

## KB-LINT

L01 SOURCE: PASS — явное решение Leo + первичные upstream-контракты.
L02 EVIDENCE: PASS — scope ограничен тремя выбранными интеграциями.
L03 PERSISTENT/DYNAMIC: PASS — учебная цена только в синтетическом тесте, не правило.
L04 TARGET: PASS — технический код, workflow и Decision Log в соответствующих слоях.
L05 CONFLICT: PASS — канонический Humanizer выше внешнего сканера; approval/Rafael/
Internal Critic сохранены; новые авторы не добавлены.
L06 SCOPE: PASS — нет publish/schedule/CMS-записи, нет обещания подключения аккаунта.
L07 REFERENCES: N/A — visual-reference библиотеки не изменялись.
L08 VERSION: PASS — пути сохранены, версии и changelog обновлены на месте.
L09 CONTENT LIBRARY: N/A — контентные записи не создавались.

## Осталось для production-подтверждения

- Реальный прайс поставщика и OCR со сверкой всех коммерческих полей.
- Три реальных готовых поста разных типов с редакторской оценкой.
- Аккаунт/канал и ключ BulkPublish; удалённый draft и read-back. Загрузка медиа
  выполняется через кабинет/отдельный инструмент, не этим bridge.
- Установка зависимостей в каждой среде, которая исполняет Simba: текущий venv
  является проверочной средой сессии и не развёртыванием на машине Leo.
