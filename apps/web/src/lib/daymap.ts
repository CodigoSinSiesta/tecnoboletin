/**
 * "Mapa del día": el subgrafo que el boletín de hoy añade o toca.
 *
 * Se construye SOLO con las relaciones que los items del día declaran
 * (`relacion_grafo`), no con el grafo entero: la pregunta que responde es
 * "¿qué mueve el boletín de hoy dentro del grafo?", y para eso 833 nodos
 * son ruido. El nodo central es el más conectado del día — normalmente el
 * concepto que hila los hallazgos.
 */
import type { BoletinItem, RelacionGrafo } from './boletin';
import { nodeLabel, nodeType } from './boletin';
import { radialLayout, getNode, type MiniMap } from './graph';

export interface DayMap {
  map: MiniMap;
  nodeTotal: number;
  relTotal: number;
  /** Conceptos que entran hoy por primera vez en el grafo. */
  conceptosNuevos: string[];
}

/** Relaciones utilizables del día (sin destinos truncados por el enriquecedor). */
export function dayRelations(items: BoletinItem[]): RelacionGrafo[] {
  return items
    .flatMap((it) => it.relacion_grafo ?? [])
    .filter((r) => r?.src && r?.dst && !r.dst.endsWith('/...') && !r.src.endsWith('/...'));
}

export function buildDayMap(items: BoletinItem[], opts: { width: number; height: number; max?: number }): DayMap | null {
  const rels = dayRelations(items);
  if (!rels.length) return null;

  const max = opts.max ?? 6;

  // Grado dentro del día, y si el nodo ya venía de boletines anteriores.
  const degree = new Map<string, number>();
  const previo = new Map<string, boolean>();
  for (const r of rels) {
    for (const id of [r.src, r.dst]) degree.set(id, (degree.get(id) ?? 0) + 1);
    // Un destino con `primera_mencion` ya se cubrió antes; si alguna de sus
    // relaciones es nueva, el nodo cuenta como nuevo.
    previo.set(r.dst, (previo.get(r.dst) ?? true) && Boolean(r.primera_mencion));
    previo.set(r.src, false); // el origen es siempre un item de hoy
  }

  const ids = [...degree.keys()];
  const rank = (id: string) =>
    degree.get(id)! * 10 + (id.startsWith('concept:') ? 5 : 0) + Math.min(getNode(id)?.degree ?? 0, 20) / 100;
  const sorted = ids.sort((a, b) => rank(b) - rank(a));

  const hubId = sorted[0];
  const satelliteIds = sorted.slice(1, 1 + max);
  const placedIds = new Set([hubId, ...satelliteIds]);

  const describe = (id: string) => ({
    id,
    label: nodeLabel(id),
    type: nodeType(id),
    previo: previo.get(id) ?? false,
  });

  const map = radialLayout(describe(hubId), satelliteIds.map(describe), {
    width: opts.width,
    height: opts.height,
    edges: rels
      .filter((r) => placedIds.has(r.src) && placedIds.has(r.dst))
      .map((r) => ({ a: r.src, b: r.dst, weak: r.src !== hubId && r.dst !== hubId })),
  });

  return {
    map,
    nodeTotal: ids.length,
    relTotal: rels.length,
    conceptosNuevos: [
      ...new Set(rels.filter((r) => !r.primera_mencion && r.dst.startsWith('concept:')).map((r) => nodeLabel(r.dst))),
    ],
  };
}
