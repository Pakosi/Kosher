import React from "react";
import { AbsoluteFill } from "remotion";

/** Instagram Reels UI overlay (approximate) for previewing in the Studio. */
export const SafeZones: React.FC = () => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "12%", background: "rgba(255,0,0,0.18)" }} />
    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "20%", background: "rgba(255,0,0,0.18)" }} />
    <div style={{ position: "absolute", top: "40%", bottom: "20%", right: 0, width: "13%", background: "rgba(255,0,0,0.18)" }} />
  </AbsoluteFill>
);
