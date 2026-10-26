import React, { useMemo } from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontStack } from "../lib/fonts";
import { hash01 } from "../lib/time";
import { chunkWords } from "../lib/captions";
import type { Timeline } from "../schema";

export const Captions: React.FC<{ tl: Timeline }> = ({ tl }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const chunks = useMemo(() => chunkWords(tl.words, tl.caption.wordsPerChunk), [tl.words, tl.caption.wordsPerChunk]);
  const idx = chunks.findIndex((c, i) => t >= c.start - 0.05 && t < (chunks[i + 1]?.start ?? c.end + 0.6) - 0.05);
  if (idx < 0) return null;
  const chunk = chunks[idx];
  const local = frame - Math.round((chunk.start - 0.05) * fps);
  const pop = spring({ frame: local, fps, config: { damping: 11, stiffness: 220, mass: 0.6 } });
  const rot = (hash01(String(idx)) - 0.5) * 6;
  const size = tl.caption.size;
  return (
    <div
      style={{
        position: "absolute",
        left: width * 0.07,
        right: width * 0.07,
        top: tl.caption.position * height,
        transform: `translateY(-50%) scale(${interpolate(pop, [0, 1], [0.72, 1])}) rotate(${rot}deg)`,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: `${size * 0.12}px ${size * 0.36}px`,
        fontFamily: fontStack(tl.caption.font),
        fontSize: size,
        lineHeight: 1.05,
        textAlign: "center",
        textTransform: "uppercase",
      }}
    >
      {chunk.words.map((w, i) => {
        const active = t >= w.start && t < w.end + 0.04;
        const said = t >= w.start;
        const color = w.emphasis || active ? tl.caption.highlight : "#FFFFFF";
        const wPop = spring({ frame: frame - Math.round(w.start * fps), fps, config: { damping: 10, stiffness: 260 } });
        const scale = active ? interpolate(wPop, [0, 1], [1.12, 1.04]) : 1;
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              padding: `0 ${size * 0.08}px`,
              fontSize: w.emphasis ? size * 1.16 : size,
              color,
              opacity: said ? 1 : 0.55,
              transform: `scale(${scale})`,
              WebkitTextStroke: `${size * 0.16}px ${tl.palette.ink}`,
              paintOrder: "stroke fill",
              textShadow: `0 ${size * 0.07}px 0 ${tl.palette.ink}`,
              letterSpacing: "0.02em",
            }}
          >
            {w.text.replace(/[,;:]$/, "")}
          </span>
        );
      })}
    </div>
  );
};
