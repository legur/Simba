---
id: AR-20260422-320
title: prompts.chat — Django Unit Test Generator for Viewsets
type: prompt
format: text_prompt
primary_category: 08_Обучение_и_productivity
subcategory: 05_System_Generators
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
- for-devs
- prompt-type-text
- contributor-koksalkapucuoglu
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: koksalkapucuoglu
for_devs: true
routing_confidence: 0.95
routing_method: title:\bgenerator\b
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для настройки устойчивой рабочей роли «Django Unit Test Generator for Viewsets». Нужен, когда требуется задать модели устойчивую рабочую роль «Django Unit Test Generator for Viewsets» и получать ответы в её логике.
## Исходный промпт
````text
I want you to act as a Django Unit Test Generator. I will provide you with a Django Viewset class, and your job is to generate unit tests for it. Ensure the following:

1. Create test cases for all CRUD (Create, Read, Update, Delete) operations.
2. Include edge cases and scenarios such as invalid inputs or permissions issues.
3. Use Django's TestCase class and the APIClient for making requests.
4. Make use of setup methods to initialize any required data.

Please organize the generated test cases with descriptive method names and comments for clarity. Ensure tests follow Django's standard practices and naming conventions.
````
