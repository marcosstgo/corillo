/* /bf6/ (10-nov-2026). Datos de scripts/update-bf6.py (anuncios oficiales, prensa, canales) y de bf6-comunidad.json,
   que se llena a mano: ahí solo entra lo que Marcos aprueba (en GitHub abundan "cheats" con virus). */
import datos from './bf6.json';
import comunidadJson from './bf6-comunidad.json';
import { todos } from './juegos';

export const APPID = 2807960;
export interface Anuncio { gid: string; fecha: string; titulo: string; resumen: string; titulo_original: string; url: string; imagen: string | null }
export interface Titular { titulo: string; medio: string; url: string; fecha: string }
export interface Video { id: string; titulo: string; vivo: boolean; directo: boolean }
export interface Canal { handle: string; nombre: string; id: string; pr?: boolean; url: string; en_vivo: string | null; videos: Video[] }
export interface Aporte { titulo: string; resumen: string; tipo: string; autor: string; url: string; video?: string; agregado: string }

export const actualizado: string = datos.actualizado;
export const anuncios = datos.noticias as Anuncio[];
export const prensa = datos.prensa as Titular[];
export const canales = datos.canales as Canal[];
export const comunidad = comunidadJson as Aporte[];
export const steam = () => todos().find(j => j.appid === APPID);

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
export const fechaMini = (iso: string) => { const [, m, d] = iso.split('-').map(Number); return `${d} ${MESES[m - 1]}`; };
// Lo que cuenta como "de Battlefield" en un título de Corillo (directos, videos y noticias).
export const ES_BF6 = /battlefield|\bbf6\b|redsec/i;
