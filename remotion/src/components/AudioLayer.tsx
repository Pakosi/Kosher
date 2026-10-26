import React from "react";
import { Audio, interpolate, Sequence, staticFile, useVideoConfig } from "remotion";
import { duckAmount } from "../lib/time";
import type { Timeline } from "../schema";

export const AudioLayer: React.FC<{ tl: Timeline }> = ({ tl }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const music = tl.music;
  return (
    <>
      <Audio src={staticFile(tl.narration)} />
      {music && (
        <Audio
          src={staticFile(music.src)}
          loop
          startFrom={Math.round(music.startFrom * fps)}
          volume={(f) => {
            const t = f / fps;
            const duck = duckAmount(tl.speech, t);
            const v = music.volume * (1 - duck) + music.duckVolume * duck;
            const fadeIn = interpolate(f, [0, fps * 0.4], [0, 1], { extrapolateRight: "clamp" });
            const fadeOut = interpolate(f, [durationInFrames - fps * 0.8, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
            return v * fadeIn * fadeOut;
          }}
        />
      )}
      {tl.sfx.map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * fps)} durationInFrames={fps * 3} layout="none">
          <Audio src={staticFile(s.src)} volume={s.volume * tl.sfxVolume} />
        </Sequence>
      ))}
    </>
  );
};
