---
id: AR-20260413-003
title: Luxury editorial full-body portrait — white suit in upscale marble interior with strict identity lock
type: prompt
status: active
language: en
format: image_prompt
platform:
  - ChatGPT Image
  - Nano Banana
  - any_image_model
mode:
  - image-generation
  - image-edit
primary_category: 01_Изображения
subcategory: 01_Портреты_и_фотосессии
tags:
  - luxury editorial portrait
  - full body portrait
  - white suit
  - identity preservation
  - marble interior
  - fashion editorial
  - corporate lobby
  - premium portrait
  - 50mm look
  - reference photo
source: user_provided_prompt
created_at: 2026-04-13
updated_at: 2026-04-13
created: 2026-04-13
updated: 2026-04-13
has_sample: true
sample_status: included
related_to: []
canonical_id: null
reference_required: true
---

## Назначение
Промт для создания полнофигурного luxury editorial-портрета по референсу с жестким сохранением лица, белым костюмом, премиальным интерьером из мрамора и magazine-ready подачей.

## Когда использовать
Подходит для:
- premium personal branding visuals
- hero portraits для соцсетей и сайта
- fashion/editorial стилизации по референсу
- имиджевых бизнес-портретов
- визуалов в эстетике luxury lobby / hotel / corporate editorial

## Инструкция
1. Использовать референсное фото как единственный источник идентичности лица.
2. Не менять форму лица, возрастное впечатление, кожу, бороду, взгляд и базовое выражение.
3. Если модель уводит внешность, отдельно усилить блок `100% facial identity lock` и повторить `no face drift`.
4. Если костюм начинает сливаться с мрамором, усилить разделение по свету и контрасту.
5. Если интерьер перетягивает внимание, ослабить детали фона и оставить его как luxury context, а не главную тему кадра.
6. Если поза выглядит слишком постановочно, ослабить микродетали рук и оставить общий спокойный confident stance.

## Исходный промпт
```text
Create a high-resolution full-body luxury editorial portrait using the exact face from the reference image with 100% facial identity lock.

Do not alter facial structure, proportions, skin tone, beard, jawline, nose, lips, eyes, or expression.
Subject & Pose
A stylish young man stands leaning naturally against a polished white-grey marble pillar inside an upscale modern interior.

Right shoulder and upper back resting against the pillar
Right hand casually placed inside the trouser pocket
Left hand gently adjusting the blazer lapel near the chest
Legs crossed casually at the ankles
Head turned slightly to the right, gaze looking off-frame
Expression calm, confident, thoughtful, and composed (no smile)
Outfit & Styling
Perfectly tailored white luxury suit with structured blazer and slim-fit trousers
Deep maroon dress shirt, clean fit, top buttons open
Black polished leather formal shoes
Neatly styled hair with natural volume and side part
Well-groomed natural beard and mustache
Subtle luxury wristwatch visible on the left wrist
Environment & Background (IMPORTANT)
Elegant high-end interior space, resembling a luxury hotel or premium corporate lobby
Large marble columns, reflective marble flooring
Background contains glass walls, gold/brass architectural accents, and crystal chandeliers softly glowing
Large windows reveal a softly blurred urban city skyline in the distance
Gold rope barriers and minimal furniture elements visible but out of focus
Strong sense of depth, scale, and architectural symmetry
Lighting & Color Tone
Soft, diffused natural daylight entering from large windows
Balanced exposure with no harsh shadows
Gentle highlights on the white suit, smooth shadow falloff
Subtle warm interior lights (chandelier glow) mixed with neutral daylight
Color grading: neutral-to-warm luxury tone
Creamy whites
Soft marble greys
Rich maroon shirt
Natural skin tones
Clean, realistic contrast with polished editorial finish
Camera & Composition
Full-body vertical framing
Eye-level camera angle
Moderate depth of field
Subject sharply in focus, background softly blurred
Shot with a 50mm lens look, natural perspective
Overall Style
Ultra-realistic, premium fashion editorial photography
Professional, elegant, masculine, confident aesthetic
High-end branding / magazine-ready look
Clean, luxurious, modern realism
```

## Адаптация под reference photo
```text id="u7v2pa"
Use the attached reference photo as the exact identity source and preserve facial identity with no face drift. Keep facial structure, proportions, skin tone, beard, jawline, nose, lips, eyes, and overall expression true to the reference.

Create a high-resolution full-body luxury editorial portrait of the same man standing naturally against a polished white-grey marble pillar inside an upscale modern interior.

Pose:
right shoulder and upper back resting against the pillar,
right hand casually inside the trouser pocket,
left hand gently adjusting the blazer lapel near the chest,
legs crossed casually at the ankles,
head turned slightly to the right,
gaze looking off-frame,
expression calm, confident, thoughtful, and composed, no smile.

Outfit:
perfectly tailored white luxury suit with structured blazer and slim-fit trousers,
deep maroon dress shirt with the top buttons open,
black polished leather formal shoes,
subtle luxury wristwatch on the left wrist,
neatly styled hair with natural volume and side part,
well-groomed natural beard and mustache.

Environment:
elegant luxury hotel or premium corporate lobby feel,
large marble columns,
reflective marble flooring,
glass walls,
gold or brass accents,
softly glowing crystal chandeliers,
large windows with a softly blurred urban skyline,
gold rope barriers and minimal furniture softly out of focus,
strong architectural depth and symmetry.

Lighting and color:
soft diffused daylight from large windows,
balanced exposure,
gentle highlights on the white suit,
subtle warm interior glow mixed with neutral daylight,
neutral-to-warm luxury grading,
creamy whites, soft marble greys, rich maroon, natural skin tones.

Camera:
full-body vertical framing,
eye-level angle,
moderate depth of field,
subject sharp, background softly blurred,
50mm editorial portrait look.

Style:
ultra-realistic premium fashion editorial photography, clean luxurious modern realism, magazine-ready.
```

## S01 — семпл использования
```text id="3l1n8m"
Use the attached reference photo as the exact face and identity reference. Preserve the same facial structure, skin tone, beard, hairline, hair texture, and calm serious expression.

Create a full-body luxury editorial portrait of the same man in a perfectly tailored white suit and deep maroon open-collar shirt, standing against a polished white-grey marble pillar inside a high-end hotel or premium corporate lobby. Right shoulder resting on the pillar, right hand in trouser pocket, left hand adjusting the blazer lapel, legs crossed at the ankles, head turned slightly right, gaze off-frame.

Reflective marble floor, glass walls, gold or brass accents, softly glowing chandeliers, distant blurred city skyline through large windows, elegant architectural symmetry. Soft natural daylight mixed with warm interior glow, neutral-warm luxury grading, sharp subject, softly blurred background, 50mm full-body editorial look, ultra-realistic, clean premium realism.
```

## Практические заметки
Сильные стороны:
- очень ясный luxury-сценарий и понятная поза
- хороший баланс между fashion portrait и business-branding visual
- белый костюм + мрамор + бордовая рубашка дают дорогой, но не кричащий образ
- промт сразу задает magazine-ready качество и глубину пространства

Риски:
- `100% facial identity lock` — сильное требование, которое модели выполняют не идеально
- белый костюм на светлом мраморном фоне может потерять контраст
- формулировка `young man` может конфликтовать с реальным возрастным впечатлением на референсе
- слишком детальный интерьер иногда забирает внимание у человека

Рекомендации:
- если главное — сходство, уменьшить сложность фона и оставить 2-3 роскошных якоря вместо полного lobby-scene
- если нужен более fashion-вид, усилить силуэт костюма и уменьшить описание архитектуры
- если нужен более бизнесовый образ, заменить chandeliers на cleaner corporate interior
- если важен белый костюм, полезно добавить separation light along shoulders and trousers

## Fix note
Самый спорный элемент промта — сочетание:
- exact face from reference
- новая полнофигурная поза
- новый роскошный интерьер
- сложная одежда с белым костюмом

На практике лучше считать приоритеты так:
1. узнаваемость лица
2. общий luxury mood
3. поза и силуэт
4. вторичные детали интерьера

## Мини-усиления
Если нужно сильнее удержать лицо:
```text id="q9c8e1"
exact face fidelity, no face drift, no age drift, preserve beard shape and natural expression
```

Если нужно лучше отделить белый костюм от фона:
```text id="f2m6rb"
subtle separation lighting and tonal contrast to keep the white suit clearly defined against the marble interior
```

Если нужен более дорогой editorial finish:
```text id="n4w7zs"
luxury magazine cover realism, refined premium styling, polished high-end editorial finish
```

## Источник/заметки
Источник — пользователь прислал промт в чат.
Исходный промт сохранен полностью, без сокращения и без переписывания.
Добавлены только карточка, адаптация под reference photo, S01-семпл и рабочие заметки.
