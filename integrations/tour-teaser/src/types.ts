export type SeatsStatus = "available" | "guaranteed" | "few_seats" | "sold_out";

export type MusicMood = "upbeat" | "relaxed" | "cultural" | "festive";

export type CityData = {
  name: string; // отображаемое имя города/региона, кириллица как в туре
  photoUrl: string; // прямая ссылка на фото (подставляется render-tour.mjs через Pexels)
};

// Пропсы верхнего уровня — то, что реально есть в Wix TourDates + производные поля
export type TourTeaserProps = {
  destination: string; // "Тур Южная Италия"
  cities: CityData[]; // список регионов/городов маршрута, в порядке показа
  dates: string; // "12–19 сентября"
  price: number;
  currency: string; // "$" | "₪"
  operator: string; // display name, не internal code
  boardType: string; // "ALL INCLUSIVE" / "HB" / "BB"
  seatsStatus: SeatsStatus;
  musicMood: MusicMood;
};

export const seatsLabel: Record<SeatsStatus, string> = {
  available: "Места есть",
  guaranteed: "Тур гарантирован",
  few_seats: "Осталось мало мест",
  sold_out: "Мест нет",
};

export const seatsColor: Record<SeatsStatus, string> = {
  available: "#4ADE80",
  guaranteed: "#38BDF8",
  few_seats: "#FBBF24",
  sold_out: "#F87171",
};

// Имя файла в public/audio/ на каждое настроение — файлы Leo подкладывает сам
export const musicFile: Record<MusicMood, string> = {
  upbeat: "upbeat-travel.mp3",
  relaxed: "relaxed-spa.mp3",
  cultural: "cultural-mediterranean.mp3",
  festive: "festive-fiesta.mp3",
};
