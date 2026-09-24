// Datos de /mercado/: se leen de la API AL COMPILAR (como /ofertas/ lee su JSON). Tras cada
// anuncio nuevo o cambio, la API pide un rebuild (scripts/mercado-rebuild.sh, con candado).
// Si la API no responde, se usa la ÚLTIMA COPIA BUENA (MERCADO_SNAPSHOT, fuera del repo) para no
// publicar un Mercado vacío por un fallo momentáneo. Sin copia (p. ej. compilando en GitHub), las
// páginas salen vacías en vez de fallar, y el navegador completa desde /api/mercado/anuncios.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CATEGORIAS, MUNICIPIOS, type Categoria } from './categorias';
import type { Lang } from '../i18n';

const URL_RESUMEN = process.env.MERCADO_API || 'http://127.0.0.1:3004/mercado/resumen';
const SNAPSHOT = process.env.MERCADO_SNAPSHOT || path.join(os.homedir(), '.cache', 'corillo-mercado-snapshot.json');

export interface Vendedor { key: string; nombre: string; color: string; avatar: string; streamer: boolean; canal: string; }
export interface Anuncio {
  id: string; titulo: string; categoria: string; subcategoria: string; marca: string; modelo: string;
  condicion: 'nuevo' | 'como-nuevo' | 'buen-estado' | 'para-piezas'; precio: number; negociable: boolean;
  descripcion: string; incluye: string[]; falta: string[]; pueblo: string; entrega: 'persona' | 'envio' | 'ambos';
  estado: 'disponible' | 'reservado' | 'vendido'; vendido_at: string; fotos: string[]; og: string;
  tiene_whatsapp: boolean; created: string; updated: string; vendedor: Vendedor;
}
export interface Resumen { total: number; por_categoria: Record<string, number>; anuncios: Anuncio[]; }

function guardarCopia(R: Resumen) {
  try {
    fs.mkdirSync(path.dirname(SNAPSHOT), { recursive: true });
    fs.writeFileSync(SNAPSHOT + '.tmp', JSON.stringify(R));
    fs.renameSync(SNAPSHOT + '.tmp', SNAPSHOT);
  } catch { /* sin disco escribible: no pasa nada */ }
}
function leerCopia(): Resumen {
  try {
    const R = JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8'));
    console.warn(`[mercado] API sin respuesta: se usa la última copia buena (${SNAPSHOT})`);
    return R;
  } catch {
    console.warn('[mercado] API sin respuesta y sin copia: páginas del Mercado sin anuncios');
    return { total: 0, por_categoria: {}, anuncios: [] };
  }
}

let memo: Promise<Resumen> | null = null;
export function loadMercado(): Promise<Resumen> {
  memo ??= fetch(URL_RESUMEN, { signal: AbortSignal.timeout(8000) })
    .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((R: Resumen) => { if (!Array.isArray(R.anuncios)) throw new Error('forma'); guardarCopia(R); return R; })
    .catch(leerCopia)
    // Igual que la API: los vendidos (visibles 14 días con su marca) siempre al final.
    .then((R: Resumen) => ({ ...R, anuncios: [...R.anuncios].sort((x, y) => Number(x.estado === 'vendido') - Number(y.estado === 'vendido')) }));
  return memo;
}

export const nombrePueblo = (slug: string) => MUNICIPIOS.find(m => m.slug === slug)?.nombre ?? slug;
export const precio = (n: number, gratis = 'Gratis') => n === 0 ? gratis : '$' + n.toLocaleString('en-US', { maximumFractionDigits: 2 });
export const categoriasConAnuncios = (R: Resumen): (Categoria & { n: number })[] =>
  CATEGORIAS.map(c => ({ ...c, n: R.por_categoria[c.slug] ?? 0 }));
/** Nombre de la categoría en el idioma de la página. */
export const nombreCat = (c: Categoria | undefined, lang: Lang) => (c ? c[lang] : '');
/** Rutas del Mercado que NO son categorías (una categoría no puede llamarse así). */
export const RUTAS_FIJAS = ['a', 'anuncio', 'vender', 'mis-anuncios', 'moderacion'];
