import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('noticias')).sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
  );

  return rss({
    title: 'CORILLO — Noticias',
    description: 'Updates de plataforma, software nuevo, cambios en el site y anuncios del proyecto.',
    site: context.site,
    items: posts.map(post => ({
      title: post.data.heroTitle,
      description: post.data.summary,
      pubDate: post.data.pubDate,
      link: `/noticias/${post.id}/`,
    })),
    customData: `<language>es-pr</language>`,
  });
}
