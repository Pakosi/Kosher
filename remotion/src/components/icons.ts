// Built-in doodle icon library (100x100 viewBox). `fills` are flat colour
// shapes drawn first; `ink` are marker strokes that animate on ("draw").
// Names must match orchestrator/reels/vocab.py ICONS.
export type Tone = "accent" | "accent2" | "highlight" | "paper" | "money" | "gray";
export type IconDef = { fills?: { d: string; tone: Tone }[]; ink: string[] };

const circle = (cx: number, cy: number, r: number) =>
  `M${cx - r},${cy} a${r},${r} 0 1,0 ${r * 2},0 a${r},${r} 0 1,0 ${-r * 2},0`;
const rect = (x: number, y: number, w: number, h: number, r = 4) =>
  `M${x + r},${y} h${w - 2 * r} q${r},0 ${r},${r} v${h - 2 * r} q0,${r} ${-r},${r} h${-(w - 2 * r)} q${-r},0 ${-r},${-r} v${-(h - 2 * r)} q0,${-r} ${r},${-r} Z`;

export const ICONS: Record<string, IconDef> = {
  money_stack: {
    fills: [{ d: rect(12, 52, 76, 26, 3), tone: "money" }, { d: rect(16, 40, 72, 14, 3), tone: "money" }, { d: rect(20, 28, 70, 14, 3), tone: "money" }],
    ink: [rect(12, 52, 76, 26, 3), rect(16, 40, 72, 14, 3), rect(20, 28, 70, 14, 3), circle(50, 65, 8), "M47,61 q6,-2 6,2 q0,3 -6,4 q-1,4 6,3 M50,57 v16", "M22,70 h8 M70,58 h8"],
  },
  bag_of_money: {
    fills: [{ d: "M30,40 q-22,30 -6,48 q26,10 52,0 q16,-18 -6,-48 Z", tone: "money" }],
    ink: ["M30,40 q-22,30 -6,48 q26,10 52,0 q16,-18 -6,-48 Z", "M36,40 l-8,-22 q10,6 22,0 q12,6 22,0 l-8,22", "M34,40 h32", "M50,52 v28 M57,57 q-14,-6 -14,3 q0,6 14,6 q0,8 -14,5"],
  },
  coin: {
    fills: [{ d: circle(50, 50, 34), tone: "highlight" }],
    ink: [circle(50, 50, 34), circle(50, 50, 26), "M58,38 q-16,-8 -16,4 q0,8 16,8 q0,12 -18,6 M50,30 v40"],
  },
  bank: {
    fills: [{ d: "M14,36 L50,14 L86,36 Z", tone: "accent2" }],
    ink: ["M14,36 L50,14 L86,36 Z", "M14,36 h72", "M22,42 v34 M38,42 v34 M62,42 v34 M78,42 v34", "M16,80 h68 M12,88 h76", circle(50, 27, 4)],
  },
  briefcase: {
    fills: [{ d: rect(12, 32, 76, 52, 6), tone: "accent" }],
    ink: [rect(12, 32, 76, 52, 6), "M38,32 v-8 q0,-6 6,-6 h12 q6,0 6,6 v8", "M12,52 h76", rect(44, 47, 12, 10, 2)],
  },
  house: {
    fills: [{ d: "M20,48 h60 v38 h-60 Z", tone: "highlight" }, { d: "M12,50 L50,16 L88,50 Z", tone: "accent" }],
    ink: ["M12,50 L50,16 L88,50", "M20,46 v40 h60 v-40", rect(42, 60, 16, 26, 2), rect(26, 56, 12, 12, 1), "M66,24 v12 h8 v-6"],
  },
  car: {
    fills: [{ d: "M10,62 q0,-14 14,-14 l10,-14 h32 l12,14 q12,0 12,14 v8 h-80 Z", tone: "accent" }],
    ink: ["M10,62 q0,-14 14,-14 l10,-14 h32 l12,14 q12,0 12,14 v8 h-80 Z", "M38,38 h12 v10 h-20 Z M56,38 h8 l8,10 h-16 Z", circle(28, 72, 9), circle(72, 72, 9)],
  },
  phone: {
    fills: [{ d: rect(30, 10, 40, 80, 8), tone: "gray" }, { d: rect(35, 20, 30, 58, 2), tone: "paper" }],
    ink: [rect(30, 10, 40, 80, 8), rect(35, 20, 30, 58, 2), "M46,15 h8", circle(50, 84, 2)],
  },
  laptop: {
    fills: [{ d: rect(20, 20, 60, 42, 4), tone: "accent2" }],
    ink: [rect(20, 20, 60, 42, 4), rect(26, 26, 48, 30, 1), "M10,70 h80 l-6,10 h-68 Z", "M42,75 h16"],
  },
  police: {
    fills: [{ d: "M50,10 l32,12 q0,40 -32,66 q-32,-26 -32,-66 Z", tone: "accent2" }],
    ink: ["M50,10 l32,12 q0,40 -32,66 q-32,-26 -32,-66 Z", "M50,30 l5,10 11,1 -8,8 2,11 -10,-5 -10,5 2,-11 -8,-8 11,-1 Z"],
  },
  clock: {
    fills: [{ d: circle(50, 52, 34), tone: "paper" }],
    ink: [circle(50, 52, 34), "M50,52 v-20 M50,52 l14,10", "M50,22 v4 M50,78 v4 M20,52 h4 M76,52 h4", "M30,16 l-10,8 M70,16 l10,8"],
  },
  globe: {
    fills: [{ d: circle(50, 50, 36), tone: "accent2" }],
    ink: [circle(50, 50, 36), "M14,50 h72", "M50,14 q-22,36 0,72 q22,-36 0,-72", "M20,32 q30,8 60,0 M20,68 q30,-8 60,0"],
  },
  lightbulb: {
    fills: [{ d: "M50,12 q26,0 26,26 q0,14 -12,24 v8 h-28 v-8 q-12,-10 -12,-24 q0,-26 26,-26 Z", tone: "highlight" }],
    ink: ["M50,12 q26,0 26,26 q0,14 -12,24 v8 h-28 v-8 q-12,-10 -12,-24 q0,-26 26,-26 Z", "M38,76 h24 M40,84 h20 M44,90 h12", "M44,60 l6,-14 6,14", "M10,30 l8,4 M90,30 l-8,4 M50,2 v4"],
  },
  brain: {
    fills: [{ d: "M50,20 q-10,-10 -22,-2 q-14,0 -14,16 q-8,10 0,22 q0,16 16,16 q8,10 20,2 q12,8 20,-2 q16,0 16,-16 q8,-12 0,-22 q0,-16 -14,-16 q-12,-8 -22,2 Z", tone: "accent" }],
    ink: ["M50,20 q-10,-10 -22,-2 q-14,0 -14,16 q-8,10 0,22 q0,16 16,16 q8,10 20,2 q12,8 20,-2 q16,0 16,-16 q8,-12 0,-22 q0,-16 -14,-16 q-12,-8 -22,2 Z", "M50,20 v54", "M30,36 q8,4 8,12 M70,36 q-8,4 -8,12 M28,58 q8,-4 14,2 M72,58 q-8,-4 -14,2"],
  },
  chart_up: {
    ink: ["M14,14 v72 h72", "M22,74 l18,-18 14,10 26,-34", "M66,30 h14 v14"],
    fills: [{ d: "M22,74 l18,-18 14,10 26,-34 v52 h-58 Z", tone: "accent2" }],
  },
  chart_down: {
    ink: ["M14,14 v72 h72", "M22,26 l18,18 14,-10 26,34", "M66,70 h14 v-14"],
    fills: [{ d: "M22,26 l18,18 14,-10 26,34 v18 h-58 Z", tone: "accent" }],
  },
  lock: {
    fills: [{ d: rect(22, 44, 56, 42, 6), tone: "highlight" }],
    ink: [rect(22, 44, 56, 42, 6), "M32,44 v-12 q0,-18 18,-18 q18,0 18,18 v12", circle(50, 62, 5), "M50,67 v8"],
  },
  key: {
    fills: [{ d: circle(30, 50, 16), tone: "highlight" }],
    ink: [circle(30, 50, 16), circle(30, 50, 6), "M46,50 h42 M76,50 v12 M86,50 v8"],
  },
  fire: {
    fills: [{ d: "M50,90 q-30,0 -30,-28 q0,-20 18,-36 q0,16 10,18 q-4,-24 16,-36 q0,22 14,34 q10,10 2,26 q-6,22 -30,22 Z", tone: "accent" }, { d: "M50,90 q-14,0 -14,-14 q0,-10 10,-18 q2,10 8,10 q4,-8 4,-14 q10,10 8,22 q-2,14 -16,14 Z", tone: "highlight" }],
    ink: ["M50,90 q-30,0 -30,-28 q0,-20 18,-36 q0,16 10,18 q-4,-24 16,-36 q0,22 14,34 q10,10 2,26 q-6,22 -30,22 Z"],
  },
  skull: {
    fills: [{ d: "M50,12 q32,0 32,32 q0,16 -12,22 v14 h-40 v-14 q-12,-6 -12,-22 q0,-32 32,-32 Z", tone: "paper" }],
    ink: ["M50,12 q32,0 32,32 q0,16 -12,22 v14 h-40 v-14 q-12,-6 -12,-22 q0,-32 32,-32 Z", circle(38, 44, 8), circle(62, 44, 8), "M50,54 l-4,8 h8 Z", "M40,80 v-8 M50,80 v-8 M60,80 v-8"],
  },
  diamond: {
    fills: [{ d: "M28,20 h44 l16,18 -38,46 -38,-46 Z", tone: "accent2" }],
    ink: ["M28,20 h44 l16,18 -38,46 -38,-46 Z", "M12,38 h76", "M28,20 l10,18 12,46 12,-46 10,-18 M38,38 l12,-18 12,18"],
  },
  document: {
    fills: [{ d: "M24,10 h38 l16,16 v64 h-54 Z", tone: "paper" }],
    ink: ["M24,10 h38 l16,16 v64 h-54 Z", "M62,10 v16 h16", "M32,40 h36 M32,50 h36 M32,60 h36 M32,70 h22"],
  },
  magnifier: {
    fills: [{ d: circle(42, 42, 24), tone: "accent2" }],
    ink: [circle(42, 42, 24), "M60,60 l24,24", "M58,64 l6,-6 24,24 -6,6 Z", "M30,34 q4,-8 12,-8"],
  },
  calendar: {
    fills: [{ d: rect(14, 22, 72, 64, 6), tone: "paper" }, { d: "M14,28 q0,-6 6,-6 h60 q6,0 6,6 v12 h-72 Z", tone: "accent" }],
    ink: [rect(14, 22, 72, 64, 6), "M14,40 h72", "M30,14 v14 M70,14 v14", "M26,52 h8 M46,52 h8 M66,52 h8 M26,68 h8 M46,68 h8"],
  },
  plane: {
    fills: [{ d: "M10,56 l30,-4 26,-30 h8 l-12,30 24,-2 8,-10 h6 l-4,16 4,16 h-6 l-8,-10 -24,-2 12,30 h-8 l-26,-30 -30,-4 Z", tone: "paper" }],
    ink: ["M10,56 l30,-4 26,-30 h8 l-12,30 24,-2 8,-10 h6 l-4,16 4,16 h-6 l-8,-10 -24,-2 12,30 h-8 l-26,-30 -30,-4 Z"],
  },
  ship: {
    fills: [{ d: "M12,60 h76 l-12,22 h-52 Z", tone: "accent" }],
    ink: ["M12,60 h76 l-12,22 h-52 Z", "M30,60 v-20 h40 v20 M40,40 v-16 h12 v16", "M6,90 q8,-6 16,0 q8,6 16,0 q8,-6 16,0 q8,6 16,0 q8,-6 16,0"],
  },
  washing_machine: {
    fills: [{ d: rect(18, 10, 64, 80, 6), tone: "paper" }, { d: circle(50, 56, 20), tone: "accent2" }],
    ink: [rect(18, 10, 64, 80, 6), "M18,28 h64", circle(50, 56, 20), circle(50, 56, 13), circle(30, 19, 3), circle(42, 19, 3), "M60,19 h14"],
  },
  casino_chip: {
    fills: [{ d: circle(50, 50, 36), tone: "accent" }, { d: circle(50, 50, 20), tone: "paper" }],
    ink: [circle(50, 50, 36), circle(50, 50, 20), "M50,14 v10 M50,76 v10 M14,50 h10 M76,50 h10 M25,25 l7,7 M68,68 l7,7 M25,75 l7,-7 M68,32 l7,-7"],
  },
  alarm: {
    fills: [{ d: "M28,74 v-26 q0,-22 22,-22 q22,0 22,22 v26 Z", tone: "accent" }],
    ink: ["M28,74 v-26 q0,-22 22,-22 q22,0 22,22 v26 Z", "M18,74 h64 v10 h-64 Z", "M50,14 v6 M18,26 l6,6 M82,26 l-6,6 M8,50 h8 M84,50 h8"],
  },
  scale: {
    fills: [{ d: "M8,54 q14,14 28,0 Z M64,44 q14,14 28,0 Z", tone: "highlight" }],
    ink: ["M50,12 v72 M32,86 h36", "M14,26 l72,-8", "M22,25 l-14,29 h28 Z M78,19 l-14,25 h28 Z", circle(50, 14, 4)],
  },
  question: {
    fills: [],
    ink: ["M30,34 q0,-22 20,-22 q20,0 20,18 q0,12 -14,18 q-6,4 -6,14 v6", circle(50, 84, 4)],
  },
  exclamation: { ink: ["M50,12 v54", circle(50, 82, 5)] },
  arrow: { ink: ["M12,60 q30,-40 70,-30", "M66,18 l16,12 -14,14"] },
  heart: {
    fills: [{ d: "M50,86 q-40,-26 -40,-50 q0,-20 20,-20 q14,0 20,14 q6,-14 20,-14 q20,0 20,20 q0,24 -40,50 Z", tone: "accent" }],
    ink: ["M50,86 q-40,-26 -40,-50 q0,-20 20,-20 q14,0 20,14 q6,-14 20,-14 q20,0 20,20 q0,24 -40,50 Z"],
  },
  star: {
    fills: [{ d: "M50,10 l12,26 28,3 -21,19 6,28 -25,-14 -25,14 6,-28 -21,-19 28,-3 Z", tone: "highlight" }],
    ink: ["M50,10 l12,26 28,3 -21,19 6,28 -25,-14 -25,14 6,-28 -21,-19 28,-3 Z"],
  },
  crown: {
    fills: [{ d: "M14,72 l-4,-44 22,18 18,-28 18,28 22,-18 -4,44 Z", tone: "highlight" }],
    ink: ["M14,72 l-4,-44 22,18 18,-28 18,28 22,-18 -4,44 Z", "M14,82 h72", circle(50, 58, 5)],
  },
  handcuffs: {
    fills: [],
    ink: [circle(28, 60, 18), circle(72, 60, 18), circle(28, 60, 10), circle(72, 60, 10), "M40,46 q10,-14 20,0", "M24,42 v-6 h8 v6 M68,42 v-6 h8 v6"],
  },
  credit_card: {
    fills: [{ d: rect(10, 24, 80, 52, 6), tone: "accent2" }],
    ink: [rect(10, 24, 80, 52, 6), "M10,38 h80", rect(18, 50, 16, 10, 2), "M18,66 h30 M58,66 h20"],
  },
  receipt: {
    fills: [{ d: "M26,8 h48 v84 l-8,-6 -8,6 -8,-6 -8,6 -8,-6 -8,6 Z", tone: "paper" }],
    ink: ["M26,8 h48 v84 l-8,-6 -8,6 -8,-6 -8,6 -8,-6 -8,6 Z", "M34,24 h32 M34,36 h24 M34,48 h32 M34,60 h18", "M34,74 h32"],
  },
  pizza: {
    fills: [{ d: "M50,90 L14,22 q36,-18 72,0 Z", tone: "highlight" }, { d: "M14,22 q36,-18 72,0 l-4,8 q-32,-14 -64,0 Z", tone: "accent" }],
    ink: ["M50,90 L14,22 q36,-18 72,0 Z", "M18,30 q32,-14 64,0", circle(40, 42, 5), circle(58, 48, 5), circle(50, 64, 4)],
  },
  eye: {
    fills: [{ d: "M8,50 q42,-44 84,0 q-42,44 -84,0 Z", tone: "paper" }, { d: circle(50, 50, 16), tone: "accent2" }],
    ink: ["M8,50 q42,-44 84,0 q-42,44 -84,0 Z", circle(50, 50, 16), circle(50, 50, 6)],
  },
  trophy: {
    fills: [{ d: "M30,14 h40 v24 q0,22 -20,22 q-20,0 -20,-22 Z", tone: "highlight" }],
    ink: ["M30,14 h40 v24 q0,22 -20,22 q-20,0 -20,-22 Z", "M30,22 h-12 q0,18 14,20 M70,22 h12 q0,18 -14,20", "M50,60 v14 M34,86 h32 v-12 h-32 Z"],
  },
  rocket: {
    fills: [{ d: "M50,8 q20,18 20,48 v14 h-40 v-14 q0,-30 20,-48 Z", tone: "paper" }, { d: "M40,70 l10,22 10,-22 Z", tone: "accent" }],
    ink: ["M50,8 q20,18 20,48 v14 h-40 v-14 q0,-30 20,-48 Z", circle(50, 38, 8), "M30,52 l-12,18 v8 l12,-8 M70,52 l12,18 v8 l-12,-8", "M40,70 l10,22 10,-22"],
  },
  battery: {
    fills: [{ d: rect(12, 32, 34, 36, 2), tone: "accent2" }],
    ink: [rect(10, 28, 72, 44, 6), "M82,42 h8 v16 h-8", "M46,32 v36"],
  },
  cloud: {
    fills: [{ d: "M24,74 q-16,0 -16,-16 q0,-14 16,-16 q2,-20 22,-20 q16,0 22,14 q22,-2 24,18 q2,20 -20,20 Z", tone: "paper" }],
    ink: ["M24,74 q-16,0 -16,-16 q0,-14 16,-16 q2,-20 22,-20 q16,0 22,14 q22,-2 24,18 q2,20 -20,20 Z"],
  },
  gift: {
    fills: [{ d: rect(16, 40, 68, 48, 4), tone: "accent" }],
    ink: [rect(16, 40, 68, 48, 4), rect(10, 30, 80, 12, 3), "M50,30 v58", "M50,30 q-24,-20 -24,-6 q0,8 24,6 q24,2 24,-6 q0,-14 -24,6"],
  },
  cart: {
    fills: [{ d: "M24,26 h64 l-8,30 h-48 Z", tone: "accent2" }],
    ink: ["M8,14 h12 l12,50 h48", "M24,26 h64 l-8,30 h-48", circle(38, 78, 7), circle(72, 78, 7)],
  },
  factory: {
    fills: [{ d: "M10,88 v-40 l20,-12 v12 l20,-12 v12 l20,-12 v52 Z", tone: "gray" }],
    ink: ["M10,88 v-40 l20,-12 v12 l20,-12 v12 l20,-12 v52 Z", "M70,88 v-74 h14 v74", "M6,88 h88", rect(20, 60, 10, 10, 1), rect(42, 60, 10, 10, 1), "M76,8 q6,-6 12,-2"],
  },
  hourglass: {
    fills: [{ d: "M30,78 q0,-14 20,-22 q20,8 20,22 Z", tone: "highlight" }],
    ink: ["M24,10 h52 M24,90 h52", "M30,10 q0,26 20,40 q-20,14 -20,40 M70,10 q0,26 -20,40 q20,14 20,40"],
  },
  target: {
    fills: [{ d: circle(46, 54, 34), tone: "accent" }, { d: circle(46, 54, 22), tone: "paper" }, { d: circle(46, 54, 10), tone: "accent" }],
    ink: [circle(46, 54, 34), circle(46, 54, 22), circle(46, 54, 10), "M46,54 l40,-40 M78,14 h8 v8"],
  },
  megaphone: {
    fills: [{ d: "M20,40 l50,-22 v64 l-50,-22 Z", tone: "accent" }],
    ink: ["M20,40 l50,-22 v64 l-50,-22 Z", rect(10, 38, 12, 24, 2), "M30,64 l6,22 h10 l-6,-18", "M80,36 q8,14 0,28 M88,30 q12,20 0,40"],
  },
  camera: {
    fills: [{ d: rect(10, 28, 80, 56, 8), tone: "gray" }, { d: circle(50, 56, 18), tone: "accent2" }],
    ink: [rect(10, 28, 80, 56, 8), "M34,28 l6,-10 h20 l6,10", circle(50, 56, 18), circle(50, 56, 8), circle(78, 38, 3)],
  },
  book: {
    fills: [{ d: "M50,24 q-18,-10 -40,-6 v64 q22,-4 40,6 Z", tone: "accent2" }, { d: "M50,24 q18,-10 40,-6 v64 q-22,-4 -40,6 Z", tone: "accent" }],
    ink: ["M50,24 q-18,-10 -40,-6 v64 q22,-4 40,6 q18,-10 40,-6 v-64 q-22,-4 -40,6 Z", "M50,24 v64"],
  },
  shield: {
    fills: [{ d: "M50,10 l34,12 q0,44 -34,68 q-34,-24 -34,-68 Z", tone: "accent2" }],
    ink: ["M50,10 l34,12 q0,44 -34,68 q-34,-24 -34,-68 Z", "M34,50 l12,12 22,-24"],
  },
  chain: {
    fills: [],
    ink: [rect(8, 38, 34, 24, 12), rect(33, 38, 34, 24, 12), rect(58, 38, 34, 24, 12)],
  },
};

export const ICON_NAMES = Object.keys(ICONS);
