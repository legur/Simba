---
id: AR-20260422-952
title: prompts.chat — Meta-prompt
type: prompt
format: text_prompt
primary_category: 09_Гайды_и_паки
subcategory: 03_Role_Masks_и_Expert_Personas
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
- contributor-princesharma2899-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: princesharma2899@gmail.com
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или улучшения промтов «Meta-prompt». Нужен, когда требуется собрать или улучшить промт под конкретную задачу.
## Исходный промпт
````text
You are an elite prompt engineering expert. Your task is to create the perfect, highly optimized prompt for my exact need.

My goal: ${${describe_what_you_want_in_detail:I want to sell notion template on my personal website. And I heard of polar.sh where I can integrate my payment gateway. I want you to tell me the following: 1. will I need a paid domain to take real payments? 2. Do i need to verify my website with indian income tax to take international payments? 3. Can I run this as a freelance business?}}

Requirements / style:
• Use chain-of-thought (let it think step by step)
• Include 2-3 strong examples (few-shot)
• Use role-playing (give it a very specific expert persona)
• Break complex tasks into subtasks / sub-prompts / chain of prompts
• Add output format instructions (JSON, markdown table, etc.)
• Use delimiters, XML tags, or clear sections
• Maximize clarity, reduce hallucinations, increase reasoning depth

Create 3 versions:
1. Short & efficient version
2. Very detailed & structured version (my favorite style)
3. Chain-of-thought heavy version with sub-steps

Now create the best possible prompt(s) for me:
````
