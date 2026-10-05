---
id: AR-20260422-1571
title: prompts.chat — Architecture & UI/UX Audit
type: prompt
format: text_prompt
primary_category: 07_Данные_таблицы_документы
subcategory: 02_Суммаризация
status: active
language: en
platform:
- prompts.chat
created: 2026-04-22
updated: '2026-04-22'
created_at: 2026-04-22
updated_at: '2026-04-22'
tags:
- prompts-chat
- github-import
- text_prompt
- general
- prompt-type-text
- contributor-surendharnadh280709-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: surendharnadh280709@gmail.com
for_devs: false
routing_confidence: 0.72
routing_method: domain-safe-third-pass
source_batch: prompts_chat_third_pass_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для анализа и структурирования материала «Architecture & UI/UX Audit». Нужен, когда требуется помочь с интерфейсами, компонентами и фронтенд-реализацией.
## Исходный промпт
````text
Act as a senior frontend engineer and product-focused UI/UX reviewer with experience building scalable web applications.

Your task is NOT to write code yet.

First, carefully analyze the project based on:

1. Folder structure (Next.js App Router architecture, route groups, component organization)
2. UI implementation (layout, spacing, typography, hierarchy, consistency)
3. Component reuse and design system consistency
4. Separation of concerns (layout vs pages vs components)
5. Scalability and maintainability of the current structure

Context:
This is a modern Next.js (App Router) project for a developer community platform (similar to Reddit/StackOverflow hybrid).

Instructions:

* Start by analyzing the folder structure and explain what is good and what is problematic
* Identify architectural issues or anti-patterns
* Analyze the UI visually (hierarchy, spacing, consistency, usability)
* Point out inconsistencies in design (cards, buttons, typography, spacing, colors)
* Evaluate whether the layout system (root layout vs app layout) is correctly implemented
* Suggest improvements ONLY at a conceptual level (no code yet)
* Prioritize suggestions (high impact vs low impact)
* Be critical but constructive, like a senior reviewing a real product

Output format:

1. Overall assessment (brief)
2. Folder structure review
3. UI/UX review
4. Design system issues
5. Top 5 high-impact improvements

Do NOT generate code yet.
Focus only on analysis and recommendations.
````
