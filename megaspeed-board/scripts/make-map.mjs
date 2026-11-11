// Projects Natural Earth country outlines (public domain) into SVG paths for the paper map.
import {readFileSync, writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {feature} from 'topojson-client';
import {geoMercator, geoPath} from 'd3-geo';

const require = createRequire(import.meta.url);
const topo = JSON.parse(readFileSync(require.resolve('world-atlas/countries-50m.json'), 'utf8'));
const countries = feature(topo, topo.objects.countries).features;

const W = 760;
const H = 900;
const box = {
  type: 'Feature',
  geometry: {type: 'LineString', coordinates: [[94, 43], [129, -9]]},
};
const projection = geoMercator().fitExtent([[0, 0], [W, H]], box);
const path = geoPath(projection).digits(1);

const highlight = {China: 'china', Taiwan: 'taiwan', Malaysia: 'malaysia', Singapore: 'singapore'};
const shapes = [];
for (const c of countries) {
  const d = path(c);
  if (!d) continue;
  const [[x0, y0], [x1, y1]] = path.bounds(c);
  if (x1 < 0 || y1 < 0 || x0 > W || y0 > H) continue;
  shapes.push({name: c.properties.name, key: highlight[c.properties.name] ?? null, d});
}

const places = {
  singapore: [103.82, 1.35],
  johor: [103.6, 1.6],
  taipei: [121.56, 25.03],
  beijing: [116.4, 39.9],
  chinaLabel: [108, 33.5],
  malaysiaLabel: [102.2, 4.6],
};
const points = Object.fromEntries(
  Object.entries(places).map(([k, ll]) => [k, projection(ll).map((v) => Math.round(v * 10) / 10)]),
);

writeFileSync('src/data/map.json', JSON.stringify({width: W, height: H, shapes, points}));
console.log(shapes.length, 'shapes', points);
