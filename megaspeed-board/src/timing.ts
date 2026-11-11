import data from './data/words.json';

export const FPS = 30;

export type Word = {i: number; text: string; beat: number; start: number; end: number};

export const words: Word[] = data.words;
export const timingSource: string = data.source;
export const narrationEnd = words[words.length - 1].end;

// Tail after the last word holds on the sources card.
export const TAIL_SECONDS = 4.2;
export const totalSeconds = narrationEnd + TAIL_SECONDS;
export const totalFrames = Math.ceil(totalSeconds * FPS);

const bare = (s: string) => s.toLowerCase().replace(/[^a-z0-9.]/g, '').replace(/\.+$/, '');

// Start time of the nth occurrence of a spoken word inside a beat.
export const at = (beat: number, token: string, nth = 1): number => {
  const hits = words.filter((w) => w.beat === beat && bare(w.text) === bare(token));
  const hit = hits[nth - 1];
  if (!hit) {
    throw new Error(`No word "${token}" (#${nth}) in beat ${beat}`);
  }
  return hit.start;
};

export const beatStart = (beat: number) => words.find((w) => w.beat === beat)!.start;
export const beatEnd = (beat: number) => [...words].reverse().find((w) => w.beat === beat)!.end;
export const beatCount = words[words.length - 1].beat;

export const frameOf = (seconds: number) => seconds * FPS;

export type Chunk = {words: Word[]; start: number; end: number};

// Caption chunks hold at most three words and never cross a sentence end.
export const chunks: Chunk[] = (() => {
  const sentences: Word[][] = [];
  let current: Word[] = [];
  for (const w of words) {
    current.push(w);
    if (/[.:?!]$/.test(w.text)) {
      sentences.push(current);
      current = [];
    }
  }
  if (current.length) sentences.push(current);

  const out: Chunk[] = [];
  for (const s of sentences) {
    const groups = Math.ceil(s.length / 3);
    const base = Math.floor(s.length / groups);
    let extra = s.length - base * groups;
    let k = 0;
    for (let g = 0; g < groups; g++) {
      const size = base + (extra-- > 0 ? 1 : 0);
      const ws = s.slice(k, k + size);
      k += size;
      out.push({words: ws, start: ws[0].start, end: ws[ws.length - 1].end});
    }
  }
  return out;
})();
