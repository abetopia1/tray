import React from 'react';
import {Img, staticFile} from 'remotion';
import type {CardItem, Line, NoteItem, PinColor, PolaroidItem, StampItem, StripItem, TagItem} from '../layout';
import {hand, marker, stampFont, typewriter} from '../fonts';

const INK = '#1f1c19';
const STAMP_RED = '#b0171f';

const fontOf = (f: Line['font']) =>
  f === 'stamp' ? stampFont : f === 'hand' ? hand : f === 'marker' ? marker : typewriter;

export const Lines: React.FC<{lines: Line[]}> = ({lines}) => (
  <>
    {lines.map((l, i) => (
      <div
        key={i}
        style={{
          fontFamily: fontOf(l.font),
          fontWeight: l.font === 'stamp' || l.font === 'hand' ? 700 : 400,
          fontSize: l.size ?? 40,
          lineHeight: l.font === 'stamp' ? 1.12 : l.font === 'hand' ? 0.98 : 1.28,
          letterSpacing: l.font === 'stamp' ? '0.02em' : 0,
          color: l.color ?? INK,
          marginTop: l.gap ?? 0,
          whiteSpace: 'nowrap',
        }}
      >
        {l.text}
      </div>
    ))}
  </>
);

const PIN_COLORS: Record<PinColor, [string, string]> = {
  red: ['#e2343c', '#8e0f16'],
  yellow: ['#f6cf3d', '#b28a07'],
  blue: ['#3f7fd6', '#1d4488'],
  green: ['#49a862', '#1f6634'],
  white: ['#f4f1ea', '#a9a399'],
};

export const Pin: React.FC<{color: PinColor; size?: number}> = ({color, size = 46}) => {
  const [light, dark] = PIN_COLORS[color];
  return (
    <div style={{position: 'relative', width: size, height: size}}>
      <div
        style={{
          position: 'absolute',
          left: size * 0.34,
          top: size * 0.4,
          width: size * 0.95,
          height: size * 0.5,
          borderRadius: '50%',
          background: 'rgba(0,0,0,0.38)',
          filter: 'blur(5px)',
          transform: 'rotate(28deg)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: `radial-gradient(circle at 34% 30%, #fff 0%, ${light} 16%, ${light} 46%, ${dark} 100%)`,
          boxShadow: 'inset -3px -4px 6px rgba(0,0,0,0.28)',
        }}
      />
    </div>
  );
};

export const Tape: React.FC<{w?: number; rot?: number}> = ({w = 150, rot = -4}) => (
  <div
    style={{
      width: w,
      height: 46,
      transform: `rotate(${rot}deg)`,
      background: 'linear-gradient(180deg, rgba(238,226,186,0.86), rgba(226,211,165,0.86))',
      boxShadow: '0 2px 5px rgba(0,0,0,0.22)',
      clipPath: 'polygon(0 0, 4% 14%, 0 30%, 3% 52%, 0 74%, 4% 100%, 97% 100%, 100% 82%, 96% 60%, 100% 40%, 97% 18%, 100% 0)',
    }}
  />
);

const paper = (file: string, size = 512): React.CSSProperties => ({
  backgroundImage: `url(${staticFile(file)})`,
  backgroundSize: `${size}px ${size}px`,
});

const TONES = {
  white: 'none',
  yellow: 'linear-gradient(rgba(250,226,120,0.42), rgba(250,226,120,0.42))',
  blue: 'linear-gradient(rgba(170,205,235,0.4), rgba(170,205,235,0.4))',
};

export const IndexCard: React.FC<{item: CardItem}> = ({item}) => (
  <div
    style={{
      width: item.w,
      padding: '56px 40px 36px',
      boxSizing: 'border-box',
      ...paper('paper.jpg'),
      backgroundImage: `${TONES[item.tone ?? 'white']}, repeating-linear-gradient(180deg, transparent 0 51px, rgba(70,110,170,0.16) 51px 53px), url(${staticFile('paper.jpg')})`,
      backgroundSize: 'auto, auto, 512px 512px',
      borderTop: '5px solid rgba(190,40,48,0.5)',
      borderRadius: 4,
    }}
  >
    <Lines lines={item.lines} />
  </div>
);

export const StickyNote: React.FC<{item: NoteItem}> = ({item}) => (
  <div
    style={{
      width: item.w,
      padding: '30px 26px 34px',
      boxSizing: 'border-box',
      textAlign: 'center',
      background: 'linear-gradient(160deg, #fbe36b 0%, #f4d348 70%, #e9c436 100%)',
      borderRadius: '2px 2px 14px 3px',
    }}
  >
    <Lines lines={item.lines} />
  </div>
);

// A label torn from a strip of typed paper.
export const Strip: React.FC<{item: StripItem}> = ({item}) => (
  <div
    style={{
      padding: '16px 34px 12px',
      ...paper('paper.jpg'),
      fontFamily: typewriter,
      fontSize: item.size ?? 52,
      color: INK,
      whiteSpace: 'nowrap',
      clipPath: 'polygon(0 6%, 2% 0, 98% 3%, 100% 12%, 99% 88%, 97% 100%, 3% 97%, 0 86%)',
    }}
  >
    {item.text}
  </div>
);

export const TAG_H = 132;

export const ManilaTag: React.FC<{item: TagItem}> = ({item}) => {
  const size = item.size ?? 62;
  const w = Math.max(300, item.text.length * size * 0.56 + 150);
  const flip = item.mirrored ? -1 : 1;
  return (
    <div style={{width: w, height: TAG_H, position: 'relative', transform: `scaleX(${flip})`}}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          ...paper('manila.jpg'),
          clipPath: 'polygon(46px 0, 100% 0, 100% 100%, 46px 100%, 0 70%, 0 30%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 30,
          top: TAG_H / 2 - 23,
          width: 46,
          height: 46,
          borderRadius: '50%',
          background: 'radial-gradient(circle, #5a3d22 0 30%, #c9a878 32% 100%)',
          boxShadow: 'inset 0 0 0 2px rgba(120,84,40,0.5)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 100,
          right: 22,
          top: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scaleX(${flip})`,
          fontFamily: stampFont,
          fontWeight: 700,
          fontSize: size,
          letterSpacing: '0.03em',
          color: '#2b2118',
          whiteSpace: 'nowrap',
        }}
      >
        {item.text}
      </div>
    </div>
  );
};

export const Silhouette: React.FC = () => (
  <svg viewBox="0 0 200 200" width="100%" height="100%" preserveAspectRatio="xMidYMax slice">
    <defs>
      <linearGradient id="sil-bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#c9c4b8" />
        <stop offset="1" stopColor="#9d978a" />
      </linearGradient>
    </defs>
    <rect width="200" height="200" fill="url(#sil-bg)" />
    <circle cx="100" cy="78" r="36" fill="#2a2826" />
    <path d="M30 200 C30 150 62 126 100 126 C138 126 170 150 170 200 Z" fill="#2a2826" />
  </svg>
);

const Placeholder: React.FC<{text: string}> = ({text}) => (
  <div
    style={{
      width: '100%',
      height: '100%',
      background: 'repeating-linear-gradient(45deg, #8d8a84 0 22px, #7f7c76 22px 44px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: typewriter,
      fontSize: 30,
      color: '#f2efe8',
      textAlign: 'center',
    }}
  >
    {text}
  </div>
);

export const Polaroid: React.FC<{item: PolaroidItem; hasImage: boolean}> = ({item, hasImage}) => {
  const pad = Math.round(item.w * 0.06);
  const photo = item.w - pad * 2;
  return (
    <div
      style={{
        width: item.w,
        boxSizing: 'border-box',
        padding: `${pad}px ${pad}px ${Math.round(pad * 0.7)}px`,
        background: 'linear-gradient(180deg, #fbfaf6, #efede6)',
        borderRadius: 3,
      }}
    >
      <div style={{width: photo, height: photo, position: 'relative', overflow: 'hidden', background: '#222'}}>
        {item.image && hasImage ? (
          <Img
            src={staticFile(item.image)}
            style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: item.focus ?? '50% 50%'}}
          />
        ) : item.art === 'silhouette' ? (
          <Silhouette />
        ) : (
          <Placeholder text="illustration pending" />
        )}
        <div style={{position: 'absolute', inset: 0, boxShadow: 'inset 0 0 40px rgba(0,0,0,0.35)'}} />
        {item.label ? (
          <div
            style={{
              position: 'absolute',
              left: 0,
              bottom: 0,
              padding: '5px 10px 3px',
              background: 'rgba(20,18,16,0.82)',
              color: '#f5f1e6',
              fontFamily: typewriter,
              fontSize: Math.max(17, Math.round(item.w * 0.05)),
              letterSpacing: '0.04em',
            }}
          >
            {item.label}
          </div>
        ) : null}
      </div>
      <div
        style={{
          fontFamily: marker,
          fontSize: Math.round(item.w * 0.105),
          color: '#23201c',
          textAlign: 'center',
          marginTop: Math.round(pad * 0.5),
          lineHeight: 1.15,
          whiteSpace: 'nowrap',
        }}
      >
        {item.caption}
      </div>
      {item.credit ? (
        <div
          style={{
            fontFamily: typewriter,
            fontSize: 19,
            lineHeight: 1.25,
            color: '#4a4640',
            textAlign: 'center',
            marginTop: 4,
          }}
        >
          {item.credit}
        </div>
      ) : null}
    </div>
  );
};

export const RubberStamp: React.FC<{item: StampItem}> = ({item}) => {
  const color = item.color ?? STAMP_RED;
  const size = item.size ?? 80;
  return (
    <div
      style={{
        padding: `${size * 0.26}px ${size * 0.36}px`,
        ...paper('paper.jpg'),
        boxShadow: '5px 9px 16px rgba(0,0,0,0.42)',
        clipPath: 'polygon(0 3%, 3% 0, 97% 2%, 100% 6%, 99% 95%, 96% 100%, 4% 98%, 0 94%)',
      }}
    >
      <div
        style={{
          padding: `${size * 0.08}px ${size * 0.3}px ${size * 0.1}px`,
          border: `${Math.max(6, size * 0.085)}px solid ${color}`,
          borderRadius: size * 0.16,
          color,
          textAlign: 'center',
          filter: 'url(#ink-rough)',
        }}
      >
        <div
          style={{
            fontFamily: stampFont,
            fontWeight: 700,
            fontSize: size,
            lineHeight: 1.05,
            letterSpacing: '0.05em',
            whiteSpace: 'nowrap',
          }}
        >
          {item.text}
        </div>
        {item.sub ? (
          <div
            style={{
              fontFamily: stampFont,
              fontWeight: 700,
              fontSize: size * 0.34,
              letterSpacing: '0.12em',
              whiteSpace: 'nowrap',
              borderTop: `${Math.max(3, size * 0.04)}px solid ${color}`,
              marginTop: size * 0.06,
              paddingTop: size * 0.05,
            }}
          >
            {item.sub}
          </div>
        ) : null}
      </div>
    </div>
  );
};

// Shared SVG filter that roughens stamp ink.
export const InkDefs: React.FC = () => (
  <svg width="0" height="0" style={{position: 'absolute'}}>
    <defs>
      <filter id="ink-rough" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" result="n" />
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.6 1.62" result="holes" />
        <feComposite in="SourceGraphic" in2="holes" operator="in" result="worn" />
        <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="8" result="w" />
        <feDisplacementMap in="worn" in2="w" scale="3" />
      </filter>
    </defs>
  </svg>
);
