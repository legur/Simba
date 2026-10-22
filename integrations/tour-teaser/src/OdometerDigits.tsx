import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Покадровая прокрутка одной цифры "как одометр": едет по вертикали через
 * несколько промежуточных цифр и с overshoot фиксируется на нужном значении.
 * Реализация по мотивам техники "odometer-digit-roll" (video-shotcraft):
 * прокрутка + overshoot + пульс на фиксации — код написан с нуля под наш кейс.
 */
const DIGIT_HEIGHT = 1; // em — высота одной цифры в текущем шрифте

const SingleDigit: React.FC<{
  target: number; // 0-9
  frame: number; // локальный кадр анимации именно этой колонки
  fps: number;
  delayFrames: number; // стаггер между колонками (правая крутится первой)
}> = ({ target, frame, fps, delayFrames }) => {
  const localFrame = frame - delayFrames;

  const progress = spring({
    frame: localFrame,
    fps,
    config: { damping: 11, stiffness: 90, mass: 0.7 }, // overshoot и лёгкий откат
  });

  // Прокручиваем "с запасом" на 10 позиций вниз, потом мимо нуля к target —
  // создаёт ощущение настоящего вращения барабана, а не прямого прыжка.
  const spins = 1; // один полный проход барабана перед остановкой
  const totalSteps = spins * 10 + target;
  const currentPos = interpolate(progress, [0, 1], [0, totalSteps]);

  const translateY = -(currentPos % 10) * DIGIT_HEIGHT;

  // Пульс на фиксации — короткий scale-удар в момент, когда колонка встаёт на место
  const settleFrame = localFrame - 18; // примерно когда spring почти долетел
  const pulse = spring({
    frame: settleFrame,
    fps,
    config: { damping: 100, stiffness: 300 },
    durationInFrames: 6,
  });
  const pulseScale = interpolate(pulse, [0, 0.5, 1], [1, 1.12, 1]);

  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        height: "1em",
        width: "0.62em",
        display: "inline-block",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          transform: `translateY(${translateY}em) scale(${pulseScale})`,
          transformOrigin: "center",
        }}
      >
        {Array.from({ length: 11 }).map((_, i) => (
          <div key={i} style={{ height: "1em", lineHeight: "1em" }}>
            {i % 10}
          </div>
        ))}
      </div>
    </div>
  );
};

export const OdometerDigits: React.FC<{
  value: number;
  startFrame: number; // кадр композиции, с которого начинается прокрутка
  style?: React.CSSProperties;
}> = ({ value, startFrame, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const digits = String(Math.round(value)).split("");

  const localFrame = frame - startFrame;
  if (localFrame < 0) return <span style={style}>{"\u00A0"}</span>;

  return (
    <span style={{ ...style, display: "inline-flex" }}>
      {digits.map((d, i) => {
        // Стаггер: цифры фиксируются слева направо, разница 4 кадра между колонками
        const delay = i * 4;
        return (
          <SingleDigit
            key={i}
            target={parseInt(d, 10)}
            frame={localFrame}
            fps={fps}
            delayFrames={delay}
          />
        );
      })}
    </span>
  );
};
