/**
 * Feed RSS del boletín diario. El README lo dejaba como aspiración ("RSS
 * propia por fuente") pero ni siquiera existía un feed general — este es
 * ese feed base, uno por boletín publicado.
 */
import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { listDates, loadBoletin, titularYEntradilla } from '../lib/boletin';
import { mdBlock } from '../lib/markdown';

export async function GET(context: APIContext) {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  const dates = await listDates();
  const boletines = await Promise.all(dates.map((d) => loadBoletin(d)));

  return rss({
    title: 'Tecnoboletín',
    description: 'Lectura enriquecida de los boletines de Código Sin Siesta.',
    // `context.site` es el dominio raíz (codigosinsiesta.github.io), sin el
    // `base` de Astro (/tecnoboletin) — sin esto el <link> del canal del
    // feed apuntaría al blog principal, no a Tecnoboletín.
    site: new URL(base, context.site!),
    items: boletines.map((b) => {
      const { titular, entradilla } = titularYEntradilla(b.editorial);
      const [y, m, d] = b.date.split('-').map(Number);
      const resumen = b.enriched?.resumen_ejecutivo?.replace(/^[-*]\s*/, '') ?? null;
      const cuerpo = entradilla ?? resumen;

      return {
        title: titular ?? `Boletín enriquecido de Código Sin Siesta del ${b.date}`,
        pubDate: new Date(Date.UTC(y, m - 1, d)),
        description: cuerpo?.slice(0, 280),
        content: cuerpo ? mdBlock(cuerpo) : undefined,
        link: `${base}enriquecido/${b.date}/`,
      };
    }),
    customData: '<language>es</language>',
  });
}
