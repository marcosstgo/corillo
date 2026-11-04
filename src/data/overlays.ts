// Catálogo de overlays para OBS. Sale en el HTML de las páginas /overlay/ para que Google lo lea.
// Los overlays viven en el repo corillo-bf6-overlays y se copian a /overlay/ al publicar; aquí solo sus tamaños y textos.
export const BF6_GRUPOS = [
  { g: 'Compactos, 380 px de ancho', items: [
    { id: 'overlay', n: 'Stats', d: 'K/D, kills, win rate, KPM y DPM', w: 380, h: 240, ic: 'chart-simple', c: 'var(--ov-sol)' },
    { id: 'weapons', n: 'Armas', d: 'Tus 5 mejores armas con barras y % de headshots', w: 380, h: 300, ic: 'gun', c: 'var(--ov-acento)' },
    { id: 'classes', n: 'Clases', d: 'Kills, K/D y KPM por clase', w: 380, h: 260, ic: 'user-shield', c: 'var(--ov-menta)' },
    { id: 'accuracy', n: 'Precisión', d: 'Precisión, headshots, ADS y hipfire', w: 380, h: 280, ic: 'bullseye', c: 'var(--ov-sol)' },
    { id: 'objective', n: 'Objetivo', d: 'Capturas, tiempo en objetivo, revives y asistencias', w: 380, h: 280, ic: 'flag', c: 'var(--ov-vivo)' },
    { id: 'session', n: 'Sesión', d: 'Kills y K/D desde que abriste OBS', w: 380, h: 275, ic: 'stopwatch', c: 'var(--ov-menta)' },
    { id: 'season', n: 'Temporada', d: 'K/D, win% y clase favorita, con datos oficiales de EA', w: 380, h: 225, ic: 'trophy', c: 'var(--ov-sol)', ea: true },
    { id: 'recent', n: 'Forma reciente', d: 'K/D de tus últimas 5 partidas', w: 380, h: 275, ic: 'fire', c: 'var(--ov-acento)' },
  ] },
  { g: 'Pantalla completa', items: [
    { id: 'lowerthird', n: 'Barra inferior', d: 'Barra con 5 bloques que rotan', w: 1920, h: 80, ic: 'grip-lines', c: 'var(--ov-acento)' },
    { id: 'dashboard', n: 'Panel completo', d: 'Combate, precisión, objetivo, armas y sesión', w: 1920, h: 1080, ic: 'table-columns', c: 'var(--ov-menta)' },
  ] },
  { g: 'Escuadrón', items: [
    { id: 'multi', n: 'Multijugador', d: 'Stats lado a lado de 2 a 4 jugadores', w: 548, h: 260, ic: 'people-group', c: 'var(--ov-sol)', multi: true },
  ] },
];

export const WD_SIN_USUARIO = [
  { id: 'pulse', file: 'pulse.html', n: 'Jugadores en vivo', d: 'Cuántos juegan WARDOGS ahora mismo, con el récord y la tendencia de la última media hora.', w: 380, h: 210 },
  { id: 'community', file: 'community.html', n: 'Comunidad', d: 'El porcentaje de reseñas positivas en Steam, los jugadores conectados y el precio.', w: 380, h: 225, resenas: true },
  { id: 'comm-es', file: 'community.html', q: '?lang=es', n: 'Comunidad en español', d: 'Solo las reseñas escritas en español. Suelen ser más positivas que el total.', w: 380, h: 225, resenas: true },
  { id: 'ach-game', file: 'achievements.html', n: 'Logros del juego', d: 'Los logros del juego con el porcentaje de jugadores que ya tiene cada uno.', w: 380, h: 395, llave: true },
];
export const WD_CON_PERFIL = [
  { id: 'profile', file: 'profile.html', n: 'Tu perfil', d: 'Tus horas, tus logros y una señal de «Jugando» cuando estás en partida.', w: 380, h: 260, steam: true, llave: true },
  { id: 'ach-mine', file: 'achievements.html', n: 'Tus logros', d: 'Los que ya tienes a color y los pendientes en gris, con su rareza.', w: 380, h: 400, steam: true, llave: true },
  { id: 'steamcard', file: 'steam.html', n: 'Tarjeta de Steam', d: 'Tu nivel y tu XP, cuánto tiempo llevas en Steam, tus juegos y tus horas totales.', w: 380, h: 262, steam: true, llave: true },
  { id: 'alert', file: 'alert.html', n: 'Alerta de logro', d: 'Aparece sola en tu pantalla cuando desbloqueas un logro, con su rareza. La vista previa repite un ejemplo.', w: 480, h: 130, steam: true, llave: true, prevQ: '?test=1' },
  { id: 'lower', file: 'lowerthird.html', n: 'Barra inferior', d: 'Una barra de pantalla completa que rota tu jugador, tus logros y el juego en vivo.', w: 1920, h: 80, steam: true, llave: true, wide: true },
];
