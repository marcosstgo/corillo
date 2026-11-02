/* Lo más jugado en Steam (2-nov-2026). Lo escribe scripts/update-juegos.py desde la API oficial de Steam. */
import foto from './juegos.json';
import catalogo from './juegos-catalogo.json';

export interface Ficha {
  nombre: string; slug: string; tipo: string; gratis: boolean; generos: string[]; desarrollador: string; lanzamiento: string;
  imagen: string; visto_desde: string; ultimo?: { fecha: string; puesto: number; ahora: number; pico: number };
}
export interface Fila { appid: number; puesto: number; ahora: number; pico: number; cambio: number | 'nuevo' | null; }
export type FilaConFicha = Fila & { ficha: Ficha };

const fichas = catalogo as unknown as Record<string, Ficha>;
export const actualizado: string = foto.actualizado;
export const top = (): FilaConFicha[] => (foto.juegos as Fila[]).map(f => ({ ...f, ficha: fichas[String(f.appid)] }));
export const todos = (): { appid: number; ficha: Ficha; fila?: Fila }[] => {
  const filas = new Map((foto.juegos as Fila[]).map(f => [f.appid, f]));
  return Object.entries(fichas).map(([a, ficha]) => ({ appid: Number(a), ficha, fila: filas.get(Number(a)) }));
};

export const numero = (n: number) => n.toLocaleString('en-US');
export const urlTienda = (appid: number) => `https://store.steampowered.com/app/${appid}/`;

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
/** «2 de noviembre de 2026, 6:10 a. m.», en la hora de Puerto Rico con la que se guardó. */
export function fechaFoto(iso: string = actualizado): string {
  const [, a, m, d, h, mi] = iso.match(/^(\d+)-(\d+)-(\d+)T(\d+):(\d+)/)!.map(Number) as number[];
  return `${d} de ${MESES[m - 1]} de ${a}, ${h % 12 || 12}:${String(mi).padStart(2, '0')} ${h < 12 ? 'a. m.' : 'p. m.'}`;
}
export const fechaCorta = (iso: string) => { const [a, m, d] = iso.split('-').map(Number); return `${d} de ${MESES[m - 1]} de ${a}`; };
