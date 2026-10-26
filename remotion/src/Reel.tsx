import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { AudioLayer } from "./components/AudioLayer";
import { PaperGrain } from "./components/Background";
import { Captions } from "./components/Captions";
import { SafeZones } from "./components/SafeZones";
import { SceneView, TRANSITION_SEC } from "./components/Scene";
import { loadFonts } from "./lib/fonts";
import type { Timeline } from "./schema";

loadFonts();

export const Reel: React.FC<Timeline> = (tl) => {
  const { fps, durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: tl.palette.paper }}>
      {tl.scenes.map((s, i) => {
        const from = Math.round(s.start * fps);
        const next = tl.scenes[i + 1];
        // keep each scene alive a little past its end so the next scene can transition over it
        const until = next ? Math.round(next.start * fps) + Math.round(TRANSITION_SEC * fps) : durationInFrames;
        return (
          <Sequence key={s.id} from={from} durationInFrames={Math.max(1, until - from)} name={`${s.id} ${s.camera}`}>
            <SceneView scene={s} tl={tl} index={i} />
          </Sequence>
        );
      })}
      <PaperGrain />
      <Captions tl={tl} />
      <AudioLayer tl={tl} />
      {tl.showSafeZones && <SafeZones />}
    </AbsoluteFill>
  );
};
