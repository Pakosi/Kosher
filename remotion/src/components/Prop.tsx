import React from "react";
import { Img, interpolate, spring, staticFile, useVideoConfig } from "remotion";
import { fontStack } from "../lib/fonts";
import { hash01 } from "../lib/time";
import type { Palette, TLProp } from "../schema";
import { DrawnIcon, DrawnSvg } from "./Doodle";
import { useBoil } from "./LineBoil";

export const Prop: React.FC<{ prop: TLProp; palette: Palette; font: string; local: number }> = ({ prop, palette, font, local }) => {
  const { fps, width, height } = useVideoConfig();
  const boil = useBoil();
  if (local < 0) return null;
  const size = 340 * prop.scale;
  const sp = spring({ frame: local, fps, config: { damping: 10, stiffness: 170 } });
  const drawDur = prop.animation === "draw" ? fps * 0.8 : fps * 0.35;
  const draw = interpolate(local, [0, drawDur], [0, 1], { extrapolateRight: "clamp" });
  let dx = 0, dy = 0, sc = 1, rot = prop.rotation;
  switch (prop.animation) {
    case "pop":
      sc = interpolate(sp, [0, 1], [0, 1]);
      break;
    case "slide_left":
      dx = interpolate(sp, [0, 1], [width, 0]);
      break;
    case "slide_right":
      dx = interpolate(sp, [0, 1], [-width, 0]);
      break;
    case "drop":
      dy = interpolate(sp, [0, 1], [-height * 0.5, 0]);
      break;
    case "stamp":
      sc = interpolate(sp, [0, 1], [2.2, 1]);
      rot += interpolate(sp, [0, 1], [-15, 0]);
      break;
  }
  const seed = hash01(prop.id + prop.x);
  const wobble = Math.sin(local / fps * 2.2 + seed * 6) * 2.2;
  const bob = Math.sin(local / fps * 1.7 + seed * 4) * 5;
  const fullDraw = prop.animation === "draw" ? draw : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: prop.x * width - size / 2 + dx,
        top: prop.y * height - size / 2 + dy + bob,
        width: size,
        height: size,
        transform: `scale(${sc}) rotate(${rot + wobble}deg)`,
        filter: boil,
      }}
    >
      {prop.kind === "icon" && <DrawnIcon name={prop.icon ?? "question"} palette={palette} draw={fullDraw} size={size} />}
      {prop.kind === "svg" && prop.src && <DrawnSvg src={prop.src} palette={palette} draw={fullDraw} size={size} />}
      {prop.kind === "image" && prop.src && (
        <Img
          src={staticFile(prop.src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            clipPath: prop.animation === "draw" ? `inset(0 ${100 - draw * 100}% 0 0)` : undefined,
          }}
        />
      )}
      {prop.label && (
        <div
          style={{
            position: "absolute",
            top: size * 0.98,
            left: -size * 0.3,
            right: -size * 0.3,
            textAlign: "center",
            fontFamily: fontStack(font),
            fontSize: 54 * Math.max(0.8, prop.scale),
            color: palette.ink,
            opacity: interpolate(local, [drawDur * 0.6, drawDur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          {prop.label}
        </div>
      )}
    </div>
  );
};
