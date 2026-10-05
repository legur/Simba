# AR-20260315-VEO-303

## Title
Veo 3.1: Travel Scene Control via Ingredients

## Type
prompt_card

## Platform
Flow / Gemini API / Vertex AI

## Purpose
Удерживать конкретную тревел-сцену: место, объект, атмосферу и повторяемые элементы окружения.

## When to use
Когда нужно показать один и тот же отель, улицу, интерьер, террасу, вид из окна, туристический объект или узнаваемый фон в серии роликов.

## Core logic
Загрузить референс локации или среды как ingredient. При наличии героя можно добавить референс героя. Текстом описывать маршрут камеры и происходящее внутри сцены.

## Prompt template
Use the uploaded location as the visual basis of the scene. Preserve architectural structure, layout, textures, dominant materials, and atmosphere. [Character or subject] moves through the space / appears in the scene. Camera: [camera move]. Time of day: [time]. Lighting: [lighting]. Mood: [mood]. Keep the location recognizable and spatially coherent.

## Short version
Same location from the reference image. Preserve layout, architecture, textures, and atmosphere. [Action]. [Camera move]. [Time of day].

## Control fields
- location_reference: required
- optional_character_reference: optional
- camera_move: required
- time_of_day: optional
- lighting: recommended
- recognizability_lock: required

## Notes
Для тревел-задач лучше не смешивать слишком много локаций в одном клипе.
Если задача рекламная, сначала закрепить hero shot локации, потом усложнять сцену людьми и движением.
