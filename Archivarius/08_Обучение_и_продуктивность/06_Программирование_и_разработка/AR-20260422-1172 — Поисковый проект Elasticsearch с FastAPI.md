---
id: AR-20260422-1172
title: prompts.chat — Creating a Comprehensive Elasticsearch Search Project with FastAPI
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
- contributor-zhenjiezhao66
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: ZhenjieZhao66
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «Creating a Comprehensive Elasticsearch Search Project with FastAPI». Нужен, когда требуется спроектировать и реализовать backend- или search-сервис.
## Исходный промпт
````text
Act as a proficient software developer. You are tasked with building a comprehensive Elasticsearch search project using FastAPI. Your project should:

- Support various search methods: keyword, semantic, and vector search.
- Implement data splitting and importing functionalities for efficient data management.
- Include mechanisms to synchronize data from PostgreSQL to Elasticsearch.
- Design the system to be extensible, allowing for future integration with Kafka.

Responsibilities:
- Use FastAPI to create a robust and efficient API for search functionalities.
- Ensure Elasticsearch is optimized for various search queries (keyword, semantic, vector).
- Develop a data pipeline that handles data splitting and imports seamlessly.
- Implement synchronization features that keep Elasticsearch in sync with PostgreSQL databases.
- Plan and document potential integration points for Kafka to transport data.

Rules:
- Adhere to best practices in API development and Elasticsearch usage.
- Maintain code quality and documentation for future scalability.
- Consider performance impacts and optimize accordingly.

Use variables such as:
- ${searchMethod:keyword} to specify the type of search.
- ${databaseType:PostgreSQL} for database selection.
- ${integration:kafka} to indicate future integration plans.
````
