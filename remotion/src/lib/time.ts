import type { Timeline } from "../schema";

export const sec = (frame: number, fps: number) => frame / fps;
export const toFrame = (s: number, fps: number) => Math.round(s * fps);

/** Binary search for the viseme active at time t for a speaker. */
export function activeShape(visemes: Timeline["visemes"], speaker: string, t: number): string | null {
  let lo = 0;
  let hi = visemes.length - 1;
  let found: string | null = null;
  if (visemes.length === 0) return null;
  // visemes are sorted by start overall; filter by speaker linearly in a small window
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (visemes[mid].start <= t) lo = mid + 1;
    else hi = mid - 1;
  }
  for (let i = Math.max(0, hi); i >= 0 && i >= hi - 40; i--) {
    const v = visemes[i];
    if (v.speaker === speaker && v.start <= t && t < v.end) {
      found = v.shape;
      break;
    }
  }
  return found;
}

export function isSpeaking(speech: Timeline["speech"], t: number): boolean {
  return speech.some((s) => t >= s.start && t < s.end);
}

/** 0..1 ducking envelope: 1 while speech is active, smoothed with attack/release ramps. */
export function duckAmount(speech: Timeline["speech"], t: number, attack = 0.12, release = 0.35): number {
  let v = 0;
  for (const s of speech) {
    if (t >= s.start - attack && t <= s.end + release) {
      const up = t < s.start ? 1 - (s.start - t) / attack : 1;
      const down = t > s.end ? 1 - (t - s.end) / release : 1;
      v = Math.max(v, Math.min(up, down));
    }
  }
  return Math.max(0, Math.min(1, v));
}

/** Deterministic hash -> [0,1) used for stable per-element jitter. */
export function hash01(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}
