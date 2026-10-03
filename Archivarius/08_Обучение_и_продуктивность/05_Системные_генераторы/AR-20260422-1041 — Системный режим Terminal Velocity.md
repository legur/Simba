---
id: AR-20260422-1041
title: prompts.chat — Terminal Velocity
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
Промт для настройки устойчивой рабочей роли «Terminal Velocity». Нужен, когда требуется задать модели устойчивую рабочую роль «Terminal Velocity» и получать ответы в её логике.
## Исходный промпт
````text
{
  "title": "Terminal Velocity",
  "description": "A high-stakes action frame capturing a woman sprinting through a crumbling industrial tunnel amidst sparks and chaos.",
  "prompt": "You will perform an image edit to create an Ultra-Photorealistic, Movie-Quality action shot. The result must be photorealistic, highly detailed, and feature cinematic lighting. Emulate the look of a blockbuster film shot on Arri Alexa with a shallow depth of field. Depict Subject 1 sprinting towards the camera in a dark, collapsing industrial tunnel, surrounded by flying sparks and falling debris.",
  "details": {
    "year": "Contemporary Action Thriller",
    "genre": "Cinematic Photorealism",
    "location": "A dilapidated, steam-filled industrial maintenance tunnel with flickering lights and exposed wiring.",
    "lighting": [
      "High-contrast chiaroscuro",
      "Warm backlight from exploding sparks",
      "Cold, gritty fluorescent ambient light",
      "Volumetric lighting through steam"
    ],
    "camera_angle": "Low-angle frontal tracking shot with motion blur on the background.",
    "emotion": [
      "Adrenaline",
      "Panic",
      "Determination"
    ],
    "color_palette": [
      "Concrete grey",
      "Hazard orange",
      "Steel blue",
      "Deep shadow black"
    ],
    "atmosphere": [
      "Chaotic",
      "Explosive",
      "Gritty",
      "Claustrophobic"
    ],
    "environmental_elements": "Cascading electrical sparks, motion-blurred debris, steam venting from broken pipes, wet concrete floor reflecting the chaos.",
    "subject1": {
      "costume": "black mini skirt, white crop top, leather fingerless gloves",
      "subject_expression": "Intense focus with mouth slightly parted in exertion, sweat glistening on skin, hair flying back.",
      "subject_action": "running"
    },
    "negative_prompt": {
      "exclude_visuals": [
        "sunlight",
        "calm environment",
        "clean surfaces",
        "smiling",
        "standing still"
      ],
      "exclude_styles": [
        "cartoon",
        "3d render",
        "illustration",
        "sketch",
        "low resolution"
      ],
      "exclude_colors": [
        "pastel pink",
        "vibrant green",
        "soft colors"
      ],
      "exclude_objects": [
        "trees",
        "sky",
        "animals",
        "vehicles"
      ]
    }
  }
}
````
