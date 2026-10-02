# ARCHIVARIUS RUNTIME TRUSTED PRIORITY

Статус: CANONICAL TRUSTED / PRIORITY LIST
Дата: 05.09.2026

## Правило

Карточки, перечисленные здесь, являются заранее проверенными `trusted / recommended` референсами и получают приоритет при поиске Rafael.

Этот файл НЕ является whitelist. Rafael может использовать и другие релевантные карточки Archivarius со статусом `active`, если они не находятся в `ARCHIVARIUS_RUNTIME_BLOCKLIST.md` и проходят текущие Brand / Fact / Rafael safety rules.

Добавление новой карточки в этот файл требует:
- ручного/системного просмотра содержания;
- понятной пользы для конкретного модуля;
- отсутствия конфликтов с Brand, Fact Safety и правилами Leo;
- фиксации `allowed_for` и допустимой механики.

## Trusted / recommended cards

### AR-20260902-001 — Минималистичный туристический постер города
- runtime_trusted: true
- allowed_for: Rafael
- use_for:
  - destination poster
  - city visual concept
  - graphic travel series
- allowed_mechanics:
  - пять узнаваемых городских символов;
  - ограниченная палитра;
  - крупное название города как часть композиции;
  - один локальный транспортный/цветовой акцент;
  - плоская графическая стилизация.
- restrictions:
  - не копировать конкретный Лондон;
  - не переносить текст/символы без адаптации;
  - не использовать как обязательный стиль каждого travel-постера.
- source_review: reviewed 05.09.2026
- sample_status: approved in Archivarius

### AR-20260902-005 — Городской постер с радиальной архитектурной композицией
- runtime_trusted: true
- allowed_for: Rafael
- use_for:
  - architecture-led destination poster
  - city campaign
  - vertical/social visual concept
- allowed_mechanics:
  - центральная главная достопримечательность;
  - 4–5 дополнительных архитектурных символов;
  - радиальная/конвергентная композиция;
  - крупная типографика названия города;
  - ограниченная палитра;
  - небольшая локальная foreground-деталь.
- restrictions:
  - исходное противоречие перспектив в карточке не переносить как правило;
  - архитектурные объекты конкретного города выбирать заново;
  - крупную типографику проверять после генерации.
- source_review: reviewed 05.09.2026

### AR-20260720-005 — Винтажный векторный постер города
- runtime_trusted: true
- allowed_for: Rafael
- use_for:
  - destination poster
  - city visual series
  - editorial travel art
- allowed_mechanics:
  - flat vector;
  - mid-century travel-poster logic;
  - simplified recognizable architecture;
  - location-inspired restrained palette;
  - balanced foreground / cityscape / background.
- restrictions:
  - не доверять автоматическому выбору достопримечательностей без проверки;
  - кириллицу проверять отдельно;
  - не использовать как источник географических фактов.
- source_review: reviewed 05.09.2026

### AR-20260720-004 — Графический постер с самостоятельной арт-дирекцией
- runtime_trusted: true
- allowed_for: Rafael
- use_for:
  - experimental visual concept
  - non-template poster direction
  - one of five deliberately different concepts
- allowed_mechanics:
  - свобода art direction;
  - самостоятельный визуальный ритм;
  - сильная современная типографическая иерархия;
  - один центральный графический прием.
- restrictions:
  - использовать только как разрешение на композиционную свободу, не как готовый бренд-стиль;
  - не копировать конкретные Behance-работы;
  - факты/claims брать только из текущего оффера.
- source_review: reviewed 05.09.2026

## Неэксклюзивность списка

Отсутствие карточки в этом файле НЕ означает запрет. Для Rafael допустимы другие релевантные `active` visual cards Archivarius, если:
- карточка относится к визуальной генерации / дизайну / изображению;
- она не находится в `ARCHIVARIUS_RUNTIME_BLOCKLIST.md`;
- ее механика не конфликтует с текущими фактами, Brand Rules, Visual Rules, Template Lock и прямым решением Leo;
- из нее извлекается конкретная визуальная механика, а не чужие claims/факты/текст.

Карточки `draft`, `needs_fix`, `archived`, `duplicate` не используются. Текстовые и манипулятивные prompt-карточки не применяются Rafael только потому, что они `active`.

## Добавление

Новые trusted/recommended записи дописываются в этот канонический файл после review.
Отдельные версии списка не создаются.
