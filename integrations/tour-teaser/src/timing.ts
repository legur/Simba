export const FPS = 30;

// Тайминги — все значения в кадрах при 30fps
const INTRO_FRAMES = 75; // 2.5 сек — заставка с названием тура
const OUTRO_FRAMES = 90; // 3 сек — цена + места + бренд

const MIN_TOTAL_FRAMES = 600; // 20 сек — жёсткий минимум по требованию
const MAX_TOTAL_FRAMES = 900; // 30 сек — жёсткий максимум по требованию
const TARGET_TOTAL_FRAMES = 750; // 25 сек — ориентир при "обычном" числе городов
const MIN_PER_CITY_FRAMES = 24; // 0.8 сек — абсолютный пол, чтобы кадр не мелькал незаметно

/**
 * Считает длительность каждого сегмента так, чтобы итог всегда укладывался
 * в 20-30 сек вне зависимости от того, сколько городов в туре (5 или 15).
 *
 * Логика:
 * 1. Целимся в 25 сек, делим оставшееся время (без intro/outro) поровну на города.
 * 2. Если городов много и это уводит нас за пределы 30 сек — сжимаем время на город,
 *    вплоть до пола в 0.8 сек, лишь бы не превысить 30 сек.
 * 3. Если городов мало и итог меньше 20 сек — наоборот, растягиваем время на город.
 */
export function computeTiming(cityCount: number) {
  const n = Math.max(1, cityCount);

  let perCity = Math.round(
    (TARGET_TOTAL_FRAMES - INTRO_FRAMES - OUTRO_FRAMES) / n,
  );
  perCity = Math.max(MIN_PER_CITY_FRAMES, perCity);

  let total = INTRO_FRAMES + OUTRO_FRAMES + perCity * n;

  if (total > MAX_TOTAL_FRAMES) {
    perCity = Math.max(
      MIN_PER_CITY_FRAMES,
      Math.floor((MAX_TOTAL_FRAMES - INTRO_FRAMES - OUTRO_FRAMES) / n),
    );
    total = INTRO_FRAMES + OUTRO_FRAMES + perCity * n;
  }

  if (total < MIN_TOTAL_FRAMES) {
    perCity = Math.floor((MIN_TOTAL_FRAMES - INTRO_FRAMES - OUTRO_FRAMES) / n);
    total = INTRO_FRAMES + OUTRO_FRAMES + perCity * n;
  }

  return {
    introFrames: INTRO_FRAMES,
    outroFrames: OUTRO_FRAMES,
    perCityFrames: perCity,
    totalFrames: total,
  };
}
