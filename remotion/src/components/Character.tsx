import React from "react";
import { interpolate, spring, staticFile } from "remotion";
import { hash01 } from "../lib/time";
import type { Palette, Rig, TLCharacter } from "../schema";
import { useBoil } from "./LineBoil";
import { Mouth } from "./Mouth";

type P = [number, number];
type PoseDef = { lh: P; rh: P; le?: P; re?: P; tilt: number; dy: number; lf: P; rf: P };

// viewBox 0 0 400 640, feet at y≈620
const POSES: Record<string, PoseDef> = {
  neutral: { lh: [100, 470], rh: [300, 470], tilt: 0, dy: 0, lf: [165, 615], rf: [235, 615] },
  point: { lh: [102, 468], rh: [392, 318], re: [330, 350], tilt: 3, dy: 0, lf: [165, 615], rf: [240, 615] },
  shock: { lh: [80, 250], rh: [320, 250], le: [92, 330], re: [308, 330], tilt: -6, dy: -26, lf: [150, 600], rf: [250, 600] },
  think: { lh: [110, 452], rh: [222, 292], re: [300, 380], tilt: -3, dy: 0, lf: [168, 615], rf: [232, 615] },
  smug: { lh: [238, 405], rh: [164, 405], le: [140, 430], re: [262, 430], tilt: -4, dy: 0, lf: [160, 615], rf: [240, 615] },
  shrug: { lh: [62, 330], rh: [338, 330], le: [92, 400], re: [308, 400], tilt: 0, dy: -4, lf: [165, 615], rf: [235, 615] },
  run: { lh: [100, 420], rh: [300, 420], tilt: 8, dy: -10, lf: [140, 600], rf: [260, 600] },
  sneak: { lh: [150, 380], rh: [262, 368], le: [120, 420], re: [300, 410], tilt: 12, dy: 18, lf: [150, 615], rf: [262, 612] },
  celebrate: { lh: [92, 118], rh: [308, 118], le: [100, 240], re: [300, 240], tilt: 0, dy: -30, lf: [160, 598], rf: [240, 598] },
  facepalm: { lh: [104, 470], rh: [214, 214], re: [300, 330], tilt: 6, dy: 4, lf: [165, 615], rf: [235, 615] },
};

const BROWS: Record<string, [number, number]> = {
  // [inner offset, outer offset] in px (negative = up)
  neutral: [0, 0],
  happy: [-6, -4],
  smug: [4, -8],
  worried: [-12, 6],
  shocked: [-18, -16],
  angry: [12, -8],
  sad: [-10, 8],
  excited: [-12, -12],
  suspicious: [6, 2],
};

const Eye: React.FC<{ cx: number; cy: number; expr: string; blink: number; look: number; ink: string; side: -1 | 1 }> = ({
  cx,
  cy,
  expr,
  blink,
  look,
  ink,
  side,
}) => {
  const r = expr === "shocked" ? 30 : expr === "excited" ? 28 : 25;
  const pupil = expr === "shocked" ? 7 : expr === "excited" ? 13 : 11;
  const lid = expr === "smug" || expr === "suspicious" ? 0.45 : expr === "angry" ? 0.25 : 0;
  const open = Math.max(0, 1 - blink);
  if (expr === "happy" && blink < 0.5) {
    return <path d={`M${cx - 20},${cy + 6} q20,-24 40,0`} fill="none" stroke={ink} strokeWidth={6} strokeLinecap="round" />;
  }
  const ry = r * open;
  return (
    <g>
      <ellipse cx={cx} cy={cy} rx={r} ry={Math.max(ry, 1.5)} fill="#fff" stroke={ink} strokeWidth={5} />
      {open > 0.25 && <circle cx={cx + look * 8 + (expr === "suspicious" ? side * -0 + 8 : 0)} cy={cy + (expr === "sad" ? 6 : 2)} r={pupil} fill={ink} />}
      {open > 0.25 && expr === "excited" && <circle cx={cx + look * 8 + 4} cy={cy - 3} r={4} fill="#fff" />}
      {lid > 0 && open > 0.25 && (
        <path
          d={`M${cx - r - 2},${cy - r * (1 - 2 * lid)} L${cx + r + 2},${cy - r * (1 - 2 * lid) + (expr === "angry" ? side * -8 : 0)} L${cx + r + 2},${cy - r - 4} L${cx - r - 2},${cy - r - 4} Z`}
          fill="#F2EFE8"
          stroke={ink}
          strokeWidth={4}
        />
      )}
    </g>
  );
};

const Accessory: React.FC<{ kind: string; ink: string; accent: string }> = ({ kind, ink, accent }) => {
  const s = { stroke: ink, strokeWidth: 6, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };
  switch (kind) {
    case "fedora":
      return (
        <g>
          <path d="M70,128 q130,-30 260,0 q-20,16 -130,16 q-110,0 -130,-16 Z" fill="#3B3B3B" {...s} />
          <path d="M118,124 q4,-64 82,-62 q78,-2 82,62 Z" fill="#3B3B3B" {...s} />
          <path d="M120,112 q80,-14 160,0 v12 q-80,-12 -160,0 Z" fill={accent} {...s} strokeWidth={4} />
        </g>
      );
    case "glasses":
      return (
        <g fill="none" {...s}>
          <circle cx={160} cy={200} r={34} />
          <circle cx={240} cy={200} r={34} />
          <path d="M194,200 h12 M126,196 l-40,-8 M274,196 l40,-8" />
        </g>
      );
    case "beanie":
      return (
        <g>
          <path d="M92,150 q8,-110 108,-110 q100,0 108,110 Z" fill={accent} {...s} />
          <path d="M84,150 h232 v28 h-232 Z" fill={accent} {...s} />
          <circle cx={200} cy={36} r={18} fill="#fff" {...s} />
        </g>
      );
    case "crown":
      return <path d="M136,118 l-8,-62 36,30 36,-46 36,46 36,-30 -8,62 Z" fill="#FFD166" {...s} />;
    case "headphones":
      return (
        <g>
          <path d="M84,210 q0,-160 116,-160 q116,0 116,160" fill="none" {...s} strokeWidth={12} />
          <rect x={64} y={180} width={34} height={70} rx={14} fill={accent} {...s} />
          <rect x={302} y={180} width={34} height={70} rx={14} fill={accent} {...s} />
        </g>
      );
    default:
      return null;
  }
};

const arm = (sh: P, hand: P, elbow?: P) => {
  const e = elbow ?? [(sh[0] + hand[0]) / 2 + (hand[0] < sh[0] ? -18 : 18), (sh[1] + hand[1]) / 2 + 14];
  return `M${sh[0]},${sh[1]} Q${e[0]},${e[1]} ${hand[0]},${hand[1]}`;
};

export const ProceduralCharacter: React.FC<{
  ch: TLCharacter;
  palette: Palette;
  shape: string | null;
  frame: number;
  fps: number;
}> = ({ ch, palette, shape, frame, fps }) => {
  const look = ch.procedural;
  const ink = palette.ink;
  const pose = POSES[ch.pose] ?? POSES.neutral;
  const t = frame / fps;
  const seed = hash01(ch.id);
  // idle breathing + talk bob
  const breathe = Math.sin(t * 2.4 + seed * 6) * 0.012;
  const talk = shape && shape !== "X" && shape !== "A" ? 1 : 0;
  const bob = Math.sin(t * 14) * 3 * talk;
  // blink: ~every 3.2s, 4 frames
  const period = 3.2 + seed;
  const phase = (t + seed * 7) % period;
  const blink = phase < 0.07 ? phase / 0.07 : phase < 0.14 ? 1 - (phase - 0.07) / 0.07 : 0;
  const lookDir = Math.sin(t * 0.7 + seed * 3) > 0.6 ? 1 : Math.sin(t * 0.7 + seed * 3) < -0.6 ? -1 : 0;

  let lh = pose.lh, rh = pose.rh, lf = pose.lf, rf = pose.rf;
  if (ch.pose === "run") {
    const c = Math.sin(t * 16);
    lh = [100 + c * 40, 420 - Math.abs(c) * 20];
    rh = [300 - c * 40, 420 - Math.abs(c) * 20];
    lf = [170 + c * 50, 600 - Math.max(0, c) * 30];
    rf = [230 - c * 50, 600 - Math.max(0, -c) * 30];
  }
  const species = look.species;
  const s = { stroke: ink, strokeWidth: 7, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };
  const brow = BROWS[ch.expression] ?? BROWS.neutral;
  const headY = species === "human" ? 210 : 215;
  const mouthShape = shape ?? "X";

  return (
    <svg viewBox="0 0 400 640" width="100%" height="100%" style={{ overflow: "visible" }}>
      <g transform={`translate(0 ${pose.dy}) rotate(${pose.tilt} 200 600) translate(200 600) scale(${1 - breathe} ${1 + breathe}) translate(-200 -600)`}>
        {/* tail */}
        {species === "raccoon" && (
          <g>
            <path d="M270,500 q90,10 100,-80 q4,-30 -14,-40 q-6,60 -90,80 Z" fill="#8C8C8C" {...s} />
            <path d="M345,455 l22,8 M352,428 l18,0 M330,478 l18,14" stroke={ink} strokeWidth={12} />
          </g>
        )}
        {species === "cat" && <path d="M268,520 q80,0 70,-110 q-2,-20 14,-26" fill="none" {...s} strokeWidth={16} stroke={look.body} />}
        {species === "cat" && <path d="M268,520 q80,0 70,-110 q-2,-20 14,-26" fill="none" stroke={ink} strokeWidth={4} />}
        {/* legs */}
        <path d={`M175,505 L${lf[0]},${lf[1] - 8}`} fill="none" {...s} strokeWidth={9} />
        <path d={`M225,505 L${rf[0]},${rf[1] - 8}`} fill="none" {...s} strokeWidth={9} />
        <ellipse cx={lf[0] - 8} cy={lf[1]} rx={24} ry={11} fill={ink} />
        <ellipse cx={rf[0] + 8} cy={rf[1]} rx={24} ry={11} fill={ink} />
        {/* body */}
        {species === "human" ? (
          <path d="M128,360 q72,-30 144,0 l14,150 q-86,24 -172,0 Z" fill={look.accent} {...s} />
        ) : (
          <ellipse cx={200} cy={425} rx={90} ry={104} fill={look.body} {...s} />
        )}
        {species !== "human" && <ellipse cx={200} cy={445} rx={52} ry={62} fill="#fff" opacity={0.55} />}
        {/* arms */}
        <path d={arm([132, 372], lh, pose.le)} fill="none" {...s} strokeWidth={9} />
        <path d={arm([268, 372], rh, pose.re)} fill="none" {...s} strokeWidth={9} />
        <circle cx={lh[0]} cy={lh[1]} r={14} fill={species === "human" ? "#F3C9A5" : look.body} {...s} strokeWidth={5} />
        <circle cx={rh[0]} cy={rh[1]} r={14} fill={species === "human" ? "#F3C9A5" : look.body} {...s} strokeWidth={5} />
        {/* head */}
        <g transform={`translate(0 ${bob})`}>
          {species === "raccoon" && (
            <g>
              <path d="M98,150 l-6,-70 62,38 Z" fill="#8C8C8C" {...s} />
              <path d="M302,150 l6,-70 -62,38 Z" fill="#8C8C8C" {...s} />
            </g>
          )}
          {species === "cat" && (
            <g>
              <path d="M100,160 l2,-96 70,52 Z" fill={look.body} {...s} />
              <path d="M300,160 l-2,-96 -70,52 Z" fill={look.body} {...s} />
            </g>
          )}
          {species === "human" ? (
            <circle cx={200} cy={headY} r={98} fill="#F3C9A5" {...s} />
          ) : (
            <ellipse cx={200} cy={headY} rx={122} ry={108} fill={species === "raccoon" ? "#A7A7A7" : look.body} {...s} />
          )}
          {species === "raccoon" && (
            <path d="M86,196 q30,-40 114,-14 q84,-26 114,14 q-10,40 -54,34 q-36,-6 -60,-20 q-24,14 -60,20 q-44,6 -54,-34 Z" fill="#3C3C3C" />
          )}
          {species === "raccoon" && <ellipse cx={200} cy={262} rx={58} ry={38} fill="#EDEDED" />}
          {species === "human" && <path d="M106,180 q20,-100 94,-90 q74,-10 94,90 q-30,-40 -94,-46 q-64,6 -94,46 Z" fill={ink} />}
          {/* brows */}
          <path d={`M128,${148 + brow[1]} L182,${150 + brow[0]}`} {...s} strokeWidth={8} />
          <path d={`M218,${150 + brow[0]} L272,${148 + brow[1]}`} {...s} strokeWidth={8} />
          <Eye cx={160} cy={195} expr={ch.expression} blink={blink} look={lookDir} ink={ink} side={-1} />
          <Eye cx={240} cy={195} expr={ch.expression} blink={blink} look={lookDir} ink={ink} side={1} />
          {/* nose */}
          {species === "raccoon" || species === "cat" ? (
            <ellipse cx={200} cy={238} rx={12} ry={8} fill={ink} />
          ) : null}
          {species === "cat" && (
            <path d="M110,240 h50 M112,256 l48,-6 M290,240 h-50 M288,256 l-48,-6" stroke={ink} strokeWidth={3} />
          )}
          <g transform={`translate(200 ${species === "human" ? 262 : 268})`}>
            <Mouth shape={mouthShape} ink={ink} mood={ch.expression} scale={1.2} />
          </g>
          {(ch.expression === "worried" || ch.expression === "shocked") && (
            <path d="M318,140 q8,14 0,22 q-8,-8 0,-22 Z" fill="#8ECAE6" stroke={ink} strokeWidth={3} />
          )}
          <Accessory kind={look.accessory} ink={ink} accent={look.accent} />
        </g>
      </g>
    </svg>
  );
};

/** Generated character: pose PNG from the rig + animated mouth and blink overlays. */
export const RigCharacter: React.FC<{ ch: TLCharacter; rig: Rig; palette: Palette; shape: string | null; frame: number; fps: number }> = ({
  ch,
  rig,
  palette,
  shape,
  frame,
  fps,
}) => {
  const poseName = rig.poses[ch.pose] ? ch.pose : rig.expressions[ch.expression] ?? Object.keys(rig.poses)[0];
  const pose = rig.poses[poseName];
  const t = frame / fps;
  const seed = hash01(ch.id);
  const phase = (t + seed * 7) % (3.3 + seed);
  const blinking = phase < 0.12;
  const breathe = Math.sin(t * 2.4 + seed * 6) * 0.01;
  const talk = shape && shape !== "X" && shape !== "A" ? Math.sin(t * 14) * 2 : 0;
  const m = pose.mouth;
  const mouthScale = (m.w ?? 60) / 60;
  return (
    <svg viewBox={`0 0 ${pose.width} ${pose.height}`} width="100%" height="100%" style={{ overflow: "visible" }}>
      <g transform={`translate(${pose.width / 2} ${pose.height}) scale(${1 - breathe} ${1 + breathe}) translate(${-pose.width / 2} ${-pose.height + talk})`}>
        <image href={staticFile(pose.src)} width={pose.width} height={pose.height} />
        {/* cover the drawn mouth with a skin patch, then draw the live mouth */}
        <g transform={`translate(${m.x} ${m.y}) rotate(${m.rotation ?? 0})`}>
          <ellipse cx={0} cy={2} rx={34 * mouthScale} ry={22 * mouthScale} fill={rig.skinColor} />
          <Mouth shape={shape ?? "X"} ink={rig.mouthColor ?? palette.ink} mood={ch.expression} scale={mouthScale} />
        </g>
        {blinking &&
          pose.eyes.map((e, i) => (
            <g key={i}>
              <ellipse cx={e.x} cy={e.y} rx={e.r * 1.15} ry={e.r * 1.15} fill={rig.skinColor} />
              <path d={`M${e.x - e.r},${e.y} q${e.r},${e.r * 0.5} ${e.r * 2},0`} stroke={palette.ink} strokeWidth={Math.max(3, e.r / 5)} fill="none" />
            </g>
          ))}
      </g>
    </svg>
  );
};

export const CharacterLayer: React.FC<{
  ch: TLCharacter;
  palette: Palette;
  shape: string | null;
  frame: number; // frames since scene start
  fps: number;
  width: number;
  height: number;
}> = ({ ch, palette, shape, frame, fps, width, height }) => {
  const boil = useBoil();
  const h = height * 0.36 * ch.scale;
  const aspect = ch.rig ? (() => {
    const p = Object.values(ch.rig.poses)[0];
    return p.width / p.height;
  })() : 400 / 640;
  const w = h * aspect;
  const enterP = spring({ frame, fps, config: { damping: 12, stiffness: 140 } });
  let dx = 0, dy = 0, sc = 1;
  if (ch.enter === "pop") sc = interpolate(enterP, [0, 1], [0.2, 1]);
  if (ch.enter === "slide_left") dx = interpolate(enterP, [0, 1], [-width * 0.6, 0]);
  if (ch.enter === "slide_right") dx = interpolate(enterP, [0, 1], [width * 0.6, 0]);
  if (ch.enter === "drop") dy = interpolate(enterP, [0, 1], [-height * 0.6, 0]);
  // tiny pose "settle" squash at scene start
  const settle = 1 + 0.04 * Math.exp(-frame / 4) * Math.cos(frame / 2);
  return (
    <div
      style={{
        position: "absolute",
        left: ch.x * width - w / 2 + dx,
        top: ch.y * height - h + dy,
        width: w,
        height: h,
        transform: `scale(${(ch.flip ? -1 : 1) * sc * (2 - settle)}, ${sc * settle})`,
        transformOrigin: "50% 100%",
        filter: boil,
      }}
    >
      {/* soft ground shadow */}
      <div
        style={{
          position: "absolute",
          left: "15%",
          right: "15%",
          bottom: -h * 0.02,
          height: h * 0.05,
          borderRadius: "50%",
          background: "rgba(0,0,0,0.12)",
        }}
      />
      {ch.rig ? (
        <RigCharacter ch={ch} rig={ch.rig} palette={palette} shape={shape} frame={frame} fps={fps} />
      ) : (
        <ProceduralCharacter ch={ch} palette={palette} shape={shape} frame={frame} fps={fps} />
      )}
    </div>
  );
};

