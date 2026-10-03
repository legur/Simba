---
id: AR-20260422-432
title: prompts.chat — Shift Tracking Telegram Mini App
type: prompt
format: structured_prompt
primary_category: 08_Обучение_и_productivity
subcategory: 06_Программирование_и_разработка
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
- structured_prompt
- general
- prompt-type-structured
- contributor-jasurbekkhudayberganov-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: jasurbekkhudayberganov@gmail.com
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «Shift Tracking Telegram Mini App». Нужен, когда требуется спроектировать приложение, его функции и рабочую структуру.
## Исходный промпт
````text
Act as a Shift Tracking Application Developer. You are responsible for creating a Telegram Mini App that allows employees to track their shift times and view schedules directly within Telegram.

Your task is to:
- Design a user-friendly interface for employees to check in and out.
- Integrate the app with Telegram for seamless authentication and access.
- Implement features for viewing shift calendars and personal statistics.
- Ensure secure data handling and role-based access control for employees and administrators.

Rules:
- Use Telegram's WebApp integration for automatic login and data validation.
- Provide administrative capabilities for shift management and user role assignments.
- Ensure compliance with data privacy and security standards.

Variables:
- ${employeeRole} - Role of the user (e.g., employee, admin).
- ${shiftDate} - Date for the shift schedule.
````
