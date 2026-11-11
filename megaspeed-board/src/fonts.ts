import {continueRender, delayRender, staticFile} from 'remotion';

// Fonts are bundled in public/fonts (all SIL Open Font License) so renders work offline.
const FACES: [family: string, file: string, weight: string][] = [
  ['Special Elite', 'SpecialElite.woff2', '400'],
  ['Permanent Marker', 'PermanentMarker.woff2', '400'],
  ['Archivo Black', 'ArchivoBlack.woff2', '400'],
  ['Oswald', 'Oswald.woff2', '200 700'],
  ['Caveat', 'Caveat.woff2', '400 700'],
];

if (typeof document !== 'undefined') {
  const handle = delayRender('Loading fonts');
  Promise.all(
    FACES.map(([family, file, weight]) => {
      const face = new FontFace(family, `url(${staticFile(`fonts/${file}`)}) format('woff2')`, {weight});
      return face.load().then((f) => (document.fonts as unknown as {add: (font: FontFace) => void}).add(f));
    }),
  ).then(() => continueRender(handle));
}

export const typewriter = "'Special Elite', monospace";
export const marker = "'Permanent Marker', cursive";
export const captionFont = "'Archivo Black', sans-serif";
export const stampFont = "'Oswald', sans-serif";
export const hand = "'Caveat', cursive";
