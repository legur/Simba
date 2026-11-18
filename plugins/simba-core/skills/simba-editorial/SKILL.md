---
name: simba-editorial
description: Текстовая редакция Simba CORE непосредственно в ChatGPT: реальные правила из GitHub, авторские проходы, Critic/Humanizer, честные статусы и согласование. Без обязательного локального MCP и платных API.
---

# Simba CORE — ChatGPT-native редакция

**Основной вход:** пользователь дает обычное текстовое задание в этом чате ChatGPT. Не требовать PowerShell, локальных Python/MCP/Windows переменных, внешнего OpenAI API, второго чата или технического selftest, если пользователь попросил именно создать/отредактировать текст.

**Канон:** `legur/Simba@main`, `ROUTER_v10.1.md`, `SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md`, `SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md`, `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CHATGPT_NATIVE_EDITORIAL.md`. GitHub — правила и история, ChatGPT — исполнение и выдача. Прочитать нужные профильные файлы, факты, Intrigan/TIA и живые источники через доступные **подключенные инструменты**. Если обязательный файл недоступен, `BLOCKED_KB_UNAVAILABLE` с конкретным путем; не заменять старой памятью.

**Режим A (по умолчанию, `CHAT_NATIVE_SINGLE_MODEL`):** ChatGPT в рамках текущего ответа выполняет авторский проход по профилю, собственную редакторскую проверку по правилам Critic, исправление, стилистическую правку по Humanizer и повторную проверку при изменении смысла. Это не отдельные независимо вызванные агенты; итог — `CHAT_DRAFT_SELF_REVIEWED_INDEPENDENCE_UNVERIFIED` и текст для обсуждения/выбора, **не** `INTERNAL_CRITIC_PASS`/`HUMANIZER_PASS` независимых агентов, не `TEXT_READY_FOR_LEO` production gate.

**Режим B (`CHAT_NATIVE_VERIFIED_ROLE_TOOLS`):** только если в текущей сессии ChatGPT действительно доступны отдельные инструменты соответствующих ролей. Вызвать каждый инструмент по очереди, привязать к точному входному тексту, проверить возвращенный output/ревизию/SHA и реальный verdict перед следующей стадией. При отсутствии инструмента — `BLOCKED_INDEPENDENT_EXECUTOR_UNAVAILABLE` для требования независимости, а не вымышленный PASS. Наличие markdown, тестового чекера или GitHub коммита не доказывает исполнение независимого агента.

**Граница:** не запускать оплачиваемые `simba_core_run_private_pilot` или внешние модельные API без самостоятельного explicit budget opt-in. `simba_core_preflight` и `simba_core_handoff_selftest` — только **опциональная legacy-диагностика по запросу**, и даже PASS самотеста `OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION` не подтверждает работу моделей.

Результаты и правки показывать прямо в текущем чате. Утверждение Leo относится к точному тексту; публикация требует отдельного явного разрешения и readback. Не касаться Rafael, Киностудии, рендеринга, клиентских данных или архивных APPROVED без прямого поручения.
