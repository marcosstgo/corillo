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
  }),
});

export const collections = { noticias };
