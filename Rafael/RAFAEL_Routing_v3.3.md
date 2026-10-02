# RAFAEL_Routing.md
## Bon Tours / Simba by Bon Tours


Версия: 3.3 · runtime amendment 25.09.2026
Статус: PRODUCTION
Часть архитектуры: → см. RAFAEL_Architecture.md


---


# ЧАСТЬ 3 — ROUTING TABLE


Таблицы ниже (3.1 и 3.1a) — рекомендация для якорного стиля (вариант A, см. System.md 1.6),
не жёсткое правило. Rafael следует рекомендации по умолчанию, но может выбрать другой стиль,
если критерии "Использовать / Не использовать" конкретного STYLE (RAFAEL_Styles.md) явно
подходят материалу лучше, чем рекомендованный — с обязательной пометкой отклонения
(механизм и формат пометки — System.md, 1.6).


## 3.1 Таблица маршрутизации


| Тип тура | Сегмент | Стиль | Simba Mode | Camera | Lighting |
|----------|---------|-------|-----------|--------|----------|
| Premium cruise | 🟣🟡 | STYLE 01 + THEATRICAL HEROIC | MODE A | LOW ANGLE POWER | SUNSET CINEMATIC |
| Авиарейс / reopening | любой | STYLE 01 + THEATRICAL HEROIC | MODE A | LOW ANGLE POWER | SUNSET CINEMATIC |
| SPA / санаторий | 🔵🟣 | STYLE 03 PREMIUM MINIMAL | MODE C | CLOSE EMOTIONAL | LUXURY DIFFUSED |
| Flash Sale (аудитория 55+) | 🟢🔵 | STYLE 04 SOCIAL IMPACT | MODE B | TELEPHOTO | HARD CONTRAST |
| Flash Sale (до 50 / urban) | 🟢🔵 | STYLE 04 + NEON INK | MODE B | TELEPHOTO | HARD CONTRAST |
| Семейный тур / детский лагерь | 🟢🔵 | STYLE 07 FLAT VECTOR | MODE A | WIDE CINEMATIC | Дневной яркий |
| Premium Европа, Япония, Дубай, Париж, Лондон, Швейцария, Сингапур | 🟣🟡 | STYLE 01 + Double Exposure | MODE B | CLOSE EMOTIONAL | LUXURY DIFFUSED |
| Мульти-направление / маршрут | 🔵🟣 | STYLE 06 GEO-COLLAGE | MODE B | WIDE CINEMATIC | SUNSET CINEMATIC |
| Ретро Европа / Италия / классические круизы | 🔵🟣 | STYLE 05 RETRO PROPAGANDA | MODE B | WIDE CINEMATIC | RETRO PRINT |
| Имиджевый / брендовый пост без оффера | — | STYLE 02 BAUHAUS | MODE C | — | HARD CONTRAST |
| Типографический / философский | — | STYLE 08 TYPOGRAPHIC | MODE C | — | Dark premium |


## 3.1a Routing Table — посты без тура (по типу поста)


Применяется когда у поста нет тура (цены/дат/оффера) — посты Info, Travel, Leo,
а также Simba без конкретного продукта. Ключ — тип поста по автодетекту Critic 3.2 (Шаг 0),
не тип тура.


### HERO IDENTITY OVERRIDE
До применения `Simba Mode` определить источник текста:
- модуль `Leo` / личный пост → главный визуальный герой **Leo**, Simba = absent;
- модуль `Info` / экспертный или справочный пост → главный визуальный герой **Leo**, Simba = absent;
- остальные типы → использовать `Simba Mode` из таблиц и Template Lock.


Этот override меняет только персонажа. Стиль, камера, свет, количество вариантов и остальные правила Rafael сохраняются. Прямая команда Leo имеет высший приоритет.


| Тип поста (Critic) | Стиль | Simba Mode |
|---|---|---|
| Экспертный / справочный | STYLE 08 TYPOGRAPHIC | MODE C |
| Прогревающий | STYLE 03 PREMIUM MINIMAL | MODE C |
| Новостной | STYLE 08 TYPOGRAPHIC | MODE C |
| Вирусный / полемический | STYLE 09 EDITORIAL SATIRE | MODE C (MODE B, если Симба — часть шутки) |


Правило приоритета 3.2/1 (тип продажи важнее направления) действует и здесь:
если у поста внезапно появляется тур внутри — используй Таблицу 3.1, не 3.1a.


## 3.2 Правила приоритета


1. Тип продажи перебивает стиль направления.
   Пример: Япония + flash sale = STYLE 04, не Double Exposure.


2. Ценовой сегмент перебивает визуальный регистр направления.
   Пример: Болгария 🟢 = STYLE 07 или STYLE 04, не EDITORIAL CINEMATIC.


3. При конфликте сегмента и типа — тип продажи главнее.


## 3.3 Ценовые сегменты Bon Tours


| Сегмент | Цена | Визуальный регистр |
|---------|------|-------------------|
| 🟢 | до $1900 | доступный, понятный, дружелюбный |
| 🔵 | $1900–3200 | культурный, эстетичный |
| 🟣 | $3200–5000 | качественный, сдержанный |
| 🟡 | $5000+ | эксклюзивный, престижный |