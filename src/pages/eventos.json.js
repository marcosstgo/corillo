/* Lo que lee El Bochinchero: solo eventos confirmados. Lo demás se queda en la página, con su advertencia. */
import { eventos, actualizado } from '../data/eventos';

export async function GET() {
  const lista = eventos().filter(e => e.confirmado).map(({ slug, nombre, inicio, fin, lugar, municipio, web, voz_extra }) =>
    ({ slug, nombre, inicio, fin, lugar, municipio, web, voz_extra }));
  return new Response(JSON.stringify({ actualizado, eventos: lista }), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
