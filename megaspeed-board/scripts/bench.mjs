// Times single frames under different effect flags.
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';

const browserExecutable = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const variants = JSON.parse(process.argv[2]);
const frames = [330, 1500, 2890];
for (const [name, inputProps, gl] of variants) {
  const chromiumOptions = gl ? {gl} : {};
  const composition = await selectComposition({serveUrl, id: 'Board', browserExecutable, chromiumOptions, inputProps});
  const t0 = Date.now();
  for (const frame of frames) {
    await renderStill({composition, serveUrl, frame, output: `out/bench.jpg`, imageFormat: 'jpeg', browserExecutable, chromiumOptions, inputProps});
  }
  console.log(name.padEnd(28), ((Date.now() - t0) / frames.length / 1000).toFixed(2), 's/frame');
}
