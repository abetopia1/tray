import React from 'react';
import {interpolate} from 'remotion';
import {BOARD_H, BOARD_W, stringPins} from '../layout';
import {stringWindows} from '../camera';

const STEPS = 48;

// Points along a sagging run of yarn between two pins.
const run = (a: [number, number], b: [number, number]): [number, number][] => {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const horizontal = Math.abs(b[0] - a[0]) / len;
  const sag = len * 0.055 * horizontal;
  const side = len * 0.02 * (1 - horizontal);
  const pts: [number, number][] = [];
  for (let i = 0; i <= STEPS; i++) {
    const u = i / STEPS;
    const bow = 4 * u * (1 - u);
    pts.push([a[0] + (b[0] - a[0]) * u + side * bow, a[1] + (b[1] - a[1]) * u + sag * bow]);
  }
  return pts;
};

const runs = stringPins.slice(0, -1).map((p, i) => run(p, stringPins[i + 1]));

const toPath = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');

const partial = (pts: [number, number][], p: number): [number, number][] => {
  if (p >= 1) return pts;
  const f = p * STEPS;
  const n = Math.floor(f);
  const head = pts.slice(0, n + 1);
  const a = pts[n];
  const b = pts[Math.min(STEPS, n + 1)];
  const r = f - n;
  head.push([a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r]);
  return head;
};

export const RedString: React.FC<{seconds: number}> = ({seconds}) => {
  const drawn = runs
    .map((pts, i) => {
      const [t0, t1] = stringWindows[i];
      const p = interpolate(seconds, [t0, t1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      return p > 0 ? toPath(partial(pts, p)) : null;
    })
    .filter(Boolean) as string[];

  return (
    <svg width={BOARD_W} height={BOARD_H} style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none', overflow: 'visible'}}>
      <defs>
        <filter id="yarn-shadow" x="-2%" y="-2%" width="104%" height="104%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>
      {drawn.map((d, i) => (
        <g key={i} fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d={d} stroke="rgba(0,0,0,0.42)" strokeWidth={9} transform="translate(7 12)" filter="url(#yarn-shadow)" />
          <path d={d} stroke="#7d0c12" strokeWidth={11} />
          <path d={d} stroke="#c8202a" strokeWidth={7.5} />
          <path d={d} stroke="#ee5a60" strokeWidth={2.2} strokeDasharray="7 11" opacity={0.75} />
        </g>
      ))}
    </svg>
  );
};
