import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame } from "remotion";
import { CityData } from "../types";

export const CityScene: React.FC<{
  city: CityData;
  index: number;
  total: number;
  durationInFrames: number;
}> = ({ city, index, total, durationInFrames }) => {
  const frame = useCurrentFrame();

  // Крестфейд: 10 кадров на вход и на выход каждой сцены
  const fadeFrames = Math.min(10, Math.floor(durationInFrames / 4));
  const opacity = interpolate(
    frame,
    [0, fadeFrames, durationInFrames - fadeFrames, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Лёгкий ken burns на каждом кадре — по очереди zoom-in / zoom-out,
  // чтобы соседние сцены визуально не повторяли друг друга
  const zoomIn = index % 2 === 0;
  const scale = interpolate(
    frame,
    [0, durationInFrames],
    zoomIn ? [1, 1.12] : [1.12, 1],
    { extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        <Img
          src={city.photoUrl}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.25) 30%, rgba(0,0,0,0) 55%)",
        }}
      />

      {/* Индикатор прогресса — N/total, верхний правый угол */}
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 40,
          fontFamily: "Arial, sans-serif",
          fontWeight: 700,
          fontSize: 28,
          color: "#fff",
          opacity: 0.85,
          textShadow: "0 2px 8px rgba(0,0,0,0.6)",
        }}
      >
        {index + 1}/{total}
      </div>

      {/* Название города/региона — низ кадра */}
      <div
        style={{
          position: "absolute",
          bottom: 100,
          left: 40,
          right: 40,
          fontFamily: "Arial, sans-serif",
          fontWeight: 900,
          fontSize: 64,
          color: "#fff",
          textShadow: "0 4px 20px rgba(0,0,0,0.6)",
        }}
      >
        {city.name}
      </div>
    </AbsoluteFill>
  );
};
