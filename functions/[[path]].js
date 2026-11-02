// Cloudflare Pages Function: lo que en el server viejo hacía nginx (corillo-infra/nginx/nginx.conf).
// Solo corre para las rutas que NO están en dist/ (ver scripts/pages-routes.mjs → dist/_routes.json):
//   /<canal>/          → la página del player con __CHANNEL__ reemplazado (antes: nginx sub_filter)
//   /mercado/a/<id>/   → anuncio recién publicado que aún no tiene página estática (lo muestra desde la API)
const CANAL = /^\/([a-z0-9][a-z0-9_]*)\/?$/;

// Canales cuyo nombre choca con archivos especiales de Pages (404.html se sirve en /404/): van directo al player.
const CHOCAN = new Set(['404']);

// El nombre y la bio del canal salen en el HTML: los leen Google y las vistas previas de WhatsApp, que no corren JavaScript.
// Si la API no contesta a tiempo, la página sale con el nombre del canal y el navegador lo vuelve a intentar.
async function perfil(canal) {
  try {
    const r = await fetch(`https://api.corillo.live/api/profile/${canal}`, { signal: AbortSignal.timeout(1500), cf: { cacheTtl: 60 } });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}
const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const json = o => JSON.stringify(o).replace(/</g, '\\u003c');
function conPerfil(html, p) {
  const nombre = p && (p.name || p.display_name);
  if (!nombre) return html;
  const sobre = (p.bio || p.sub || '').trim();
  const desc = `${nombre} en Corillo${sobre ? `: ${sobre}` : ''}. Transmisiones en vivo y videos desde Puerto Rico.`;
  const url = `https://corillo.live/${p.key}/`;
  const ld = { '@context': 'https://schema.org', '@type': 'ProfilePage', url, mainEntity: { '@type': 'Person', name: nombre, description: sobre || undefined,
    image: p.avatar_url || undefined, url, sameAs: [p.twitch && `https://twitch.tv/${p.twitch}`, p.instagram && `https://instagram.com/${p.instagram}`, p.tiktok && `https://tiktok.com/@${p.tiktok}`].filter(Boolean) } };
  return html
    .replaceAll('__CHANNEL__ — corillo', `${esc(nombre)} en Corillo`)
    .replaceAll('__CHANNEL__ en vivo en corillo — plataforma independiente desde Puerto Rico.', esc(desc))
    .replace('<h1 class="ch-name" id="chName"></h1>', `<h1 class="ch-name" id="chName">${esc(nombre)}</h1>`)
    .replace('</head>', `<script type="application/ld+json">${json(ld)}</script><script>window.__PERFIL__=${json(p)}</script></head>`);
}

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const directo = url.pathname.match(CANAL);
  const res = directo && CHOCAN.has(directo[1]) ? new Response(null, { status: 404 }) : await env.ASSETS.fetch(request);
  if (res.status !== 404) return res;

  const anuncio = url.pathname.match(/^(\/en)?\/mercado\/a\/[^/]+\/?$/);
  if (anuncio) return env.ASSETS.fetch(new URL(`${anuncio[1] || ''}/mercado/anuncio/`, url));

  const m = url.pathname.match(CANAL);
  if (!m) return res;
  if (!url.pathname.endsWith('/')) return Response.redirect(`${url.origin}${url.pathname}/${url.search}`, 301);
  const player = await env.ASSETS.fetch(new URL('/player/', url));
  const html = conPerfil(await player.text(), await perfil(m[1])).replaceAll('__CHANNEL__', m[1]);
  return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=60' } });
}
