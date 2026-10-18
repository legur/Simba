# KB RUNTIME PROTOCOL — SIMBA KNOWLEDGE BASE

Статус: MANDATORY RUNTIME DEPENDENCY  
Редакция: runtime 2.0 · 18.10.2026
Дата: 18.10.2026 · pre-approval Humanizer gate + approval invalidation
Канонический путь: `legur/Simba@main / SIMBA KNOWLEDGE BASE`

## 1. Назначение

Knowledge Base — обязательный общий контекст системы. Она не заменяет профильные правила модулей и не является источником текущих цен/наличия. Она хранит стабильные правила бренда, аудитории, бизнеса, workflow, историю контента и подтвержденные learning-сигналы.

До выполнения содержательной задачи выбранный модуль обязан пройти KB PREFLIGHT.

## 1A. Канонический runtime после миграции

С 02.10.2026 эта Knowledge Base читается и обновляется непосредственно в `legur/Simba@main`.

- GitHub — канонический источник текущих правил и write-back.
- Google Drive `New Simba` — архив миграции и не используется как штатная runtime-зависимость.
- Физические пути профильных модулей определены в корневом `AGENTS.md`.
- Любая legacy-ссылка на Drive ID внутри старого перенесённого материала считается исторической, если META/AGENTS не указывают иное.


## 2. KB PREFLIGHT

1. Прочитать `00_CORE/KNOWLEDGE_MAP.md`.
2. Прочитать этот `00_CORE/KB_RUNTIME_PROTOCOL.md`.
3. Определить тип задачи, продукт, канал и выбранный модуль.
4. Загрузить только обязательные для задачи слои.
5. Не начинать генерацию/оценку/визуал до завершения загрузки.
6. Если обязательный файл недоступен — вернуть `BLOCKED_KB_UNAVAILABLE` с точным названием недоступного файла. Не заменять его памятью о прошлой версии.

<!-- EXTERNAL_RUNTIME_BRIDGE_START -->
## 2A. Runtime mode + external reference gate
После определения типа задачи выбрать режим `FAST | DEEP | STRICT`.
Для Rafael:
1. прочитать `00_CORE/ARCHIVARIUS_RUNTIME_BRIDGE.md`;
2. прочитать `00_CORE/ARCHIVARIUS_RUNTIME_TRUSTED.md`;
3. прочитать `00_CORE/ARCHIVARIUS_RUNTIME_BLOCKLIST.md`;
4. выполнить trusted-first поиск и при необходимости расширить его на релевантные `active` visual cards Archivarius вне blocklist;
5. попытаться выполнить YouMind search по актуальному manifest;
6. не загружать библиотеки целиком;
7. текстовую pattern extraction передавать TIA.

Недоступность внешнего Archivarius или YouMind не равна `BLOCKED_KB_UNAVAILABLE`. Если недоступна одна библиотека — использовать вторую; если обе — Rafael продолжает по Visual Rules и фиксирует `REFERENCE_LIBRARIES_UNAVAILABLE`.

После генерации Rafael обязан показать Leo названия реально использованных reference-карточек/шаблонов и сохранить `REFERENCE_TRACE` по вариантам в `03_CONTENT_LIBRARY`.
<!-- EXTERNAL_RUNTIME_BRIDGE_END -->

## 2B. SOURCE RESOLUTION + EXECUTION GATE

Для email/source mining до классификации обязательна попытка чтения всех доступных носителей: `BODY → HTML/RAW MIME → ATTACHMENTS → INLINE IMAGES → VIEW-IN-BROWSER/CAMPAIGN LINK`. Пустой text-body не является доказательством отсутствия оффера. Технически недоступный материал получает `SOURCE_BLOCKED`.

После выбора профильного модуля обязательны runtime states:

`EXECUTOR_SELECTED → EXECUTOR_RULES_LOADED → EXECUTOR_EXECUTED → EXECUTOR_RESULT_VALIDATED`.

Router/Маркетолог не заменяют выбранного текстового исполнителя и не создают визуальное решение вместо Rafael. Если исполнение нельзя подтвердить — `BLOCKED_EXECUTOR_NOT_RUN`.

Rafael = `VISUAL_EXECUTOR`; image generator = `RENDERER`.

Для supplier-email отдельно определяются `COMMERCIAL_SCORE` и `NEWS_SCORE`; цена не является обязательным условием `NEWS_HIGH`.

## 2C. PROVENANCE MANIFEST

Для production-материала внутренне сохранять:
`SOURCE / CLASSIFICATION / STRATEGIST / TEXT_EXECUTOR / VISUAL_EXECUTOR / RENDERER / EXECUTION_STATES / STATUS`.

Manifest не заменяет Content Library и показывается Leo по запросу/при диагностике.

## 2D. FACEBOOK FEEDBACK LEARNING OVERLAY

Канонический learning-файл для содержательных разборов budetsdelano.ai: `07_LEARNINGS/PATTERN_WATCH.md`.

Для любого создания или редактирования Facebook-поста через Simba, Info, Travel, Leo или News, включая маршруты через AI-Маркетолога, PATTERN_WATCH является обязательным runtime-контекстом. Загружать файл до генерации и передавать исполнителю только релевантные `OBSERVATION / SIGNAL / ACTIVE RULE CANDIDATE` для текущего модуля, канала, цели и механики поста.

Humanizer не выбирает новые learning-сигналы, но обязан сохранять уже выбранные релевантные сигналы, если они не конфликтуют с фактами или правилами модуля. Для иных каналов применять только записи PATTERN_WATCH, явно относящиеся к этому каналу.

Новый содержательный разбор budetsdelano.ai записывается непосредственно в PATTERN_WATCH. Разборы Critic, ChatGPT, Claude, ручные оценки и отдельные метрики могут использоваться для текущей правки, но не повышают уровень budetsdelano-паттернов.

Legacy `Feedback-Learning-*` не является runtime-зависимостью.

## 3. Обязательные наборы контекста

### Рекламный Facebook-пост / Simba
Обязательно:
- `01_BRAND/STYLE_LEO.md`
- `01_BRAND/ANTI_STYLE.md`
- `01_BRAND/BRAND_RULES.md`
- `02_AUDIENCE/SEGMENTS.md`
- `02_AUDIENCE/OBJECTIONS_AND_LANGUAGE.md`
- `03_CONTENT_LIBRARY/_INDEX.md`
- `03_CONTENT_LIBRARY/_PATTERN_TRACKER.md`
- `07_LEARNINGS/PATTERN_WATCH.md`
- релевантные файлы `04_BUSINESS`
- `05_OPERATIONAL_RULES/FACTS_FRESHNESS_PRICING.md`
- `06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md`

По необходимости:
- последние релевантные полные APPROVED/PUBLISHED материалы из `03_CONTENT_LIBRARY`;
- `07_LEARNINGS/STYLE_FEEDBACK_MINING.md`;
- `07_LEARNINGS/CORRECTIONS_LOG.md` и `DECISION_LOG.md`.

### AI-Маркетолог
Обязательно:
- `01_BRAND/BRAND_RULES.md`
- `02_AUDIENCE/SEGMENTS.md`
- `02_AUDIENCE/OBJECTIONS_AND_LANGUAGE.md`
- релевантные `04_BUSINESS`
- `05_OPERATIONAL_RULES/FACTS_FRESHNESS_PRICING.md`
- `06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md`

Для Facebook дополнительно:
- `01_BRAND/STYLE_LEO.md`
- `01_BRAND/ANTI_STYLE.md`
- `03_CONTENT_LIBRARY/_INDEX.md`
- `03_CONTENT_LIBRARY/_PATTERN_TRACKER.md`
- `07_LEARNINGS/PATTERN_WATCH.md`

### Новости туризма / News
Обязательно:
- `01_BRAND/STYLE_LEO.md`
- `01_BRAND/ANTI_STYLE.md`
- `01_BRAND/BRAND_RULES.md`
- релевантные `02_AUDIENCE`
- `05_OPERATIONAL_RULES/FACTS_FRESHNESS_PRICING.md`
- `06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md`
- подтвержденный текущий источник события.

Цена не требуется. Архивные расписания/условия не использовать как текущий факт.

### Critic
Critic имеет два runtime-режима.

**`INTERNAL_CRITIC_MODE`** загружается автоматически для каждого `SIMBA_DRAFT_READY` и является обязательным скрытым quality-gate до показа результата Leo. При `REVISE` текст возвращается Simba, а не редактируется Critic. После новой редакции Critic запускается повторно до `INTERNAL_CRITIC_PASS` или фактического `BLOCKED_*`.

**`EXTERNAL_REVIEW_MODE`** загружается только когда Leo отдельно вызывает Critic для независимой оценки текста. Этот режим не является production-PASS.

Обязательно для обоих режимов:
- `01_BRAND/STYLE_LEO.md`
- `01_BRAND/ANTI_STYLE.md`
- `03_CONTENT_LIBRARY/_PATTERN_TRACKER.md`
- `_INDEX.md` и последние релевантные APPROVED/PUBLISHED посты, если доступны;
- `07_LEARNINGS/STYLE_FEEDBACK_MINING.md`.

Critic оценивает повторяемость не только внутри текущего текста, но и относительно последних материалов. Архив не используется для проверки текущих цен и фактов. Внутренний Critic не показывает Leo промежуточные баллы/таблицы; после `PASS` Simba выполняет финальную авторскую редакцию и передаёт пост в Humanizer, а готовый результат показывается Leo только после `HUMANIZER_PASS`.

### Humanizer
Humanizer является обязательной runtime-зависимостью готовых постов Simba, Info, Travel, Leo и News до первого `LEO_APPROVAL` либо `POLICY_APPROVED_FOR_VISUAL`. Wix-форматтер, клиентские письма/документы, JSON и визуальные результаты этим правилом автоматически не охватываются.

Обязательно:
- `Симба (Писатель)/Humanizer-v1.4.md`;
- актуальный файл профильного автора и его завершённая редакция;
- выбранные релевантные KB-сигналы, уже применённые автором;
- `06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md`;
- `06_AGENT_WORKFLOWS/AI_PLUGIN_TOOLS.md` для проверки доступности опционального `humanizer-ru`.

Недоступность внешнего сканера не блокирует маршрут: выполнить ручной Humanizer по каноническому файлу. Недоступность самого канонического Humanizer или его обязательных внутренних KB-зависимостей даёт `BLOCKED_KB_UNAVAILABLE`.

Для Simba вход в Humanizer разрешён только после `INTERNAL_CRITIC_PASS → SIMBA_FINALIZE`. Для Info, Travel, Leo и News Internal Critic автоматически не добавляется. Смысловая правка возвращает текст профильному автору; Simba повторяет Internal Critic, другие авторы — собственную проверку. `HUMANIZER_PASS` обязателен до ready-state и approval/policy-trigger.

### Rafael
Обязательно:
- `01_BRAND/BRAND_RULES.md`
- `01_BRAND/VISUAL_RULES.md`
- релевантный сегмент из `02_AUDIENCE`
- утвержденный `APPROVED_TEXT`
- подтвержденные факты текущего оффера
- `06_AGENT_WORKFLOWS/RAFAEL_TRIGGER.md`

После этого Rafael выполняет обязательные попытки reference-search в Archivarius и YouMind согласно своему системному файлу. Недоступность внешней библиотеки обрабатывается degraded mode и не равна KB failure.

### Клиентское предложение / письмо / документ
Не применять рекламный стиль автоматически. Читать:
- релевантные `04_BUSINESS`
- `05_OPERATIONAL_RULES`
- продуктовый контекст
- правила конкретного формата/модуля.

## 4. Что нельзя брать из архива как текущий факт

Никогда не переносить из старых постов без нового подтверждения:
- цену;
- наличие;
- дату акции;
- расписание;
- тариф;
- налоги;
- правила отмены;
- включения;
- визовые/въездные условия;
- состояние рейсов.

`03_CONTENT_LIBRARY` — источник стиля, истории решений и контроля повторов, а не текущей коммерческой истины.

`_CONFIRMED_MISSING_POSTS.md` разрешен только для анализа исторической реакции Leo/Critic и паттернов.  
`_REQUESTED_OR_UNCERTAIN.md` запрещен как доказательство стиля, существования готового поста или исторической статистики.

## 5. Приоритет при конфликте

1. Прямое текущее указание Leo.
2. Подтвержденные факты конкретного задания.
3. Актуальные Router / META-Governance / правила профильного модуля.
4. Стабильные правила SIMBA KNOWLEDGE BASE.
5. `07_LEARNINGS/PATTERN_WATCH.md` и другие внешние/накопительные рекомендации.
6. Старые примеры и архивные материалы.

Архивный пример никогда не отменяет текущий факт или прямое решение Leo.

## 6. Контракт передачи контекста

Router или Маркетолог перед вызовом исполнителя формирует внутренний блок:

```text
[KB_CONTEXT]
KNOWLEDGE_MAP: LOADED
KB_RUNTIME_PROTOCOL: LOADED
LOADED_FILES:
- ...
PATTERN_WARNINGS:
- ...
LEARNING_SIGNALS:
- ...
EXCLUDED_AS_CURRENT_FACTS:
- archive prices / availability / stale conditions
```

Этот служебный блок не показывается Leo, если он отдельно его не запросил.

## 7. Learning write-back

### Прямая корректировка Leo
Записать в `07_LEARNINGS/CORRECTIONS_LOG.md`:
- дату;
- материал;
- точную суть корректировки;
- что было изменено;
- единичный это сигнал или повтор.

### Системное решение Leo
Записать в `07_LEARNINGS/DECISION_LOG.md`.

### Утвержденный текст
После `APPROVED_TEXT` сохранить полный текст в `03_CONTENT_LIBRARY` со статусом `APPROVED` и обновить `_INDEX.md`.

Любое изменение утверждённой редакции снимает `APPROVED_TEXT` либо `POLICY_APPROVED_FOR_VISUAL`. Предыдущую редакцию сохранить как историческую, без разрушительного перезаписывания. Новая редакция повторяет авторскую проверку, Internal Critic для Simba, Humanizer и новое утверждение/policy-trigger. Зависимые visual/package ready-states снимаются до QA затронутых визуалов и нового render, когда изменены exact text или другие visual inputs.

### Подтверждение фактической публикации
Только после явного подтверждения публикации изменить статус на `PUBLISHED`.

### Critic / внешняя критика
Internal Critic является обязательным quality-gate Simba, но его единичное замечание не становится постоянным стилевым правилом само по себе.

Leo может отдельно приносить комментарии внешнего критика. Они используются как evidence текущей доработки: после фильтрации применимости замечания возвращаются Simba, а обновленный текст снова проходит `INTERNAL_CRITIC_MODE`. Постоянное правило появляется только после прямого решения Leo или достаточного повторного подтверждения по модели доказательности `STYLE_FEEDBACK_MINING.md`.

`07_LEARNINGS/PATTERN_WATCH.md` является каноническим Feedback Learning каналом budetsdelano.ai и не имеет приоритета над прямыми решениями Leo или стабильными правилами Knowledge Base.

## 8. Promotion rule

Из `07_LEARNINGS` в `STYLE_LEO.md`, `ANTI_STYLE.md` или `_PATTERN_TRACKER.md` переносить только:
- прямое правило Leo (`всегда`, `никогда`, явное системное решение); или
- повторяемый подтвержденный паттерн.

Единичное мнение хранится как observation и не превращается автоматически в догму.

## 9. Одна актуальная версия файла

Рабочие системные и Knowledge Base файлы обновляются **на месте**.

Запрещено создавать параллельные `v1`, `v2`, `old`, `backup`, `final-final` и аналогичные рабочие копии без отдельной команды Leo.

Если устаревшая отдельная рабочая версия найдена, удалить ее после проверки актуального файла.

Исключение: исторические оригиналы контента и доказательные revision-материалы, где старая версия сама является объектом анализа.

<!-- KB_LINT_RUNTIME_START -->
## 10. KB-LINT после write-back
После изменения Knowledge Base или системной зависимости выполнить `00_CORE/KB_LINT.md`.
Обязательно после изменения постоянного правила, promotion из `07_LEARNINGS`, core/workflow/Router/META/агента и после изменения Archivarius trusted/blocklist governance.
Для APPROVED/PUBLISHED поста применяется сокращенный Content Library profile.
`KB-LINT: FAIL` означает, что write-back не завершен до исправления и повторного PASS/WARNING.
<!-- KB_LINT_RUNTIME_END -->


## 11. Optional technical tools — 15.10.2026
Для структурированного извлечения документов, запроса внешнего сканера или
BulkPublish читать `06_AGENT_WORKFLOWS/AI_PLUGIN_TOOLS.md` (1.0).
Проверить фактическую доступность в текущей среде. EXTRACTED_UNVERIFIED не является
FACTS_VERIFIED; SCANNED не является APPROVED_TEXT; DRAFT_CREATED не является PUBLISHED.
Недоступность внешнего пакета не является BLOCKED_KB_UNAVAILABLE. Для Xberg/сканера
допустим штатный reader/ручной Humanizer, для удалённого draft нужен доступ к сервису.

## 12. Changelog

### Runtime 2.0 — 18.10.2026
Тип: структурное изменение общей runtime-последовательности.
Добавлена обязательная зависимость Humanizer до approval/policy-trigger и единый контракт invalidation для любой правки утверждённого текста с сохранением исторической версии.
