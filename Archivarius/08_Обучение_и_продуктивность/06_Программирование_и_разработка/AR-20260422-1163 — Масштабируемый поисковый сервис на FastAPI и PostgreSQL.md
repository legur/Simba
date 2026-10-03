---
id: AR-20260422-1163
title: prompts.chat — Building a Scalable Search Service with FastAPI and PostgreSQL
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
Промт для разработки или техразбора «Building a Scalable Search Service with FastAPI and PostgreSQL». Нужен, когда требуется спроектировать и реализовать backend- или search-сервис.
## Исходный промпт
````text
Act as a software engineer tasked with developing a scalable search service. You are tasked to use FastAPI along with PostgreSQL to implement a system that supports keyword and synonym searches. Your task is to:

- Develop a FastAPI application with endpoints for searching data stored in PostgreSQL.
- Implement keyword and synonym search functionalities.
- Design the system architecture to allow future integration with Elasticsearch for enhanced search capabilities.
- Plan for Kafka integration to handle search request logging and real-time updates.

Guidelines:
- Use FastAPI for creating RESTful API services.
- Utilize PostgreSQL's full-text search features for keyword search.
- Implement synonym search using a suitable library or algorithm.
- Consider scalability and code maintainability.
- Ensure the system is designed to easily extend with Elasticsearch and Kafka in the future.
````
