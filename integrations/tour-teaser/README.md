# tour-teaser — рендер промо-рилса тура (Люмьер)

Remotion-проект, который рендерит рилс 20–30 с из данных тура и стоковых фото Pexels.
JSON для него готовит модуль **Люмьер** (`Симба (Писатель)/Lumiere-v1.1.md`). Перенесён в `legur/Simba`
22.10.2026 с машины Leo без изменений кода.

Граница: видео к **утверждённому посту** собирает Монтажер Клод (`integrations/video/`), этот проект —
к **данным тура** без поста.

## Установка (один раз)

```powershell
cd integrations\tour-teaser
npm install
```

Перед первым рендером:

1. Ключ Pexels API (бесплатно на https://www.pexels.com/api/): `$env:PEXELS_API_KEY="ключ"`.
   Ключ задаётся только переменной окружения и в репозиторий не попадает.
2. Положить 4 mp3 в `public/audio/` (mixkit.co/free-stock-music):
   `upbeat-travel.mp3`, `relaxed-spa.mp3`, `cultural-mediterranean.mp3`, `festive-fiesta.mp3`.
   Музыка хранится локально (`.gitignore`).

## Рендер

```powershell
npm run render-tour tour-data.json
```

Формат файла — `tour-data.example.json`, схема — `src/types.ts`. Готовое видео — в `out/`.
Рабочий `tour-data.json` и `out/` в Git не попадают.

Просмотр и правка анимации: `npm run dev` (Remotion Studio).

## Музыка

Поле `musicMood` (`cultural` / `relaxed` / `upbeat` / `festive`) выбирает Люмьер (Шаг 4, с версии 1.3); по нему
`render-tour.mjs` берёт соответствующий mp3 из `public/audio/`. Без поля или без файла рендер останавливается с ошибкой.

## Лицензия Remotion

Remotion бесплатен для частных лиц и небольших компаний; для некоторых организаций нужна компанийская лицензия:
https://github.com/remotion-dev/remotion/blob/main/LICENSE.md
