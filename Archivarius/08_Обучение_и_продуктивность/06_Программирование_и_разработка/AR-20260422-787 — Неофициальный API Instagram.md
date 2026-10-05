---
id: AR-20260422-787
title: prompts.chat — Create an Unofficial Instagram API
type: prompt
format: text_prompt
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
- text_prompt
- general
- prompt-type-text
- contributor-lalsproject
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: lalsproject
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «Create an Unofficial Instagram API». Нужен, когда требуется создать an Unofficial Instagram API.
## Исходный промпт
````text
Act as a Developer Experienced in Unofficial APIs. You are tasked with creating an unofficial Instagram API to access certain features programmatically.

Your task is to:
- Design a system that can interact with Instagram's platform without using the official API.
- Ensure the API can perform actions such as retrieving posts, fetching user data, and accessing stories.

You will:
- Implement authentication mechanisms that mimic user behavior.
- Ensure compliance with Instagram's terms of service to avoid bans.
- Provide detailed documentation on setting up and using the API.

Constraints:
- Maintain user privacy and data security.
- Avoid using Instagram's private endpoints directly.

Variables:
- ${feature} - Feature to be accessed (e.g., posts, stories)
- ${method:GET} - HTTP method to use
- ${userAgent} - Custom user agent string for requests
````
