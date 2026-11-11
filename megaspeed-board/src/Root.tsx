import {Composition} from 'remotion';
import {Board} from './Board';
import {FPS, totalFrames} from './timing';

export const Root = () => (
  <Composition id="Board" component={Board} width={1080} height={1920} fps={FPS} durationInFrames={totalFrames} />
);
