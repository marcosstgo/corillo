// Datos de /mercado/: se leen de la API AL COMPILAR (como /ofertas/ lee su JSON). Tras cada
// anuncio nuevo o cambio, la API pide un rebuild (scripts/deploy-corillo.sh, con candado).
// Si la API no responde (p. ej. compilando en GitHub sin acceso), las páginas salen vacías
// en vez de fallar, y el navegador completa desde /api/mercado/anuncios.
import { CATEGORIAS, MUNICIPIOS, type Categoria } from './categorias';

const URL_RESUMEN = process.env.MERCADO_API || 'http://127.0.0.1:3004/mercado/resumen';

export interface Vendedor { key: string; nombre: string; color: string; avatar: string; streamer: boolean; canal: string; }
export interface Anuncio {
  id: string; titulo: string; categoria: string; subcategoria: string; marca: string; modelo: string;
  condicion: 'nuevo' | 'como-nuevo' | 'buen-estado' | 'para-piezas'; precio: number; negociable: boolean;
  descripcion: string; incluye: string[]; falta: string[]; pueblo: string; entrega: 'persona' | 'envio' | 'ambos';
  estado: 'disponible' | 'reservado' | 'vendido'; vendido_at: string; fotos: string[]; og: string;
  tiene_whatsapp: boolean; created: string; updated: string; vendedor: Vendedor;
}
export interface Resumen { total: number; por_categoria: Record<string, number>; anuncios: Anuncio[]; }

let memo: Promise<Resumen> | null = null;
export function loadMercado(): Promise<Resumen> {
  memo ??= fetch(URL_RESUMEN, { signal: AbortSignal.timeout(8000) })
    .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
    // Igual que la API: los vendidos (visibles 14 días con su marca) siempre al final.
    .then((R: Resumen) => ({ ...R, anuncios: [...R.anuncios].sort((x, y) => Number(x.estado === 'vendido') - Number(y.estado === 'vendido')) }))
    .catch(() => ({ total: 0, por_categoria: {}, anuncios: [] }));
  return memo;
}

export const CONDICION: Record<Anuncio['condicion'], string> = {
  'nuevo': 'Nuevo', 'como-nuevo': 'Como nuevo', 'buen-estado': 'Buen estado', 'para-piezas': 'Para piezas',
};
export const ENTREGA: Record<Anuncio['entrega'], string> = {
  persona: 'En persona', envio: 'Envío', ambos: 'En persona o envío',
};
export const nombrePueblo = (slug: string) => MUNICIPIOS.find(m => m.slug === slug)?.nombre ?? slug;
export const precio = (n: number) => n === 0 ? 'Gratis' : '$' + n.toLocaleString('en-US', { maximumFractionDigits: 2 });
export const categoriasConAnuncios = (R: Resumen): (Categoria & { n: number })[] =>
  CATEGORIAS.map(c => ({ ...c, n: R.por_categoria[c.slug] ?? 0 }));
export const hoyHay = (n: number, donde = 'en Puerto Rico') =>
  n ? `Hoy hay ${n} ${n === 1 ? 'anuncio' : 'anuncios'} de equipo usado ${donde}` : `Equipo usado ${donde}`;
