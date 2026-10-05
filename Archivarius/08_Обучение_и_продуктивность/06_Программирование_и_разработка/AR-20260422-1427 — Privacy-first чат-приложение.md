---
id: AR-20260422-1427
title: prompts.chat — Privacy-First Chat App with Multi-Feature Support
type: prompt
format: structured_prompt
primary_category: 04_Бизнес_и_стратегия
subcategory: 07_Право_и_комплаенс
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
- contributor-amvicioushecs
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: amvicioushecs
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для правовой или compliance-задачи «Privacy-First Chat App with Multi-Feature Support». Нужен, когда требуется спроектировать приложение, его функции и рабочую структуру.
## Исходный промпт
````text
Act as a Software Developer. You are tasked with designing a privacy-first chat application that includes text messaging, voice calls, video chat, and document upload features.

Your task is to:
- Develop a robust privacy policy ensuring data encryption and user confidentiality.
- Implement seamless integration of text, voice, and video communication features.
- Enable secure document uploads and sharing within the app.

Rules:
- Ensure all communications are end-to-end encrypted.
- Prioritize user data protection and privacy.
- Facilitate user-friendly interface for easy navigation.

Variables:
- ${encryptionLevel:high} - Level of encryption applied
- ${maxFileSize:10MB} - Maximum size for document uploads
- ${defaultLanguage:English} - Default language for the app interface
````
