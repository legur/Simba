// render-tour.mjs
//
// Один вызов: данные тура + список городов (JSON) -> автоподбор фото
// для каждого города (Pexels) -> готовый MP4 20-30 сек с музыкой.
//
// Использование:
//   node render-tour.mjs tour-data.json
//
// Перед первым запуском:
//   1. Зарегистрируйся на https://www.pexels.com/api/ (бесплатно, мгновенно)
//   2. Задай ключ: $env:PEXELS_API_KEY="твой_ключ"   (PowerShell)
//   3. Положи 4 mp3-файла в public/audio/ (см. musicMood в src/types.ts) —
//      источник: mixkit.co/free-stock-music (бесплатная коммерческая лицензия)
//        upbeat-travel.mp3, relaxed-spa.mp3, cultural-mediterranean.mp3, festive-fiesta.mp3
//
// Формат tour-data.json — см. tour-data.example.json рядом с этим файлом.

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PEXELS_API_KEY = process.env.PEXELS_API_KEY;

const ALLOWED_MOODS = ["upbeat", "relaxed", "cultural", "festive"];
const MUSIC_FILES = {
  upbeat: "upbeat-travel.mp3",
  relaxed: "relaxed-spa.mp3",
  cultural: "cultural-mediterranean.mp3",
  festive: "festive-fiesta.mp3",
};

async function fetchStockPhoto(query) {
  if (!PEXELS_API_KEY) {
    throw new Error(
      "PEXELS_API_KEY не задан. См. инструкцию в шапке render-tour.mjs.",
    );
  }
  const url = `https://api.pexels.com/v1/search?query=${encodeURIComponent(
    query,
  )}&orientation=portrait&per_page=1`;

  const res = await fetch(url, { headers: { Authorization: PEXELS_API_KEY } });
  if (!res.ok) {
    throw new Error(`Pexels API вернул ошибку ${res.status}: ${await res.text()}`);
  }
  const data = await res.json();
  const photo = data.photos?.[0];
  if (!photo) {
    throw new Error(
      `Pexels не нашёл фото по запросу "${query}". Уточни photoQuery для этого города (на английском).`,
    );
  }
  return photo.src.large2x;
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]+/gi, "-")
    .replace(/(^-|-$)/g, "");
}

async function main() {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error("Использование: node render-tour.mjs tour-data.json");
    process.exit(1);
  }

  const tourData = JSON.parse(fs.readFileSync(inputPath, "utf-8"));

  const requiredFields = [
    "destination",
    "cities",
    "dates",
    "price",
    "currency",
    "operator",
    "boardType",
    "seatsStatus",
    "musicMood",
  ];
  for (const field of requiredFields) {
    if (tourData[field] === undefined) {
      throw new Error(`В tour-data.json отсутствует обязательное поле: ${field}`);
    }
  }
  if (!Array.isArray(tourData.cities) || tourData.cities.length === 0) {
    throw new Error("Поле cities должно быть непустым массивом объектов {name, photoQuery}.");
  }
  if (!ALLOWED_MOODS.includes(tourData.musicMood)) {
    throw new Error(
      `musicMood должен быть одним из: ${ALLOWED_MOODS.join(", ")}. Получено: ${tourData.musicMood}`,
    );
  }

  const audioPath = path.join(__dirname, "public", "audio", MUSIC_FILES[tourData.musicMood]);
  if (!fs.existsSync(audioPath)) {
    throw new Error(
      `Не найден файл музыки: ${audioPath}\nПоложи mp3 в public/audio/ (см. инструкцию в шапке render-tour.mjs).`,
    );
  }

  console.log(`Ищу фото для ${tourData.cities.length} городов...`);
  const cities = await Promise.all(
    tourData.cities.map(async (city) => {
      const query = city.photoQuery || city.name;
      const photoUrl = await fetchStockPhoto(query);
      console.log(`  ${city.name}: найдено`);
      return { name: city.name, photoUrl };
    }),
  );

  console.log("Собираю проект...");
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "src", "index.ts"),
  });

  const inputProps = {
    destination: tourData.destination,
    cities,
    dates: tourData.dates,
    price: tourData.price,
    currency: tourData.currency,
    operator: tourData.operator,
    boardType: tourData.boardType,
    seatsStatus: tourData.seatsStatus,
    musicMood: tourData.musicMood,
  };

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "TourTeaser",
    inputProps,
  });

  const outDir = path.join(__dirname, "out");
  fs.mkdirSync(outDir, { recursive: true });
  const outputLocation = path.join(
    outDir,
    `${slugify(tourData.destination)}-${Date.now()}.mp4`,
  );

  console.log(
    `Рендерю видео (${(composition.durationInFrames / composition.fps).toFixed(1)} сек)...`,
  );
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation,
    inputProps,
  });

  console.log(`Готово: ${outputLocation}`);
}

main().catch((err) => {
  console.error("Ошибка:", err.message);
  process.exit(1);
});
