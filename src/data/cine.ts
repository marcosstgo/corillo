/* Cine (1-nov-2026): junta las fichas propias (src/content/cine/*.md, texto de Corillo) con la cartelera de TMDB
   (src/data/cine.json, la escribe scripts/update-cine.py). Una película de TMDB que también tenga ficha propia
   usa la propia. Todo se genera en el build: cada película es una página real que Google puede leer. */
import { getCollection, type CollectionEntry } from 'astro:content';
import datos from './cine.json';

export type Pelicula = {
  slug: string; title: string; original?: string; year?: number; pr: boolean;
  estreno?: string;          // AAAA-MM-DD (en Puerto Rico)
  estrenoNota?: string; duracion?: number; clasificacion?: string;
  generos: string[]; direccion: string[]; guion?: string[]; reparto: string[]; productora?: string[]; distribuidora?: string;
  resumen: string; description: string; afiche?: string; fondo?: string; imagenCredito?: string;
  trailer?: string; trailerCanal?: string; filmadaEn?: string[]; premios?: string[];
  dondeVer?: { name: string; url?: string; nota?: string }[]; enlaces?: { name: string; url: string }[];
  tmdb?: number; fuentes: { name: string; url: string }[]; propia: boolean; entry?: CollectionEntry<'cine'>;
  popularidad?: number;
};

type Tmdb = {
  tmdb: number; title: string; original?: string; estreno?: string; resumen?: string; generos?: string[];
  afiche?: string; fondo?: string; duracion?: number; clasificacion?: string; direccion?: string[]; reparto?: string[];
  trailer?: string; trailerCanal?: string; dondeVer?: { name: string; url?: string }[]; popularidad?: number; pr?: boolean;
};

export const slugify = (t: string) => t.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

const iso = (d?: Date) => d ? d.toISOString().slice(0, 10) : undefined;

let _todas: Pelicula[] | null = null;

export async function todas(): Promise<Pelicula[]> {
  if (_todas) return _todas;
  const propias: Pelicula[] = (await getCollection('cine')).map(e => ({
    ...e.data, slug: e.id, estreno: iso(e.data.estreno), propia: true, entry: e,
  }));
  const porTmdb = new Map(propias.filter(p => p.tmdb).map(p => [p.tmdb, p]));
  const usados = new Set(propias.map(p => p.slug));
  const deTmdb: Pelicula[] = [];
  const lista: Tmdb[] = [...(datos.pegao as Tmdb[]), ...(datos.cartelera as Tmdb[]), ...(datos.proximos as Tmdb[])];
  for (const t of lista) {
    const propia = porTmdb.get(t.tmdb);
    if (propia) { propia.popularidad = Math.max(propia.popularidad || 0, t.popularidad || 0); continue; }
    const year = t.estreno ? Number(t.estreno.slice(0, 4)) : undefined;
    const slug = `${slugify(t.title)}${year ? '-' + year : ''}`;
    if (usados.has(slug)) continue;
    usados.add(slug);
    deTmdb.push({
      slug, title: t.title, original: t.original !== t.title ? t.original : undefined, year, pr: !!t.pr,
      estreno: t.estreno, duracion: t.duracion, clasificacion: t.clasificacion, generos: t.generos || [],
      direccion: t.direccion || [], reparto: t.reparto || [], resumen: t.resumen || '',
      description: (t.resumen || `${t.title}: estreno, tráiler y dónde verla en Puerto Rico.`).slice(0, 155),
      afiche: t.afiche, fondo: t.fondo, imagenCredito: 'Datos e imágenes: TMDB', trailer: t.trailer,
      trailerCanal: t.trailerCanal, dondeVer: t.dondeVer, tmdb: t.tmdb, popularidad: t.popularidad,
      fuentes: [{ name: 'TMDB', url: `https://www.themoviedb.org/movie/${t.tmdb}` }], propia: false,
    });
  }
  _todas = [...propias, ...deTmdb];
  return _todas;
}

const ids = (k: 'pegao' | 'cartelera' | 'proximos') => new Set((datos[k] as Tmdb[]).map(t => t.tmdb));
const hoy = () => new Date().toISOString().slice(0, 10);

export async function hechoEnPR() {
  return (await todas()).filter(p => p.pr).sort((a, b) => (b.estreno || '').localeCompare(a.estreno || ''));
}
export async function pegao() {
  const s = ids('pegao');
  return (await todas()).filter(p => p.tmdb && s.has(p.tmdb)).sort((a, b) => (b.popularidad || 0) - (a.popularidad || 0));
}
export async function cartelera() {
  const s = ids('cartelera');
  return (await todas()).filter(p => (p.tmdb && s.has(p.tmdb)) || (p.pr && p.estreno && p.estreno <= hoy() && enCines(p)));
}
export async function proximos() {
  const s = ids('proximos');
  return (await todas()).filter(p => p.estreno && p.estreno > hoy() && ((p.tmdb && s.has(p.tmdb)) || p.pr))
    .sort((a, b) => (a.estreno || '').localeCompare(b.estreno || ''));
}
/** Una boricua sigue «en cartelera» ~6 semanas después del estreno (si su ficha no dice otra cosa en dondeVer). */
function enCines(p: Pelicula) {
  if (!p.estreno) return false;
  const dias = (Date.now() - new Date(p.estreno + 'T12:00:00').valueOf()) / 864e5;
  return dias <= 42 && !(p.dondeVer || []).some(d => /netflix|prime|max|disney|apple|hulu|paramount|vix|youtube/i.test(d.name));
}
export const actualizado = datos.actualizado as string | null;

export function fechaLarga(d?: string) {
  if (!d) return '';
  return new Date(d + 'T12:00:00').toLocaleDateString('es-PR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Puerto_Rico' });
}
export function fechaCorta(d?: string) {
  if (!d) return '';
  return new Date(d + 'T12:00:00').toLocaleDateString('es-PR', { day: 'numeric', month: 'short', timeZone: 'America/Puerto_Rico' });
}
export function duracionTexto(min?: number) {
  if (!min) return '';
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h} h${m ? ` ${m} min` : ''}` : `${m} min`;
}

/** JSON-LD schema.org/Movie para la ficha (lo que Google usa para entender y mostrar la película). */
export function movieLd(p: Pelicula, url: string) {
  const persona = (n: string) => ({ '@type': 'Person', name: n });
  return {
    '@context': 'https://schema.org', '@type': 'Movie', name: p.title, url,
    ...(p.original ? { alternateName: p.original } : {}),
    description: p.description,
    ...(p.afiche || p.fondo ? { image: new URL(p.afiche || p.fondo!, 'https://corillo.live/').href } : {}),
    ...(p.estreno ? { datePublished: p.estreno } : {}),
    ...(p.duracion ? { duration: `PT${Math.floor(p.duracion / 60)}H${p.duracion % 60}M` } : {}),
    ...(p.generos.length ? { genre: p.generos } : {}),
    ...(p.direccion.length ? { director: p.direccion.map(persona) } : {}),
    ...(p.reparto.length ? { actor: p.reparto.slice(0, 10).map(persona) } : {}),
    ...(p.productora?.length ? { productionCompany: p.productora.map(n => ({ '@type': 'Organization', name: n })) } : {}),
    ...(p.pr ? { countryOfOrigin: { '@type': 'Country', name: 'Puerto Rico' } } : {}),
    ...(p.clasificacion ? { contentRating: p.clasificacion } : {}),
    ...(p.trailer ? { trailer: { '@type': 'VideoObject', name: `${p.title} — tráiler oficial`, embedUrl: `https://www.youtube.com/embed/${p.trailer}`,
        thumbnailUrl: `https://i.ytimg.com/vi/${p.trailer}/hqdefault.jpg`, uploadDate: p.estreno || undefined, description: `Tráiler oficial de ${p.title}` } } : {}),
    ...(p.premios?.length ? { award: p.premios } : {}),
    ...(p.enlaces?.length ? { sameAs: p.enlaces.map(e => e.url) } : {}),
    inLanguage: 'es',
  };
}
