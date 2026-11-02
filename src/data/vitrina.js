/* Reglas de la vitrina del inicio (el slider del hero). Una sola lógica: la usa el build y la usa el navegador.
   Pruebas: node --test src/data/vitrina.test.mjs

   1. Lo fechado (noticias y videos) va de lo más nuevo a lo más viejo, sin importar de qué tipo sea.
   2. Lo que no tiene fecha (juegos gratis, ofertas) acompaña: entra después de las dos publicaciones más nuevas y
      luego se alterna, para que nunca le pase por delante a algo recién publicado.
   3. Lo que llega tarde (los videos se piden al cargar) nunca interrumpe: lo que está en pantalla se queda donde está
      y lo demás se acomoda alrededor. Si lo nuevo es lo más reciente, sale en el próximo turno. */

const ZONA = 'America/Puerto_Rico';
const diaPR = new Intl.DateTimeFormat('en-CA', { timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit' });

/** @param {{fecha?: number}[]} slides */
export function ordenarVitrina(slides) {
  const fechados = slides.filter(s => s.fecha).sort((a, b) => b.fecha - a.fecha);
  const sinFecha = slides.filter(s => !s.fecha);
  const orden = fechados.slice(0, 2);
  const resto = fechados.slice(2);
  while (resto.length || sinFecha.length) {
    if (sinFecha.length) orden.push(sinFecha.shift());
    if (resto.length) orden.push(resto.shift());
  }
  return orden;
}

/** Deja `visible` en la posición `pos` y el resto en su orden, para no cortar lo que la persona está viendo. */
export function conservarVisible(orden, visible, pos) {
  const resto = orden.filter(x => x !== visible);
  if (!orden.includes(visible)) return resto;
  const i = Math.min(Math.max(pos, 0), resto.length);
  return [...resto.slice(0, i), visible, ...resto.slice(i)];
}

/** Hoy, Ayer o «31 de octubre», por el día del calendario en Puerto Rico (no por horas transcurridas). */
export function cuando(fechaMs, ahora = Date.now()) {
  const dia = t => { const [a, m, d] = diaPR.format(t).split('-').map(Number); return Date.UTC(a, m - 1, d) / 864e5; };
  const dias = dia(ahora) - dia(fechaMs);
  if (dias <= 0) return 'Hoy';
  if (dias === 1) return 'Ayer';
  return new Date(fechaMs).toLocaleDateString('es-PR', { day: 'numeric', month: 'long', timeZone: ZONA });
}

/** Falso solo si `hasta` es una fecha válida y ya pasó (un juego que dejó de estar gratis entre publicaciones). */
export function vigente(hasta, ahora = Date.now()) {
  const t = hasta ? new Date(hasta).getTime() : NaN;
  return Number.isNaN(t) || t > ahora;
}
