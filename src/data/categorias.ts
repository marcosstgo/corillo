// Taxonomía ÚNICA de equipo: la usan /equipo/ (afiliados) y /mercado/ (usados), y la API del
// Mercado la lee del mismo JSON para validar. Añadir una categoría = añadir una línea en
// categorias.json (slug estable: es la URL /mercado/<slug>/ y lo guardan los anuncios).
// `equipoKinds` dice qué tipos de producto de /equipo/ caen en cada categoría.
import CATS from './categorias.json';
import MUNIS from './municipios.json';

export type Lang = 'es' | 'en';
export interface Subcategoria { slug: string; es: string; en: string; }
export interface Categoria { slug: string; es: string; en: string; icon: string; equipoKinds: string[]; sub: Subcategoria[]; }
export interface Municipio { slug: string; nombre: string; lat: number; lng: number; }

export const CATEGORIAS = CATS as Categoria[];
export const MUNICIPIOS = MUNIS as Municipio[];

export const categoria = (slug: string) => CATEGORIAS.find(c => c.slug === slug);
export const categoriaDeKind = (kind: string) => CATEGORIAS.find(c => c.equipoKinds.includes(kind));
export const municipio = (slug: string) => MUNICIPIOS.find(m => m.slug === slug);
