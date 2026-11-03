/* «Lo último de cada uno» en /streamers/: el video más reciente de cada streamer. Lo usan el build (para que salga en el
   HTML) y el navegador (para que un video nuevo aparezca sin esperar la próxima publicación).
   Pruebas: node --test src/data/videos-canal.test.mjs */
import { cuando } from './vitrina.js';

export const MAX_VIDEOS = 6;
const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ms = v => new Date(String(v.date).replace(' ', 'T')).getTime() || 0;
const duracion = s => {
  const t = Math.max(0, Math.round(s || 0)), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), x = t % 60;
  return t ? `${h ? `${h}:${String(m).padStart(2, '0')}` : m}:${String(x).padStart(2, '0')}` : '';
};

/** Uno por canal, de lo más nuevo a lo más viejo. Sin portada no entra: la tarjeta es la imagen. */
export function ultimoDeCada(videos, max = MAX_VIDEOS) {
  const vistos = new Set();
  return [...videos].sort((a, b) => ms(b) - ms(a)).filter(v => v.thumb && v.channel && !vistos.has(v.channel) && vistos.add(v.channel)).slice(0, max);
}

/** @param {object} v video de PocketBase  @param {object} [s] streamer de ese canal */
export function tarjetaVideo(v, s = {}) {
  const nombre = s.name || v.channel;
  const dur = duracion(v.duration);
  const cara = s.avatar_url ? `<img src="${esc(s.avatar_url)}" alt="" loading="lazy" onerror="this.remove()">` : esc((s.ava || nombre[0] || '').toString().toUpperCase());
  const titulo = v.title || `Video de ${nombre}`;
  return `<a class="sr-vd" href="/vods/v/?id=${encodeURIComponent(v.id)}" data-canal="${esc(v.channel)}"${v.preview ? ` data-preview="${esc(v.preview)}"` : ''}>
    <span class="sr-vd-pic"><img src="${esc(v.thumb)}" alt="" width="640" height="360" loading="lazy" decoding="async">
      <span class="sr-vd-play" aria-hidden="true"><i class="fa-solid fa-play"></i></span>${dur ? `<span class="sr-vd-dur">${dur}</span>` : ''}</span>
    <span class="sr-vd-txt"><span class="sr-vd-face" style="background:${esc(s.color || '#1e3a4a')}">${cara}</span>
      <span class="sr-vd-t"><strong>${esc(titulo)}</strong><small>${esc(nombre)} · <span data-rel="${ms(v)}">${esc(cuando(ms(v)))}</span></small></span></span>
  </a>`;
}
