/* Eventos de videojuegos en Puerto Rico (1-nov-2026). Los escribe scripts/update-eventos.py. */
import datos from './eventos.json';

export interface Evento {
  slug: string; nombre: string; inicio: string; fin: string; lugar: string; municipio: string; detalle: string; precio: string;
  web: string; confirmado: boolean; fuente_nombre: string; fuente_url: string; voz_extra: string;
}

const hoy = () => new Date(Date.now() - 4 * 3600 * 1000).toISOString().slice(0, 10);   // Puerto Rico: AST todo el año
export const eventos = (): Evento[] => (datos.eventos as Evento[]).filter(e => e.fin >= hoy());
export const actualizado: string = datos.actualizado;
export interface Pasado { nombre: string; inicio: string; fin: string; lugar: string; municipio: string; detalle: string }
export const pasados = (): Pasado[] => ((datos as any).pasados || []) as Pasado[];

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
export function fechaEvento(e: Pick<Evento, 'inicio' | 'fin'>): string {
  const [a, m, d] = e.inicio.split('-').map(Number);
  const f = Number(e.fin.split('-')[2]);
  return `${d}${e.fin !== e.inicio ? ` y ${f}` : ''} de ${MESES[m - 1]} de ${a}`;
}
export const dondeEvento = (e: Pick<Evento, 'lugar' | 'municipio'>) => [e.lugar, e.municipio].filter(Boolean).join(', ');

/* schema.org/Event: solo para lo confirmado. Una fecha equivocada en Google es peor que no salir. */
export const eventoLd = (e: Evento, url: string) => ({
  '@context': 'https://schema.org', '@type': 'Event', name: e.nombre, url, startDate: e.inicio, endDate: e.fin,
  eventStatus: 'https://schema.org/EventScheduled', eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
  description: e.detalle || `${e.nombre} en ${dondeEvento(e)}, Puerto Rico.`,
  location: { '@type': 'Place', name: e.lugar, address: { '@type': 'PostalAddress', addressLocality: e.municipio, addressRegion: 'PR', addressCountry: 'US' } },
  ...(e.web ? { sameAs: e.web } : {}),
});

/* Para la tarjeta: «5:00 PM · Super Smash Bros. Ultimate» → hora y juegos. Lo que no tenga ese formato sigue siendo texto. */
export function detalleDe(e: Pick<Evento, 'detalle'>): { hora: string; juegos: string[]; texto: string } {
  const m = (e.detalle || '').match(/^(\d{1,2}:\d{2}\s*[AP]M)(?:\s*·\s*(.*))?$/);
  if (m) return { hora: m[1], juegos: (m[2] || '').split(',').map(j => j.trim()).filter(Boolean), texto: '' };
  return { hora: '', juegos: [], texto: e.detalle || '' };
}

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const parte = (f: string) => f.split('-').map(Number);
const diaSemana = (f: string) => { const [a, m, d] = parte(f); return new Date(Date.UTC(a, m - 1, d)).getUTCDay(); };
export function ficha(e: Pick<Evento, 'inicio' | 'fin'>) {
  const [, m, d] = parte(e.inicio), f = parte(e.fin)[2];
  return { dia: e.fin !== e.inicio ? `${d}–${f}` : String(d), mes: MESES[m - 1].slice(0, 3),
           semana: DIAS[diaSemana(e.inicio)] + (e.fin !== e.inicio ? ` y ${DIAS[diaSemana(e.fin)]}` : '') };
}
export const diasEntre = (desde: string, hasta: string) => {
  const [a, b, c] = parte(desde), [x, y, z] = parte(hasta);
  return Math.round((Date.UTC(x, y - 1, z) - Date.UTC(a, b - 1, c)) / 86400000);
};
export const hoyPR = hoy;
export const faltan = (n: number) => n <= 0 ? 'Hoy' : n === 1 ? 'Mañana' : `Faltan ${n} días`;

const sinGuiones = (f: string) => f.replaceAll('-', '');
const diaSiguiente = (f: string) => { const [a, m, d] = parte(f); return new Date(Date.UTC(a, m - 1, d + 1)).toISOString().slice(0, 10); };

/* Solo con un lugar concreto: un mapa de «San Juan» no ayuda a llegar. */
export const mapaUrl = (e: Pick<Evento, 'lugar' | 'municipio'>) => e.lugar && e.municipio
  ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${e.lugar}, ${e.municipio}, Puerto Rico`)}` : '';

const notaCalendario = (e: Evento) => [e.confirmado ? '' : 'Por confirmar: verifica con el organizador antes de ir.', e.detalle, e.web || e.fuente_url].filter(Boolean).join('\n');
export const googleUrl = (e: Evento) => 'https://calendar.google.com/calendar/render?action=TEMPLATE'
  + `&text=${encodeURIComponent(e.nombre)}&dates=${sinGuiones(e.inicio)}/${sinGuiones(diaSiguiente(e.fin))}`
  + `&location=${encodeURIComponent([dondeEvento(e), 'Puerto Rico'].filter(Boolean).join(', '))}&details=${encodeURIComponent(notaCalendario(e))}`;

/* iCalendar (RFC 5545): eventos de día completo; DTEND es el día después. */
const escIcs = (t: string) => t.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
function doblar(l: string) {
  const b = [...l]; const out: string[] = []; let linea = '', bytes = 0;
  for (const ch of b) {
    const n = new TextEncoder().encode(ch).length;
    if (bytes + n > 73) { out.push(linea); linea = ' '; bytes = 1; }
    linea += ch; bytes += n;
  }
  out.push(linea);
  return out.join('\r\n');
}
export function calendarioIcs(lista: Evento[], nombre: string) {
  const sello = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
  const lineas = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CORILLO//Eventos//ES', 'CALSCALE:GREGORIAN', `X-WR-CALNAME:${escIcs(nombre)}`, 'X-WR-TIMEZONE:America/Puerto_Rico'];
  for (const e of lista) lineas.push('BEGIN:VEVENT', `UID:${e.slug}@corillo.live`, `DTSTAMP:${sello}`, `DTSTART;VALUE=DATE:${sinGuiones(e.inicio)}`,
    `DTEND;VALUE=DATE:${sinGuiones(diaSiguiente(e.fin))}`, `SUMMARY:${escIcs((e.confirmado ? '' : '[Por confirmar] ') + e.nombre)}`,
    `LOCATION:${escIcs([dondeEvento(e), 'Puerto Rico'].filter(Boolean).join(', '))}`, `DESCRIPTION:${escIcs(notaCalendario(e))}`, 'END:VEVENT');
  lineas.push('END:VCALENDAR');
  return lineas.map(doblar).join('\r\n') + '\r\n';
}
export const respuestaIcs = (texto: string) => new Response(texto, { headers: { 'Content-Type': 'text/calendar; charset=utf-8' } });

/* Los meses del calendario visual: desde este mes hasta el del último evento (máximo 4). */
export function mesesCalendario(lista: Pick<Evento, 'inicio' | 'fin' | 'slug' | 'nombre'>[]) {
  const [a0, m0] = parte(hoy());
  const ultimo = lista.reduce((u, e) => e.inicio > u ? e.inicio : u, hoy());
  const [a1, m1] = parte(ultimo);
  const total = Math.min(4, (a1 - a0) * 12 + (m1 - m0) + 1);
  return Array.from({ length: total }, (_, i) => {
    const f = new Date(Date.UTC(a0, m0 - 1 + i, 1)), a = f.getUTCFullYear(), m = f.getUTCMonth();
    const dias = new Date(Date.UTC(a, m + 1, 0)).getUTCDate();
    return { titulo: `${MESES[m]} ${a}`, hueco: f.getUTCDay(), dias: Array.from({ length: dias }, (_, d) => {
      const fecha = `${a}-${String(m + 1).padStart(2, '0')}-${String(d + 1).padStart(2, '0')}`;
      return { n: d + 1, fecha, evento: lista.find(e => e.inicio <= fecha && fecha <= e.fin) };
    }) };
  });
}
