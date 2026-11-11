import React from 'react';
import {interpolate, spring, staticFile} from 'remotion';
import map from '../data/map.json';
import {stampFont, typewriter} from '../fonts';
import {Pin} from './Paper';

const LAND: Record<string, string> = {
  china: '#d9b88a',
  taiwan: '#cfd8b0',
  malaysia: '#cfd8b0',
  singapore: '#b0171f',
};

type Props = {w: number; flagFrame: number; fps: number};

// Outlines come from Natural Earth (public domain). The flag lands when Megaspeed is named.
export const PaperMap: React.FC<Props> = ({w, flagFrame, fps}) => {
  const k = w / map.width;
  const h = map.height * k;
  const [sx, sy] = map.points.singapore;
  const [cx, cy] = map.points.chinaLabel;
  const [tx, ty] = map.points.taipei;
  const flag = flagFrame >= 0 ? spring({frame: flagFrame, fps, config: {damping: 13, stiffness: 200, mass: 0.6}}) : 0;

  return (
    <div style={{width: w, height: h, position: 'relative', background: '#e9e2cf', padding: 14, boxSizing: 'content-box'}}>
      <div style={{position: 'absolute', inset: 14, overflow: 'hidden', background: '#c9dbe0'}}>
        <svg viewBox={`0 0 ${map.width} ${map.height}`} width={w} height={h}>
          {map.shapes.map((s) => (
            <path
              key={s.name}
              d={s.d}
              fill={s.key ? LAND[s.key] : '#e6dcc2'}
              stroke="#8c7d62"
              strokeWidth={1.4}
              strokeLinejoin="round"
            />
          ))}
          <text x={cx} y={cy} fontFamily={stampFont} fontWeight={700} fontSize={44} fill="#6b5234" letterSpacing={6} textAnchor="middle">
            CHINA
          </text>
          <text x={tx + 18} y={ty + 8} fontFamily={typewriter} fontSize={24} fill="#4c4636">
            Taiwan
          </text>
          <text x={map.points.malaysiaLabel[0] + 96} y={map.points.malaysiaLabel[1] - 14} fontFamily={typewriter} fontSize={24} fill="#4c4636">
            Malaysia
          </text>
          <circle cx={sx} cy={sy} r={16} fill="none" stroke="#b0171f" strokeWidth={5} />
        </svg>
        {/* Fold creases */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(90deg, transparent 49.6%, rgba(60,40,10,0.22) 50%, rgba(255,255,255,0.3) 50.4%, transparent 50.8%), linear-gradient(180deg, transparent 33%, rgba(60,40,10,0.18) 33.3%, rgba(255,255,255,0.28) 33.6%, transparent 34%), linear-gradient(180deg, transparent 66%, rgba(60,40,10,0.18) 66.3%, rgba(255,255,255,0.28) 66.6%, transparent 67%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `url(${staticFile('paper.jpg')})`,
            backgroundSize: '512px 512px',
            mixBlendMode: 'multiply',
            opacity: 0.7,
          }}
        />
      </div>
      <div style={{position: 'absolute', left: 14 + sx * k - 20, top: 14 + sy * k - 20}}>
        <Pin color="red" size={40} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 14 + sx * k + 34,
          top: 14 + sy * k - 96,
          transformOrigin: '0% 100%',
          transform: `scale(${interpolate(flag, [0, 1], [1.6, 1])}) rotate(${interpolate(flag, [0, 1], [-14, -5])}deg)`,
          opacity: Math.min(1, flag * 3),
          padding: '8px 16px 5px',
          background: '#fbf8ef',
          boxShadow: '3px 5px 10px rgba(0,0,0,0.35)',
          fontFamily: stampFont,
          fontWeight: 700,
          fontSize: 34,
          color: '#b0171f',
          whiteSpace: 'nowrap',
          lineHeight: 1.1,
        }}
      >
        MEGASPEED
        <div style={{fontFamily: typewriter, fontWeight: 400, fontSize: 20, color: '#2a2622'}}>Singapore</div>
      </div>
    </div>
  );
};
