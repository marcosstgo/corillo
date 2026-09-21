// Datos de /ofertas/: los escribe scripts/update-deals.py fuera del repo (así un push a main no los borra).
// Si el archivo no existe (p. ej. compilando en otra máquina) las páginas salen vacías en vez de fallar.
import fs from 'node:fs';

const FILE = process.env.OFERTAS_JSON || '/home/corillo-adm/corillo-deals/ofertas.json';

export interface Deal {
  id: string; title: string; store: 'steam' | 'gog' | 'epic'; url: string; image: string | null;
  price?: string; original?: string | null; pct?: number; rating?: number | null; reviews?: number; lowest?: boolean;
  starts?: string; ends?: string;
}
export interface Ofertas { updatedAt: string | null; free: Deal[]; soon: Deal[]; steam: Deal[]; gog: Deal[]; asOf: Record<string, string>; }

export function loadOfertas(): Ofertas {
  const empty: Ofertas = { updatedAt: null, free: [], soon: [], steam: [], gog: [], asOf: {} };
  try { return { ...empty, ...JSON.parse(fs.readFileSync(FILE, 'utf8')) }; } catch { return empty; }
}

export const STORES = {
  steam: { label: 'Steam', color: '#66c0f4' },
  gog:   { label: 'GOG', color: '#c58bff' },
  epic:  { label: 'Epic Games Store', color: '#f5f8ff' },
} as const;

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
          price: d.store === 'epic' && d.ends ? '0' : (d.price || '0').replace(/[^0-9.]/g, ''),
          availability: 'https://schema.org/InStock',
          ...(d.ends ? { priceValidUntil: d.ends.slice(0, 10) } : {}),
          seller: { '@type': 'Organization', name: STORES[d.store].label },
        },
      },
    })),
  };
}
