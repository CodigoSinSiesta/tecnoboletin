/**
 * Render de markdown a HTML para los campos de texto libre que vienen de los
 * JSON de enriquecido/editorial (resumen_ejecutivo, posicionamiento,
 * convergencia_stack_css, cruzado_grafo, tendencias_5_boletines, alertas,
 * que_es, por_que_importa, accion_sugerida, resumen de boletin, etc.).
 *
 * Antes se pintaban tal cual con whitespace-pre-wrap: los asteriscos de
 * negrita y los backticks de codigo se veian literales en pantalla.
 *
 * Estos JSON los genera nuestra propia pipeline LLM local (no es input de
 * usuario externo), pero aun asi se usa `marked` en su configuracion segura
 * por defecto -- sin activar ninguna opcion que permita HTML crudo
 * adicional al que ya forma parte del propio markdown/CommonMark.
 */
import { marked } from 'marked';

marked.setOptions({
  gfm: true,
});

/**
 * Render de bloque: parrafos, listas, etc. Usar dentro de un contenedor que
 * NO sea <p> (p.ej. <div>), porque el HTML resultante puede incluir sus
 * propios <p>/<ul>/<ol> y anidar <p> dentro de <p> es HTML invalido.
 */
export function mdBlock(text: string | undefined | null): string {
  if (!text) return '';
  return marked.parse(text, { async: false }) as string;
}

/**
 * Render solo inline: negrita, code, enlaces, cursiva -- sin envolver el
 * resultado en <p>. Pensado para usarse dentro de un <p>/<li>/<span> propio,
 * en textos de una sola linea/parrafo (que_es, por_que_importa, alertas,
 * excerpts truncados).
 */
export function mdInline(text: string | undefined | null): string {
  if (!text) return '';
  return marked.parseInline(text, { async: false }) as string;
}
