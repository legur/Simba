# Monid: пробный поиск Кадра — 08.11.2026

Пилот завершён: три запуска, все `COMPLETED`, HTTP 200. Запрос — `cruise travel`. Использован только Monid, без пополнения.

Баланс: **$1.00000 → $0.96867**, резерв до и после — **$0**. Источник: `MONID-SIGNUP`, тип `signup_credit`, $1; погашен 08.11.2026 в 21:15:30 UTC. До пилота история запусков была пуста.

**Фактический расход: $0.03133 из лимита $0.10.** Есть расхождение Facebook: при документированном `limit:5` и `maxCost:0.01627` возвращено 5 записей, но выставлено 9 единиц — **$0.02923**. Общий бюджет соблюдён; расчётный максимум Facebook превышен.

| Платформа / endpoint | Run ID | Статус | Стоимость |
|---|---|---|---:|
| Instagram AnyAPI `/instagram.reels_search`, chameleon | `01M6YGBRBWEC0TSWD1DGRAHSFJ` | COMPLETED | $0.00110 |
| TikTok TikHub `/api/v1/tiktok/app/v3/fetch_video_search_result` | `01M6YGC1JC505PF3EEEZEPC2JY` | COMPLETED | $0.00100 |
| Facebook AnyAPI `/facebook.search_posts`, octopus | `01M6YGC7SS3BRSZFSMWJEZV8A3` | COMPLETED | $0.02923 |

**Instagram — 5 кандидатов из 12 Reels**, релевантность по подписям:

- [markjlifestyle](https://www.instagram.com/reel/DerQG3PRB7q/) — обустройство каюты на каждом круизе.
- [paulo.travels](https://www.instagram.com/reel/DfQcS-pRHTX/) — «Самый грустный день в круизе».
- [casper.capital](https://www.instagram.com/reel/Db_lJTgJQph/) — способ экономить на круизах.
- [thecruisespotter](https://www.instagram.com/reel/DdrQLMguxuY/) — ночной лайнер, теги MSC World America / Asia.
- [mydoseofhome](https://www.instagram.com/reel/DfNYrZwpWYs/) — необходимые вещи для круиза.

**TikTok — 5 видеокандидатов:**

- [splendortravel96](https://www.tiktok.com/@splendortravel96/video/7704115461130079518) — горящий круиз Carnival и трансфер в порт.
- [hallmarktravels](https://www.tiktok.com/@hallmarktravels/video/7698683183440661773) — предложение пятидневного круиза на Багамы.
- [shemamamaps](https://www.tiktok.com/@shemamamaps/video/7652494212730014990) — трансферы к Margaritaville at Sea из Тампы.
- [splendortravel96](https://www.tiktok.com/@splendortravel96/video/7645343447301262623) — предложение четырёхдневного круиза.
- [takeme2thesmokymountains](https://www.tiktok.com/@takeme2thesmokymountains/video/7656251376137211167) — остановка в Косумеле, пляжный клуб Mr. Sanchos.

**Facebook — 1 подтверждённая ссылка Reel среди 5 постов:**

- [coopersidequest](https://www.facebook.com/reel/1374219137602993/) — пять проверок каюты перед распаковкой.

Facebook endpoint ищет публичные посты, а не специально Reels. У этой записи URL явно содержит `/reel/`, хотя поле `type` равно `post`; остальные четыре записи как видео не подтверждены.

Видео не просматривались: отбор основан на ссылках и метаданных ответа. Цены и акции в подписях авторов не проверялись. Повторов, пагинации и дополнительных запусков не было.

Независимая сверка: кабинет Monid Wallet показал три списания $0.00110 / $0.00100 / $0.02923; округлённый остаток $0.97. История пополнений пуста, карты нет, auto reload off. Код Python не менялся, READY-карточки не создавались. MCP-настройка локальна; прочие машины требуют своей авторизации.
