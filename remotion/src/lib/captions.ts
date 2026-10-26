import type { Timeline } from "../schema";

export type W = Timeline["words"][number];
export type Chunk = { words: W[]; start: number; end: number };

export function chunkWords(words: W[], perChunk: number): Chunk[] {
  const chunks: Chunk[] = [];
  let cur: W[] = [];
  const flush = () => {
    if (cur.length) chunks.push({ words: cur, start: cur[0].start, end: cur[cur.length - 1].end });
    cur = [];
  };
  words.forEach((w, i) => {
    const prev = words[i - 1];
    if (cur.length && prev && w.start - prev.end > 0.35) flush();
    cur.push(w);
    const longWord = w.text.length > 9;
    if (cur.length >= perChunk || /[.!?,;:]$/.test(w.text) || (longWord && cur.length >= 2)) flush();
  });
  flush();
  return chunks;
}

