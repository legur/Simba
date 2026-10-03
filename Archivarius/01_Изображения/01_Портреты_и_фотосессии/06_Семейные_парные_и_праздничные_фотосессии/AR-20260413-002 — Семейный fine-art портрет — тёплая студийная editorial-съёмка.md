---
id: AR-20260413-002
title: Семейный fine-art портрет — тёплая студийная editorial-съёмка
type: prompt
status: active
language: multi
format: image_prompt
primary_category: 01_Изображения
subcategory: 01_Портреты_и_фотосессии
created: 2026-04-13
updated: 2026-07-16
version: v2
tags:
  - family
  - fine_art
  - editorial
  - studio
  - identity_lock
  - rembrandt_light
  - photoreal
source: uploaded_text_file_user_provided
has_sample: true
sample_status: approved
reference_required: true
related_to: []
canonical_id: null
---

## Пост
Премиальный семейный fine-art портрет с тёплой editorial-подачей.

## Назначение
Создание премиального fine-art семейного портрета четырёх человек с точным сохранением идентичности, студийным светом и editorial-подачей.

## Инструкция
1. Использовать загруженное референсное фото как единственный источник идентичности для всех четырех человек.
2. Не менять возраст, пропорции лица, кожу, волосы, черты лица и семейное сходство.
3. Если модель начинает «улучшать» лица, повторно усилить блок `Identity & Face Matching (Strict)`.
4. Если композиция распадается, отдельно усилить треугольную схему: mother center, children lower corners, father slightly behind.
5. Если фон начинает отвлекать, усилить `soft and unobtrusive dark textured studio backdrop`.
6. Если результат слишком модный и холодный, вернуть акцент на `warm, intimate, timeless aesthetic`.

## Промпт
```text
Create a professionally captured fine-art studio family portrait based strictly on the uploaded reference image. The final image should look like a high-end editorial family photograph with a warm, intimate, timeless aesthetic.
Identity & Face Matching (Strict)

Use the uploaded reference image to accurately reproduce all four individuals. Maintain exact age and identity fidelity for each subject.

Preserve precisely:
facial structure and proportions

bone structure and jawline

eye shape, spacing, and gaze direction

nose structure and lip shape

cheekbone definition

skin tone and undertone

hairstyle, hairline, and natural hair colour & texture

facial hair
Do not beautify, stylize, alter facial proportions, or invent features.
Each person must remain clearly recognizable as the same individual from the reference.
Subjects & Composition (Very strict)
Mother (Center)

Position the mother centrally as the emotional focal point of the portrait.
Appearance and clothing:
cream / ivory chunky-knit ribbed sweater

natural color hair with soft natural highlights

warm, genuine smile directed toward the camera
Pose:
seated slightly forward

her body angled subtly toward the father to create a natural sense of connection

right arm wrapped gently around her daughter

left hand lightly holding her partner’s hand
The mother and father should lean slightly toward each other in a relaxed, natural way, creating a subtle inward curve in the composition.

Mother's head should naturally tilt toward the father's head, creating a soft, affectionate family connection.
The pose must feel organic and unforced, never stiff or overly posed.
Father (Right / Slightly Behind)

Position the father behind and slightly to the right of the mother, leaning forward slightly into the composition.
Appearance and clothing:
dark charcoal or deep navy wool overshirt / shirt-jacket

tan or camel knit crewneck sweater underneath

Natural hairstyle

well-groomed beard (if present)
Pose:
leaning slightly inward toward the mother and children

head slightly inclined toward the mother so their heads gently touch

left hand resting gently on his son’s shoulder

right hand resting behind the mother or out of frame

soft confident smile toward the camera
His posture should communicate protective warmth and relaxed confidence.
Daughter (Left Foreground)

Position the daughter seated on the left side of the frame, slightly leaning toward her mother.
Appearance and clothing:
simple long-sleeve linen dress in light beige / oatmeal tone

natural hairstyle

soft natural smile directed at camera
Pose:
seated comfortably

hands resting naturally in her lap

slightly leaning inward to maintain the family connection.
Son (Right Foreground)

Position the son seated on the right side in front of the father.
Appearance and clothing:
tan T-shirt under a brown corduroy button-down shirt

matching brown trousers

natural hairstyle
Expression:
joyful smile

bright, energetic presence
Pose:
seated cross-legged or comfortably on the rug

relaxed posture.
Composition

The family should form a tight triangular composition:
mother at the central peak

children forming the lower corners

father slightly behind completing the triangle
This structure conveys stability, unity, and emotional closeness.
Subtle physical contact should be visible:
hands held between parents

arms around children

gentle shoulder touches

parents leaning naturally toward one another
Environment
Background

Dark, textured studio backdrop with painterly gradients.
Characteristics:
deep charcoal / black tones on one side

warm bronze / brown tones on the opposite side

subtle mottled texture

soft vignette toward edges
The background must remain soft and unobtrusive, enhancing the subjects.
Lighting

Use Rembrandt-style studio lighting with subtle cinematic rim separation.
Lighting setup:
primary soft key light from the upper left

creates subtle facial shadow depth

small triangle of light visible on the shadow side of faces
Add a very soft rim light or edge light from the rear-right side of the scene to create a gentle highlight along the edges of hair and shoulders.

This rim lighting should be subtle and natural, helping separate the subjects from the darker background without appearing dramatic or artificial.
Lighting qualities:
soft diffused light from large softbox

gentle falloff

cinematic portrait depth

soft catchlights in the eyes

subtle rim highlights on hair edges and shoulders.
Color Palette

Use a cohesive earth-tone palette:
creams

beiges

tans

browns

charcoal / deep navy
Clothing should feel coordinated but not identical, creating an elegant timeless style.
Environment Details

The family is seated on a neutral woven rug placed over a natural wood floor.
Visible textures:
ribbed knit sweater

corduroy fabric on the boy’s shirt

soft woven rug fibers

wood grain floor

subtle clothing fabric folds.
Camera & Technical Details
aspect ratio: 4:5 vertical portrait

ultra-high resolution studio photography

85mm portrait lens

aperture f/1.8 – f/2.8

shallow depth of field

subjects tack sharp

background softly blurred

Fine-art color grading with warm tonal balance.
Style & Mood

The portrait should feel:
warm

sentimental

elegant

timeless
The result should resemble luxury studio family portrait photography, suitable for framing or editorial family albums.
```

## Примечания
Сильные стороны:
- очень детально собрана композиция семьи
- хорошо держит иерархию персонажей и эмоциональный центр кадра
- свет, палитра и фактуры прописаны на уровне editorial portrait brief
- подходит для дорогого семейного визуала с теплой подачей

Риски:
- для генеративной модели промт очень длинный, часть деталей может потеряться
- точное воспроизведение сразу четырех лиц сложнее, чем одного или двух
- одежда и позы могут конфликтовать с реальным составом и возрастом людей на референсе
- модель может сделать картинку слишком постановочной и неестественной

Рекомендации:
- лучше использовать качественный семейный референс, где все лица хорошо видны
- если состав семьи отличается, переделать блок Subjects & Composition под реальный набор людей
- для большей естественности можно ослабить часть жестких микропоз и оставить общий композиционный каркас
- приоритетно сохранять идентичность и семейную связь, а не каждую текстильную деталь

## Дополнительные материалы

## Адаптация под reference photo
```text
Use the uploaded family reference image as the exact identity source for all four individuals. Preserve age, facial structure, proportions, bone structure, jawline, eye shape, spacing, gaze direction, nose, lips, cheekbones, skin tone, undertone, hairstyle, hairline, hair texture, natural hair color, and facial hair exactly as in the reference. Do not beautify, stylize, alter facial proportions, or invent features.

Create a professionally captured fine-art studio family portrait with a high-end editorial look and a warm, intimate, timeless aesthetic.

Composition:
Mother centered as the emotional focal point, seated slightly forward, body subtly angled toward the father, right arm around the daughter, left hand lightly holding the father’s hand. Father positioned slightly behind and to the right, leaning inward, head gently inclined toward the mother, left hand resting on the son’s shoulder. Daughter seated in the left foreground, leaning slightly inward. Son seated in the right foreground in front of the father, relaxed and joyful. The family forms a tight triangular composition with subtle physical contact and natural emotional closeness.

Wardrobe:
Mother in a cream or ivory chunky ribbed knit sweater.
Father in a dark charcoal or deep navy overshirt or shirt-jacket with a tan or camel knit crewneck underneath.
Daughter in a simple long-sleeve light beige or oatmeal linen dress.
Son in a tan T-shirt under a brown corduroy button-down shirt with matching brown trousers.

Environment and lighting:
Dark textured studio backdrop with painterly gradients, deep charcoal and warm bronze-brown tones, soft vignette. Neutral woven rug over natural wood floor. Rembrandt-style studio lighting with a soft key light from upper left and a very subtle rear-right rim light. Soft catchlights, gentle falloff, cinematic depth, warm fine-art color grading.

Camera:
4:5 vertical portrait, 85mm portrait lens look, shallow depth of field, subjects tack sharp, background softly blurred.

Mood:
warm, sentimental, elegant, timeless, luxury studio family portrait photography.
```

## S01 — семпл использования
```text
Create a luxury fine-art studio family portrait based strictly on the uploaded family reference image.

Identity matching must remain exact for all four people. Preserve age, facial structure, proportions, skin tone, hairline, hairstyle, hair texture, facial hair, and overall likeness with no beautification and no invented features.

Arrange the family in a tight triangular composition. Mother centered and slightly forward in a cream chunky-knit sweater, father slightly behind on the right in a dark overshirt with a camel knit underneath, daughter in the left foreground in a light beige linen dress, son in the right foreground in brown corduroy and tan tones. Natural physical connection between all family members, gentle smiles, relaxed premium studio posing.

Use a dark textured painterly studio background with charcoal and warm brown tones, a neutral woven rug on natural wood floor, Rembrandt-style soft lighting, subtle rear rim light, warm fine-art editorial grading, shallow depth of field, 85mm portrait look, 4:5 vertical composition.
```

## Практические заметки
Сильные стороны:
- очень детально собрана композиция семьи
- хорошо держит иерархию персонажей и эмоциональный центр кадра
- свет, палитра и фактуры прописаны на уровне editorial portrait brief
- подходит для дорогого семейного визуала с теплой подачей

Риски:
- для генеративной модели промт очень длинный, часть деталей может потеряться
- точное воспроизведение сразу четырех лиц сложнее, чем одного или двух
- одежда и позы могут конфликтовать с реальным составом и возрастом людей на референсе
- модель может сделать картинку слишком постановочной и неестественной

Рекомендации:
- лучше использовать качественный семейный референс, где все лица хорошо видны
- если состав семьи отличается, переделать блок Subjects & Composition под реальный набор людей
- для большей естественности можно ослабить часть жестких микропоз и оставить общий композиционный каркас
- приоритетно сохранять идентичность и семейную связь, а не каждую текстильную деталь

## Fix note
Самый уязвимый участок промта — одновременное требование:
- точного сходства 4 человек
- новой студийной позы
- новой одежды
- новой световой схемы

Это выполнимо не всеми моделями одинаково стабильно.
Рабочая трактовка:
главный приоритет — узнаваемость лиц и общая семейная композиция, а не буквальная точность каждой складки одежды.

## Мини-усиления
Если нужно сильнее удержать внешность:
```text
exact identity fidelity for all four individuals, no face drift, no age drift, no beautification
```

Если нужно больше естественности в позах:
```text
natural relaxed family posing, organic body language, unforced emotional connection
```

Если нужен еще более премиальный студийный вид:
```text
luxury editorial family portrait, museum-quality studio photography, refined fine-art finishing
```

## Источник/заметки
Источник — загруженный пользователем текстовый файл с промтом.
Исходный промт сохранен полностью, без сокращения и без переписывания.
Добавлены только карточка, адаптация под reference photo, S01-семпл и рабочие заметки.
