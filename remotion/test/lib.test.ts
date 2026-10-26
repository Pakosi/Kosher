import { describe, expect, it } from "vitest";
import { chunkWords } from "../src/lib/captions";
import { activeShape, duckAmount } from "../src/lib/time";

const w = (text: string, start: number, end: number) => ({ text, start, end, emphasis: false });

describe("chunkWords", () => {
  it("splits on size, punctuation and pauses", () => {
    const words = [w("If", 0, 0.1), w("you", 0.1, 0.2), w("had", 0.2, 0.3), w("twenty", 0.3, 0.5), w("million,", 0.5, 0.8), w("how", 1.5, 1.6)];
    const chunks = chunkWords(words, 3).map((c) => c.words.map((x) => x.text).join(" "));
    expect(chunks).toEqual(["If you had", "twenty million,", "how"]);
  });
});

describe("duckAmount", () => {
  it("ramps around speech", () => {
    const speech = [{ start: 1, end: 2 }];
    expect(duckAmount(speech, 0)).toBe(0);
    expect(duckAmount(speech, 1.5)).toBe(1);
    expect(duckAmount(speech, 2.1)).toBeGreaterThan(0);
    expect(duckAmount(speech, 2.1)).toBeLessThan(1);
    expect(duckAmount(speech, 3)).toBe(0);
  });
});

describe("activeShape", () => {
  it("finds the viseme for a speaker", () => {
    const v = [
      { speaker: "a", shape: "D", start: 0, end: 0.2 },
      { speaker: "b", shape: "E", start: 0.1, end: 0.3 },
      { speaker: "a", shape: "A", start: 0.2, end: 0.4 },
    ];
    expect(activeShape(v, "a", 0.15)).toBe("D");
    expect(activeShape(v, "b", 0.15)).toBe("E");
    expect(activeShape(v, "a", 0.3)).toBe("A");
    expect(activeShape(v, "a", 1)).toBeNull();
  });
});
