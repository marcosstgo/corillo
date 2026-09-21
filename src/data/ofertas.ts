// Datos de /ofertas/: los escribe scripts/update-deals.py fuera del repo (así un push a main no los borra).
// Si el archivo no existe (p. ej. compilando en otra máquina) las páginas salen vacías en vez de fallar.
import fs from 'node:fs';

const FILE = process.env.OFERTAS_JSON || '/home/corillo-adm/corillo-deals/ofertas.json';

export type StoreKey = 'steam' | 'gog' | 'epic' | 'humble' | 'fanatical' | 'gmg' | 'gamersgate';
export interface Deal {
  id: string; title: string; store: StoreKey; url: string; image: string | null;
  price?: string; priceNum?: number; original?: string | null; pct?: number; rating?: number | null; reviews?: number; lowest?: boolean;
  starts?: string; ends?: string;
}
export interface Ofertas { updatedAt: string | null; free: Deal[]; freeSteam: Deal[]; soon: Deal[]; steam: Deal[]; gog: Deal[]; humble: Deal[]; fanatical: Deal[]; gmg: Deal[]; gamersgate: Deal[]; asOf: Record<string, string>; }

export function loadOfertas(): Ofertas {
  const empty: Ofertas = { updatedAt: null, free: [], freeSteam: [], soon: [], steam: [], gog: [], humble: [], fanatical: [], gmg: [], gamersgate: [], asOf: {} };
  try { return { ...empty, ...JSON.parse(fs.readFileSync(FILE, 'utf8')) }; } catch { return empty; }
}

export const STORES: Record<StoreKey, { label: string; color: string }> = {
  steam: { label: 'Steam', color: '#66c0f4' },
  gog: { label: 'GOG', color: '#c58bff' },
  epic: { label: 'Epic Games Store', color: '#f5f8ff' },
  humble: { label: 'Humble Store', color: '#ff7a59' },
  fanatical: { label: 'Fanatical', color: '#ffb020' },
  gmg: { label: 'Green Man Gaming', color: '#7bd66a' },
  gamersgate: { label: 'GamersGate', color: '#5ec8e5' },
};

/** Todo lo que hoy es gratis (Epic y Steam). */
export const allFree = (D: Ofertas): Deal[] => [...D.free, ...D.freeSteam];
/** Todas las ofertas con precio, de todas las tiendas. */
export const allPriced = (D: Ofertas): Deal[] => [...D.steam, ...D.gog, ...D.humble, ...D.fanatical, ...D.gmg, ...D.gamersgate];
const norm = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
/** Un juego aparece una sola vez: gana la oferta más barata. */
export function cheapestPerGame(items: Deal[]): Deal[] {
  const m = new Map<string, Deal>();
  for (const d of items) { const k = norm(d.title); const c = m.get(k); if (!c || (d.priceNum ?? 1e9) < (c.priceNum ?? 1e9)) m.set(k, d); }
  return [...m.values()];
}
const priceOf = (d: Deal) => d.priceNum ?? parseFloat((d.price || '0').replace(/[^0-9.]/g, ''));

export interface Lista { slug: string; h1: string; title: string; blurb: string; items: (D: Ofertas) => Deal[]; store?: StoreKey; asOfKey?: string; }
const byScore = (a: Deal, b: Deal) => ((b.pct ?? 0) + (b.lowest ? 25 : 0)) - ((a.pct ?? 0) + (a.lowest ? 25 : 0));
export const LISTAS: Lista[] = [
  { slug: 'steam', store: 'steam', asOfKey: 'steam', h1: 'Ofertas en Steam', title: 'Ofertas en Steam hoy: los juegos mejor reseñados con descuento',
    blurb: 'Los juegos de Steam con mejores reseñas que están en oferta ahora mismo. Solo entran los que tienen al menos 30 % de descuento, 75 % de reseñas positivas y 500 reseñas o más.', items: D => D.steam },
  { slug: 'gog', store: 'gog', asOfKey: 'gog', h1: 'Ofertas en GOG', title: 'Ofertas en GOG hoy: juegos sin DRM con descuento',
    blurb: 'Juegos de GOG, la tienda sin DRM: los compras una vez y son tuyos. Solo entran los que tienen al menos 30 % de descuento y buenas reseñas.', items: D => D.gog },
  { slug: 'humble', store: 'humble', asOfKey: 'humble', h1: 'Ofertas en Humble Store', title: 'Ofertas en Humble Store hoy: juegos de PC con descuento',
    blurb: 'Ofertas de Humble Store en juegos de PC bien valorados, con al menos 30 % de descuento.', items: D => D.humble },
  { slug: 'fanatical', store: 'fanatical', asOfKey: 'fanatical', h1: 'Ofertas en Fanatical', title: 'Ofertas en Fanatical hoy: juegos de PC con descuento',
    blurb: 'Ofertas de Fanatical en juegos de PC bien valorados, con al menos 30 % de descuento.', items: D => D.fanatical },
  { slug: 'green-man-gaming', store: 'gmg', asOfKey: 'gmg', h1: 'Ofertas en Green Man Gaming', title: 'Ofertas en Green Man Gaming hoy: juegos de PC con descuento',
    blurb: 'Ofertas de Green Man Gaming en juegos de PC bien valorados, con al menos 30 % de descuento.', items: D => D.gmg },
  { slug: 'gamersgate', store: 'gamersgate', asOfKey: 'gamersgate', h1: 'Ofertas en GamersGate', title: 'Ofertas en GamersGate hoy: juegos de PC con descuento',
    blurb: 'Ofertas de GamersGate en juegos de PC bien valorados, con al menos 30 % de descuento.', items: D => D.gamersgate },
  { slug: 'minimos-historicos', h1: 'Juegos en su precio más bajo de la historia', title: 'Juegos en su mínimo histórico: el precio más bajo que han tenido',
    blurb: 'Juegos que hoy cuestan lo mismo que su precio más bajo registrado, según CheapShark. Si buscas el mejor momento para comprar, es este.',
    items: D => cheapestPerGame(allPriced(D).filter(d => d.lowest)).sort(byScore) },
  { slug: 'menos-de-5-dolares', h1: 'Juegos por menos de $5', title: 'Juegos por menos de 5 dólares: las mejores ofertas de hoy',
    blurb: 'Los juegos bien reseñados que cuestan $5 o menos ahora mismo en Steam, GOG, Humble, Fanatical, Green Man Gaming y GamersGate. Cuando un juego está en varias tiendas, mostramos la más barata.',
    items: D => cheapestPerGame(allPriced(D).filter(d => priceOf(d) <= 5)).sort(byScore).slice(0, 60) },
];
export const lista = (slug: string) => LISTAS.find(l => l.slug === slug)!;

const TZ = 'America/Puerto_Rico';
export const fmtDay = (iso: string) => new Date(iso).toLocaleDateString('es-PR', { day: 'numeric', month: 'long', timeZone: TZ });
export const fmtStamp = (iso: string) => new Date(iso).toLocaleString('es-PR', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit', timeZone: TZ });

/** Datos estructurados (schema.org) para que Google entienda las ofertas. */
export function offersJsonLd(items: Deal[], name: string, url: string) {
  return {
    '@context': 'https://schema.org', '@type': 'ItemList', name, url,
    itemListElement: items.slice(0, 40).map((d, i) => ({
      '@type': 'ListItem', position: i + 1,
      item: {
        '@type': 'Product', name: d.title, ...(d.image ? { image: d.image } : {}),
        offers: {
          '@type': 'Offer', url: d.url, priceCurrency: 'USD',
          price: d.price ? d.price.replace(/[^0-9.]/g, '') : '0',
          availability: 'https://schema.org/InStock',
          ...(d.ends ? { priceValidUntil: d.ends.slice(0, 10) } : {}),
          seller: { '@type': 'Organization', name: STORES[d.store].label },
        },
      },
    })),
  };
}
