import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const IntroScene: React.FC<{
  destination: string;
  dates: string;
  operator: string;
}> = ({ destination, dates, operator }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleProgress = spring({ frame, fps, config: { damping: 200 } });
  const titleY = interpolate(titleProgress, [0, 1], [30, 0]);
  const titleOpacity = interpolate(titleProgress, [0, 1], [0, 1]);

  const subProgress = spring({
    frame: frame - 12,
    fps,
    config: { damping: 200 },
  });
  const subOpacity = interpolate(subProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#111",
        background:
          "radial-gradient(circle at 50% 30%, #1f2937 0%, #0b0f14 70%)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Arial, sans-serif",
        color: "#fff",
        textAlign: "center",
        padding: "0 60px",
      }}
    >
      <div
        style={{
          fontSize: 30,
          fontWeight: 700,
          letterSpacing: 2,
          color: "#FDE047",
          marginBottom: 20,
          opacity: subOpacity,
        }}
      >
        SIMBA · {operator}
      </div>
      <div
        style={{
          fontSize: 84,
          fontWeight: 900,
          lineHeight: 1.1,
          transform: `translateY(${titleY}px)`,
          opacity: titleOpacity,
          textShadow: "0 4px 24px rgba(0,0,0,0.6)",
        }}
      >
        {destination}
      </div>
      <div
        style={{
          fontSize: 36,
          fontWeight: 600,
          marginTop: 24,
          opacity: subOpacity,
        }}
      >
        {dates}
      </div>
    </AbsoluteFill>
  );
};
