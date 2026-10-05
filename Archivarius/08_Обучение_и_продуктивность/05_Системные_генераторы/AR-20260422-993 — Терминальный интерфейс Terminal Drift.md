---
id: AR-20260422-993
title: prompts.chat — Terminal Drift
type: prompt
format: structured_prompt
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
- structured_prompt
- general
- prompt-type-structured
- contributor-ersinkoc
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: ersinkoc
for_devs: false
routing_confidence: 0.95
routing_method: title:\bterminal\b
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для настройки устойчивой рабочей роли «Terminal Drift». Нужен, когда требуется задать модели устойчивую рабочую роль «Terminal Drift» и получать ответы в её логике.
## Исходный промпт
````text
{
  "title": "Terminal Drift",
  "description": "A haunting visualization of a lone traveler stuck in an infinite, empty airport terminal that defies logic.",
  "prompt": "You will perform an image edit using the person from the provided photo as the main subject. Preserve her core likeness. Transform Subject 1 (female) into a solitary figure standing in an endless, windowless airport terminal. The surrounding space is a repetitive hallway of beige walls, low ceilings, and patterned carpet. There are no exits, only the endless stretch of artificial lighting and empty waiting chairs. The composition should adhere to a cinematic 1:1 aspect ratio.",
  "details": {
    "year": "Indeterminate 1990s",
    "genre": "Liminal Space",
    "location": "A vast, curving airport corridor with no windows, endless beige walls, and complex patterned carpet.",
    "lighting": [
      "Flat fluorescent overheads",
      "Uniform artificial glow",
      "No natural light source"
    ],
    "camera_angle": "Wide shot, symmetrical center-framed composition.",
    "emotion": [
      "Disassociation",
      "Unease",
      "Solitude"
    ],
    "color_palette": [
      "Beige",
      "Muted Teal",
      "Faded Maroon",
      "Off-white"
    ],
    "atmosphere": [
      "Uncanny",
      "Sterile",
      "Silent",
      "Timeless"
    ],
    "environmental_elements": "Rows of empty connected waiting chairs, commercial carpeting with a confusing pattern, generic signage with indecipherable text.",
    "subject1": {
      "costume": "A slightly oversized pastel sweater and loose trousers, appearing mundane and timeless.",
      "subject_expression": "A vacant, glazed-over stare, looking slightly past the camera into the void.",
      "subject_action": "Standing perfectly still, arms hanging loosely at her sides, holding a generic roller suitcase."
    },
    "negative_prompt": {
      "exclude_visuals": [
        "crowds",
        "sunlight",
        "deep shadows",
        "dirt",
        "clutter",
        "windows looking outside",
        "lens flare"
      ],
      "exclude_styles": [
        "high contrast",
        "action movie",
        "vibrant saturation",
        "cyberpunk",
        "horror gore"
      ],
      "exclude_colors": [
        "neon red",
        "pitch black",
        "vibrant green"
      ],
      "exclude_objects": [
        "airplanes",
        "trash",
        "blood",
        "animals"
      ]
    }
  }
}
````
