import React from "react";

/** Rhubarb / Preston Blair mouth set. Drawn centred at (0,0), ~60 units wide. */
export const Mouth: React.FC<{ shape: string; ink: string; tongue?: string; mood?: string; scale?: number }> = ({
  shape,
  ink,
  tongue = "#E86A6A",
  mood = "neutral",
  scale = 1,
}) => {
  const s = { stroke: ink, strokeWidth: 4.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const dark = "#3A1F1F";
  let el: React.ReactNode;
  switch (shape) {
    case "A": // M B P
      el = <path d="M-20,0 q20,4 40,0" fill="none" {...s} />;
      break;
    case "B": // most consonants, teeth
      el = (
        <g>
          <path d="M-20,-5 q20,-3 40,0 q-2,12 -20,12 q-18,0 -20,-12 Z" fill={dark} {...s} />
          <path d="M-16,-3 h32" stroke="#fff" strokeWidth={4} />
        </g>
      );
      break;
    case "C": // EH AE
      el = (
        <g>
          <ellipse cx={0} cy={2} rx={22} ry={13} fill={dark} {...s} />
          <path d="M-12,9 q12,-6 24,0" fill={tongue} />
        </g>
      );
      break;
    case "D": // AA wide open
      el = (
        <g>
          <path d="M-26,-8 q26,-6 52,0 q0,34 -26,34 q-26,0 -26,-34 Z" fill={dark} {...s} />
          <path d="M-14,18 q14,-12 28,0 q-4,6 -14,6 q-10,0 -14,-6 Z" fill={tongue} />
          <path d="M-20,-6 h40" stroke="#fff" strokeWidth={4} />
        </g>
      );
      break;
    case "E": // AO ER rounded
      el = <ellipse cx={0} cy={3} rx={15} ry={16} fill={dark} {...s} />;
      break;
    case "F": // UW OW W pucker
      el = <ellipse cx={0} cy={2} rx={9} ry={10} fill={dark} {...s} />;
      break;
    case "G": // F V
      el = (
        <g>
          <path d="M-18,2 q18,8 36,0" fill="none" {...s} />
          <path d="M-12,-2 h24 v5 h-24 Z" fill="#fff" stroke={ink} strokeWidth={3} />
        </g>
      );
      break;
    case "H": // L
      el = (
        <g>
          <ellipse cx={0} cy={3} rx={18} ry={14} fill={dark} {...s} />
          <path d="M-8,-2 q8,-8 16,0 v6 h-16 Z" fill={tongue} />
        </g>
      );
      break;
    default: {
      // rest: depends on mood
      const rest: Record<string, React.ReactNode> = {
        happy: <path d="M-20,-4 q20,22 40,0" fill="none" {...s} />,
        excited: <path d="M-22,-6 q22,4 44,0 q-4,24 -22,24 q-18,0 -22,-24 Z" fill={dark} {...s} />,
        smug: <path d="M-18,4 q22,4 34,-10" fill="none" {...s} />,
        worried: <path d="M-18,4 q6,-6 12,0 q6,6 12,0 q6,-6 12,0" fill="none" {...s} />,
        shocked: <ellipse cx={0} cy={4} rx={13} ry={17} fill={dark} {...s} />,
        angry: <path d="M-20,6 q20,-12 40,0" fill="none" {...s} />,
        sad: <path d="M-18,8 q18,-14 36,0" fill="none" {...s} />,
        suspicious: <path d="M-16,2 h28" fill="none" {...s} />,
      };
      el = rest[mood] ?? <path d="M-18,0 q18,8 36,0" fill="none" {...s} />;
    }
  }
  return <g transform={`scale(${scale})`}>{el}</g>;
};
