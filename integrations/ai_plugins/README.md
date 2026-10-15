# Внешние инструменты Simba

Версия: 1.0 · 15.10.2026

Адаптеры Xberg, BulkPublish и humanizer-ru. Это технические инструменты существующих
исполнителей, не новые авторы и не замена Router/Simba/Rafael/Critic.
Обязательный контракт: `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/AI_PLUGIN_TOOLS.md`.

## Установка в исполнительной среде

Python 3.10+. Из корня репозитория:

```bash
python3 -m venv .venv-ai-plugins
source .venv-ai-plugins/bin/activate
python -m pip install -r integrations/ai_plugins/requirements.txt
python integrations/ai_plugins/bridge.py doctor
```

На Windows активация: `.venv-ai-plugins\Scripts\Activate.ps1`.
Не коммитить виртуальную среду, ключи и клиентские документы.
Xberg и ru-humanizer устанавливаются отдельно от инструкций Simba. Наличие этого
каталога в GitHub не означает, что зависимости установлены в каждом чате.
Версии закреплены по upstream на дату интеграции; обновление после smoke-теста.

## Xberg: извлечение документов

```bash
python integrations/ai_plugins/bridge.py extract /absolute/path/price.pdf > extracted.json
python integrations/ai_plugins/bridge.py extract /absolute/path/scan.pdf --ocr-language rus+eng > extracted.json
```

Передавать только локальный файл. Для OCR нужны Tesseract и соответствующие языковые
данные. Результат включает SHA-256 исходника, текст и таблицы, статус
`EXTRACTED_UNVERIFIED`. Сверить цены/даты/валюту/единицу тарифа/номера/пакеты с оригиналом.
Адаптер не сопоставляет номера с Wix и ничего не записывает в CMS.
Вывод перенаправления может быть пустым при ошибке: проверять exit code и статус JSON.

## humanizer-ru: сканер, не автоматическое переписывание

```bash
python integrations/ai_plugins/bridge.py scan /absolute/path/post.txt
python integrations/ai_plugins/bridge.py scan /absolute/path/final.txt --before /absolute/path/original.txt --genre news
```

JSON содержит `scanner_exit_code`: 0, 1 (найдены запреты), 2 (сигнал факт-замка).
Это код сканера; сам bridge при валидном отчёте возвращает 0 даже при находках.
Любой ненулевой код сканера требует просмотра, не означает автоматический запрет
публикации. Системный Humanizer и правила Leo определяют правку. При недоступности
сканера ручная проверка обязательна, балл не придумывать.

## BulkPublish: только черновики

Ключ `BULKPUBLISH_API_KEY` задаётся через секреты исполнительной среды. Адаптер не
читает `.env` автоматически. Не вставлять ключ в чат, JSON или GitHub-файлы.

```bash
python integrations/ai_plugins/bridge.py channels
python integrations/ai_plugins/bridge.py draft integrations/ai_plugins/example-package.json
python integrations/ai_plugins/bridge.py draft /absolute/path/approved-package.json --send
```

Второй вызов является локальным dry-run. Example содержит вымышленные channel ID и
учебный статус APPROVED_TEXT, не доказывающий реальное утверждение Leo. Не отправлять
его как production-материал. Рабочий package готовит PROCESS_OWNER после реального
утверждения; ID канала брать из `channels`, content сохранять дословно. `mediaFiles`
содержит ID уже загруженных в BulkPublish финальных изображений/видео; загрузка медиа
в этой версии адаптера не реализована. Для медиа нужен `visualStatus=FINAL_VISUAL_READY`.
Все package-поля являются утверждениями вызывающего процесса, а не проверяемой
подписью Leo; агент обязан проверить историю утверждения перед `--send`.

`--send` создаёт удалённый draft, не расписание и не публикацию. Адаптер не имеет
команд publish/schedule. После сетевого сбоя не повторять POST автоматически:
проверить кабинет, чтобы не получить дубль. `DRAFT_CREATED` не равен `PUBLISHED`.

## Проверки

```bash
python -m unittest discover -s integrations/ai_plugins -p 'test_*.py' -v
```

Offline-тесты используют подмены внешних зависимостей. Они не подтверждают доступ
к аккаунту, реальное OCR или качество сканера. Smoke: один реальный прайс с ручной
сверкой, три готовых текста с before/after, один удалённый draft в выбранном канале.
Не считать smoke выполненным до фактического запуска и read-back результата.

## Первичные контракты

- https://github.com/xberg-io/xberg/blob/main/packages/python/README.md
- https://github.com/ilyautov/humanizer-ru/blob/main/pyproject.toml
- https://github.com/ilyautov/humanizer-ru/blob/main/pypi/README.md
- https://github.com/azeemkafridi/bulkpublish-api/blob/c02828ef44c71cc27635b5aecb985d4c9f1b3df8/openapi.json

Проверены ExtractInput/extract и tables.markdown/cells, ru-humanizer --json/--before,
GET /api/channels, POST /api/posts с camelCase channelId/mediaFiles и status=draft.
