# Archivarius Card Schema v2.0

## Обязательный front matter

```yaml
id: AR-20260306-061
title: POV из холодильника
type: prompt
status: active
language: en
created: 2026-03-06
updated: 2026-03-06
tags:
  - pov
  - fridge
  - fisheye
has_sample: false
sample_status: none
source: user
```

## Допустимые значения поля type
- prompt
- prompt_pack
- guide
- methodology

## Допустимые значения поля status
- draft
- active
- needs_fix
- archived
- duplicate

## Дополнительные поля

```yaml
format: post_instruction_prompt
platform:
  - ChatGPT
mode:
  - image-to-image
variables:
  - season
aspect_ratio: 4:5
reference_required: true
sample_path: 03_SAMPLES/AR-20260306-061/S01.webp
related_to: []
canonical_id: null
```

## Правила по телу карточки

### Для prompt
Обязательные секции:
- Пост
- Инструкция
- Промпт

### Для prompt_pack
Обязательные секции:
- Пост
- Инструкция
- Промпты

### Для guide
Обязательные секции:
- Пост
- Шаги
- Промпт или Промпты

### Для methodology
Обязательные секции:
- Пост
- Назначение
- Структура
- Промпт или Сценарий

## Правило промпта
Любой промпт должен находиться внутри блока:

```text
...
```

Если промпт не выделен явно, карточка должна получать статус `needs_fix`.
