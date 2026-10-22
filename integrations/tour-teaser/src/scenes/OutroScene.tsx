import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { OdometerDigits } from "../OdometerDigits";
import { SeatsStatus, seatsColor, seatsLabel } from "../types";

export const OutroScene: React.FC<{
  price: number;
  currency: string;
  operator: string;
  boardType: string;
  seatsStatus: SeatsStatus;
}> = ({ price, currency, operator, boardType, seatsStatus }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const badgeProgress = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });
  const badgeScale = interpolate(badgeProgress, [0, 1], [0.6, 1]);
  const badgeOpacity = interpolate(badgeProgress, [0, 1], [0, 1]);

  const textProgress = spring({
    frame: frame - 8,
    fps,
    config: { damping: 200 },
  });
  const textY = interpolate(textProgress, [0, 1], [30, 0]);
  const textOpacity = interpolate(textProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#111",
        background:
          "radial-gradient(circle at 50% 70%, #1f2937 0%, #0b0f14 70%)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Arial, sans-serif",
        color: "#fff",
        textAlign: "center",
      }}
    >
      <div
        style={{
          padding: "14px 28px",
          borderRadius: 999,
          backgroundColor: seatsColor[seatsStatus],
          opacity: badgeOpacity,
          transform: `scale(${badgeScale})`,
          fontWeight: 700,
          fontSize: 32,
          color: "#111",
          marginBottom: 40,
        }}
      >
        {seatsLabel[seatsStatus]}
      </div>

      <div
        style={{
          transform: `translateY(${textY}px)`,
          opacity: textOpacity,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            color: "#FDE047",
            display: "flex",
            alignItems: "baseline",
            justifyContent: "center",
          }}
        >
          <span style={{ marginRight: 6 }}>от {currency}</span>
          <OdometerDigits value={price} startFrame={0} />
        </div>
        <div style={{ fontSize: 34, marginTop: 16, opacity: 0.9 }}>
          {boardType}
        </div>
        <div style={{ fontSize: 28, marginTop: 10, opacity: 0.75 }}>
          Оператор: {operator}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 70,
          fontWeight: 900,
          fontSize: 40,
          letterSpacing: 2,
          opacity: textOpacity,
        }}
      >
        SIMBA
      </div>
    </AbsoluteFill>
  );
};
