import React from 'react';
import {AbsoluteFill, Audio, getInputProps, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const FLAGS = getInputProps() as {noBlur?: boolean; noGrain?: boolean; noVignette?: boolean};
import {cameraAt} from './camera';
import {Captions} from './components/Captions';
import {IndexCard, InkDefs, ManilaTag, Pin, Polaroid, RubberStamp, StickyNote, Strip, TAG_H, Tape} from './components/Paper';
import {PaperMap} from './components/PaperMap';
import {RedString} from './components/RedString';
import {BOARD_H, BOARD_W, FRAME, Item, Prop, items, props} from './layout';
import assets from './data/assets.json';

const hasAsset = (name?: string) => Boolean(name && (assets.images as string[]).includes(name));

const shadowFor = (lift: number) =>
  `${4 + lift * 0.5}px ${7 + lift}px ${12 + lift * 1.2}px rgba(0,0,0,${0.42 - Math.min(0.2, lift * 0.004)})`;

const ItemView: React.FC<{item: Item}> = ({item}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const f = frame - item.t * fps;
  if (f < 0) return null;

  if (item.kind === 'stamp') {
    // Stamps slam straight down and leave ink.
    const hit = interpolate(f, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
    const scale = interpolate(hit, [0, 1], [2.3, 1]);
    const jolt = f >= 4 && f < 8 ? Math.sin((f - 4) * 2.4) * 1.2 : 0;
    return (
      <div
        style={{
          position: 'absolute',
          left: item.x,
          top: item.y,
          transform: `translate(-50%, -50%) rotate(${item.rot + jolt}deg) scale(${scale})`,
          opacity: interpolate(f, [0, 3], [0, 1], {extrapolateRight: 'clamp'}),
          zIndex: 5,
        }}
      >
        <RubberStamp item={item} />
      </div>
    );
  }

  const s = spring({frame: f, fps, config: {damping: 15, stiffness: 190, mass: 0.7}});
  const scale = interpolate(s, [0, 1], [1.3, 1]);
  const lift = interpolate(s, [0, 1], [46, 0]);
  const tilt = interpolate(s, [0, 1], [item.rot > 0 ? -5 : 5, 0]);
  const opacity = interpolate(f, [0, 3], [0, 1], {extrapolateRight: 'clamp'});
  const pinIn = spring({frame: f - 5, fps, config: {damping: 12, stiffness: 260, mass: 0.5}});

  // Pinned paper stirs slightly in the air.
  const flutter = Math.sin(frame * 0.045 + item.x * 0.01) * 0.25;

  if (item.kind === 'tag') {
    // A tag hangs from the pin through its hole, so it swings around that point.
    const swing = interpolate(s, [0, 1], [item.mirrored ? 24 : -24, 0]) + flutter * 2;
    const holeX = 53;
    return (
      <div style={{position: 'absolute', left: item.x, top: item.y, opacity, zIndex: 4}}>
        <div
          style={{
            position: 'absolute',
            left: item.mirrored ? undefined : -holeX,
            right: item.mirrored ? -holeX : undefined,
            top: -TAG_H / 2,
            transformOrigin: `${item.mirrored ? `calc(100% - ${holeX}px)` : `${holeX}px`} 50%`,
            transform: `rotate(${item.rot + swing}deg) scale(${scale})`,
            filter: `drop-shadow(${4 + lift * 0.4}px ${7 + lift * 0.8}px ${8 + lift * 0.6}px rgba(0,0,0,0.4))`,
          }}
        >
          <ManilaTag item={item} />
        </div>
        <div style={{position: 'absolute', left: -23, top: -23, transform: `scale(${interpolate(pinIn, [0, 1], [1.8, 1])})`, opacity: Math.min(1, pinIn * 4)}}>
          <Pin color="red" />
        </div>
      </div>
    );
  }

  const clipped = item.kind === 'strip';
  return (
    <div
      style={{
        position: 'absolute',
        left: item.x,
        top: item.y,
        transform: `translate(-50%, -50%) translateY(${-lift * 0.5}px) rotate(${item.rot + tilt + flutter}deg) scale(${scale})`,
        opacity,
        zIndex: item.kind === 'note' ? 3 : 2,
      }}
    >
      <div style={clipped ? {filter: `drop-shadow(4px ${7 + lift * 0.6}px 8px rgba(0,0,0,0.42))`} : {boxShadow: shadowFor(lift)}}>
        {item.kind === 'card' ? <IndexCard item={item} /> : null}
        {item.kind === 'note' ? <StickyNote item={item} /> : null}
        {item.kind === 'strip' ? <Strip item={item} /> : null}
        {item.kind === 'polaroid' ? <Polaroid item={item} hasImage={hasAsset(item.image)} /> : null}
        {item.kind === 'map' ? <PaperMap w={item.w} flagFrame={frame - item.flagAt * fps} fps={fps} /> : null}
      </div>
      {item.pin === 'tape' ? (
        <div style={{position: 'absolute', left: '50%', top: -22, marginLeft: -75, opacity: Math.min(1, pinIn * 4)}}>
          <Tape />
        </div>
      ) : item.kind === 'map' ? (
        <>
          <div style={{position: 'absolute', left: 18, top: -16, opacity: Math.min(1, pinIn * 4)}}>
            <Tape w={130} rot={-32} />
          </div>
          <div style={{position: 'absolute', right: 18, top: -16, opacity: Math.min(1, pinIn * 4)}}>
            <Tape w={130} rot={30} />
          </div>
        </>
      ) : item.pin && item.pin !== 'none' ? (
        <div
          style={{
            position: 'absolute',
            left: `${(item.pinX ?? 0.5) * 100}%`,
            top: item.kind === 'strip' ? 14 : 9,
            marginLeft: -21,
            transform: `scale(${interpolate(pinIn, [0, 1], [1.8, 1])})`,
            opacity: Math.min(1, pinIn * 4),
          }}
        >
          <Pin color={item.pin} size={42} />
        </div>
      ) : null}
    </div>
  );
};

const PropView: React.FC<{prop: Prop}> = ({prop}) => {
  const at: React.CSSProperties = {position: 'absolute', left: prop.x, top: prop.y};
  if (prop.kind === 'spare-pin') {
    return (
      <div style={{...at, marginLeft: -20, marginTop: -20}}>
        <Pin color={prop.color} size={40} />
      </div>
    );
  }
  if (prop.kind === 'blank') {
    return (
      <div
        style={{
          ...at,
          width: prop.w,
          height: prop.w * 0.6,
          transform: `translate(-50%, -50%) rotate(${prop.rot}deg)`,
          backgroundImage: `repeating-linear-gradient(180deg, transparent 0 51px, rgba(70,110,170,0.16) 51px 53px), url(${staticFile('paper.jpg')})`,
          backgroundSize: 'auto, 512px 512px',
          borderTop: '5px solid rgba(190,40,48,0.5)',
          boxShadow: '4px 7px 12px rgba(0,0,0,0.4)',
        }}
      />
    );
  }
  if (prop.kind === 'envelope') {
    return (
      <div
        style={{
          ...at,
          width: 640,
          height: 420,
          transform: `translate(-50%, -50%) rotate(${prop.rot}deg)`,
          backgroundImage: `linear-gradient(160deg, transparent 49.7%, rgba(90,60,20,0.35) 50%, transparent 50.6%), linear-gradient(200deg, transparent 49.7%, rgba(90,60,20,0.35) 50%, transparent 50.6%), url(${staticFile('manila.jpg')})`,
          backgroundSize: '50% 62%, 50% 62%, 512px 512px',
          backgroundPosition: 'left top, right top, 0 0',
          backgroundRepeat: 'no-repeat, no-repeat, repeat',
          boxShadow: '5px 9px 16px rgba(0,0,0,0.42)',
        }}
      >
        <div style={{position: 'absolute', left: '50%', top: 10, marginLeft: -21}}>
          <Pin color="blue" size={42} />
        </div>
      </div>
    );
  }
  // A spare hank of red yarn hanging from a pin.
  return (
    <div style={at}>
      <svg width={260} height={520} style={{position: 'absolute', left: -130, top: -10, overflow: 'visible'}}>
        <g fill="none" strokeLinecap="round">
          {[0, 1, 2, 3].map((i) => (
            <path
              key={i}
              d={`M130 10 C ${40 - i * 14} 160, ${50 + i * 10} ${400 + i * 20}, 130 ${440 + i * 16} C ${210 - i * 8} ${400 + i * 20}, ${220 + i * 12} 160, 130 10`}
              stroke={i % 2 ? '#c8202a' : '#a3141c'}
              strokeWidth={8}
            />
          ))}
        </g>
      </svg>
      <div style={{position: 'absolute', left: -23, top: -23}}>
        <Pin color="red" />
      </div>
    </div>
  );
};

const Cork: React.FC = () => (
  <>
    {/* Wall behind the board */}
    <div
      style={{
        position: 'absolute',
        left: -3000,
        top: -3000,
        width: BOARD_W + 6000,
        height: BOARD_H + 6000,
        background: 'radial-gradient(ellipse at 50% 40%, #4b5653 0%, #2c3432 60%, #1b2120 100%)',
      }}
    />
    {/* Wooden frame */}
    <div
      style={{
        position: 'absolute',
        left: -FRAME,
        top: -FRAME,
        width: BOARD_W + FRAME * 2,
        height: BOARD_H + FRAME * 2,
        background: 'linear-gradient(135deg, #8a5a2e 0%, #6e4521 35%, #94663a 60%, #5e3a1b 100%)',
        boxShadow: '30px 50px 120px rgba(0,0,0,0.6), inset 0 0 0 6px rgba(0,0,0,0.25)',
        borderRadius: 10,
      }}
    />
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: BOARD_W,
        height: BOARD_H,
        backgroundImage: `url(${staticFile('cork.jpg')})`,
        backgroundSize: '1024px 1024px',
        boxShadow: 'inset 0 0 90px rgba(40,20,0,0.55), inset 14px 20px 40px rgba(0,0,0,0.35)',
      }}
    />
    {/* Uneven light across the board hides the tile repeat */}
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: BOARD_W,
        height: BOARD_H,
        background:
          'radial-gradient(ellipse 60% 40% at 30% 20%, rgba(255,226,170,0.22), transparent 70%), radial-gradient(ellipse 70% 50% at 75% 70%, rgba(60,30,0,0.26), transparent 70%), radial-gradient(ellipse 50% 30% at 20% 85%, rgba(255,220,160,0.14), transparent 70%)',
      }}
    />
  </>
);

export const Board: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seconds = frame / fps;
  const cam = cameraAt(seconds);

  return (
    <AbsoluteFill style={{backgroundColor: '#1b2120', overflow: 'hidden'}}>
      <InkDefs />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: BOARD_W,
          height: BOARD_H,
          transformOrigin: '0 0',
          transform: `translate(540px, ${cam.focusY}px) rotate(${cam.rot}deg) scale(${cam.zoom}) translate(${-cam.x}px, ${-cam.y}px)`,
        }}
      >
        <Cork />
        {props.map((prop, i) => (
          <PropView key={i} prop={prop} />
        ))}
        {items.map((item) => (
          <ItemView key={item.id} item={item} />
        ))}
        <div style={{position: 'absolute', left: 0, top: 0, zIndex: 3}}>
          <RedString seconds={seconds} />
        </div>
      </div>

      {/* Lens: soft edges, warm falloff, grain */}
      {FLAGS.noBlur ? null : <AbsoluteFill
        style={{
          backdropFilter: 'blur(3px)',
          WebkitMaskImage: 'radial-gradient(ellipse 78% 70% at 50% 46%, transparent 58%, black 100%)',
          maskImage: 'radial-gradient(ellipse 78% 70% at 50% 46%, transparent 58%, black 100%)',
        }}
      />}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse 85% 75% at 50% 44%, rgba(255,214,150,0.08) 0%, rgba(0,0,0,0) 45%, rgba(10,6,2,0.5) 100%)',
        }}
      />
      {FLAGS.noGrain ? null : <AbsoluteFill
        style={{
          backgroundImage: `url(${staticFile('grain.png')})`,
          backgroundPosition: `${(Math.floor(frame / 2) * 137) % 512}px ${(Math.floor(frame / 2) * 89) % 512}px`,
          mixBlendMode: 'overlay',
          opacity: 0.07,
        }}
      />}

      <Captions seconds={seconds} />
      {assets.audio ? <Audio src={staticFile(assets.audio)} /> : null}
    </AbsoluteFill>
  );
};
