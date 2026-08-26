/**
 * Etiquetas y colores del grafo, SIN el JSON de datos.
 *
 * Vive aparte de `lib/graph.ts` a propósito: el explorador 3D descarga
 * `public/data/knowledge-graph.json` en runtime (300 KB), así que su script
 * de cliente no puede importar el módulo que hace `import` del JSON —
 * acabaría empaquetado dentro del bundle además de descargado. Aquí solo
 * hay constantes, y las comparten servidor y cliente.
 */

export const TYPE_LABEL: Record<string, string> = {
  repo: 'Repositorio',
  concept: 'Concepto',
  company: 'Empresa',
  tool: 'Herramienta',
  framework: 'Framework',
  protocol: 'Protocolo',
  risk: 'Riesgo',
  problem: 'Problema',
  cluster: 'Cluster',
  skill: 'Skill',
  pattern: 'Patrón',
  license: 'Licencia',
  arxiv: 'Paper',
  article_angle: 'Ángulo editorial',
};

/**
 * Color por tipo de nodo. Toda la escala vive dentro del azul de marca
 * (repo -> concepto -> herramienta, de más claro a más profundo) salvo el
 * rojo de riesgo/problema, que es uno de los tres estados del sistema.
 * Antes cada tipo tenía un acento distinto (ámbar, violeta, verde, rosa) y
 * el grafo parecía un semáforo sin significado.
 */
export const TYPE_COLOR: Record<string, string> = {
  repo: '#60A5FA',
  concept: '#93C5FD',
  tool: '#1E3A8A',
  framework: '#1E3A8A',
  skill: '#1E3A8A',
  protocol: '#3B82F6',
  pattern: '#3B82F6',
  company: '#475569',
  cluster: '#475569',
  license: '#475569',
  arxiv: '#475569',
  article_angle: '#475569',
  risk: '#F87171',
  problem: '#F87171',
};

export const DEFAULT_TYPE_COLOR = '#475569';

export function colorForType(type: string): string {
  return TYPE_COLOR[type] ?? DEFAULT_TYPE_COLOR;
}

export const REL_LABEL: Record<string, string> = {
  competes_with: 'compite con',
  implements: 'implementa',
  complements: 'complementa',
  uses: 'usa',
  relevant_to: 'relevante para',
  enables: 'habilita',
  solves: 'resuelve',
  supports: 'da soporte a',
  developed_by: 'desarrollado por',
  integrates_with: 'se integra con',
  inspired_by: 'inspirado en',
  authored: 'autoría de',
  sibling_of: 'hermano de',
  evolves: 'evoluciona a',
  reveals: 'revela',
  forked_by: 'forkeado por',
  used_by: 'usado por',
};

export const SECCION_LABEL: Record<string, string> = {
  hallazgo_principal: 'hallazgo principal',
  radar_secundario: 'radar secundario',
  radar_secundario_recuperado: 'radar secundario (recuperado)',
};
