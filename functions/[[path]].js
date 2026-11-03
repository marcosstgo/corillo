// Cloudflare Pages Function: lo que en el server viejo hacía nginx (corillo-infra/nginx/nginx.conf).
// Solo corre para las rutas que NO están en dist/ (ver scripts/pages-routes.mjs → dist/_routes.json):
//   /<canal>/          → la página del player con __CHANNEL__ reemplazado (antes: nginx sub_filter)
//   /mercado/a/<id>/   → anuncio recién publicado que aún no tiene página estática (lo muestra desde la API)
//   /vods/v/?id=<id>   → la página del video, con su título y portada para WhatsApp, redes y Google
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

// Título, portada y datos de un video en el HTML: quien comparte el enlace ve el video, no un texto genérico.
async function datosVideo(id) {
  const opciones = { signal: AbortSignal.timeout(1500), cf: { cacheTtl: 60 } };
  try {
    const r = await fetch(`https://pb.corillo.live/api/collections/vods/records/${id}?fields=id,channel,title,thumb,duration,date,filename`, opciones);
    if (!r.ok) return null;
    const vod = await r.json();
    let autor = null;
    try { const p = await fetch(`https://api.corillo.live/api/profile/${encodeURIComponent(vod.channel)}`, opciones); if (p.ok) autor = await p.json(); } catch {}
    return { vod, autor };
  } catch { return null; }
}
const duracion = s => { const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = Math.floor(s % 60); return `${h ? `${h}:${String(m).padStart(2, '0')}` : m}:${String(x).padStart(2, '0')}`; };
export function conVideo(html, { vod, autor }) {
  const nombre = (autor && (autor.name || autor.display_name)) || vod.channel;
  const fecha = new Date(String(vod.date).replace(' ', 'T'));
  const hayFecha = !isNaN(fecha);
  const dia = hayFecha ? fecha.toLocaleDateString('es-PR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Puerto_Rico' }) : '';
  const seg = Math.max(0, Math.round(vod.duration || 0));
  const titulo = vod.title || `Video de ${nombre}`;
  const encabezado = vod.title ? `${vod.title} — ${nombre}` : titulo;
  const desc = [`Video de ${nombre} en Corillo`, dia, seg ? duracion(seg) : ''].filter(Boolean).join(' · ');
  const url = `https://corillo.live/vods/v/?id=${vod.id}`;
  const portada = /^https:\/\/vods\.corillo\.live\//.test(vod.thumb || '') ? vod.thumb : '';
  const fijar = (h, atributo, nombreMeta, valor) => h.replace(new RegExp(`(<meta ${atributo}="${nombreMeta}" content=")[^"]*(")`), (_m, a, b) => a + esc(valor) + b);
  let h = html
    .replace(/<title>[^<]*<\/title>/, () => `<title>${esc(`${encabezado} | Corillo`)}</title>`)
    .replace(/(<link rel="canonical" href=")[^"]*(")/, (_m, a, b) => a + esc(url) + b);
  h = fijar(h, 'name', 'description', desc);
  for (const [a, n, v] of [['property', 'og:type', 'video.other'], ['property', 'og:url', url], ['property', 'og:title', encabezado], ['property', 'og:description', desc],
    ['name', 'twitter:url', url], ['name', 'twitter:title', encabezado], ['name', 'twitter:description', desc]]) h = fijar(h, a, n, v);
  if (portada) {
    for (const [a, n, v] of [['property', 'og:image', portada], ['property', 'og:image:width', '1920'], ['property', 'og:image:height', '1080'], ['name', 'twitter:image', portada]]) h = fijar(h, a, n, v);
  }
  const ld = { '@context': 'https://schema.org', '@type': 'VideoObject', name: titulo, description: desc, url, thumbnailUrl: portada ? [portada] : undefined,
    uploadDate: hayFecha ? fecha.toISOString() : undefined, duration: seg ? `PT${Math.floor(seg / 60)}M${seg % 60}S` : undefined,
    contentUrl: vod.filename ? `https://vods.corillo.live/${encodeURIComponent(vod.channel)}/${encodeURIComponent(vod.filename)}` : undefined,
    author: { '@type': 'Person', name: nombre, url: `https://corillo.live/${encodeURIComponent(vod.channel)}/` } };
  return h.replace('</head>', () => `<script type="application/ld+json">${json(ld)}</script></head>`);
}

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  if (url.pathname === '/vods/v/') {
    const pagina = await env.ASSETS.fetch(request);
    const id = url.searchParams.get('id') || '';
    const datos = pagina.ok && /^[a-z0-9]{5,30}$/.test(id) ? await datosVideo(id) : null;
    if (!datos) return pagina;
    const cabeceras = new Headers(pagina.headers);
    cabeceras.set('cache-control', 'public, max-age=60');
    cabeceras.delete('content-length'); cabeceras.delete('etag');
    return new Response(conVideo(await pagina.text(), datos), { status: 200, headers: cabeceras });
  }
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
