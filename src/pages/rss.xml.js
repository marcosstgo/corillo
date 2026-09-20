import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('noticias')).sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
  );

  return rss({
    title: 'CORILLO — Noticias',
    description: 'Gaming y esports, tecnología e IA, streaming y creación de contenido, cultura geek y Puerto Rico. Por CORILLO.',
    site: context.site,
    items: posts.map(post => ({
      title: post.data.heroTitle,
      description: post.data.summary,
      pubDate: post.data.pubDate,
      link: `/noticias/${post.id}/`,
      categories: [post.data.category || 'corillo', ...(post.data.tags || [])],
    })),
    customData: `<language>es-pr</language>`,
  });
}
