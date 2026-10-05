---
id: AR-20260903-003
title: Marketing Skills for AI Agents — библиотека маркетинговых agent skills
type: methodology
status: active
language: ru
format: framework
primary_category: 04_Бизнес_и_стратегия
subcategory: 01_Личный_бренд_и_маркетинг
created: 2026-09-03
updated: 2026-09-03
version: v1
tags:
  - marketing
  - agent-skills
  - ai-marketing
  - seo
  - cro
  - copywriting
  - analytics
  - growth
  - gtm
  - strategy
source: user
has_sample: false
sample_status: none
related_to: []
canonical_id: null
mode:
  - strategy
reference_required: false
---

## Пост
Открытая библиотека специализированных marketing skills для AI-агентов. Репозиторий объединяет прикладные сценарии по SEO, CRO, копирайтингу, рекламе, аналитике, growth, retention, продажам, GTM и маркетинговой стратегии.

## Назначение
Использовать как системную базу навыков для AI-агентов, которые выполняют маркетинговые задачи. Библиотека помогает не ограничиваться одним универсальным промптом, а подключать отдельные специализированные workflow под конкретную задачу: аудит, исследование, создание контента, оптимизацию конверсии, рекламу, аналитику, запуск, pricing, retention и другие направления.

## Структура
Базовым контекстным слоем выступает `product-marketing`: остальные skills используют его как основу для понимания продукта, аудитории и позиционирования.

Основные группы навыков:

- SEO и контент: `seo-audit`, `ai-seo`, `site-architecture`, `programmatic-seo`, `schema`, `content-strategy`, `aso`;
- CRO: `cro`, `signup`, `onboarding`, `popups`, `paywalls`;
- контент и тексты: `copywriting`, `copy-editing`, `cold-email`, `emails`, `social`, `video`, `image`, `sms`;
- платная реклама и измерение: `ads`, `ad-creative`, `ab-testing`, `analytics`, `attribution`;
- growth и retention: `referrals`, `free-tools`, `churn-prevention`, `community-marketing`, `lead-magnets`, `co-marketing`;
- продажи и GTM: `revops`, `sales-enablement`, `launch`, `pricing`, `competitors`, `competitor-profiling`, `directory-submissions`, `prospecting`;
- стратегия: `marketing-ideas`, `marketing-psychology`, `customer-research`, `marketing-plan`, `marketing-council`, `marketing-loops`, `offers`.

Skills могут ссылаться друг на друга и использоваться как связанная система, а не изолированные инструкции.

## Сценарий
1. Подключить библиотеку к AI-агенту, который поддерживает Agent Skills.
2. Сначала сформировать или обновить контекст продукта через `product-marketing`.
3. Определить маркетинговую задачу и выбрать соответствующий skill.
4. При необходимости подключить связанные skills из блока Related Skills.
5. Выполнить workflow выбранного навыка, сохраняя общий product context.
6. Для повторяющихся процессов использовать skills, ориентированные на системные циклы и автоматизацию маркетинга.

## Примечания
- Источник: https://github.com/coreyhaines31/marketingskills
- Автор репозитория: Corey Haines (`coreyhaines31`).
- Репозиторий предназначен для Claude Code, OpenAI Codex, Cursor, Windsurf и других агентов, поддерживающих Agent Skills spec.
- Библиотека распространяется по MIT License.
- В архиве уже существует отдельная адаптация подходов этого репозитория под туристическое агентство: `AI-Marketer-Simba-by-Bon-Tours-v1.0.md`. Это не дубль данной карточки, а производная прикладная версия.
- Исходный репозиторий хранит skills как отдельные markdown-файлы; при необходимости каждый отдельный skill может быть разобран и сохранён в Archivarius отдельной карточкой.
