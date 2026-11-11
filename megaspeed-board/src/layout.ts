import {at, narrationEnd} from './timing';

export const BOARD_W = 3240;
// Extra cork below the last row keeps the final close shot on the board.
export const BOARD_H = 6120;
export const FRAME = 70;

const COLS = [540, 1620, 2700];
const ROWS = [720, 2160, 3600, 5040];

// Clusters follow the story in a zigzag, so the string reads left to right, then back.
export const centers: Record<number, [number, number]> = {
  1: [COLS[0], ROWS[0]],
  2: [COLS[1], ROWS[0]],
  3: [COLS[2], ROWS[0]],
  4: [COLS[2], ROWS[1]],
  5: [COLS[1], ROWS[1]],
  6: [COLS[0], ROWS[1]],
  7: [COLS[0], ROWS[2]],
  8: [COLS[1], ROWS[2]],
  9: [COLS[2], ROWS[2]],
  10: [COLS[1], ROWS[3]],
};

export type Line = {
  text: string;
  size?: number;
  color?: string;
  font?: 'type' | 'stamp' | 'hand' | 'marker';
  gap?: number;
};

export type PinColor = 'red' | 'yellow' | 'blue' | 'green' | 'white';

type Base = {
  id: string;
  beat: number;
  x: number;
  y: number;
  rot: number;
  t: number;
  pin?: PinColor | 'tape' | 'none';
  // Where the pin sits across the item, 0 = left edge, 1 = right edge.
  pinX?: number;
};

export type TagItem = Base & {kind: 'tag'; text: string; mirrored?: boolean; size?: number};
export type CardItem = Base & {kind: 'card'; w: number; lines: Line[]; tone?: 'white' | 'yellow' | 'blue'; ruled?: boolean};
export type PolaroidItem = Base & {
  kind: 'polaroid';
  w: number;
  image?: string;
  art?: 'silhouette' | 'placeholder';
  caption: string;
  label?: string;
  credit?: string;
  focus?: string;
};
export type StampItem = Base & {kind: 'stamp'; text: string; sub?: string; size?: number; color?: string};
export type MapItem = Base & {kind: 'map'; w: number; flagAt: number};
export type NoteItem = Base & {kind: 'note'; w: number; lines: Line[]};
export type StripItem = Base & {kind: 'strip'; text: string; size?: number};

export type Item = TagItem | CardItem | PolaroidItem | StampItem | MapItem | NoteItem | StripItem;

const RED = '#b0171f';

// Item positions inside a cluster are written relative to the cluster centre.
type Local = Item extends infer T ? (T extends Item ? Omit<T, 'beat' | 'id'> : never) : never;

const cluster = (beat: number, locals: Local[]): Item[] =>
  locals.map((l, i) => ({
    ...l,
    id: `b${beat}-${i}`,
    beat,
    x: centers[beat][0] + l.x,
    y: centers[beat][1] + l.y,
  })) as Item[];

// The red string is pinned at each tag's hole. Local offset of that hole from the cluster centre.
const HOLE: [number, number] = [-452, -584];
const HOLE_MIRRORED: [number, number] = [452, -584];

export const stringPins: [number, number][] = [
  [centers[1][0] + 318, centers[1][1] - 596],
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((b): [number, number] => [centers[b][0] + HOLE[0], centers[b][1] + HOLE[1]]),
  [centers[10][0] + HOLE_MIRRORED[0], centers[10][1] + HOLE_MIRRORED[1]],
];

const tag = (beat: number, text: string, t: number, extra: Partial<TagItem> = {}): Local =>
  ({kind: 'tag', text, t, x: HOLE[0], y: HOLE[1], rot: 9, pin: 'red', ...extra}) as Local;

export type Prop =
  | {kind: 'envelope'; x: number; y: number; rot: number}
  | {kind: 'blank'; x: number; y: number; rot: number; w: number}
  | {kind: 'spare-pin'; x: number; y: number; color: PinColor}
  | {kind: 'yarn'; x: number; y: number};

// Loose props fill the unused corners, so the wide shot reads as a working board.
export const props: Prop[] = [
  {kind: 'envelope', x: 470, y: 4990, rot: -4},
  {kind: 'blank', x: 300, y: 5560, rot: 5, w: 420},
  {kind: 'blank', x: 380, y: 5530, rot: -3, w: 420},
  {kind: 'spare-pin', x: 760, y: 5420, color: 'yellow'},
  {kind: 'spare-pin', x: 820, y: 5490, color: 'blue'},
  {kind: 'spare-pin', x: 735, y: 5540, color: 'green'},
  {kind: 'spare-pin', x: 850, y: 5400, color: 'white'},
  {kind: 'yarn', x: 2760, y: 4900},
  {kind: 'blank', x: 2800, y: 5620, rot: -6, w: 400},
  {kind: 'spare-pin', x: 2480, y: 5380, color: 'red'},
  {kind: 'spare-pin', x: 2540, y: 5460, color: 'yellow'},
];

export const items: Item[] = [
  ...cluster(1, [
    {kind: 'strip', text: 'THREE NAMES. ONE BOARD.', x: -70, y: -590, rot: -1.5, t: -1, pin: 'red', pinX: 0.985},
    {
      kind: 'card', w: 640, x: -130, y: -330, rot: -3, t: at(1, 'Nvidia'), pin: 'yellow',
      lines: [
        {text: 'NVIDIA', size: 96, font: 'stamp'},
        {text: 'the most valuable company', size: 38},
        {text: 'in the world', size: 38},
      ],
    },
    {
      kind: 'card', w: 640, x: 130, y: -10, rot: 2.5, t: at(1, 'Megaspeed'), pin: 'blue',
      lines: [
        {text: 'MEGASPEED', size: 88, font: 'stamp'},
        {text: 'a chip buyer few had heard of', size: 36},
      ],
    },
    {
      kind: 'polaroid', w: 400, x: -210, y: 375, rot: -4, t: at(1, 'Alice'), pin: 'tape',
      art: 'silhouette', caption: 'Alice Huang', label: 'SILHOUETTE · NO PHOTO USED',
    },
    {
      kind: 'note', w: 330, x: 270, y: 430, rot: 5, t: at(1, 'Follow'),
      lines: [{text: 'follow the', size: 64, font: 'hand'}, {text: 'string →', size: 64, font: 'hand', color: RED}],
    },
  ]),

  ...cluster(2, [
    tag(2, 'OCT 2022', at(2, 'October')),
    {
      kind: 'card', w: 760, x: 60, y: -300, rot: 1.5, t: at(2, 'bars'), pin: 'yellow',
      lines: [
        {text: 'WASHINGTON', size: 70, font: 'stamp'},
        {text: 'bars sales of the most', size: 44},
        {text: 'advanced AI chips to China', size: 44},
      ],
    },
    {
      kind: 'polaroid', w: 430, x: -200, y: 200, rot: -3.5, t: at(2, 'chips'), pin: 'tape',
      image: 'art-chip.jpg', art: 'placeholder', caption: 'advanced AI chip', label: 'ILLUSTRATION · AI-GENERATED',
    },
    {kind: 'stamp', text: 'EXPORT BAN', x: 268, y: 405, rot: -8, t: at(2, 'China'), size: 70},
  ]),

  ...cluster(3, [
    tag(3, '2023', at(3, '2023')),
    {
      kind: 'card', w: 560, x: -30, y: -385, rot: -2.5, t: at(3, 'gaming'), pin: 'blue',
      lines: [
        {text: '7ROAD', size: 66, font: 'stamp'},
        {text: 'Chinese gaming company', size: 34},
        {text: 'spins off its Singapore arm', size: 34},
      ],
    },
    {kind: 'map', w: 500, x: 232, y: 95, rot: 2, t: at(3, 'Singapore'), flagAt: at(3, 'Megaspeed'), pin: 'none'},
    {
      kind: 'polaroid', w: 300, x: -245, y: 55, rot: -5, t: at(3, 'Alice'), pin: 'tape',
      art: 'silhouette', caption: 'Alice Huang', label: 'SILHOUETTE',
    },
    {
      kind: 'card', w: 600, x: -105, y: 505, rot: 2, t: at(3, 'Le'), pin: 'green',
      lines: [
        {text: 'also known as HUANG LE', size: 38},
        {text: 'first managing director', size: 38, color: RED},
      ],
    },
  ]),

  ...cluster(4, [
    tag(4, 'THE ORDERS', at(4, 'orders'), {size: 48}),
    {
      kind: 'polaroid', w: 460, x: 205, y: -245, rot: 3, t: at(4, 'orders') + 0.25, pin: 'tape',
      image: 'art-racks.jpg', art: 'placeholder', caption: 'racks of AI servers', label: 'ILLUSTRATION · AI-GENERATED',
    },
    {
      kind: 'strip', text: 'THE NEW YORK TIMES REPORTS:', x: -90, y: 95, rot: -3, t: at(4, 'York'), size: 40, pin: 'none',
    },
    {
      kind: 'card', w: 800, x: 20, y: 365, rot: -1.5, t: at(4, '4.8'), pin: 'yellow',
      lines: [
        {text: '$4.8 BILLION+', size: 114, font: 'stamp', color: RED},
        {text: 'of Nvidia chips bought by', size: 42},
        {text: 'Megaspeed in two years', size: 42},
      ],
    },
  ]),

  ...cluster(5, [
    tag(5, 'OCT 2025', at(5, 'October')),
    {
      kind: 'card', w: 780, x: 70, y: -290, rot: 1.5, t: at(5, 'Commerce'), pin: 'yellow',
      lines: [
        {text: 'COMMERCE DEPT. INVESTIGATING', size: 50, font: 'stamp'},
        {text: 'Did Megaspeed help Chinese', size: 40},
        {text: 'firms get around the ban?', size: 40},
        {text: '— reported by The New York Times', size: 28, gap: 10},
      ],
    },
    {
      kind: 'card', w: 620, x: -150, y: 80, rot: -3, t: at(5, 'Nvidia'), pin: 'green',
      lines: [
        {text: 'NVIDIA SAYS', size: 44, font: 'stamp'},
        {text: '“no evidence of diversion”', size: 42},
      ],
    },
    {
      kind: 'card', w: 660, x: 150, y: 400, rot: 2.5, t: at(5, 'Megaspeed', 2), pin: 'blue',
      lines: [
        {text: 'MEGASPEED SAYS', size: 44, font: 'stamp'},
        {text: '“fully in compliance with', size: 40},
        {text: 'all applicable laws”', size: 40},
      ],
    },
  ]),

  ...cluster(6, [
    tag(6, 'OCT 29, 2026', at(6, 'October'), {size: 50}),
    {
      kind: 'card', w: 760, x: 90, y: -305, rot: -1.5, t: at(6, 'intelligence'), pin: 'yellow',
      lines: [
        {text: 'THE TIMES REPORTS:', size: 46, font: 'stamp'},
        {text: 'U.S. intelligence had been', size: 40},
        {text: 'watching Alice Huang as a', size: 40},
        {text: 'suspected Chinese asset', size: 40, color: RED},
      ],
    },
    {
      kind: 'polaroid', w: 320, x: -225, y: 175, rot: -5, t: at(6, 'Alice'), pin: 'tape',
      art: 'silhouette', caption: 'Alice Huang', label: 'SILHOUETTE',
    },
    {kind: 'stamp', text: 'ALLEGED', x: 300, y: -62, rot: -9, t: at(6, 'suspected'), size: 80},
    {
      kind: 'polaroid', w: 430, x: 215, y: 300, rot: 4, t: at(6, 'Jensen'), pin: 'tape',
      image: 'jensen-huang.jpg', caption: 'Jensen Huang', label: 'NVIDIA CEO',
      credit: 'Photo: The White House / Daniel Torok · public domain · Wikimedia Commons', focus: '50% 30%',
    },
    {
      kind: 'note', w: 290, x: -235, y: 505, rot: -4, t: at(6, 'not'),
      lines: [{text: 'NOT', size: 70, font: 'hand', color: RED}, {text: 'related', size: 60, font: 'hand'}],
    },
  ]),

  ...cluster(7, [
    tag(7, 'NOV 8, 2026', at(7, 'November'), {size: 54}),
    {
      kind: 'card', w: 760, x: 80, y: -300, rot: -2, t: at(7, 'unfaithful'), pin: 'yellow',
      lines: [
        {text: '“I was unfaithful', size: 62},
        {text: 'to my wife.”', size: 62},
        {text: '— Jensen Huang, email to staff', size: 30, gap: 12},
      ],
    },
    {
      kind: 'note', w: 330, x: 290, y: -40, rot: 5, t: at(7, 'names'),
      lines: [{text: 'he names', size: 58, font: 'hand'}, {text: 'no one', size: 62, font: 'hand', color: RED}],
    },
    {
      kind: 'card', w: 640, x: -100, y: 195, rot: -3, t: at(7, 'board'), pin: 'blue',
      lines: [
        {text: 'NVIDIA’S BOARD', size: 60, font: 'stamp'},
        {text: 'opens an independent', size: 40},
        {text: 'investigation', size: 40},
      ],
    },
    {
      kind: 'card', w: 740, x: 110, y: 480, rot: 2, t: at(7, 'reason'), pin: 'green',
      lines: [
        {text: 'THE BOARD SAYS', size: 40, font: 'stamp'},
        {text: '“no reason to believe that either', size: 34},
        {text: 'national security or NVIDIA', size: 34},
        {text: 'secrets were compromised”', size: 34},
      ],
    },
  ]),

  ...cluster(8, [
    tag(8, 'NOV 9, 2026', at(8, 'next'), {size: 54}),
    {kind: 'strip', text: 'CBS NEWS · NBC NEWS REPORT:', x: -70, y: -418, rot: -2, t: at(8, 'CBS'), size: 36, pin: 'none'},
    {
      kind: 'card', w: 720, x: 80, y: -215, rot: 1.5, t: at(8, 'Justice'), pin: 'yellow',
      lines: [
        {text: 'JUSTICE DEPT.', size: 72, font: 'stamp'},
        {text: 'criminal investigation', size: 44},
        {text: 'into Megaspeed', size: 44},
      ],
    },
    {kind: 'stamp', text: 'UNNAMED SOURCES', x: 235, y: 15, rot: -7, t: at(8, 'Megaspeed') + 0.3, size: 48},
    {
      kind: 'card', w: 660, x: -110, y: 240, rot: -3, t: at(8, 'FBI'), pin: 'blue',
      lines: [
        {text: 'PRESIDENT TRUMP', size: 50, font: 'stamp'},
        {text: 'says the FBI is', size: 40},
        {text: '“looking into it”', size: 46, color: RED},
      ],
    },
    {
      kind: 'card', w: 600, x: 60, y: 500, rot: 2.5, t: at(8, 'absolutely'), pin: 'green',
      lines: [
        {text: 'TRUMP ON HUANG', size: 44, font: 'stamp'},
        {text: '“absolutely no idea”', size: 46},
      ],
    },
  ]),

  ...cluster(9, [
    tag(9, 'THE OTHER SIDE', at(9, 'other'), {size: 44}),
    {
      kind: 'card', w: 700, x: 110, y: -300, rot: -2, t: at(9, 'China'), pin: 'yellow',
      lines: [
        {text: 'CHINA’S FOREIGN MINISTRY', size: 46, font: 'stamp'},
        {text: '“nothing but smears', size: 44},
        {text: 'against China”', size: 44},
      ],
    },
    {
      kind: 'card', w: 600, x: 170, y: -20, rot: 3, t: at(9, 'Megaspeed'), pin: 'blue',
      lines: [
        {text: 'MEGASPEED', size: 54, font: 'stamp'},
        {text: 'denies any wrongdoing', size: 42},
      ],
    },
    {
      kind: 'card', w: 600, x: -60, y: 235, rot: -3, t: at(9, 'Alice'), pin: 'green',
      lines: [
        {text: 'ALICE HUANG', size: 54, font: 'stamp'},
        {text: 'no public comment', size: 42},
      ],
    },
    {kind: 'stamp', text: 'NO CHARGES', sub: 'AS OF NOV 11, 2026', x: 130, y: 478, rot: -6, t: at(9, 'charged'), size: 94},
  ]),

  ...cluster(10, [
    {
      kind: 'tag', text: 'NOV 18, 2026', mirrored: true, size: 52, x: HOLE_MIRRORED[0], y: HOLE_MIRRORED[1], rot: -9,
      t: at(10, 'Next') + 0.1, pin: 'red',
    },
    {
      kind: 'card', w: 740, x: -60, y: -290, rot: -1.5, t: at(10, 'Lawmakers'), pin: 'yellow',
      lines: [
        {text: 'HOUSE COMMITTEE CHAIRS', size: 52, font: 'stamp'},
        {text: 'ask Jensen Huang for a', size: 42},
        {text: 'closed-door briefing', size: 42},
      ],
    },
    {kind: 'stamp', text: 'REQUESTED', x: 250, y: -70, rot: -10, t: at(10, 'asked'), size: 78},
    {
      kind: 'polaroid', w: 370, x: -285, y: 175, rot: -4, t: at(10, 'closed'), pin: 'tape',
      image: 'art-door.jpg', art: 'placeholder', caption: 'closed doors', label: 'ILLUSTRATION · AI-GENERATED',
    },
    {
      kind: 'card', w: 630, x: 215, y: 372, rot: 2, t: narrationEnd + 0.45, pin: 'red', tone: 'yellow',
      lines: [
        {text: 'SOURCES', size: 42, font: 'stamp'},
        {text: 'The New York Times · CBS News', size: 29},
        {text: 'NBC News · CNBC · AP · Bloomberg', size: 29},
        {text: 'Facts checked 11 Nov 2026', size: 29, gap: 8},
        {text: 'Photo: The White House, public domain', size: 25, gap: 8},
        {text: 'Illustrations, voice, music: AI-made', size: 25},
      ],
    },
  ]),
];
