# Simba — Bon Tours Content System

Приватный репозиторий канонической системы создания контента Simba.

**Источник истины:** `legur/Simba@main`  
**Google Drive `New Simba`:** архив миграции, не рабочий runtime.

## Как запускать

В Codex/агентной среде достаточно открыть этот репозиторий и дать обычную задачу:

- «Сделай рекламный пост по этому предложению»
- «Сделай новость»
- «Запусти Симбу»
- «Теперь Рафаэль»
- «Измени правило системы…»

Корневой `AGENTS.md` задаёт среде точку входа и реальные пути файлов.

Базовый старт любой контентной задачи:

```text
AGENTS.md
  → ROUTER_v10.1.md
  → KNOWLEDGE_MAP.md
  → KB_RUNTIME_PROTOCOL.md
  → профильный модуль
  → обязательный KB context
  → результат
```

Для системного изменения дополнительно используется `META-Governance-v8.1.md`.

## Основной production flow

```text
SOURCE / TASK
  → ROUTER
  → PROFILE MODULE
  → KB PREFLIGHT
  → EXECUTION
  → VALIDATION
  → RESULT TO LEO
```

Для рекламного текста Simba:

```text
AI-Маркетолог (если нужна стратегия)
  → Simba
  → INTERNAL_CRITIC_MODE
  → Simba repair/finalize
  → TEXT_READY_FOR_LEO
```

После утверждения текста:

```text
LEO_APPROVAL
  → APPROVED_TEXT
  → Content Library write-back
  → Rafael
  → 5 previews
  → Leo selects
  → separate final 1:1 render
```

Автопубликации без отдельного утверждённого процесса нет.

## Структура

```text
/
├── AGENTS.md
├── ROUTER_v10.1.md
├── META-Governance-v8.1.md
├── AI-Marketer-Simba-by-Bon-Tours-v5.0.md
├── Симба (Писатель)/
│   ├── Simba-v5.0.md
│   ├── Humanizer-v1.4.md
│   ├── News-v1.2.md
│   ├── Travel-v1.3.md
│   ├── Info-v1.2.md
│   ├── Leo-v1.3.md
│   ├── Lumiere-v1.1.md
│   └── Session-Logs/
├── Critic/
├── Rafael/
├── Сценарист/
├── Wix-Formatter/
└── SIMBA KNOWLEDGE BASE/
    ├── 00_CORE/
    ├── 01_BRAND/
    ├── 02_AUDIENCE/
    ├── 03_CONTENT_LIBRARY/
    ├── 04_BUSINESS/
    ├── 05_OPERATIONAL_RULES/
    ├── 06_AGENT_WORKFLOWS/
    └── 07_LEARNINGS/
```

## Что является каноническим

Рабочие системные файлы обновляются **на месте**. Git хранит историю версий, поэтому для рабочей версии не создаются `old`, `backup`, `final-final` и параллельные копии.

Исторические материалы в Content Library и Session Logs являются отдельными объектами и сохраняются как история.

## Knowledge Base

Перед содержательной работой система обязана пройти KB PREFLIGHT. Полные правила находятся в:

- `SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md`
- `SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md`

Content Library используется для стиля, истории решений и контроля повторов — **не** как источник текущих цен, наличия или условий.

## Изменение системы

При изменении Router, META, агента, workflow или Knowledge Base:

1. прочитать `META-Governance-v8.1.md`;
2. изменить канонический файл;
3. сделать Git-коммит;
4. выполнить required `KB_LINT.md`;
5. проверить результат после записи.

## Миграция

Система была перенесена из Google Drive `New Simba` в GitHub 02.10.2026.

Google Drive не синхронизируется автоматически с репозиторием. Новые системные изменения и production write-back должны происходить в GitHub.
