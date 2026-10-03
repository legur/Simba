# AGENTS.md — Archivarius branch runtime

## Назначение

Эта ветка `archivarius` предназначена для Archivarius — системы хранения, нормализации, поиска, классификации и релизной сборки карточек промтов, гайдов и методологий.

Рабочая ветка Simba остаётся `main`.
Не переносить изменения из Archivarius в Simba `main` автоматически.

## Точка входа

Перед любой задачей Archivarius читать:

1. `Archivarius/System/Archivarius-System-v2.7.md`
2. `Archivarius/System/Archivarius-CoreSpec-v2.2.md`
3. `Archivarius/System/Archivarius-CardSchema-v2.1.md`
4. `Archivarius/System/Archivarius-Tags-v2.1.md`
5. `Archivarius/INDEX_ARCHIVARIUS.md`
6. `Archivarius/MIGRATION_STATUS.md`

Для viral prompt-posts дополнительно использовать:
`Archivarius/System/Archivarius-ViralPromptPosts-Protocol-v1.0.md`, если файл присутствует.

## Source of truth во время миграции

Пока `Archivarius/MIGRATION_STATUS.md` имеет статус «миграция не завершена»:

- системный слой Archivarius читается из GitHub ветки `archivarius`;
- физически перенесённые карточки читаются из GitHub;
- карточки, которых ещё нет в GitHub, остаются на Google Drive;
- нельзя утверждать, что GitHub содержит полную библиотеку, пока не выполнена count/hash reconciliation.

После завершения миграции источник истины должен быть переключён отдельным явным решением.

## Запись новых правил

Если Leo говорит «сохрани», «теперь делаем так», «всегда», «больше не» применительно к Archivarius:

1. определить, является ли это системным правилом;
2. обновить соответствующий файл в ветке `archivarius`;
3. зафиксировать Git commit;
4. подтвердить Leo commit SHA.

## Карточки

- AR-ID не меняется.
- Не создавать смысловые дубли.
- Источник истины карточки — сама карточка, а не индекс.
- Индексы являются производными.
- В PROD идут только допустимые системой карточки.
- Непроверенный массовый внешний импорт не считать автоматически авторским/проверенным слоем.

## GitHub

Все изменения Archivarius сохранять в ветку `archivarius`.
Не писать Archivarius runtime-файлы в `main` без отдельной команды Leo.
