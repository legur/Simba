# KB-LINT

Статус: MANDATORY LIGHTWEIGHT WRITE CHECK
Дата: 05.09.2026

## Назначение

`KB-LINT` — легкая проверка одного изменения Knowledge Base.
Он запускается после записи/обновления знания и не заменяет полный системный аудит.

Цель: не допустить, чтобы случайная правка, динамический факт, дубль или слабое наблюдение стали постоянной истиной системы.

## Когда запускать

Обязательно после:
- записи в `07_LEARNINGS`;
- promotion из Learnings в `STYLE_LEO`, `ANTI_STYLE`, `_PATTERN_TRACKER` или другой канонический rule-файл;
- добавления/изменения файла `00_CORE`;
- изменения workflow;
- изменения Archivarius trusted/blocklist governance;
- системной правки Router / META / профильного агента, если она меняет зависимость от KB.

Для сохранения нового APPROVED поста в Content Library проверяется сокращенный профиль LINT.

## Checks

### L01 — SOURCE
Понятно ли, откуда взялось знание:
- прямое решение Leo;
- текущий подтвержденный источник;
- Critic/TIA evidence;
- утвержденный/опубликованный материал;
- внешний reference.

Если источник неясен → WARNING или FAIL в зависимости от влияния.

### L02 — EVIDENCE LEVEL
Единичное наблюдение не выдано за постоянное правило.
Постоянное правило допустимо при:
- прямом системном решении Leo; или
- достаточном повторном подтверждении по принятой модели доказательности.

### L03 — PERSISTENT vs DYNAMIC
Цена, наличие, расписание, срок акции, текущий тариф, налоги, entry rules и другие изменчивые значения не записаны как постоянная истина.

Нарушение → FAIL.

### L04 — TARGET LAYER
Запись находится в правильном слое:
- Brand → `01_BRAND`;
- Audience → `02_AUDIENCE`;
- approved content/history → `03_CONTENT_LIBRARY`;
- stable business → `04_BUSINESS`;
- operational invariant → `05_OPERATIONAL_RULES`;
- workflow → `06_AGENT_WORKFLOWS`;
- evidence/learning → `07_LEARNINGS`;
- runtime architecture → `00_CORE`.

### L05 — DUPLICATE / CONFLICT
Нет смыслового дубля или неразрешенного конфликта с существующим каноническим правилом.
При конфликте применяется приоритет `KNOWLEDGE_MAP.md`.

### L06 — SCOPE
Правило не расширено дальше того, что реально подтверждено.
Например реакция на один SPA-пост не становится правилом для всех текстов без основания.

### L07 — ARCHIVARIUS / REFERENCE SAFETY
Если используется Archivarius / YouMind:
- для Rafael trusted-card имеет приоритет, но не является обязательным условием; допускается релевантная `active` visual card вне blocklist;
- blocklist и wrong-status (`draft`, `needs_fix`, `archived`, `duplicate`) соблюдены;
- external prompt не превращен в брендовый закон;
- чужие claims/credentials/факты не перенесены;
- недоступность внешней reference-библиотеки не ошибочно превращена в блокировку всей генерации;
- если визуалы уже сгенерированы, `REFERENCE_TRACE` содержит только реально использованные источники.

### L08 — VERSION HYGIENE
Канонический рабочий файл обновлен на месте.
Не создана параллельная `v2`, `old`, `backup`, `final-final` копия без прямой команды Leo.

### L09 — CONTENT LIBRARY QUICK CHECK
Для нового APPROVED/PUBLISHED материала:
- полный текст сохранен;
- статус корректен;
- дата/тип/продукт/angle/CTA по возможности указаны;
- dynamic offer facts не становятся общими правилами;
- `_INDEX.md` обновлен.

## Результат

### PASS
Изменение можно считать каноническим.

### WARNING
Изменение допустимо, но есть некритичная неопределенность. Сохранить warning рядом с evidence/в отчете.

### FAIL
Изменение нельзя продвигать в каноническое постоянное правило до исправления.

## Fix behavior

При FAIL:
1. определить конкретный failed check;
2. не имитировать успешную запись;
3. исправить target/source/scope/conflict;
4. повторить KB-LINT;
5. только после PASS/WARNING завершить системный write-back.

## Короткий вывод

```text
KB-LINT: PASS | WARNING | FAIL
changed_file:
source:
evidence_level:
persistent_or_dynamic:
duplicate_conflict:
warnings:
```
