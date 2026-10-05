---
id: AR-20260422-685
title: prompts.chat — Studio Beauty Editorial (close-up, pro)
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
- contributor-dorukkurtoglu-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: dorukkurtoglu@gmail.com
for_devs: false
routing_confidence: 0.82
routing_method: image-body-portrait
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---

## Назначение
Промт для генерации изображения «Studio Beauty Editorial (close-up, pro)». Нужен, когда требуется сгенерировать портрет с нужной атмосферой, светом и ракурсом.
## Исходный промпт
````text
{
  "category": "STUDIO_BEAUTY_EDITORIAL_CLOSEUP",
  "subject": {
    "demographics": "Adult woman, 21-27, Turkish-looking, beauty campaign vibe.",
    "hair": {
      "color": "Dark brown",
      "style": "Sleek but natural (not helmet hair)",
      "texture": "Individual strands visible, subtle flyaways"
    },
    "face": {
      "shape": "Soft oval",
      "eyes": "Sharp catchlights, clean lashes",
      "makeup": "Clean glam, subtle contour, natural lip",
      "skin_details": "High fidelity pores, no airbrush",
      "micro_details": "Fine vellus hairs visible under light"
    },
    "clothing": {
      "outfit": "Minimal black top, no logos"
    },
    "accessories": {
      "jewelry": ["Silver hoops"]
    }
  },
  "pose": {
    "type": "Beauty close-up",
    "orientation": "Frontal close-up",
    "hands": "One hand lightly framing jawline (perfect anatomy)",
    "gaze": "Direct eye contact",
    "expression": "Neutral confident"
  },
  "setting": {
    "environment": "Studio seamless background",
    "background_elements": ["Clean gradient backdrop, no texture distractions"],
    "depth": "Very shallow background distraction, subject isolated"
  },
  "camera": {
    "shot_type": "Close-up portrait",
    "angle": "Eye-level",
    "focal_length_equivalent": "85mm editorial portrait feel",
    "framing": "4:5 (tight head-and-shoulders)",
    "focus": "Eyes razor sharp, skin texture preserved"
  },
  "lighting": {
    "source": "Softbox key + gentle fill + subtle rim",
    "direction": "Key slightly above and to one side",
    "highlights": "Clean speculars, not oily",
    "shadows": "Soft, sculpted, premium"
  },
  "mood_and_expression": {
    "tone": "Premium, elegant, calm",
    "atmosphere": "High-end beauty campaign"
  },
  "style_and_realism": {
    "style": "Photoreal editorial",
    "fidelity": "Extremely high detail, no smoothing"
  },
  "technical_details": {
    "aspect_ratio": "4:5",
    "noise": "Very low",
    "resolution": "High"
  },
  "constraints": {
    "adult_only": true,
    "no_text": true,
    "no_logos": true,
    "no_watermarks": true
  },
  "negative_prompt": [
    "airbrushed skin", "plastic face", "cgi",
    "extra fingers", "warped hands",
    "readable text", "logos", "watermark"
  ]
}
````
