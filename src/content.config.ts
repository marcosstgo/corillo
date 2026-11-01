import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const noticias = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/noticias' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    ogTitle: z.string().optional(),
    ogDescription: z.string().optional(),
    badgeClass: z.string(),
    badgeIcon: z.string(),
    badgeLabel: z.string(),
    date: z.string(),       // fecha para mostrar, ej. "29 marzo 2026"
    pubDate: z.date(),      // fecha real — orden + RSS
    heroTitle: z.string(),
    heroSub: z.string(),
    wide: z.boolean().optional(),
    cardTitle: z.string().optional(), // título alterno para la tarjeta en /noticias/ (default: heroTitle)
    summary: z.string(),    // teaser corto para la tarjeta en /noticias/
    // — línea editorial (opcionales: las notas viejas no los tienen) —
    category: z.enum(['gaming', 'tech', 'streaming', 'geek', 'pr', 'corillo']).optional(),
    tags: z.array(z.string()).optional(),
    game: z.string().optional(),        // juego del que trata la nota (para buscar su arte oficial)
    image: z.string().optional(),       // portada 16:9 (scripts/news_cover.py): /noticias/portadas/<slug>.jpg
    imageCredit: z.string().optional(), // "Arte oficial: X (Steam)", "Ilustración generada para Corillo" o "Portada de Corillo"
    sources: z.array(z.object({ name: z.string(), url: z.string().url() })).optional(),
    ai: z.boolean().optional(),   // redactada con apoyo de IA a partir de las fuentes citadas (se avisa al lector)
  }),
});

// Cine (1-nov-2026): una ficha por película con TEXTO PROPIO de Corillo (sobre todo el cine puertorriqueño). Las de la
// cartelera general salen de TMDB (src/data/cine.json, scripts/update-cine.py); si una de esas tiene ficha aquí, gana esta.
const enlace = z.object({ name: z.string(), url: z.string().url() });
const cine = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/cine' }),
  schema: z.object({
    title: z.string(),
    original: z.string().optional(),          // título original si es otro
    year: z.number(),
    pr: z.boolean().default(false),           // cine puertorriqueño → sección «Hecho en Puerto Rico»
    estreno: z.date().optional(),             // estreno en cines de Puerto Rico
    estrenoNota: z.string().optional(),       // «Caribbean Cinemas y Fine Arts», «salas selectas»…
    duracion: z.number().optional(),          // minutos
    clasificacion: z.string().optional(),
    generos: z.array(z.string()).default([]),
    direccion: z.array(z.string()).default([]),
    guion: z.array(z.string()).optional(),
    reparto: z.array(z.string()).default([]),
    productora: z.array(z.string()).optional(),
    distribuidora: z.string().optional(),
    resumen: z.string(),                       // 1-2 oraciones para tarjetas
    description: z.string(),                   // meta description (≤160)
    afiche: z.string().optional(),             // vertical 2:3
    fondo: z.string().optional(),              // horizontal 16:9
    imagenCredito: z.string().optional(),      // «Afiche oficial: <productora>» / «Imágenes: TMDB»
    trailer: z.string().optional(),            // id de YouTube del canal OFICIAL
    trailerCanal: z.string().optional(),
    filmadaEn: z.array(z.string()).optional(),
    premios: z.array(z.string()).optional(),
    dondeVer: z.array(z.object({ name: z.string(), url: z.string().url().optional(), nota: z.string().optional() })).optional(),
    enlaces: z.array(enlace).optional(),       // sitio, Instagram, Facebook oficiales
    tmdb: z.number().optional(),
    fuentes: z.array(enlace).default([]),
    actualizado: z.date(),
  }),
});

export const collections = { noticias, cine };
