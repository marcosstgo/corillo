import test from 'node:test';
import assert from 'node:assert/strict';
import { ordenarVitrina, conservarVisible, cuando, vigente } from './vitrina.js';

const nota1 = { id: 'nota-hoy', fecha: 300 }, video = { id: 'video-ayer', fecha: 200 }, nota2 = { id: 'nota-ayer', fecha: 150 }, video2 = { id: 'video-viejo', fecha: 100 };
const gratis = { id: 'gratis' }, equipo = { id: 'equipo' }, gratis2 = { id: 'gratis2' };
const ids = l => l.map(x => x.id);

test('la noticia de hoy va antes que un video de ayer', () => {
  assert.deepEqual(ids(ordenarVitrina([video, gratis, nota2, equipo, nota1, video2])),
    ['nota-hoy', 'video-ayer', 'gratis', 'nota-ayer', 'equipo', 'video-viejo']);
});
test('un video más nuevo que la noticia va primero', () => {
  assert.deepEqual(ids(ordenarVitrina([nota2, { id: 'video-ya', fecha: 999 }, gratis])), ['video-ya', 'nota-ayer', 'gratis']);
});
test('sin fechados, solo las ofertas; sin ofertas, solo fechados; vacío no rompe', () => {
  assert.deepEqual(ids(ordenarVitrina([gratis, equipo, gratis2])), ['gratis', 'equipo', 'gratis2']);
  assert.deepEqual(ids(ordenarVitrina([video2, nota1, nota2])), ['nota-hoy', 'nota-ayer', 'video-viejo']);
  assert.deepEqual(ordenarVitrina([]), []);
});
test('no cambia la lista que recibe', () => {
  const l = [video, nota1]; ordenarVitrina(l); assert.deepEqual(l, [video, nota1]);
});
test('lo visible no se mueve aunque llegue algo más nuevo', () => {
  const orden = [{ id: 'video-ya' }, { id: 'nota' }, { id: 'gratis' }];
  assert.deepEqual(ids(conservarVisible(orden, orden[1], 0)), ['nota', 'video-ya', 'gratis']);   // el nuevo sale en el próximo turno
  assert.deepEqual(ids(conservarVisible(orden, orden[2], 2)), ['video-ya', 'nota', 'gratis']);
  assert.deepEqual(ids(conservarVisible(orden, orden[0], 9)), ['nota', 'gratis', 'video-ya']);   // posición fuera de rango
});
test('cuando: cuenta días del calendario de Puerto Rico', () => {
  const ahora = Date.parse('2026-11-02T21:00:00Z');                                     // 5 PM en PR
  assert.equal(cuando(Date.parse('2026-11-02T11:30:00Z'), ahora), 'Hoy');
  assert.equal(cuando(Date.parse('2026-11-01T07:16:29Z'), ahora), 'Ayer');
  assert.equal(cuando(Date.parse('2026-11-02T03:00:00Z'), ahora), 'Ayer');              // 11 PM del 1 en PR, aunque sea día 2 en UTC
  assert.equal(cuando(Date.parse('2026-11-02T21:00:00Z'), Date.parse('2026-11-03T05:00:00Z')), 'Ayer'); // solo 8 horas, pero ya es otro día en PR
  assert.equal(cuando(Date.parse('2026-10-31T05:26:42Z'), ahora), '31 de octubre');
  assert.equal(cuando(ahora + 60000, ahora), 'Hoy');                                    // reloj adelantado
});
test('vigente', () => {
  assert.equal(vigente('2026-11-05T15:00:00Z', Date.parse('2026-11-02T00:00:00Z')), true);
  assert.equal(vigente('2026-11-01T15:00:00Z', Date.parse('2026-11-02T00:00:00Z')), false);
  assert.equal(vigente(undefined), true);
  assert.equal(vigente('sin fecha'), true);
});
