import React from "react";
import { Composition } from "remotion";
import { Reel } from "./Reel";
import { sampleTimeline } from "./sample";
import { timelineSchema } from "./schema";

export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    schema={timelineSchema}
    defaultProps={sampleTimeline}
    durationInFrames={sampleTimeline.durationInFrames || 300}
    fps={30}
    width={1080}
    height={1920}
    calculateMetadata={({ props }) => ({
      durationInFrames: props.durationInFrames,
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
