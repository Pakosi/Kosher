// Mirrors orchestrator/reels/spec.py `Timeline` (the Remotion input props).
import { z } from "zod";

const span = z.object({ start: z.number(), end: z.number() });

export const rigPose = z.object({
  src: z.string(),
  width: z.number(),
  height: z.number(),
  mouth: z.record(z.string(), z.number()),
  eyes: z.array(z.record(z.string(), z.number())).default([]),
});

export const rig = z.object({
  poses: z.record(z.string(), rigPose),
  expressions: z.record(z.string(), z.string()).default({}),
  mouthColor: z.string().default("#1B1B1B"),
  skinColor: z.string().default("#FFFFFF"),
});

export const procedural = z.object({
  species: z.string(),
  body: z.string(),
  accent: z.string(),
  accessory: z.string(),
});

export const character = z.object({
  id: z.string(),
  pose: z.string(),
  expression: z.string(),
  x: z.number(),
  y: z.number(),
  scale: z.number(),
  flip: z.boolean(),
  enter: z.string(),
  rig: rig.nullable().default(null),
  procedural,
});

export const prop = z.object({
  id: z.string(),
  kind: z.enum(["icon", "svg", "image"]),
  icon: z.string().nullable().default(null),
  src: z.string().nullable().default(null),
  label: z.string().nullable().default(null),
  x: z.number(),
  y: z.number(),
  scale: z.number(),
  rotation: z.number(),
  at: z.number(),
  animation: z.string(),
});

export const scene = z.object({
  id: z.string(),
  start: z.number(),
  end: z.number(),
  background: z.object({
    kind: z.enum(["builtin", "image", "svg"]),
    name: z.string().default("plain"),
    src: z.string().nullable().default(null),
  }),
  characters: z.array(character),
  props: z.array(prop),
  camera: z.string(),
  cameraIntensity: z.number(),
  text: z
    .object({ text: z.string(), style: z.string(), at: z.number(), color: z.string().nullable().default(null) })
    .nullable()
    .default(null),
  transition: z.string(),
});

export const timelineSchema = z.object({
  episodeId: z.string(),
  title: z.string(),
  fps: z.number(),
  width: z.number(),
  height: z.number(),
  durationInFrames: z.number(),
  palette: z.object({
    paper: z.string(),
    ink: z.string(),
    accent: z.string(),
    accent2: z.string(),
    highlight: z.string(),
  }),
  caption: z.object({
    font: z.string(),
    size: z.number(),
    highlight: z.string(),
    position: z.number(),
    wordsPerChunk: z.number(),
  }),
  narration: z.string(),
  music: z
    .object({ src: z.string(), volume: z.number(), duckVolume: z.number(), startFrom: z.number().default(0) })
    .nullable()
    .default(null),
  speech: z.array(span),
  sfx: z.array(z.object({ src: z.string(), at: z.number(), volume: z.number().default(1) })),
  words: z.array(z.object({ text: z.string(), start: z.number(), end: z.number(), emphasis: z.boolean().default(false) })),
  visemes: z.array(z.object({ speaker: z.string(), shape: z.string(), start: z.number(), end: z.number() })),
  scenes: z.array(scene),
  lineBoil: z.boolean().default(true),
  showSafeZones: z.boolean().default(false),
  sfxVolume: z.number().default(0.7),
});

export type Timeline = z.infer<typeof timelineSchema>;
export type TLScene = z.infer<typeof scene>;
export type TLCharacter = z.infer<typeof character>;
export type TLProp = z.infer<typeof prop>;
export type Rig = z.infer<typeof rig>;
export type Palette = Timeline["palette"];
