/**
 * Acceso al grafo de conocimiento (public/data/knowledge-graph.json) y
 * cálculo de los mini-mapas que se pintan en el boletín y en la ficha de
 * repositorio.
 *
 * Los mini-mapas NO son un force-graph: son un layout radial/por capas
 * DETERMINISTA calculado en build. Es a propósito — el mapa del día tiene
 * que salir idéntico en cada build y no puede depender de una simulación
 * física que converge distinto cada vez.
 */
import graphJson from '../../public/data/knowledge-graph.json';
import { colorForType, DEFAULT_TYPE_COLOR } from './graph-tokens';

export interface Aparicion {
  date: string;
  titulo?: string;
  seccion?: string;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  degree?: number;
  description?: string;
  resumen?: string;
  stars?: number;
  lang?: string;
  synthetic?: boolean;
  apariciones?: Aparicion[];
  menciones?: string[];
}

export interface GraphLink {
  source: string;
  target: string;
  rel: string;
  added?: string;
  note?: string;
}

const graph = graphJson as unknown as {
  generated_at?: string;
  node_count: number;
  link_count: number;
  nodes: GraphNode[];
  links: GraphLink[];
};

export const nodes: GraphNode[] = graph.nodes;
export const links: GraphLink[] = graph.links;
export const generatedAt = graph.generated_at ?? null;
export const nodeCount = graph.node_count ?? nodes.length;
export const linkCount = graph.link_count ?? links.length;

export const byId = new Map(nodes.map((n) => [n.id, n]));

export interface Neighbor {
  rel: string;
  dir: 'out' | 'in';
  other: GraphNode;
  otherId: string;
  added?: string;
  note?: string;
}

const neighborIndex = new Map<string, Neighbor[]>();
for (const l of links) {
  const push = (from: string, to: string, dir: 'out' | 'in') => {
    if (!neighborIndex.has(from)) neighborIndex.set(from, []);
    const other = byId.get(to);
    if (!other) return;
    neighborIndex.get(from)!.push({ rel: l.rel, dir, other, otherId: to, added: l.added, note: l.note });
  };
  push(l.source, l.target, 'out');
  push(l.target, l.source, 'in');
}

export function neighbors(id: string): Neighbor[] {
  return neighborIndex.get(id) ?? [];
}

export function getNode(id: string): GraphNode | undefined {
  return byId.get(id);
}

export const typeCounts: Record<string, number> = nodes.reduce<Record<string, number>>((acc, n) => {
  acc[n.type] = (acc[n.type] ?? 0) + 1;
  return acc;
}, {});

export const relCounts: Record<string, number> = links.reduce<Record<string, number>>((acc, l) => {
  acc[l.rel] = (acc[l.rel] ?? 0) + 1;
  return acc;
}, {});

// Etiquetas y colores viven en `graph-tokens.ts` (sin el JSON de datos) para
// que el explorador 3D pueda importarlos desde su script de cliente sin
// arrastrar los 300 KB del grafo al bundle. Se reexportan aquí para que el
// resto del código servidor tenga una sola puerta de entrada.
export {
  TYPE_LABEL, TYPE_COLOR, DEFAULT_TYPE_COLOR, colorForType, REL_LABEL, SECCION_LABEL,
} from './graph-tokens';

/* ------------------------------------------------------------------ *
 * Layouts deterministas para los mini-mapas
 * ------------------------------------------------------------------ */

export interface PlacedNode {
  id: string;
  label: string;
  type: string;
  color: string;
  x: number;
  y: number;
  /** Radio del punto en px. El hub es siempre el mayor. */
  r: number;
  hub?: boolean;
  /** true si el nodo ya existía en boletines anteriores (se pinta apagado). */
  previo?: boolean;
}

export interface PlacedEdge {
  x1: number; y1: number; x2: number; y2: number;
  /** `weak` son aristas de contexto entre satélites, no del hub. */
  weak?: boolean;
}

export interface MiniMap {
  width: number;
  height: number;
  nodes: PlacedNode[];
  edges: PlacedEdge[];
}

/**
 * Layout radial: un hub en el centro y el resto repartidos en un anillo,
 * empezando arriba a la izquierda y alternando lados para que las
 * etiquetas (que se pintan bajo el punto) no se pisen entre sí.
 */
export function radialLayout(
  hub: { id: string; label: string; type: string; previo?: boolean },
  satellites: { id: string; label: string; type: string; previo?: boolean }[],
  opts: { width: number; height: number; radius?: number; edges?: { a: string; b: string; weak?: boolean }[] }
): MiniMap {
  const { width, height } = opts;
  const cx = width / 2;
  const cy = height / 2;
  const radius = opts.radius ?? Math.min(width, height) * 0.42;

  const placed: PlacedNode[] = [
    {
      id: hub.id, label: hub.label, type: hub.type, color: colorForType(hub.type),
      x: cx, y: cy, r: 8, hub: true, previo: hub.previo,
    },
  ];

  const n = satellites.length;
  satellites.forEach((s, i) => {
    // Se arranca en -135° y se reparte el círculo completo; con pocos
    // satélites eso deja el hueco inferior libre para la leyenda.
    const angle = (-135 + (360 / Math.max(n, 1)) * i) * (Math.PI / 180);
    // Anillo ligeramente achatado en vertical; en horizontal se queda a
    // 0.88·radio para que las etiquetas (centradas bajo el punto) no se
    // corten contra los bordes de la tarjeta.
    placed.push({
      id: s.id, label: s.label, type: s.type,
      color: s.previo ? DEFAULT_TYPE_COLOR : colorForType(s.type),
      x: Math.round(cx + Math.cos(angle) * radius * 0.88),
      y: Math.round(cy + Math.sin(angle) * radius * 0.86),
      r: s.previo ? 3.5 : Math.max(4.5, 6.5 - i * 0.3),
      previo: s.previo,
    });
  });

  // Solo se dibujan las aristas que existen de verdad en los datos: un nodo
  // del día sin relación con el hub queda suelto en el anillo, y eso es
  // información (es un hallazgo todavía no conectado), no un fallo de layout.
  const pos = new Map(placed.map((p) => [p.id, p]));
  const edges: PlacedEdge[] = [];
  for (const e of opts.edges ?? []) {
    const a = pos.get(e.a);
    const b = pos.get(e.b);
    if (a && b) edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, weak: e.weak });
  }

  return { width, height, nodes: placed, edges };
}

/**
 * Layout por capas: el sujeto a la izquierda, sus relaciones directas en el
 * centro y los vecinos de segundo grado a la derecha. Es el mapa de
 * "posición en el ecosistema" de la ficha de repositorio.
 */
export interface LayeredEntry {
  id: string;
  label: string;
  type: string;
  rel: string;
  dir: 'out' | 'in';
  second: { id: string; label: string; type: string }[];
}

export function layeredNeighbors(id: string, opts: { max?: number; maxSecond?: number } = {}): LayeredEntry[] {
  const max = opts.max ?? 3;
  const maxSecond = opts.maxSecond ?? 1;
  const seen = new Set<string>([id]);
  const direct = neighbors(id)
    .filter((n) => {
      if (seen.has(n.otherId)) return false;
      seen.add(n.otherId);
      return true;
    })
    // Conceptos primero: dicen QUÉ es esto, que es lo que interesa al
    // lector antes de con quién compite.
    .sort((a, b) => {
      const rank = (t: string) => (t === 'concept' ? 0 : t === 'repo' ? 1 : 2);
      return rank(a.other.type) - rank(b.other.type) || (b.other.degree ?? 0) - (a.other.degree ?? 0);
    })
    .slice(0, max);

  return direct.map((n) => ({
    id: n.otherId,
    label: n.other.name,
    type: n.other.type,
    rel: n.rel,
    dir: n.dir,
    second: neighbors(n.otherId)
      .filter((s) => !seen.has(s.otherId))
      .sort((a, b) => (b.other.degree ?? 0) - (a.other.degree ?? 0))
      .slice(0, maxSecond)
      .map((s) => {
        seen.add(s.otherId);
        return { id: s.otherId, label: s.other.name, type: s.other.type };
      }),
  }));
}

/**
 * Fechas en las que un nodo ha aparecido en un boletín, ordenadas. Es lo
 * que alimenta la barra de "cómo creció este nodo".
 */
export function nodeTimeline(id: string): string[] {
  const n = byId.get(id);
  if (!n) return [];
  const dates = new Set<string>();
  for (const a of n.apariciones ?? []) if (a.date) dates.add(a.date);
  for (const d of n.menciones ?? []) if (d) dates.add(d);
  return [...dates].sort();
}
