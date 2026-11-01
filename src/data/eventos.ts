/* Eventos de videojuegos en Puerto Rico (1-nov-2026). Los escribe scripts/update-eventos.py. */
import datos from './eventos.json';

export interface Evento {
  slug: string; nombre: string; inicio: string; fin: string; lugar: string; municipio: string; detalle: string; precio: string;
  web: string; confirmado: boolean; fuente_nombre: string; fuente_url: string; voz_extra: string;
}

const hoy = () => new Date(Date.now() - 4 * 3600 * 1000).toISOString().slice(0, 10);   // Puerto Rico: AST todo el año
export const eventos = (): Evento[] => (datos.eventos as Evento[]).filter(e => e.fin >= hoy());
export const actualizado: string = datos.actualizado;

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
