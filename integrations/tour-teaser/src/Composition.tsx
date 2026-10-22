import { CalculateMetadataFunction, Composition } from "remotion";
import { TourTeaser } from "./TourTeaser";
import { TourTeaserProps } from "./types";
import { computeTiming, FPS } from "./timing";

// Тестовые данные — пример из брифа: тур "Южная Италия", 10 регионов.
// В реальном пайплайне cities[].photoUrl подставляет render-tour.mjs через Pexels.
const testData: TourTeaserProps = {
  destination: "Тур Южная Италия",
  cities: [
    { name: "Бари", photoUrl: "https://images.pexels.com/photos/12461234/pexels-photo-12461234.jpeg" },
    { name: "Остуни", photoUrl: "https://images.pexels.com/photos/16264511/pexels-photo-16264511.jpeg" },
    { name: "Лечче", photoUrl: "https://images.pexels.com/photos/19764354/pexels-photo-19764354.jpeg" },
    { name: "Альберобелло", photoUrl: "https://images.pexels.com/photos/13943881/pexels-photo-13943881.jpeg" },
    { name: "Конверсано", photoUrl: "https://images.pexels.com/photos/2166553/pexels-photo-2166553.jpeg" },
    { name: "Мартина-Франка", photoUrl: "https://images.pexels.com/photos/2166553/pexels-photo-2166553.jpeg" },
    { name: "Сант-Агата-де-Готи", photoUrl: "https://images.pexels.com/photos/2166553/pexels-photo-2166553.jpeg" },
    { name: "Беневенто", photoUrl: "https://images.pexels.com/photos/2166553/pexels-photo-2166553.jpeg" },
    { name: "Неаполь", photoUrl: "https://images.pexels.com/photos/1701595/pexels-photo-1701595.jpeg" },
    { name: "Капри", photoUrl: "https://images.pexels.com/photos/1450340/pexels-photo-1450340.jpeg" },
  ],
  dates: "12–19 сентября",
  price: 1290,
  currency: "$",
  operator: "Метрополь",
  boardType: "HB",
  seatsStatus: "few_seats",
  musicMood: "cultural",
};

const calculateMetadata: CalculateMetadataFunction<TourTeaserProps> = ({
  props,
}) => {
  const { totalFrames } = computeTiming(props.cities.length);
  return { durationInFrames: totalFrames };
};

export const MyComposition = () => {
  return (
    <Composition
      id="TourTeaser"
      component={TourTeaser}
      durationInFrames={computeTiming(testData.cities.length).totalFrames}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={testData}
      calculateMetadata={calculateMetadata}
    />
  );
};
