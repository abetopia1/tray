// Writes src/data/words.json with ESTIMATED word timings, for layout work before the voice exists.
// scripts/align.py replaces the file with timings measured from the real audio.
import {readFileSync, writeFileSync} from 'node:fs';

const beats = readFileSync('script.txt', 'utf8').trim().split(/\n\s*\n/);
const syllables = (w) => Math.max(1, (w.toLowerCase().replace(/[^a-z0-9]/g, '').match(/[aeiouy]+|\d/g) ?? []).length);

const SYLLABLE = 0.2;
const words = [];
let t = 0.5;
beats.forEach((text, b) => {
  // The last beat waits while the camera pulls back to the whole board.
  if (b === beats.length - 1) t += 2.6 * 1.39;
  for (const token of text.split(/\s+/)) {
    const dur = 0.09 + SYLLABLE * syllables(token);
    words.push({i: words.length, text: token, beat: b + 1, start: +t.toFixed(3), end: +(t + dur).toFixed(3)});
    t += dur + 0.03;
    if (/[.:?!]$/.test(token)) t += 0.32;
    else if (/,$/.test(token)) t += 0.16;
  }
  t += 0.45;
});

// Scale to a typical narration length of about 2.6 words per second.
const TARGET = words.length / 2.6;
const k = TARGET / t;
for (const w of words) {
  w.start = +(w.start * k).toFixed(3);
  w.end = +(w.end * k).toFixed(3);
}

writeFileSync('src/data/words.json', JSON.stringify({source: 'estimate', duration: +TARGET.toFixed(3), words}, null, 1));
console.log(words.length, 'words,', TARGET.toFixed(1), 's (estimated)');
