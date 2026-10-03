---
id: AR-20260903-013
title: YouMind — App - Web Design — внешний пакет
type: prompt_pack
status: needs_fix
language: multi
format: image_prompt
primary_category: 08_Обучение_и_productivity
subcategory: 07_Продукт_и_UI_UX
created: 2026-09-03
updated: 2026-09-03
version: v1
tags:
  - youmind
  - github_import
  - image_prompt
  - external_library
  - prompt_pack
source: YouMind-OpenLab/ai-image-prompts-skill
source_url: https://github.com/YouMind-OpenLab/ai-image-prompts-skill
source_file: references/app-web-design.json
source_file_url: https://raw.githubusercontent.com/YouMind-OpenLab/ai-image-prompts-skill/main/references/app-web-design.json
source_batch: youmind_ai_image_prompts_20260903
external_collection: true
external_item_count: 236
reviewed: false
routing_confidence: 0.85
routing_method: source_category_with_runtime_reclassification
has_sample: true
sample_status: external
related_to: []
canonical_id: null
---

## Пост
Внешний пакет YouMind «App - Web Design»: 236 промптов для генерации изображений. Зарегистрирован в Archivarius как массовый внешний автоимпорт, без включения в PROD до ручной проверки конкретных элементов.

## Назначение
Использовать как подключённый каталог промптов по теме «App - Web Design». Карточка является маршрутизатором к внешней коллекции, а не нормализованной копией всех 236 промптов.

## Инструкция
1. При поиске обращаться к `source_file_url` или репозиторию GitHub.
2. Выбирать конкретные записи по полям `title`, `description` и `content`.
3. Перед использованием повторно классифицировать найденный промпт по фактическому конечному артефакту, а не слепо доверять исходной категории YouMind.
4. Если промпт будет добавляться в PROD Archivarius, создать отдельную нормализованную карточку с полным исходным текстом, русским переводом при необходимости и `reviewed: true` после проверки.

## Промпты
Полный массив находится во внешнем JSON-файле:

```text
https://raw.githubusercontent.com/YouMind-OpenLab/ai-image-prompts-skill/main/references/app-web-design.json
```

Количество элементов на момент регистрации: **236**.

## Примечания
UI-макеты, веб-дизайн, экраны приложений и визуальные интерфейсы. Если промпт просит именно реализовать интерфейс кодом, маршрутизировать в программирование и разработку.

Этот пакет намеренно имеет `status: needs_fix`: текущий Drive-коннектор не позволяет безопасно зеркалировать весь многомегабайтный JSON как тысячи отдельных `.md`-карточек в одном действии. Содержимое не считается ручной проверкой и по правилам Archivarius не должно автоматически попадать в PROD.
