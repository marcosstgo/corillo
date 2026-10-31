// Cloudflare Pages Function: lo que en el server viejo hacía nginx (corillo-infra/nginx/nginx.conf).
// Solo corre para las rutas que NO están en dist/ (ver scripts/pages-routes.mjs → dist/_routes.json):
//   /<canal>/          → la página del player con __CHANNEL__ reemplazado (antes: nginx sub_filter)
//   /mercado/a/<id>/   → anuncio recién publicado que aún no tiene página estática (lo muestra desde la API)
const CANAL = /^\/([a-z0-9][a-z0-9_]*)\/?$/;

export async function onRequest({ request, env }) {
  const res = await env.ASSETS.fetch(request);
  if (res.status !== 404) return res;
  const url = new URL(request.url);

  const anuncio = url.pathname.match(/^(\/en)?\/mercado\/a\/[^/]+\/?$/);
  if (anuncio) return env.ASSETS.fetch(new URL(`${anuncio[1] || ''}/mercado/anuncio/`, url));

  const m = url.pathname.match(CANAL);
  if (!m) return res;
  if (!url.pathname.endsWith('/')) return Response.redirect(`${url.origin}${url.pathname}/${url.search}`, 301);
  const player = await env.ASSETS.fetch(new URL('/player/', url));
  const html = (await player.text()).replaceAll('__CHANNEL__', m[1]);
  return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=60' } });
}
