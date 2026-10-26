import { continueRender, delayRender } from "remotion";
import gochi from "@fontsource/gochi-hand/files/gochi-hand-latin-400-normal.woff2";
import bangers from "@fontsource/bangers/files/bangers-latin-400-normal.woff2";
import patrick from "@fontsource/patrick-hand/files/patrick-hand-latin-400-normal.woff2";
import marker from "@fontsource/permanent-marker/files/permanent-marker-latin-400-normal.woff2";
import caveat from "@fontsource/caveat-brush/files/caveat-brush-latin-400-normal.woff2";
import luckiest from "@fontsource/luckiest-guy/files/luckiest-guy-latin-400-normal.woff2";

// Bundled (offline) fonts. Series configs pick one by family name.
export const FONTS: Record<string, string> = {
  "Gochi Hand": gochi,
  Bangers: bangers,
  "Patrick Hand": patrick,
  "Permanent Marker": marker,
  "Caveat Brush": caveat,
  "Luckiest Guy": luckiest,
};

let loaded = false;

export function loadFonts() {
  if (loaded || typeof document === "undefined") return;
  loaded = true;
  const handle = delayRender("fonts");
  Promise.all(
    Object.entries(FONTS).map(async ([family, url]) => {
      const face = new FontFace(family, `url(${url}) format("woff2")`);
      await face.load();
      (document.fonts as unknown as Set<FontFace>).add(face);
    }),
  )
    .then(() => continueRender(handle))
    .catch((e) => {
      console.error("font load failed", e);
      continueRender(handle);
    });
}

export const fontStack = (family: string) => `"${family}", "Patrick Hand", "Comic Sans MS", cursive`;
