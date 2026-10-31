# AGENTS.md — Simba runtime adapter

## Назначение

Этот репозиторий — каноническая система создания контента Simba by Bon Tours.
Источник истины: `legur/Simba@main`.

Этот файл задаёт среде Codex физические пути и порядок загрузки. Он **не заменяет** Router, META-Governance, профильные модули или Knowledge Base.

## 1. Перед любой содержательной задачей

Всегда сначала прочитать:

1. `ROUTER_v10.1.md`
2. `SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md`
3. `SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md`

После классификации задачи Router определяет профильный модуль и обязательный KB PREFLIGHT.

Если обязательный KB-файл недоступен, не подменять его памятью: `BLOCKED_KB_UNAVAILABLE`.

## 2. Перед изменением самой системы

Если задача меняет архитектуру, routing, правила, KB, workflow, версию модуля или поведение системы:

1. прочитать `META-Governance-v8.1.md`;
2. использовать режим `STRICT`;
3. прочитать затрагиваемый канонический файл целиком;
4. изменить существующий файл по тому же пути;
5. выполнить `SIMBA KNOWLEDGE BASE/00_CORE/KB_LINT.md`, если изменение затрагивает Router/META/00_CORE/workflow/KB-зависимость;
6. проверить результат после записи.

Не создавать параллельные рабочие копии `old`, `backup`, `final-final`, `v2` без прямой команды Leo.

## 3. Физическая карта активных модулей

| Логическая роль | Канонический файл |
|---|---|
| Router | `ROUTER_v10.1.md` |
| META-Governance | `META-Governance-v8.1.md` |
| AI-Маркетолог | `AI-Marketer-Simba-by-Bon-Tours-v5.0.md` |
| Simba | `Симба (Писатель)/Simba-v5.0.md` |
| Humanizer | `Симба (Писатель)/Humanizer-v1.4.md` |
| News | `Симба (Писатель)/News-v1.2.md` |
| Travel | `Симба (Писатель)/Travel-v1.3.md` |
| Info | `Симба (Писатель)/Info-v1.2.md` |
| Leo | `Симба (Писатель)/Leo-v1.3.md` |
| Lumiere | `Симба (Писатель)/Lumiere-v1.1.md` |
| Critic | `Critic/Critic-5.7.md` |
| Audit | `Critic/Audit-v1.2.md` |
| Rafael | `Rafael/RAFAEL_System_v6.2.md` |
| Rafael routing | `Rafael/RAFAEL_Routing_v3.3.md` |
| Rafael styles | `Rafael/RAFAEL_Styles_v3.3.md` |
| Wix Formatter | `Wix-Formatter/Wix-TourFormatter-v1.5.md` |
| Сценарист | `Сценарист/SCENARIST_Simba_by_Bon_Tours_v1.0.md` |
| Монтажер Клод | `Монтажер Клод/MONTAZHER_KLOD_v1.0.md` (инструмент `integrations/video/`) |

## 4. Runtime invariant

Для создания/содержательной переработки постов до написания загрузить `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/INTRIGAN.md`. После цели/основной мысли/фактов выполнить `INTRIGAN_CHECK → [INTRIGUE_PLAN_READY | INTRIGAN_SKIPPED(reason)]`, затем действующие TIA/авторские проверки. Интриган не автор; News/оперативные инструкции сохраняют FACT_FIRST. Недоступность внешнего skill допускает исполнение канонического протокола.


## COPYWRITER_TEST_MODE — 31.10.2026

По прямому решению Leo включен тестовый дополнительный вариант «Копирайтер-универсал» внутри существующего процесса Simba. Канонический контракт: `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/COPYWRITER_TEST.md` (1.0). При новом обычном задании Simba сохраняет три штатных варианта и добавляет один явно подписанный тестовый вариант на том же брифе; это не новый самостоятельный production-автор. При явном запросе только дополнительной версии выдавать только ее, не повторять прежние три. Длина и структура соответствуют задаче; Intrigan/TIA, факты, Internal Critic и Humanizer сохраняются. GROK_ADS_MODE, точечная правка и запрос одного выбранного текста автоматически не получают четвертого варианта. Тест не меняет права публикации. При недоступности skill сообщить причину пропуска, не имитировать его исполнение. Команда Leo «выключи тест копирайтера» отключает режим.

После выбора исполнителя обязательны состояния:

`EXECUTOR_SELECTED → EXECUTOR_RULES_LOADED → EXECUTOR_EXECUTED → EXECUTOR_RESULT_VALIDATED`.

Router и AI-Маркетолог не пишут финальный текст вместо выбранного профильного модуля.
Rafael является `VISUAL_EXECUTOR`; конкретный image generator является `RENDERER`.

Для результата Simba обязателен скрытый:

`SIMBA_DRAFT_READY → INTERNAL_CRITIC_MODE → [REVISE → SIMBA_REPAIR]* → INTERNAL_CRITIC_PASS → SIMBA_FINALIZE`.

Готовые посты Simba, Info, Travel, Leo и News до финальной выдачи/утверждения проходят `HUMANIZER_EXECUTED → HUMANIZER_PASS` по `Симба (Писатель)/Humanizer-v1.4.md`. Для Simba этот этап следует после финализации автором и Internal Critic; другим авторам Internal Critic не добавляется. Смысловые правки возвращаются автору и повторяют применимые проверки. Изменение уже утверждённого текста снимает прежнее утверждение/policy и готовность зависимого пакета до нового approval и visual QA по `CONTENT_PIPELINE.md` / `RAFAEL_TRIGGER.md`.

Промежуточные внутренние оценки Critic не показывать Leo без отдельного запроса.

## 5. Knowledge Base

Не загружать всю KB автоматически. Читать только набор, заданный `KB_RUNTIME_PROTOCOL.md`.

Ключевые каталоги:

- `00_CORE` — runtime architecture;
- `01_BRAND` — голос и визуальные правила;
- `02_AUDIENCE` — сегменты и язык;
- `03_CONTENT_LIBRARY` — approved/published history и контроль повторов;
- `04_BUSINESS` — стабильный бизнес-контекст;
- `05_OPERATIONAL_RULES` — точность и публикационные ограничения;
- `06_AGENT_WORKFLOWS` — передача задач между агентами;
- `07_LEARNINGS` — решения, исправления, наблюдаемые паттерны.

Никогда не использовать архивные цены, наличие, даты, расписания, тарифы, налоги, условия отмены, визовые/entry rules как текущие факты без нового подтверждения.

## 6. Write-back

По действующему runtime:

- прямая корректировка Leo → `SIMBA KNOWLEDGE BASE/07_LEARNINGS/CORRECTIONS_LOG.md`;
- системное решение Leo → `SIMBA KNOWLEDGE BASE/07_LEARNINGS/DECISION_LOG.md`;
- `APPROVED_TEXT` → полный текст в `SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY/` + обновление `_INDEX.md`;
- статус `PUBLISHED` ставится только после явного подтверждения фактической публикации;
- production provenance хранит `SOURCE / CLASSIFICATION / STRATEGIST / TEXT_EXECUTOR / VISUAL_EXECUTOR / RENDERER / EXECUTION_STATES / STATUS`.

После write-back выполнять соответствующий профиль `KB_LINT.md`.

## 7. Rafael

После разрешённого триггера читать:

- `Rafael/RAFAEL_System_v6.2.md`;
- `Rafael/RAFAEL_Routing_v3.3.md`;
- `Rafael/RAFAEL_Styles_v3.3.md`;
- `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/RAFAEL_TRIGGER.md`;
- обязательный Rafael KB context из runtime protocol.

Rafael должен формировать 5 существенно разных preview-концепций. Выбор Leo запускает отдельный финальный 1:1 render по сохранённому полному production prompt выбранного варианта.

Для `Leo` и `Info` действует `HERO_IDENTITY_OVERRIDE=LEO`.

Archivarius и YouMind — внешние reference-библиотеки. Их недоступность переводит Rafael в degraded mode, но не является `BLOCKED_KB_UNAVAILABLE`.

## 8. GitHub и Google Drive

GitHub `legur/Simba@main` — единственный канонический рабочий runtime.

Google Drive `New Simba` после миграции — архив. Не читать и не писать его как источник актуальных системных правил, если Leo явно не просит сверить/восстановить материал.

Legacy Drive IDs и инструкции, встречающиеся в старых перенесённых документах, не имеют приоритета над META-Governance и этим runtime adapter.

## 9. Приоритет конфликтов

1. прямое текущее указание Leo;
2. подтверждённые факты текущей задачи;
3. актуальные Router / META / профильный модуль;
4. Knowledge Base;
5. накопительные внешние рекомендации;
6. архивные примеры.

Не принимать решения за Leo там, где workflow требует его утверждения.


## 10. Persistent rule write-back confirmation

Если Leo во время работы формулирует постоянное изменение системы словами или смыслом уровня «теперь делаем так», «всегда», «больше не», «сохрани это», «запомни как правило»:

1. отличить постоянное правило от правки только текущего материала;
2. обновить соответствующий канонический файл в `legur/Simba@main`;
3. записать корректировку в `CORRECTIONS_LOG.md` или системное решение в `DECISION_LOG.md`;
4. выполнить требуемый `KB_LINT`;
5. сделать Git commit;
6. только после успешного commit считать правило сохранённым;
7. в ответ Leo коротко подтвердить:
   - что сохранено;
   - суть правила;
   - commit SHA.

Нельзя говорить «сохранено», если изменение осталось только в текущем чате, памяти модели или локальной незакоммиченной рабочей копии.


## 11. Optional AI plugin tools — 15.10.2026
Для Xberg, humanizer-ru или BulkPublish сначала читать `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/AI_PLUGIN_TOOLS.md`,
затем `integrations/ai_plugins/README.md`. Выполнить bridge.py doctor в текущей среде.
Наличие файлов не подтверждает доступность пакетов/аккаунта. BulkPublish только draft;
humanizer-ru диагностирует, авторские правила и утверждения сохраняются.

