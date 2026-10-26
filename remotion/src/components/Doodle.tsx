import React, { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";
import type { Palette } from "../schema";
import { ICONS, type Tone } from "./icons";

export const toneColor = (tone: Tone, p: Palette): string =>
  ({
    accent: p.accent,
    accent2: p.accent2,
    highlight: p.highlight,
    paper: "#FFFFFF",
    money: "#9ED9A0",
    gray: "#D5D2CB",
  })[tone];

/** A built-in icon drawn on with marker strokes: `draw` 0..1 = stroke progress,
 * fills fade in during the second half. */
export const DrawnIcon: React.FC<{ name: string; palette: Palette; draw: number; size: number; stroke?: number }> = ({
  name,
  palette,
  draw,
  size,
  stroke = 4.2,
}) => {
  const icon = ICONS[name] ?? ICONS.question;
  const fillOpacity = Math.max(0, Math.min(1, (draw - 0.45) / 0.4));
  const n = icon.ink.length;
  return (
    <svg width={size} height={size} viewBox="-6 -6 112 112" style={{ overflow: "visible" }}>
      {icon.fills?.map((f, i) => (
        <path key={`f${i}`} d={f.d} fill={toneColor(f.tone, palette)} opacity={fillOpacity} transform="translate(2.5,2.5)" />
      ))}
      {icon.ink.map((d, i) => {
        // strokes draw one after another
        const local = Math.max(0, Math.min(1, draw * n * 1.15 - i));
        return (
          <path
            key={i}
            d={d}
            pathLength={1}
            fill="none"
            stroke={palette.ink}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={1}
            strokeDashoffset={1 - local}
          />
        );
      })}
    </svg>
  );
};

type ParsedSvg = { viewBox: string; transform: string; paths: string[] };
const svgCache = new Map<string, ParsedSvg>();

/** A potrace SVG (generated prop): outlines draw on, then the ink fill appears. */
export const DrawnSvg: React.FC<{ src: string; palette: Palette; draw: number; size: number }> = ({ src, palette, draw, size }) => {
  const [data, setData] = useState<ParsedSvg | null>(svgCache.get(src) ?? null);
  const [handle] = useState(() => (svgCache.has(src) ? null : delayRender(`svg ${src}`)));
  useEffect(() => {
    if (data) return;
    fetch(staticFile(src))
      .then((r) => r.text())
      .then((txt) => {
        const doc = new DOMParser().parseFromString(txt, "image/svg+xml");
        const svg = doc.querySelector("svg");
        const g = doc.querySelector("g");
        const parsed: ParsedSvg = {
          viewBox: svg?.getAttribute("viewBox") ?? "0 0 100 100",
          transform: g?.getAttribute("transform") ?? "",
          paths: Array.from(doc.querySelectorAll("path")).map((p) => p.getAttribute("d") ?? ""),
        };
        svgCache.set(src, parsed);
        setData(parsed);
        if (handle !== null) continueRender(handle);
      })
      .catch((e) => {
        console.error(e);
        if (handle !== null) continueRender(handle);
      });
  }, [src, data, handle]);
  if (!data) return null;
  const fill = Math.max(0, Math.min(1, (draw - 0.55) / 0.35));
  return (
    <svg width={size} height={size} viewBox={data.viewBox} preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
      <g transform={data.transform}>
        {data.paths.map((d, i) => (
          <path
            key={i}
            d={d}
            pathLength={1}
            fill={palette.ink}
            fillOpacity={fill}
            stroke={palette.ink}
            strokeWidth={18}
            strokeDasharray={1}
            strokeDashoffset={1 - Math.min(1, draw * 1.4)}
          />
        ))}
      </g>
    </svg>
  );
};
