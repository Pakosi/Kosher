import React from "react";
import { interpolate, spring, useVideoConfig } from "remotion";
import { fontStack } from "../lib/fonts";
import type { Palette } from "../schema";

export const OnScreenText: React.FC<{
  text: string;
  style: string;
  color: string | null;
  palette: Palette;
  font: string;
  local: number; // frames since appearance
}> = ({ text, style, color, palette, font, local }) => {
  const { fps, width, height } = useVideoConfig();
  if (local < 0) return null;
  const sp = spring({ frame: local, fps, config: { damping: 9, stiffness: 180 } });
  const base: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    top: height * 0.155,
    display: "flex",
    justifyContent: "center",
    fontFamily: fontStack(style === "stamp" || style === "banner" ? "Bangers" : font),
  };
  const len = text.length;
  const fs = Math.min(150, (width * 1.5) / Math.max(len, 4));

  if (style === "stamp") {
    const scale = interpolate(sp, [0, 1], [2.6, 1]);
    const c = color ?? palette.accent;
    return (
      <div style={base}>
        <div
          style={{
            transform: `scale(${scale}) rotate(-7deg)`,
            opacity: Math.min(1, local / 2),
            border: `10px solid ${c}`,
            outline: `4px solid ${c}`,
            outlineOffset: 8,
            borderRadius: 18,
            padding: "6px 34px",
            color: c,
            fontSize: fs,
            letterSpacing: "0.06em",
            background: "rgba(255,255,255,0.75)",
          }}
        >
          {text}
        </div>
      </div>
    );
  }
  if (style === "banner") {
    const x = interpolate(sp, [0, 1], [-width, 0]);
    return (
      <div style={base}>
        <div
          style={{
            transform: `translateX(${x}px) rotate(-3deg)`,
            background: color ?? palette.accent2,
            color: "#fff",
            fontSize: fs * 0.85,
            padding: "14px 40px",
            border: `6px solid ${palette.ink}`,
            boxShadow: `10px 10px 0 ${palette.ink}`,
            WebkitTextStroke: `3px ${palette.ink}`,
            paintOrder: "stroke fill",
          }}
        >
          {text}
        </div>
      </div>
    );
  }
  let shown = text;
  if (style === "counter") {
    const m = text.match(/([\d,.]+)/);
    if (m) {
      const target = parseFloat(m[1].replace(/,/g, ""));
      const p = interpolate(local, [0, fps * 0.9], [0, 1], { extrapolateRight: "clamp", easing: (x) => 1 - Math.pow(1 - x, 3) });
      const val = Math.round(target * p).toLocaleString("en-US");
      shown = text.replace(m[1], val);
    }
  }
  // marker: highlighter swipe + handwritten text written left to right
  const reveal = interpolate(local, [0, fps * 0.5], [0, 100], { extrapolateRight: "clamp" });
  return (
    <div style={base}>
      <div style={{ position: "relative", fontSize: fs, color: color ?? palette.ink, transform: "rotate(-2deg)" }}>
        <div
          style={{
            position: "absolute",
            left: -20,
            right: -20,
            top: "38%",
            height: "48%",
            background: palette.highlight,
            opacity: 0.85,
            borderRadius: 12,
            clipPath: `inset(0 ${100 - Math.min(100, reveal * 1.3)}% 0 0)`,
          }}
        />
        <div style={{ position: "relative", clipPath: `inset(-20% ${100 - reveal}% -20% 0)` }}>{shown}</div>
      </div>
    </div>
  );
};
