/* Un evento suelto, para añadirlo a Apple Calendar, Outlook o cualquier otro. */
import { eventos, calendarioIcs, respuestaIcs } from '../../../data/eventos';

export function getStaticPaths() { return eventos().map(e => ({ params: { slug: e.slug }, props: { e } })); }
export async function GET({ props }) { return respuestaIcs(calendarioIcs([props.e], props.e.nombre)); }
