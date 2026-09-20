// Línea editorial de Noticias: 5 áreas + plataforma. Una sola definición para listado, notas, RSS y el redactor automático.
export interface Cat { id: string; label: string; icon: string; color: string; blurb: string }
export const CATEGORIES: Cat[] = [
  { id: 'gaming',    label: 'Gaming y esports',        icon: 'fa-gamepad',            color: 'var(--h2-cyan, #ff6a3d)', blurb: 'Lanzamientos, torneos y lo que se está jugando.' },
  { id: 'tech',      label: 'Tecnología e IA',         icon: 'fa-microchip',          color: 'var(--h2-mag, #ffd23f)',  blurb: 'Hardware, software e inteligencia artificial que importa a creadores y gamers.' },
  { id: 'streaming', label: 'Streaming y creadores',   icon: 'fa-tower-broadcast',    color: 'var(--crl-confirm, #35e0a1)', blurb: 'Plataformas, herramientas y cambios que afectan a quien transmite.' },
  { id: 'geek',      label: 'Cultura geek',            icon: 'fa-wand-magic-sparkles', color: '#8b95ff',                blurb: 'Cine, series, anime, cómics y entretenimiento.' },
  { id: 'pr',        label: 'Puerto Rico',             icon: 'fa-flag',               color: '#7aa2ff',                blurb: 'Lo que pasa en la isla en estas áreas.' },
  { id: 'corillo',   label: 'Plataforma',              icon: 'fa-bolt',               color: 'var(--h2-live, #ff2d55)', blurb: 'Novedades de CORILLO.' },
];
const BY_ID = Object.fromEntries(CATEGORIES.map(c => [c.id, c]));
/** Categoría de una nota: la del frontmatter; en las notas viejas se infiere de la etiqueta. */
export function catOf(data: { category?: string; badgeLabel?: string }): Cat {
  if (data.category && BY_ID[data.category]) return BY_ID[data.category];
  const l = (data.badgeLabel || '').toLowerCase();
  if (l.includes('gaming') || l.includes('juego')) return BY_ID.gaming;
  return BY_ID.corillo;
}
/** Minutos de lectura estimados (200 palabras/min). */
export function readMinutes(body: string | undefined): number {
  const words = (body || '').replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}
