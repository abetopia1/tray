// Renders check frames. Usage: node scripts/stills.mjs <scale> <seconds> [<seconds> ...]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdirSync} from 'node:fs';
import path from 'node:path';

const [scale, ...times] = process.argv.slice(2);
const browserExecutable = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const chromiumOptions = {gl: 'swangle'};

mkdirSync('out/stills', {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'Board', browserExecutable, chromiumOptions});
console.log('duration', (composition.durationInFrames / composition.fps).toFixed(1), 's');

for (const t of times) {
  const frame = Math.min(composition.durationInFrames - 1, Math.round(Number(t) * composition.fps));
  const output = `out/stills/t${String(t).padStart(6, '0')}.jpg`;
  await renderStill({composition, serveUrl, frame, output, imageFormat: 'jpeg', jpegQuality: 88, scale: Number(scale), browserExecutable, chromiumOptions});
  console.log(output);
}
