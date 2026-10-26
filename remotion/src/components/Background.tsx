import React from "react";
import { Img, staticFile } from "remotion";
import type { Palette, TLScene } from "../schema";

const W = 1080;
const H = 1920;

const Decor: React.FC<{ name: string; p: Palette }> = ({ name, p }) => {
  const s = { stroke: p.ink, strokeWidth: 5, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const, opacity: 0.16 };
  switch (name) {
    case "grid":
      return (
        <g>
          {Array.from({ length: 34 }, (_, i) => (
            <line key={`h${i}`} x1={0} x2={W} y1={i * 60} y2={i * 60} stroke="#7FB3D5" strokeWidth={2} opacity={0.35} />
          ))}
          <line x1={120} x2={120} y1={0} y2={H} stroke="#E57373" strokeWidth={3} opacity={0.45} />
        </g>
      );
    case "dots":
      return (
        <g opacity={0.22}>
          {Array.from({ length: 18 * 32 }, (_, i) => (
            <circle key={i} cx={(i % 18) * 64 + 20} cy={Math.floor(i / 18) * 64 + 20} r={3} fill={p.ink} />
          ))}
        </g>
      );
    case "desk":
      return (
        <g {...s}>
          <path d="M0,1520 h1080" />
          <path d="M60,1520 v320 M1020,1520 v320" />
          <path d="M820,1520 l40,-200 l-90,-80 M770,1240 l-60,40 l50,30 Z" />
          <rect x={120} y={1420} width={200} height={100} rx={8} />
        </g>
      );
    case "city":
      return (
        <g {...s}>
          <path d="M0,1500 v-260 h120 v-120 h90 v200 h80 v-340 h140 v280 h90 v-180 h120 v260 h100 v-400 h130 v360 h110 v200" />
          {Array.from({ length: 12 }, (_, i) => (
            <rect key={i} x={300 + (i % 3) * 40} y={900 + Math.floor(i / 3) * 70} width={20} height={30} />
          ))}
          <path d="M0,1500 h1080" />
          <circle cx={880} cy={300} r={70} />
        </g>
      );
    case "bank":
      return (
        <g {...s}>
          <path d="M140,760 L540,560 L940,760 Z M140,760 h800" />
          {[220, 380, 540, 700, 860].map((x) => (
            <path key={x} d={`M${x},790 v520 M${x - 30},790 h60 M${x - 30},1310 h60`} />
          ))}
          <path d="M100,1340 h880 M60,1400 h960" />
          <text x={540} y={720} textAnchor="middle" fontSize={60} fill={p.ink} stroke="none" opacity={0.9}>
            $
          </text>
        </g>
      );
    case "alley":
      return (
        <g {...s}>
          <path d="M0,300 L380,900 V1500 L0,1920 M1080,300 L700,900 V1500 L1080,1920 M380,900 H700 M380,1500 H700" />
          {Array.from({ length: 10 }, (_, i) => (
            <path key={i} d={`M${20 + i * 30},${420 + i * 60} h60 M${1000 - i * 30},${420 + i * 60} h-60`} />
          ))}
          <rect x={470} y={1080} width={140} height={420} />
        </g>
      );
    case "lab":
      return (
        <g {...s}>
          <path d="M80,700 h920 M80,1000 h920 M0,1520 h1080" />
          <path d="M160,700 v-120 h40 v120 M180,580 v-20 M300,700 q-50,0 -30,-80 l20,-80 h20 l20,80 q20,80 -30,80" />
          <circle cx={760} cy={940} r={50} />
          <path d="M760,890 v-80" />
          <path d="M860,1000 v-140 h60 v140" />
        </g>
      );
    case "map":
      return (
        <g {...s}>
          <path d="M80,200 q200,120 160,380 q-40,260 160,320 q220,60 160,320 q-40,200 200,380" strokeDasharray="20 22" strokeWidth={6} />
          <path d="M120,1300 q140,-80 260,40 q120,120 300,-20 M600,400 q120,-60 260,40 q80,80 140,-10" />
          <path d="M840,1560 l60,60 M900,1560 l-60,60" strokeWidth={9} opacity={0.4} />
        </g>
      );
    case "room":
      return (
        <g {...s}>
          <path d="M0,1440 h1080" />
          <rect x={640} y={420} width={280} height={340} />
          <path d="M780,420 v340 M640,590 h280" />
          <rect x={150} y={520} width={220} height={160} />
          <path d="M180,650 l60,-70 50,50 30,-30 50,50" />
        </g>
      );
    default:
      return (
        <g {...s}>
          <path d="M90,220 l14,28 30,4 -22,20 6,30 -28,-14 -26,14 6,-30 -22,-20 30,-4 Z" />
          <path d="M930,1700 q40,-40 80,0 q-40,40 -80,0" />
          <path d="M960,240 q-30,30 0,60 q30,30 0,60" />
          <path d="M80,1740 h80 M120,1700 v80" />
        </g>
      );
  }
};

export const Background: React.FC<{ bg: TLScene["background"]; palette: Palette }> = ({ bg, palette }) => (
  <div style={{ position: "absolute", inset: 0, background: palette.paper }}>
    {bg.kind === "image" && bg.src ? (
      <Img src={staticFile(bg.src)} style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.85 }} />
    ) : (
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
        <Decor name={bg.name} p={palette} />
      </svg>
    )}
  </div>
);

const GRAIN_TILE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 0.08"/></feComponentTransfer></filter><rect width="256" height="256" filter="url(#n)"/></svg>`,
  );

/** Paper grain: a small noise tile rasterised once and repeated (cheap). */
export const PaperGrain: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      pointerEvents: "none",
      mixBlendMode: "multiply",
      backgroundImage: `url("${GRAIN_TILE}")`,
      backgroundRepeat: "repeat",
    }}
  />
);
