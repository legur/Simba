# AR-20260315-VEO-301

## Title
Veo 3.1: Character Consistency via Ingredients

## Type
prompt_card

## Platform
Flow / Gemini API / Vertex AI

## Purpose
Удерживать одного и того же героя между несколькими сценами.

## When to use
Когда нужен один и тот же человек или персонаж в серии кадров, но меняются фон, действие, настроение или ракурс.

## Core logic
Сначала загрузить референс персонажа как ingredient, затем текстом описывать только действие, камеру, свет и среду.

## Prompt template
Use the uploaded character as the same person in every shot. Keep face structure, hairstyle, body proportions, age impression, and clothing identity consistent. Place the character in [environment]. The character [action]. Camera: [camera]. Lighting: [lighting]. Mood: [mood]. Preserve likeness and visual continuity across the shot.

## Short version
Same character from the reference image. Preserve face, proportions, and clothing identity. [Action] in [environment]. [Camera]. [Lighting].

## Control fields
- character_reference: required
- environment: optional
- action: required
- camera: recommended
- lighting: recommended
- mood: optional
- continuity_lock: preserve face, silhouette, clothes

## Notes
Не перегружать промт биографией персонажа.
Не просить модель заново «придумать» героя, если он уже дан референсом.
Лучше менять 1-2 параметра за итерацию: фон, затем движение, затем свет.
