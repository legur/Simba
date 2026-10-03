---
id: AR-20260422-1080
title: prompts.chat — Influencer Candid Bedtime Selfie
type: prompt
format: structured_prompt
primary_category: 01_Изображения
subcategory: 01_Портреты_и_фотосессии
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
- contributor-mujdecialperenn-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: mujdecialperenn@gmail.com
for_devs: false
routing_confidence: 0.95
routing_method: title:\bselfie\b
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для генерации изображения «Influencer Candid Bedtime Selfie». Нужен, когда требуется создать визуал по сценарию «Influencer Candid Bedtime Selfie».
## Исходный промпт
````text
{
  "meta": {
    "aspect_ratio": "9:16",
    "quality": "raw_photo, uncompressed, 8k",
    "camera": "iPhone 15 Pro Max front camera",
    "lens": "23mm f/1.9",
    "style": "influencer candid bedtime selfie, clean girl aesthetic, youthful natural beauty, ultra-realistic",
    "iso": "800 (clean, low noise)"
  },
  "scene": {
    "location": "Luxury bedroom interior",
    "environment": [
      "high thread count white or cream bedding",
      "fluffy down pillows",
      "soft warm ambient light from background",
      "hint of a silk headboard"
    ],
    "time": "Late night / Bedtime",
    "atmosphere": "intimate, relaxing, soft luxury, innocent"
  },
  "lighting": {
    "type": "Phone screen softbox effect",
    "key_light": "Soft cool light from phone screen illuminating the face center, enhancing skin smoothness",
    "fill_light": "Warm, dim bedside lamp in background creating depth",
    "shadows": "Very gentle, soft shadows",
    "highlights": "Creamy, dewy highlights on the nose bridge and cheekbones (hydrated glow)"
  },
  "camera_perspective": {
    "pov": "Selfie (arm extended)",
    "angle": "High angle, slightly tilted head (flattering portrait angle)",
    "framing": "Close-up on face and upper chest",
    "focus": "Sharp focus on eyes and lips, soft focus on hair and background"
  },
  "subject": {
    "demographics": {
      "gender": "female",
      "age": "24 years old",
      "ethnicity": "Northern European (fair skin)",
      "look": "Fresh-faced, youthful model off-duty"
    },
    "face": {
      "structure": "Symmetrical soft features, youthful plump cheeks, defined but soft jawline, delicate nose",
      "skin_texture": "smooth, youthful complexion, 'glass skin' effect (ultra-hydrated and plump), porcelain/pale skin tone, extremely fine texture with minimal visible pores, radiant healthy glow, naturally flawless without heavy texture",
      "lips": "Naturally plush lips, soft pink/rosy natural pigment, hydrated balm texture",
      "eyes": "Large, expressive piercing blue eyes, clear bright iris detail, long natural dark lashes, looking into camera lens",
      "brows": "Naturally thick, groomed, soft taupe color matching hair roots"
    },
    "hair": {
      "color": "Cool-toned honey blonde with platinum highlights",
      "style": "Chic blunt bob cut, chin-length, slightly tousled on the pillow but maintaining shape",
      "texture": "Silky, healthy shine, fine soft hair texture"
    },
    "expression": "Soft, innocent, confident but sleepy, slight gentle smile"
  },
  "outfit": {
    "headwear": {
      "item": "Luxury silk sleep mask",
      "position": "Pushed up onto the forehead/hair",
      "color": "Champagne gold or blush pink",
      "texture": "Satin sheen"
    },
    "top": {
      "type": "Silk or satin pajama camisole",
      "color": "Matching champagne or soft white",
      "details": "Delicate lace trim at neckline, thin straps, fabric draping naturally over collarbones"
    }
  },
  "details": {
    "realism_focus": [
      "Intense dewy moisturizer sheen on skin",
      "Realistic lip balm texture",
      "Reflection of phone screen in the clear blue pupils",
      "Softness of the fabrics",
      "Focus on dewy hydration sheen rather than heavy skin texture"
    ],
    "negative_prompt": [
      "heavy makeup",
      "foundation",
      "cakey skin",
      "plastic skin",
      "airbrushed",
      "acne",
      "blemishes",
      "dark hair",
      "brown eyes",
      "long hair",
      "large pores",
      "rough texture",
      "wrinkles",
      "aged skin",
      "mature appearance"
    ]
  }
}
````
