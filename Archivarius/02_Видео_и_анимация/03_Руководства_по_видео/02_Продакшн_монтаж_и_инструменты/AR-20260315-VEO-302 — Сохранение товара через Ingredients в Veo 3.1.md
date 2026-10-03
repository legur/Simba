# AR-20260315-VEO-302

## Title
Veo 3.1: Product / Object Control via Ingredients

## Type
prompt_card

## Platform
Flow / Gemini API / Vertex AI

## Purpose
Сохранять форму, материал, цвет и узнаваемость товара или объекта в ролике.

## When to use
Для рекламы продукта, предметной съемки, упаковки, витрин, брендовых объектов.

## Core logic
Загрузить объект как отдельный ingredient. Текстом управлять только сценарием показа: как объект движется, где находится, как на него работает свет и камера.

## Prompt template
Use the uploaded object as the same product throughout the clip. Preserve shape, proportions, materials, surface finish, label placement, and key colors. Show the product in [environment]. Action: [action]. Camera: [camera]. Lighting: [lighting]. Keep the object accurate and recognizable, without redesigning or restyling it.

## Short version
Same product from the reference image. Keep shape, materials, and colors accurate. [Action] in [environment]. [Camera]. [Lighting].

## Control fields
- product_reference: required
- environment: optional
- action: required
- camera: recommended
- lighting: recommended
- no_redesign: required

## Notes
Если важна упаковка, отдельно прописывать label placement.
Если объект брендовый, явно запрещать redesign/restyle.
Для luxury/object shots полезно давать спокойное действие и четкий свет, а не сложную хореографию.
