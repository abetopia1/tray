import React from 'react';
import {interpolate} from 'remotion';
import {captionFont} from '../fonts';
import {chunks} from '../timing';

const clean = (s: string) => s.replace(/[.,:;!?“”"]/g, '').toUpperCase();

// One chip of up to three words. The word being spoken turns red.
export const Captions: React.FC<{seconds: number}> = ({seconds}) => {
  const i = chunks.findIndex((c, k) => {
    const next = chunks[k + 1];
    const until = next && next.start - c.end < 0.45 ? next.start : c.end + 0.22;
    return seconds >= c.start - 0.04 && seconds < until;
  });
  if (i < 0) return null;
  const chunk = chunks[i];
  const pop = interpolate(seconds, [chunk.start - 0.04, chunk.start + 0.07], [0.86, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Archivo Black caps average about 0.72em wide. Long chips shrink to fit the frame.
  const SIZE = 78;
  const texts = chunk.words.map((w) => clean(w.text));
  const estimate = texts.join('').length * SIZE * 0.72 + (texts.length - 1) * 22 + 82;
  const fit = Math.min(1, 980 / estimate);

  // A word stays lit until the next word in the chip starts.
  let active = 0;
  chunk.words.forEach((w, k) => {
    if (seconds >= w.start) active = k;
  });

  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 1486, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          display: 'flex',
          gap: 22,
          padding: '20px 36px 16px',
          background: '#fbf8f0',
          borderRadius: 22,
          border: '5px solid #17130f',
          boxShadow: '0 10px 0 rgba(0,0,0,0.55), 0 22px 40px rgba(0,0,0,0.45)',
          transform: `scale(${pop * fit})`,
        }}
      >
        {chunk.words.map((w, k) => (
          <span
            key={w.i}
            style={{
              fontFamily: captionFont,
              fontSize: SIZE,
              lineHeight: 1,
              letterSpacing: '-0.01em',
              color: k === active ? '#d4161f' : '#17130f',
              whiteSpace: 'nowrap',
            }}
          >
            {clean(w.text)}
          </span>
        ))}
      </div>
    </div>
  );
};
