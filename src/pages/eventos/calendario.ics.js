/* Todos los eventos para suscribirse desde el celular: el calendario se actualiza solo. */
import { eventos, calendarioIcs, respuestaIcs } from '../../data/eventos';

export async function GET() { return respuestaIcs(calendarioIcs(eventos(), 'Eventos de videojuegos en Puerto Rico · CORILLO')); }
