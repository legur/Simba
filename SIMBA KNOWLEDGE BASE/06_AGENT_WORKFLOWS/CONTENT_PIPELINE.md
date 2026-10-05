# CONTENT PIPELINE

Версия: 1.6 · 05.10.2026

## Полнота смешанного запроса

Перед production-маршрутом применять раздел «Главная цель и полный результат» из канонического `ROUTER_v10.1.md` (внутренняя версия 10.2).

PROCESS_OWNER сохраняет перечень всех явно запрошенных результатов, зависимости этапов и критерий завершения. Для каждого результата подтверждаются исполнение профильного модуля и его проверка. Главная цель не отменяет вторичные запросы.

Перед завершением сверить запрошенное и фактически готовое. Если этап заблокирован или ожидает обязательного выбора/утверждения Leo, показать готовые результаты и конкретную зависимость; продолжить независимые доступные части. `COMPLETE` допустим только когда выполнен весь запрошенный объём. Preview-концепции и ожидание выбора не равны финальному постеру.

## HARD DEFAULT — SOURCE-ONLY INPUT

Если Leo присылает содержательный внешний источник без отдельной команды, он считается `NEW_SOURCE`.

```text
SOURCE_ONLY_INPUT
  → NEW_SOURCE
  → SOURCE_RESOLUTION(BODY→HTML/MIME→ATTACHMENTS→INLINE→WEB_VERSION)
  → ROUTER_TASK_CLASSIFIED
  → KB_PREFLIGHT
  → EXECUTOR_SELECTED
  → EXECUTOR_RULES_LOADED
  → PROFILE_MODULE_EXECUTED
  → EXECUTOR_RESULT_VALIDATED
  → RESULT_TO_LEO
```

Router не спрашивает назначение материала, если его можно определить из содержания.

Типовой выбор:
- новость / актуальная статья / статистика / изменение правил → `News`;
- коммерческая рассылка / акция / предложение с ценой и датами → `AI-Маркетолог` → профильный исполнитель;
- объясняющий материал → `Info`;
- материал о месте/путешествии → `Travel`;
- личная позиция Leo → `Leo`.


Для supplier-email действует двойная оценка: `COMMERCIAL_SCORE` и `NEWS_SCORE`. Отсутствие цены не блокирует `NEWS_HIGH`. Существенное изменение рейсов/частоты/расписания/условий должно идти в `News`, даже если коммерческий оффер отсутствует.

До `ROUTER_TASK_CLASSIFIED` запрещено считать источник неполным, пока не проверены HTML/MIME, вложения, inline-изображения и доступная web-версия рассылки. Неразрешимый технический источник получает `SOURCE_BLOCKED`.

Если Leo одновременно дал явную команду, она имеет приоритет над source-only default. Системные файлы и материалы, присланные для явного анализа/редактирования/сохранения, не превращаются автоматически в пост.

Внешний Critic/внешняя критика автоматически в этот маршрут не входят. `INTERNAL_CRITIC_MODE` является обязательным скрытым gate для результата Simba.

## Основной маршрут рекламного материала

### Execution invariant

Router/Маркетолог не являются финальными авторами вместо профильного модуля. Каждый исполнитель проходит `SELECTED → RULES_LOADED → EXECUTED → VALIDATED`. При нарушении — `BLOCKED_EXECUTOR_NOT_RUN`.

### Коммерческая ветка

```text
NEW_SOURCE
  → ROUTER_CORE_PREFLIGHT(KNOWLEDGE_MAP+KB_RUNTIME_PROTOCOL)
  → ROUTER_TASK_CLASSIFIED
  → MODULE_KB_PREFLIGHT
  → MARKETER_NORMALIZED
  → AUDIENCE_SELECTED
  → MARKETING_HYPOTHESIS_READY
  → SIMBA_TASK
  → SIMBA_KB_PREFLIGHT
  → SIMBA_DRAFT_READY
  → INTERNAL_CRITIC_MODE
  → [REVISE → SIMBA_REPAIR → INTERNAL_CRITIC_MODE]*
  → INTERNAL_CRITIC_PASS
  → SIMBA_FINALIZE
  → TEXT_READY_FOR_LEO
  → LEO_APPROVAL
  → APPROVED_TEXT
  → CONTENT_LIBRARY_ARCHIVE(APPROVED)
  → RAFAEL_TASK_CREATED
  → RAFAEL_KB_PREFLIGHT
  → REFERENCE_SEARCH_ATTEMPT(ARCHIVARIUS+YOUMIND)
  → FIVE_PREVIEWS_READY
  → REFERENCE_TRACE_SAVED
  → REFERENCE_NAMES_SHOWN_TO_LEO
  → PREVIEW_SELECTED
  → SELECTED_PROMPT_RELOADED
  → FINAL_RENDER_EXECUTED
  → FINAL_VISUAL_READY
  → PUBLICATION_PACKAGE_READY
  → FINAL_LEO_APPROVAL
  → LEARNING_WRITEBACK
```

## Новостная ветка «Новости туризма»

```text
SOURCE_RESOLVED
  → MARKETER_NORMALIZED
  → NEWS_SCORE_HIGH
  → NEWS_TASK
  → NEWS_KB_PREFLIGHT
  → NEWS_RULES_LOADED
  → NEWS_EXECUTED
  → NEWS_RESULT_VALIDATED
  → NEWS_TEXT_READY
  → [LEO_APPROVAL | POLICY_APPROVED_FOR_VISUAL]
  → RAFAEL_TASK_CREATED
  → RAFAEL_RULES_LOADED
  → RAFAEL_CONCEPTS_AND_PROMPTS_READY
  → RENDERER_EXECUTED
  → FULL_VISUAL_SET_READY
  → PROVENANCE_SAVED
```

News, а не Router/Маркетолог, является текстовым исполнителем. Цена не требуется для прохождения этой ветки.

## AUTOMATION_CONTINUOUS_MODE

Для конкретной scheduled-задачи, где Leo заранее разрешил не останавливаться между текстом и постером, `NEWS_TEXT_READY` или финальный результат Simba получает `POLICY_APPROVED_FOR_VISUAL` без интерактивного подтверждения. Это разрешает только переход к Rafael; **автопубликация запрещена**.

Rafael остается владельцем визуального решения. Image generator — renderer и работает только после Rafael-process; Router/Маркетолог не составляют за Rafael визуальные prompts.

## Provenance

Каждый production-result сохраняет `SOURCE / CLASSIFICATION / STRATEGIST / TEXT_EXECUTOR / VISUAL_EXECUTOR / RENDERER / EXECUTION_STATES / STATUS`.

## Critic: internal gate и внешний review

### Internal Critic
`INTERNAL_CRITIC_MODE` — обязательный скрытый production-gate **только для Simba**. Он запускается после черновой редакции Simba и до `TEXT_READY_FOR_LEO`.

- `PASS` → Simba финализирует текст и только затем результат показывается Leo;
- `REVISE` → замечания возвращаются Simba, который сам переписывает текст и снова проходит Critic;
- Critic не переписывает пост и не заменяет Simba как финального автора;
- промежуточные оценки и итерации пользователю не показываются.

### Внешний Critic / внешний разбор
Leo по-прежнему может отдельно запускать Critic или приносить комментарии любого внешнего критика. Это evidence для текущей доработки, а не самостоятельный production-PASS. Принятые замечания идут обратно Simba, и новая версия снова проходит Internal Critic.

Внешняя критика не заменяет решение Leo и не становится постоянным правилом автоматически.

## KB PREFLIGHT
Каждый этап читает только свои обязательные KB-слои по `00_CORE/KB_RUNTIME_PROTOCOL.md`. Если внутренний обязательный KB-файл недоступен, маршрут останавливается как `BLOCKED_KB_UNAVAILABLE`; память о старой версии не используется как замена. Внешние reference-библиотеки Archivarius/YouMind не являются KB-файлами: их недоступность переводит Rafael в degraded mode и не останавливает визуальную генерацию.

## BLOCKED
Если Simba возвращает `BLOCKED_*`, Маркетолог не перекладывает уточнение на Simba. Он анализирует причину, корректирует исходное задание на основании имеющейся информации и повторно вызывает исполнителя. Если критического факта действительно нет, только тогда требуется получение этого факта.

## Learning write-back
- прямая корректировка Leo → `07_LEARNINGS/CORRECTIONS_LOG.md`;
- системное решение → `DECISION_LOG.md`;
- утвержденный полный текст → `03_CONTENT_LIBRARY` со статусом `APPROVED`;
- только подтвержденная фактическая публикация меняет статус на `PUBLISHED`;
- внутренний Critic является quality-gate, но его единичные замечания не становятся вечными правилами автоматически;
- внешний Critic/внешняя критика дает evidence для текущей доработки и также не становится вечным правилом автоматически.

## Rafael selected-variant final render
- Пять первоначально сгенерированных вариантов являются preview-кандидатами для выбора.
- `PREVIEW_SELECTED` не равен `FINAL_VISUAL_READY`.
- После выбора Лео Rafael обязан повторно загрузить полный сохраненный production-prompt выбранного варианта и выполнить отдельный полноразмерный render 1:1.
- Пересборка prompt по памяти, краткому описанию или анализу preview запрещена.
- Только этот отдельный render после QA может перейти в `PUBLICATION_PACKAGE_READY`.

## Rafael reference trace
- Перед концепциями Rafael обязан попытаться выполнить поиск в Archivarius и YouMind.
- После генерации пяти визуалов сохранить `REFERENCE_TRACE` по вариантам 1–5 в visual-session / публикационный пакет `03_CONTENT_LIBRARY`.
- В trace включаются только реально использованные карточки/шаблоны, а не все просмотренные.
- Leo сразу после генерации видит компактный блок с названиями использованных Archivarius cards и YouMind templates.
- Полные prompts, JSON, ссылки и sample images не показываются без отдельного запроса.

## Публикация
Автоматическая публикация без финального подтверждения Лео запрещена, если отдельно не создан другой утвержденный процесс.


## Changelog

### 1.6 — 05.10.2026
Уточнена полнота смешанного запроса: цель, все результаты, зависимости, проверка завершения и конкретное сообщение о блокировке. Существующие роли и approval/preview gates сохранены.


### 1.5 — 08.09.2026
Добавлены source-resolution gate, dual Commercial/News routing, hard executor states, отдельная News-ветка, provenance и ограниченный `AUTOMATION_CONTINUOUS_MODE`. Renderer отделен от Rafael.

### 1.4 — 08.09.2026
Добавлен обязательный `INTERNAL_CRITIC_MODE` для Simba с repair-loop до PASS; внешний Critic сохранен как отдельный evidence-канал; после внешней критики обновленный текст снова проходит internal gate.
