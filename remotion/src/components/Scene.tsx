import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { noise2D } from "@remotion/noise";
import { activeShape } from "../lib/time";
import type { Timeline, TLScene } from "../schema";
import { Background } from "./Background";
import { CharacterLayer } from "./Character";
import { LineBoil } from "./LineBoil";
import { OnScreenText } from "./OnScreenText";
import { Prop } from "./Prop";

export const TRANSITION_SEC = 0.32;

function cameraTransform(scene: TLScene, local: number, fps: number): string {
  const dur = Math.max(scene.end - scene.start, 0.1) * fps;
  const p = Math.min(1, Math.max(0, local / dur));
  const k = scene.cameraIntensity;
  const ease = Easing.inOut(Easing.cubic)(p);
  switch (scene.camera) {
    case "push_in":
      return `scale(${1 + 0.12 * k * ease})`;
    case "pull_out":
      return `scale(${1 + 0.12 * k * (1 - ease)})`;
    case "pan_left":
      return `scale(1.08) translateX(${interpolate(ease, [0, 1], [40, -40]) * k}px)`;
    case "pan_right":
      return `scale(1.08) translateX(${interpolate(ease, [0, 1], [-40, 40]) * k}px)`;
    case "tilt_up":
      return `scale(1.08) translateY(${interpolate(ease, [0, 1], [-40, 40]) * k}px)`;
    case "shake": {
      const decay = Math.exp(-local / (fps * 0.35)) * 0.85 + 0.15;
      const x = noise2D("sx", local * 0.35, 0) * 22 * k * decay;
      const y = noise2D("sy", local * 0.35, 0) * 22 * k * decay;
      return `translate(${x}px, ${y}px) rotate(${noise2D("sr", local * 0.3, 0) * 1.5 * k * decay}deg)`;
    }
    case "whip_zoom": {
      const z = interpolate(local, [0, fps * 0.3], [1.4, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.exp) });
      return `scale(${z + 0.04 * k * ease})`;
    }
    default:
      return `scale(${1 + 0.02 * ease})`; // never fully static: subtle drift keeps it alive
  }
}

function transitionStyle(kind: string, local: number, fps: number, width: number): React.CSSProperties {
  const d = TRANSITION_SEC * fps;
  if (kind === "cut" || local >= d) return {};
  const p = Easing.out(Easing.cubic)(Math.max(0, local / d));
  switch (kind) {
    case "whip":
      return { transform: `translateX(${(1 - p) * width}px)`, filter: `blur(${(1 - p) * 18}px)` };
    case "paper":
      return {
        transform: `translateY(${(1 - p) * 110}%) rotate(${(1 - p) * 6}deg)`,
        boxShadow: "0 -20px 40px rgba(0,0,0,0.25)",
      };
    case "zoom":
      return { transform: `scale(${0.55 + 0.45 * p})`, opacity: p };
    case "ink_wipe":
      return { clipPath: `circle(${p * 120}% at 50% 55%)` };
    default:
      return {};
  }
}

export const SceneView: React.FC<{ scene: TLScene; tl: Timeline; index: number }> = ({ scene, tl, index }) => {
  const frame = useCurrentFrame(); // relative to the scene Sequence
  const { fps, width, height } = useVideoConfig();
  const tAbs = scene.start + frame / fps;
  const at = (s: number) => Math.round((s - scene.start) * fps);
  return (
    <AbsoluteFill style={{ overflow: "hidden", ...transitionStyle(index === 0 ? "cut" : scene.transition, frame, fps, width) }}>
      <AbsoluteFill style={{ transform: cameraTransform(scene, frame, fps), transformOrigin: "50% 60%" }}>
        <Background bg={scene.background} palette={tl.palette} />
        <LineBoil enabled={tl.lineBoil}>
          {scene.props.map((p) => (
            <Prop key={p.id} prop={p} palette={tl.palette} font={tl.caption.font} local={frame - at(p.at)} />
          ))}
          {scene.characters.map((c) => (
            <CharacterLayer
              key={c.id}
              ch={c}
              palette={tl.palette}
              shape={activeShape(tl.visemes, c.id, tAbs)}
              frame={frame}
              fps={fps}
              width={width}
              height={height}
            />
          ))}
        </LineBoil>
      </AbsoluteFill>
      {scene.text && (
        <OnScreenText
          text={scene.text.text}
          style={scene.text.style}
          color={scene.text.color}
          palette={tl.palette}
          font={tl.caption.font}
          local={frame - at(scene.text.at)}
        />
      )}
    </AbsoluteFill>
  );
};
