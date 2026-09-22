// Equipo recomendado (/equipo/): lista curada a mano por Marcos, con enlaces de afiliado de Amazon.
// A diferencia de /ofertas/ (que se scrapea sola cada hora), esto no tiene precio en vivo: Amazon
// no nos deja consultar precios/imágenes por API hasta tener las primeras 3 ventas del programa
// de Associates. Cuando esa API se habilite, esto se puede migrar a datos automáticos igual que ofertas.

const TAG = 'corillolive-20';

export function withTag(url: string): string {
  try {
    const u = new URL(url);
    u.searchParams.set('tag', TAG);
    return u.toString();
  } catch {
    return url;
  }
}

export interface EquipoItem {
  id: string;
  title: string;
  category: string;
  why: string;
  url: string;
  image: string;
}

// Las imágenes se sacaron a mano de cada página de producto (campo data-old-hires, la foto
// principal en alta resolución que usa el propio Amazon) y se verificó que cada una carga
// (HTTP 200, content-type imagen) antes de publicarla. Ninguna es genérica ni inventada.
export const ITEMS: EquipoItem[] = [
  { id: 'webcam-c920s', category: 'Webcam (entrada)', title: 'Logitech C920S HD Pro Webcam',
    why: 'El estándar que todo el mundo busca: plug-and-play, 1080p30, audio estéreo claro.',
    url: 'https://www.amazon.com/Logitech-C920S-Pro-HD-Webcam/dp/B07K986YLL',
    image: 'https://m.media-amazon.com/images/I/61-6uAf8soL._AC_SL1500_.jpg' },
  { id: 'webcam-facecam-mk2', category: 'Webcam (calidad)', title: 'Elgato Facecam MK.2',
    why: 'El upgrade natural cuando ya tenés un setup serio: sensor Sony, HDR, controles tipo DSLR.',
    url: 'https://www.amazon.com/Elgato-Facecam-MK-2-Streaming-Recording/dp/B0CW1S7XP5',
    image: 'https://m.media-amazon.com/images/I/61J7cBOVGWL._AC_SL1500_.jpg' },
  { id: 'mic-blue-yeti', category: 'Micrófono (el más vendido)', title: 'Blue Yeti USB',
    why: 'El micrófono USB más buscado para streaming y podcasting: plug-and-play, 4 patrones de captación.',
    url: 'https://www.amazon.com/Blue-Microphones-Yeti-Microphone-Blackout/dp/B00N1YPXW2',
    image: 'https://m.media-amazon.com/images/I/61KTMvS5JBL._AC_SL1500_.jpg' },
  { id: 'mic-shure-mv7i', category: 'Micrófono (pro)', title: 'Shure MV7i',
    why: 'Interfaz de audio integrada, XLR y USB-C: para quien se toma el streaming o el podcast en serio.',
    url: 'https://www.amazon.com/Shure-Smart-Microphone-Built-Interface/dp/B0DNTZ22M5',
    image: 'https://m.media-amazon.com/images/I/81-fw2w0K3L._AC_SL1500_.jpg' },
  { id: 'capture-elgato-hd60s', category: 'Capture card', title: 'Elgato HD60 S+',
    why: 'La marca reina de captura: 1080p60 HDR10 o 4K60 HDR10 con latencia ultra baja.',
    url: 'https://www.amazon.com/Elgato-External-Capture-1080p60-ultra-low/dp/B07XB6VNLJ',
    image: 'https://m.media-amazon.com/images/I/51+P1sThIVL._AC_SL1000_.jpg' },
  { id: 'teclado-corsair-galleon', category: 'Teclado (streamer)', title: 'Corsair Galleon 100 SD',
    why: 'Stream Deck integrado en el teclado: un dispositivo menos en el escritorio.',
    url: 'https://www.amazon.com/Corsair-Galleon-Mechanical-Gaming-Keyboard/dp/B0G3PN1VS4',
    image: 'https://m.media-amazon.com/images/I/71+tkqze3FL._AC_SL1500_.jpg' },
  { id: 'teclado-aula-win68', category: 'Teclado (económico)', title: 'AULA WIN68 HE',
    why: 'La entrada más barata a switches Hall Effect (magnéticos), con actuación ajustable.',
    url: 'https://www.amazon.com/AULA-Mechanical-Keyboard-Adjustable-Actuation/dp/B0DT43NNNF',
    image: 'https://m.media-amazon.com/images/I/61uArG8glcL._AC_SL1500_.jpg' },
  { id: 'mouse-g305', category: 'Mouse (presupuesto)', title: 'Logitech G305 Lightspeed',
    why: 'Inalámbrico de verdad, sensor HERO, precio bajo: se vende solo por la relación precio/calidad.',
    url: 'https://www.amazon.com/Logitech-LIGHTSPEED-Wireless-Gaming-Mouse/dp/B07CMS5Q6P',
    image: 'https://m.media-amazon.com/images/I/51sg9BLSMTL._AC_SL1500_.jpg' },
  { id: 'headset-recon70', category: 'Headset (económico)', title: 'Turtle Beach Recon 70',
    why: 'Multiplataforma y barato: el "regalo seguro" para quien está empezando.',
    url: 'https://www.amazon.com/Turtle-Gaming-Headset-PlayStation-Nintendo-4/dp/B07NQX1J99',
    image: 'https://m.media-amazon.com/images/I/71vBFHa8cyL._AC_SL1500_.jpg' },
  { id: 'luz-newmowa', category: 'Iluminación', title: 'Newmowa 60 LED recargable',
    why: 'La luz clip que se volvió viral en TikTok: barata, recargable, mejora la cámara de cualquier setup.',
    url: 'https://www.amazon.com/Newmowa-Rechargeable-Adjusted-Android-Conference/dp/B08BCH841V',
    image: 'https://m.media-amazon.com/images/I/61ey6xjyElL._AC_SL1500_.jpg' },
  { id: 'brazo-neewer', category: 'Accesorio', title: 'Brazo articulado NEEWER para micrófono',
    why: 'Libera el escritorio y mejora el ángulo del mic; compatible con Blue Yeti y la mayoría de condensadores.',
    url: 'https://www.amazon.com/NEEWER-Articulating-Management-Microphone-MST002/dp/B0DTTMSFMY',
    image: 'https://m.media-amazon.com/images/I/51VlxbZOZZL._AC_SL1500_.jpg' },
  { id: 'filtro-pop-neewer', category: 'Accesorio', title: 'Filtro anti-pop NEEWER',
    why: 'Elimina los golpes de aire de las "p" y "b"; barato y hace una diferencia real en el audio.',
    url: 'https://www.amazon.com/Neewer-Studio-Microphone-Filter-Shield/dp/B00ACFAULC',
    image: 'https://m.media-amazon.com/images/I/5100Z2AnzpL._AC_SL1500_.jpg' },
  { id: 'cable-hdmi-ugreen', category: 'Accesorio', title: 'Cable HDMI 2.1 8K UGREEN',
    why: 'Hace falta para capturar 4K/120 u 8K de consolas nuevas; muchos setups fallan por usar un cable viejo.',
    url: 'https://www.amazon.com/UGREEN-Certified-Aluminum-Compatible-Blu-ray/dp/B0CFFFSFFN',
    image: 'https://m.media-amazon.com/images/I/71zjZ-AM8ZL._AC_SL1500_.jpg' },
  { id: 'hub-anker', category: 'Accesorio', title: 'Hub USB-C Anker 8-en-1',
    why: 'Para conectar capture card, webcam, mic y más sin quedarte sin puertos.',
    url: 'https://www.amazon.com/Anker-PowerExpand-Adapter-Delivery-Ethernet/dp/B087QZVQJX',
    image: 'https://m.media-amazon.com/images/I/71zuiK5poRL._AC_SL1500_.jpg' },
];

export const byId = (id: string) => ITEMS.find(i => i.id === id)!;

export interface Guia { slug: string; title: string; blurb: string; itemIds: string[]; }
export const GUIAS: Guia[] = [
  { slug: 'setup-del-novato', title: 'El setup del novato (menos de $200)',
    blurb: 'Lo mínimo para empezar a transmitir con buena imagen y audio, sin gastar de más.',
    itemIds: ['webcam-c920s', 'mic-blue-yeti', 'luz-newmowa'] },
  { slug: 'streamer-serio', title: 'El upgrade del streamer serio',
    blurb: 'Cuando ya transmitís seguido y querés que se note: mejor cámara, mejor audio, control desde el teclado.',
    itemIds: ['webcam-facecam-mk2', 'mic-shure-mv7i', 'teclado-corsair-galleon'] },
  { slug: 'nadie-menciona', title: 'Accesorios que nadie menciona',
    blurb: 'Lo que separa un setup que se ve bien de uno que se ve profesional, y que casi nadie recomienda de entrada.',
    itemIds: ['brazo-neewer', 'filtro-pop-neewer', 'cable-hdmi-ugreen', 'hub-anker'] },
];
