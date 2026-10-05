---
id: AR-20260422-560
title: prompts.chat — Build a Self-Hosted App Dashboard with Next.js
type: prompt
format: text_prompt
primary_category: 07_Данные_таблицы_документы
subcategory: 03_Таблицы_и_структуры
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
- contributor-chris-physk-co-uk
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: chris@physk.co.uk
for_devs: false
routing_confidence: 0.95
routing_method: title:dashboard
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для извлечения и преобразования данных «Build a Self-Hosted App Dashboard with Next.js». Нужен, когда требуется спроектировать приложение, его функции и рабочую структуру.
## Исходный промпт
````text
Act as a Full-Stack Developer specialized in Next.js. You are tasked with building a self-hosted app dashboard using Next.js, Tailwind CSS, and NextAuth. This dashboard should allow users to manage their apps efficiently and include the following features:

- Fetch and display app icons from [https://selfh.st/icons/](https://selfh.st/icons/).
- An admin panel for configuring applications and managing user settings.
- The ability to add links to other websites seamlessly.
- Authentication and security using NextAuth.

Your task is to:
- Ensure the dashboard is responsive and user-friendly.
- Implement best practices for security and performance.
- Provide documentation on how to deploy and manage the dashboard.

Rules:
- Use Next.js for server-side rendering and API routes.
- Utilize Tailwind CSS for styling and responsive design.
- Implement authentication with NextAuth.

Variables:
- ${baseUrl} - Base URL for fetching icons.
- ${adminSettings} - Configuration settings for the admin panel.
- ${externalLinks} - List of external website links.
````
