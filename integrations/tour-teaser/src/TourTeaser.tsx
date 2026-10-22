import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Series,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { IntroScene } from "./scenes/IntroScene";
import { CityScene } from "./scenes/CityScene";
import { OutroScene } from "./scenes/OutroScene";
import { computeTiming } from "./timing";
import { TourTeaserProps, musicFile } from "./types";

export const TourTeaser: React.FC<TourTeaserProps> = ({
  destination,
  cities,
  dates,
  price,
  currency,
  operator,
  boardType,
  seatsStatus,
  musicMood,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { introFrames, outroFrames, perCityFrames } = computeTiming(
    cities.length,
  );

  // Фейд музыки: 1 сек на вход, 1 сек на выход (30 кадров при 30fps)
  const musicVolume = interpolate(
    frame,
    [0, 30, durationInFrames - 30, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      <Audio src={staticFile(`audio/${musicFile[musicMood]}`)} volume={musicVolume} />

      <Series>
        <Series.Sequence durationInFrames={introFrames}>
          <IntroScene destination={destination} dates={dates} operator={operator} />
        </Series.Sequence>

        {cities.map((city, i) => (
          <Series.Sequence key={city.name + i} durationInFrames={perCityFrames}>
            <CityScene
              city={city}
              index={i}
              total={cities.length}
              durationInFrames={perCityFrames}
            />
          </Series.Sequence>
        ))}

        <Series.Sequence durationInFrames={outroFrames}>
          <OutroScene
            price={price}
            currency={currency}
            operator={operator}
            boardType={boardType}
            seatsStatus={seatsStatus}
          />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
