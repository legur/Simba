---
id: AR-20260122-031
title: Skyfall - падение с неба (кадры + Kling)
type: prompt
status: active
language: ru
format: post_instruction_prompt
primary_category: 02_Видео_и_анимация
subcategory: 01_Image_to_Video
platform:
  - unknown
mode:
  - unspecified
created: 2026-01-22
updated: 2026-03-06
tags:
  - skyfall
  - падение
  - неба
  - кадры
  - kling
has_sample: false
sample_status: none
source: migrated
related_to: []
canonical_id: null
---

## Пост
Сгенерировать набор кадров для трендового видео "Skyfall" (падение с неба) и собрать видео в Kling.
- VeoSeeBot / neuroplace.ai
- Nano Banana Pro (image-to-image)
- Kling 2.5 Turbo (video)

## Инструкция
1. Откройте нужный инструмент
2. Загрузите референс, если он требуется
3. Вставьте промпт
4. При необходимости отредактируйте переменные

## Промпт
```text
Generate a person from photo 1. The location is very high in the sky at a slightly pinkish sunset. A man is in a horizontal position with a falling effect. The man’s face is calm, he is falling backwards. The frame is at human eye level, and we see the full body. Movie shot, slightly blurred background, beautiful color correction.
(the falling person/object)

---

Take a picture from below as this man is very high in the sky, very small, slightly visible because he is far away. The camera is looking up, the sky has the same color. The angle is from bottom to top. The person has his back toward us, and we are looking up at the sky as in photo 2. (Distant top shot)

---

A smooth camera movement downward, a man falling from the sky with natural falling motion.

---

Используй первое изображение как основной референс сцены и композиции с левитацией в розовом небе на закате, второе изображение используй как точный референс внешности лица, сохранить идентичность лица на 100%, ту же форму лица, нос, губы, глаза, кожу, возраст и мимику, помести этого персонажа в ту же сцену с левитацией в облаках, камера находится близко к лицу, портретный кадр, легкий наклон головы, взгляд направлен вверх, лицо слегка повернуто в сторону камеры, волосы приподняты и мягко развеваются в воздухе как при падении, без эффекта ветра, естественная гравитация, спокойное выражение лица, мягкая легкая улыбка, розовое кинематографичное освещение закатного неба, мягкие теплые тени, фотореализм, высокая детализация кожи, натуральная текстура кожи без пластика.
```

## Source Snapshot
```md
# AR-20260122-031 - Skyfall - падение с неба (кадры + Kling)

## Назначение
Сгенерировать набор кадров для трендового видео "Skyfall" (падение с неба) и собрать видео в Kling.

## Инструменты
- VeoSeeBot / neuroplace.ai
- Nano Banana Pro (image-to-image)
- Kling 2.5 Turbo (video)

## Входные данные
- Фото 1 - человек/объект в полный рост (референс)
- Опционально - селфи (для точной идентичности лица в крупном плане)

## Выход
- Кадр 1 - близкий (full body, человек в падении)
- Кадр 2 - дальний (широкий план, человек маленький в небе)
- Видео (Kling) по 1-му и 2-му кадру
- Доп. макро-кадры (руки/телефон/часы/лицо) - опционально

## Пайплайн (как в туториале)
### Шаг 1 - Кадр падения (Nano Banana Pro)
Prompt (EN):
```
Generate a person from photo 1. The location is very high in the sky at a slightly pinkish sunset. A man is in a horizontal position with a falling effect. The man’s face is calm, he is falling backwards. The frame is at human eye level, and we see the full body. Movie shot, slightly blurred background, beautiful color correction.
(the falling person/object)
```

### Шаг 2 - Широкий кадр снизу (Nano Banana Pro)
Prompt (EN):
```
Take a picture from below as this man is very high in the sky, very small, slightly visible because he is far away. The camera is looking up, the sky has the same color. The angle is from bottom to top. The person has his back toward us, and we are looking up at the sky as in photo 2. (Distant top shot)
```

### Шаг 3 - Видео (Kling 2.5 Turbo)
Prompt (EN):
```
A smooth camera movement downward, a man falling from the sky with natural falling motion.
```

### Шаг 4 - Макро-кадры (Nano Banana Pro, опционально)
Пример:
- "Сделай макро фото iphone в руках персонажа из фото"

Если нужно приблизить лицо (2 референса):
```
Используй первое изображение как основной референс сцены и композиции с левитацией в розовом небе на закате, второе изображение используй как точный референс внешности лица, сохранить идентичность лица на 100%, ту же форму лица, нос, губы, глаза, кожу, возраст и мимику, помести этого персонажа в ту же сцену с левитацией в облаках, камера находится близко к лицу, портретный кадр, легкий наклон головы, взгляд направлен вверх, лицо слегка повернуто в сторону камеры, волосы приподняты и мягко развеваются в воздухе как при падении, без эффекта ветра, естественная гравитация, спокойное выражение лица, мягкая легкая улыбка, розовое кинематографичное освещение закатного неба, мягкие теплые тени, фотореализм, высокая детализация кожи, натуральная текстура кожи без пластика.
```

### Шаг 5 - Оживление всех кадров (Kling)
Подсказка:
- "slow motion effect"
- "slow movement"
- "the person/object is falling downward"

## Негативные ограничения (рекомендуемо)
- no text, no watermark, no logos, no UI
- no extra limbs, no face distortion
- keep clothing consistent with reference

## Семпл
- S01: AR-20260122-031__S01.webp

## Метаданные
- source: @neuro_smoking / dailyprompts (tutorial)
- tags: skyfall, falling, sunset, cinematic, nano-banana, kling, tutorial
- status: fixed
- sample_policy: generate once on card add, store in archivarius archive
```
