// Default props for `npm run studio`. Regenerate with:
//   reels studio-sample <episode>   (copies that episode's timeline + public files here)
import sample from "./sample.json";
import type { Timeline } from "./schema";

export const sampleTimeline = sample as unknown as Timeline;
