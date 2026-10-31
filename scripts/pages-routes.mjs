// Después del build: dist/_routes.json para Cloudflare Pages. La función (functions/[[path]].js) solo debe
// correr para canales (/<canal>/) y anuncios nuevos del Mercado; todo lo que ya existe en dist/ se sirve directo
// (así no gasta invocaciones: el plan gratis da 100,000 al día). Límite de Cloudflare: 100 reglas.
import fs from 'node:fs';

const PASAN = new Set(['mercado', 'en']);   // carpetas que también pueden necesitar la función
const exclude = [];
for (const e of fs.readdirSync('dist', { withFileTypes: true })) {
  if (e.name.startsWith('_routes') || e.name === '404.html' || PASAN.has(e.name)) continue;
  exclude.push(e.isDirectory() ? `/${e.name}/*` : `/${e.name}`);
}
// Sin barra final, /overlay caería en la función como si fuera el canal "overlay": se sirve directo y Pages redirige a /overlay/.
if (fs.existsSync('dist/overlay')) exclude.push('/overlay', '/overlay/bf6', '/overlay/wardogs');
exclude.push('/');
if (exclude.length > 99) throw new Error(`_routes.json: ${exclude.length} reglas, Cloudflare acepta 100`);
// Sin dist/404.html, Pages responde la portada (modo SPA) a cualquier ruta desconocida y la función nunca ve el 404.
if (fs.existsSync('dist/_404/index.html')) fs.copyFileSync('dist/_404/index.html', 'dist/404.html');
fs.writeFileSync('dist/_routes.json', JSON.stringify({ version: 1, include: ['/*'], exclude }, null, 2));
console.log(`_routes.json: ${exclude.length} rutas servidas directo, el resto pasa por la función`);
