# RAFAEL GPT IMAGE 2.5 EXAMPLES

Версия: 1.0
Дата: 11.09.2026
Статус: REFERENCE LIBRARY
Источник: официальный OpenAI GPT Image 2.5 prompting guide

Официальный материал: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5

## Назначение

Это визуальная библиотека Rafael: не только правила, но и пары «входные изображения → задача → Flare → Sunburst». Она используется для понимания механики промпта и различий результата. Чужая стилистика, бренды, тексты и сюжеты не копируются в постеры Bon Tours.

## EX-01 — Точный текст в рекламном макете

Оригинальный prompt и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#render-exact-text

Задача: рекламная fashion-сцена с одним точным слоганом и запретом дополнительных надписей.

Механика промпта: назвать аудиторию и характер съёмки, дать единственную строку в кавычках, потребовать появление ровно один раз, запретить лишний текст, водяные знаки и посторонние логотипы.

- [Flare](https://drive.google.com/file/d/1J_iSOzjLoBeM9De2RLrznl55Mzhg8fLb/view)
- [Sunburst](https://drive.google.com/file/d/1Vw2qM8-26UhZLhU4EpGcUo2MGzu0HKze/view)

Применение в Rafael: заголовок, дата, цена и «Simba by Bon Tours» задаются отдельно, дословно и с количеством появлений.

## EX-02 — Сохранение личности при замене одежды

Оригинальный prompt и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#preserve-identity-and-change-clothing

Задача: оставить человека узнаваемым и заменить только одежду по трём отдельным референсам.

Механика промпта: перечислить неизменяемые признаки личности, позу, фон, камеру и свет; разрешить только одежду; потребовать естественную посадку ткани и согласованные тени.

Входные изображения:

- [Identity](https://drive.google.com/file/d/1qRt4NE5m_ucbBTkyy5M3f86uo0EOvrBT/view)
- [Jacket](https://drive.google.com/file/d/1pLpP_LghlF0zhlflG2NbUw-WOO0fgHya/view)
- [Top](https://drive.google.com/file/d/1uw2XrE3ThPCSreBhy_Hxhs1JPu7YIqwn/view)
- [Boots](https://drive.google.com/file/d/172jftKoBV6mOH6ozTMRO_6kg1M6xIRHT/view)

Результаты:

- [Flare](https://drive.google.com/file/d/1dx9t0ROCBiCOt5OjhVSASjGyydgVZVCi/view)
- [Sunburst](https://drive.google.com/file/d/1h3qjhBZcJaNZKXvKyzyLq39jSCeWKu8o/view)

Применение в Rafael: фотографии Лео и master-reference Simba получают роль identity; одежда никогда не используется как источник лица или телосложения.

## EX-03 — Объединение двух референсов

Оригинальный prompt и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#combine-references

Задача: перенести один объект из второго изображения в сцену первого, не перестраивая остальное.

Механика промпта: Image 1 назначается сценой, Image 2 — источником конкретного объекта; указываются точное место вставки и запрет других изменений.

Входные изображения:

- [Scene](https://drive.google.com/file/d/1toHmptd1Ildz4HamfOpIAgLVuXEJCjTP/view)
- [Subject](https://drive.google.com/file/d/1Z5mgcXAEVNk6uGOp9MVkIWiEUF7EQAnL/view)

Результаты:

- [Flare](https://drive.google.com/file/d/1v8C9nA21cg9o-LCoiIZreU7Aqv5EColV/view)
- [Sunburst](https://drive.google.com/file/d/1NQ88m_7ber-E2lgAag26f2XauAluujIC/view)

Применение в Rafael: Simba переносится из master-reference в travel-сцену с согласованием света, перспективы и масштаба; фон не должен заимствовать внешность персонажа.

## EX-04 — Удаление одного объекта

Оригинальный prompt и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#remove-an-object

Задача: удалить предмет из руки человека, сохранив сцену.

Механика промпта: назвать один удаляемый объект и закончить жёстким запретом любых других изменений.

Входное изображение:

- [Original](https://drive.google.com/file/d/1HyoYFBXfOwuBjECCVRcvZCOKHmE9N5Jr/view)

Результаты:

- [Flare](https://drive.google.com/file/d/18cGZgJcYJlu6M_an7u2oiCz-8o4wPWhS/view)
- [Sunburst](https://drive.google.com/file/d/1tFWZF0o-b1mpDe94Nu5PRspja1XXepKp/view)

Применение в Rafael: лишняя надпись, предмет или артефакт исправляются локальным edit, а не полной перегенерацией удачного постера.

## EX-05 — Последовательное редактирование

Оригинальные prompts и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#refine-an-image-across-turns

Задача: сначала создать рекламный билборд с точной надписью, затем изменить только сезон и погоду.

Механика промпта: первый запрос создаёт принятый baseline; второй получает этот результат как input и меняет одно условие. Критические элементы макета повторно фиксируются.

Входное изображение:

- [Product](https://drive.google.com/file/d/1di3tWEfN2pwkBLCSD1zwbyn3a-IKtmG9/view)

Baseline:

- [Flare](https://drive.google.com/file/d/1KDne6cTtnwM2608sC40MaSbliCvFONyv/view)
- [Sunburst](https://drive.google.com/file/d/14lpFHHfrrZgEUiytoIy0PoXfLeienPZT/view)

После изменения условия:

- [Flare](https://drive.google.com/file/d/1Em96lmuU7BBDMzDGh5EmHN9nNTPE3e6d/view)
- [Sunburst](https://drive.google.com/file/d/1FdT1M4eY8FcDFhv-5GJs5gVJ4WOl5m44/view)

Применение в Rafael: команда Лео «сделай квадрат», «передвинь Симбу» или «исправь строку» выполняется от последнего принятого визуала с сохранением остального.

## EX-06 — Один персонаж в нескольких сценах

Оригинальные prompts и описание: https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5#keep-a-character-consistent

Задача: сначала определить персонажа, затем продолжить историю в новой сцене без его редизайна.

Механика промпта: на первом изображении фиксируются лицо, пропорции, одежда и визуальный язык; в продолжении повторяются признаки идентичности и отдельно описывается только новая сцена.

Master character:

- [Flare](https://drive.google.com/file/d/1ZgaZRBUlAk6oDsNByV5GOhbTRT9zWDgG/view)
- [Sunburst](https://drive.google.com/file/d/1lcYWB1uv4t1HKtEpeJNf6MZ9Nvb9Y8AO/view)

Следующая сцена:

- [Flare](https://drive.google.com/file/d/1a5wgvRyW4gBl4iUeDcSbNcmqx1iilZJl/view)
- [Sunburst](https://drive.google.com/file/d/1prKerHnyKCIiZm32Or6dXBvFb9JjbKos/view)

Применение в Rafael: один утверждённый master-reference Simba используется во всей серии; меняются окружение и действие, но не сам персонаж.

## Runtime-правило

Перед generation-spec Rafael проверяет эту библиотеку, если задача связана хотя бы с одним из признаков:

- точный текст на изображении;
- identity-sensitive изображение Лео или Simba;
- два и более входных референса;
- локальная правка принятого визуала;
- последовательная серия с одним персонажем;
- сравнение Flare и Sunburst.

Выбирается только релевантный пример. Библиотека не заменяет Archivarius, YouMind, Visual Rules, Template Lock или master-reference Simba.

## Provenance

Все 24 изображения скачаны 11.09.2026 с официального OpenAI GPT Image 2.5 prompting guide и сохранены без изменений. Полные оригинальные prompts остаются в официальном источнике; в этой библиотеке зафиксирована их рабочая механика и связь с конкретными визуальными результатами.
