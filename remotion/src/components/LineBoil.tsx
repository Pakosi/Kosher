import React, { createContext, useContext } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

const BoilCtx = createContext<string | null>(null);

/** CSS filter value for an element that should "boil" (null when disabled). */
export const useBoil = (): string | undefined => {
  const id = useContext(BoilCtx);
  return id ? `url(#${id})` : undefined;
};

/** Hand-drawn "line boil": a turbulence displacement whose seed changes ~10x/s
 * through a 4-drawing cycle. The filter is applied per element (props,
 * characters) rather than full-frame, which keeps render cost low. */
export const LineBoil: React.FC<{ enabled: boolean; strength?: number; children: React.ReactNode }> = ({
  enabled,
  strength = 3.2,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!enabled) return <>{children}</>;
  const step = Math.max(1, Math.round(fps / 10));
  const seed = Math.floor(frame / step) % 4;
  const id = `boil-${seed}`;
  return (
    <BoilCtx.Provider value={id}>
      <svg width={0} height={0} style={{ position: "absolute" }}>
        <filter id={id} x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves={2} seed={seed * 17 + 1} result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale={strength} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>
      {children}
    </BoilCtx.Provider>
  );
};
