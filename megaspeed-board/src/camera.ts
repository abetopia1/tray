import {Easing, interpolate} from 'remotion';
import {BOARD_H, BOARD_W, FRAME, centers} from './layout';
import {beatCount, beatEnd, beatStart, narrationEnd, totalSeconds} from './timing';

export type Cam = {x: number; y: number; zoom: number; focusY: number; rot: number};

// Close shots keep the cluster above the caption band.
const FOCUS_CLOSE = 830;
const close = (beat: number, zoom = 1, rot = 0): Cam => ({
  x: centers[beat][0],
  y: centers[beat][1],
  zoom,
  focusY: FOCUS_CLOSE,
  rot,
});

export const WIDE: Cam = {
  x: BOARD_W / 2,
  y: BOARD_H / 2,
  zoom: Math.min(1080 / (BOARD_W + FRAME * 2 + 90), 1880 / (BOARD_H + FRAME * 2)),
  focusY: 960,
  rot: 0,
};

type Key = {t: number; cam: Cam};

const TRAVEL = 1.05;
const ROLL = [0, -0.5, 0.45, -0.35, 0.5, -0.45, 0.4, -0.5, 0.35, -0.4, 0.3];

// Seconds the wide shot needs between beat 9 and beat 10. The voice edit leaves this gap.
export const WIDE_GAP = 2.6;

const keys: Key[] = (() => {
  const k: Key[] = [{t: 0, cam: close(1, 0.94, ROLL[1])}];
  for (let b = 1; b <= beatCount - 1; b++) {
    // Each beat ends slightly pushed in, then the camera rides the string to the next pin.
    const gapMid = (beatEnd(b) + beatStart(b + 1)) / 2;
    const leave = b === beatCount - 1 ? beatEnd(b) + 0.45 : gapMid - TRAVEL / 2;
    k.push({t: leave, cam: close(b, 1.05, ROLL[b])});
    if (b < beatCount - 1) {
      k.push({t: gapMid + TRAVEL / 2, cam: close(b + 1, 0.98, ROLL[b + 1])});
    }
  }
  const last = beatCount;
  const wideAt = beatEnd(last - 1) + 0.45 + 1.25;
  k.push({t: wideAt, cam: WIDE});
  k.push({t: beatStart(last) + 0.55, cam: {...WIDE, zoom: WIDE.zoom * 1.04}});
  k.push({t: beatStart(last) + 2.0, cam: close(last, 0.98, ROLL[last])});
  k.push({t: narrationEnd + 0.3, cam: close(last, 1.03, ROLL[last])});
  // Final hold drifts down toward the sources card.
  k.push({t: totalSeconds, cam: {...close(last, 1.08, 0), y: centers[last][1] + 30, x: centers[last][0] + 30}});
  return k;
})();

const ease = Easing.inOut(Easing.cubic);

export const cameraAt = (seconds: number): Cam => {
  let i = 0;
  while (i < keys.length - 2 && seconds > keys[i + 1].t) i++;
  const a = keys[i];
  const b = keys[i + 1];
  const p = interpolate(seconds, [a.t, b.t], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const samePlace = a.cam.x === b.cam.x && a.cam.y === b.cam.y;
  const e = samePlace ? p : ease(p);
  const mix = (u: number, v: number) => u + (v - u) * e;
  // Zoom blends in log space so a pull-back feels even.
  const zoom = Math.exp(mix(Math.log(a.cam.zoom), Math.log(b.cam.zoom)));

  // Slow handheld drift, scaled so the wide shot stays steady.
  const sway = Math.min(1, zoom);
  const dx = (Math.sin(seconds * 0.9) * 7 + Math.sin(seconds * 2.3 + 1) * 2.5) * sway;
  const dy = (Math.cos(seconds * 0.7 + 2) * 6 + Math.sin(seconds * 1.9) * 2) * sway;

  return {
    x: mix(a.cam.x, b.cam.x) + dx,
    y: mix(a.cam.y, b.cam.y) + dy,
    zoom,
    focusY: mix(a.cam.focusY, b.cam.focusY),
    rot: mix(a.cam.rot, b.cam.rot) + Math.sin(seconds * 0.5) * 0.12 * sway,
  };
};

// When each string segment starts and finishes drawing. Segment i runs from pin i to pin i + 1.
export const stringWindows: [number, number][] = (() => {
  const out: [number, number][] = [];
  for (let b = 1; b <= beatCount - 1; b++) {
    if (b === beatCount - 1) {
      out.push([beatStart(b + 1) - 0.55, beatStart(b + 1) + 0.1]);
    } else {
      const gapMid = (beatEnd(b) + beatStart(b + 1)) / 2;
      out.push([gapMid - TRAVEL / 2 - 0.1, beatStart(b + 1) + 0.02]);
    }
  }
  return out;
})();
