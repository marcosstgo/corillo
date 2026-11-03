import test from 'node:test';
import assert from 'node:assert/strict';
import { ultimoDeCada, tarjetaVideo } from './videos-canal.js';

const v = (channel, date, extra = {}) => ({ id: channel + date.slice(8, 10), channel, date: `${date} 12:00:00.000Z`, thumb: 'https://vods.corillo.live/x.jpg', ...extra });

test('uno por canal, el más nuevo, y en orden', () => {
  const r = ultimoDeCada([v('marcos', '2026-11-01'), v('kata', '2026-10-31'), v('kata', '2026-11-02'), v('tea', '2026-10-01')]);
  assert.deepEqual(r.map(x => x.channel + x.date.slice(8, 10)), ['kata02', 'marcos01', 'tea01']);
});
test('sin portada no entra, y si el más nuevo no tiene, usa el anterior', () => {
  const r = ultimoDeCada([v('kata', '2026-11-02', { thumb: '' }), v('kata', '2026-10-31')]);
  assert.equal(r.length, 1); assert.equal(r[0].date.slice(8, 10), '31');
});
test('respeta el máximo y no rompe sin videos', () => {
  assert.equal(ultimoDeCada(Array.from({ length: 9 }, (_, i) => v('c' + i, '2026-11-02')), 6).length, 6);
  assert.deepEqual(ultimoDeCada([]), []);
});
test('escapa título, nombre, portada y canal', () => {
  const h = tarjetaVideo(v('ka"ta', '2026-11-02', { title: '<img src=x onerror=alert(1)>', thumb: '"><script>1</script>', preview: '"><b>' }), { name: '<b>Kata', color: '"red' });
  assert.ok(!/<img src=x|<script>|<b>/.test(h), h);
});
test('sin título ni perfil no queda vacía; enlace real al video', () => {
  const h = tarjetaVideo(v('kata', '2026-11-02', { duration: 1772 }));
  assert.match(h, /Video de kata/); assert.match(h, /href="\/vods\/v\/\?id=kata02"/); assert.match(h, /29:32/);
});
