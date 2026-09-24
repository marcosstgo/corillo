// Sistema de traducciones del sitio (reutilizable fuera del Mercado).
//  - Diccionarios: src/i18n/<idioma>.json, agrupados por sección ("comun", "mercado", …).
//    Para traducir otra sección, añade su bloque en los dos JSON y usa t('seccion.clave').
//  - Español es el idioma principal y la red de seguridad: si falta una clave en inglés, sale en español.
//  - Rutas: español sin prefijo (/mercado/), inglés bajo /en/ (/en/mercado/). ruta() y alternos() lo resuelven.
//  - En el navegador: <I18nCliente secciones={[...]}> deja el diccionario en window.I18N y
//    /assets/i18n.js expone window.t() con la misma sintaxis.
import es from './es.json';
import en from './en.json';

export type Lang = 'es' | 'en';
export const IDIOMAS: Lang[] = ['es', 'en'];
export const DICC: Record<Lang, any> = { es, en };
const SITIO = 'https://corillo.live';

function buscar(d: any, clave: string): any {
  return clave.split('.').reduce((o, k) => (o == null ? undefined : o[k]), d);
}

/** t('mercado.vender') · t('mercado.hoy_hay', { n: 3 }) · plurales: claves con _uno / _otros y var n. */
export function traductor(lang: Lang) {
  return function t(clave: string, vars: Record<string, string | number> = {}): string {
    let v = buscar(DICC[lang], clave) ?? buscar(DICC.es, clave);
    if (v && typeof v === 'object' && 'n' in vars) v = Number(vars.n) === 1 ? v.uno : v.otros;
    if (typeof v !== 'string') return clave;
    return v.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
  };
}

/** Ruta en el idioma dado: ruta('en', '/mercado/') → '/en/mercado/'. */
export const ruta = (lang: Lang, path: string) => (lang === 'es' ? path : `/${lang}${path}`);

/** Enlaces hreflang para SiteShell (incluye x-default = español). */
export const alternos = (path: string) => [
  ...IDIOMAS.map(l => ({ lang: l === 'es' ? 'es-PR' : 'en', href: SITIO + ruta(l, path) })),
  { lang: 'x-default', href: SITIO + path },
];

/** Sección(es) del diccionario para mandar al navegador. */
export const paraCliente = (lang: Lang, secciones: string[]) =>
  Object.fromEntries(secciones.map(s => [s, { ...DICC.es[s], ...DICC[lang][s] }]));
