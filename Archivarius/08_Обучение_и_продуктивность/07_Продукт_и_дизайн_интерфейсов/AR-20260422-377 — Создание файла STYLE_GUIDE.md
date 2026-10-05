---
id: AR-20260422-377
title: prompts.chat — Create STYLE_GUIDE.md
type: prompt
format: structured_prompt
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
- structured_prompt
- general
- prompt-type-structured
- contributor-ilkerulusoy
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: ilkerulusoy
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для работы с моделью в роли «Create STYLE_GUIDE.md». Нужен, когда требуется создать STYLE_GUIDE.md.
## Исходный промпт
````text
{
  "role": "Style Guide Creator",
  "task": "Generate a detailed style guide",
  "sections": [
    "Overview",
    "Color Palette",
    "Typography",
    "Spacing System",
    "Component Styles",
    "Shadows & Elevation",
    "Animations & Transitions",
    "Border Radius",
    "Opacity & Transparency",
    "Common Tailwind CSS Usage"
  ],
  "details": "Provide detailed analysis and descriptions to the project style system, ensuring no important details are missed.",
  "example": "Include an example component reference design code."
}
````
