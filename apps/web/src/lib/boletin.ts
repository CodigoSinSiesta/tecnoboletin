/**
 * Lectura y normalización de los datos de un boletín enriquecido.
 *
 * Los JSON los genera la pipeline LLM local (scripts/enrich.py) y su forma
 * es estable, pero varios campos son TEXTO LIBRE con formato inconsistente
 * entre boletines. Todo lo que este módulo hace es extraer de ese texto
 * libre los datos estructurados que la interfaz necesita (estado de la
 * acción, estrellas, licencia, madurez…) sin inventarse nada: cuando un
 * dato no aparece, se devuelve `null` y la UI pinta "—".
 */
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

const DATA_DIR = path.join(process.cwd(), 'src', 'data', 'boletines');

export interface RelacionGrafo {
  src: string;
  rel: string;
  dst: string;
  primera_mencion?: string | null;
}

export interface BoletinItem {
  idx: number;
  titulo: string;
  url?: string;
  url_inferida?: boolean;
  seccion: 'hallazgo_principal' | 'radar_secundario' | string;
  contenido?: {
    que_es?: string;
    por_que_importa?: string;
    madurez_senales?: string;
    accion_sugerida?: string;
    descripcion_raw?: string;
  };
  relacion_grafo?: RelacionGrafo[];
  clasificacion?: {
    tipo?: string;
    idioma?: string;
    autor?: string | null;
    medio?: string | null;
    tema_principal?: string;
    temas_secundarios?: string[];
    confianza?: number;
  };
}

export interface Enriched {
  version?: number;
  date: string;
  boletin_origen?: string;
  resumen_ejecutivo?: string;
  items: BoletinItem[];
  stats?: Record<string, unknown>;
}

export interface Editorial {
  date?: string;
  posicionamiento?: string;
  convergencia_stack_css?: string;
  cruzado_grafo?: string;
  tendencias_5_boletines?: string;
  alertas?: string[];
  acciones_concretas?: { tipo: string; item_idx: number; razon: string }[];
}

export interface Boletin {
  date: string;
  enriched: Enriched | null;
  editorial: Editorial | null;
  edges: RelacionGrafo[];
  items: BoletinItem[];
  hallazgos: BoletinItem[];
  radar: BoletinItem[];
  /** idx de los items que editorial.acciones_concretas marca como "explora". */
  pickIdx: Set<number>;
}

// El build genera ~500 páginas y muchas de ellas necesitan los mismos
// boletines (el raíl de fechas del triaje los lee todos, las fichas de repo
// buscan en todo el histórico). Cachear en memoria durante el build baja
// eso de miles de lecturas de disco a una por fichero.
const dateCache: { value: string[] | null } = { value: null };
const boletinCache = new Map<string, Promise<Boletin>>();

/** Fechas de boletín disponibles, de más reciente a más antigua. */
export async function listDates(): Promise<string[]> {
  if (dateCache.value) return dateCache.value;
  const entries = await readdir(DATA_DIR, { withFileTypes: true });
  dateCache.value = entries
    .filter((e) => e.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(e.name))
    .map((e) => e.name)
    .sort()
    .reverse();
  return dateCache.value;
}

export async function latestDate(): Promise<string | null> {
  const dates = await listDates();
  return dates[0] ?? null;
}

async function readJson<T>(file: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(file, 'utf-8')) as T;
  } catch {
    return null;
  }
}

export function loadBoletin(date: string): Promise<Boletin> {
  let cached = boletinCache.get(date);
  if (!cached) {
    cached = readBoletin(date);
    boletinCache.set(date, cached);
  }
  return cached;
}

async function readBoletin(date: string): Promise<Boletin> {
  const dir = path.join(DATA_DIR, date);
  const enriched = await readJson<Enriched>(path.join(dir, 'enriched.json'));
  const editorial = await readJson<Editorial>(path.join(dir, 'editorial.json'));

  let edges: RelacionGrafo[] = [];
  try {
    edges = (await readFile(path.join(dir, 'edges.jsonl'), 'utf-8'))
      .split('\n')
      .filter(Boolean)
      .map((l) => JSON.parse(l));
  } catch {}

  const items = enriched?.items ?? [];
  return {
    date,
    enriched,
    editorial,
    edges,
    items,
    hallazgos: items.filter((it) => it.seccion === 'hallazgo_principal'),
    radar: items.filter((it) => it.seccion === 'radar_secundario'),
    pickIdx: new Set(
      (editorial?.acciones_concretas ?? [])
        .filter((a) => a.tipo === 'explora')
        .map((a) => a.item_idx)
    ),
  };
}

/* ------------------------------------------------------------------ *
 * Acción sugerida — texto libre -> estado
 *
 * `contenido.accion_sugerida` llega como "explorar -- ...", "**explorar**",
 * ": vigilar", "sugerida: probar -- ...", "**leer**." etc. Se limpia el
 * markdown y la puntuación de cabecera antes de leer el verbo, para que el
 * color de estado nunca dependa de cómo formateó el LLM esa línea.
 * ------------------------------------------------------------------ */

/** Los cuatro estados con los que se tria un item, más el descarte. */
export type Estado = 'explorar' | 'probar' | 'leer' | 'vigilar' | 'descartar';

/** Color semántico de cada estado. Ver la cabecera de global.css. */
export const ESTADO_TONE: Record<Estado, 'go' | 'warn' | 'read' | 'alert'> = {
  explorar: 'go',
  probar: 'go',
  leer: 'read',
  vigilar: 'warn',
  descartar: 'alert',
};

export function normalizeAccion(raw: string | undefined | null): string {
  let t = (raw ?? '').trim();
  t = t.replace(/^[*_~`\s:.-]+/, '');
  t = t.replace(/^sugerida\s*:?\s*/i, '');
  t = t.replace(/^[*_~`\s:.-]+/, '');
  return t;
}

/** Verbo crudo tal cual lo escribió el enriquecedor ("explorar", "leer"…). */
export function accionVerb(raw: string | undefined | null): string | null {
  const m = normalizeAccion(raw).match(/^[a-záéíóúñ]+/i);
  return m ? m[0].toLowerCase() : null;
}

/**
 * Estado del item. `null` cuando el enriquecedor no dejó un verbo
 * reconocible (119 de 480 items del histórico) — esos no se inventan: se
 * agrupan aparte como "sin acción sugerida".
 */
export function accionEstado(raw: string | undefined | null): Estado | null {
  const v = accionVerb(raw);
  if (!v) return null;
  if (v.startsWith('explor')) return 'explorar';
  if (v.startsWith('prob')) return 'probar';
  if (v.startsWith('leer') || v.startsWith('lee')) return 'leer';
  if (v.startsWith('vigil')) return 'vigilar';
  if (v.startsWith('ignor') || v.startsWith('descart')) return 'descartar';
  return null;
}

/** Resto del texto tras el verbo, sin duplicar el verbo que ya va en el badge. */
export function accionDetail(raw: string | undefined | null): string {
  let t = normalizeAccion(raw);
  const m = t.match(/^[a-záéíóúñ]+/i);
  if (m) t = t.slice(m[0].length);
  t = t.replace(/^[*_~`\s:.—-]+/, '');
  t = t.replace(/[*_~`\s]+$/, '');
  // El detalle casi siempre viene entre paréntesis: "(alpha con API
  // inestable; no se recomienda...)". Se quitan porque el badge ya hace de
  // apertura y el paréntesis suelto se ve como un error de render.
  const paren = t.match(/^\((.*)\)\.?$/s);
  if (paren) t = paren[1];
  return t.trim();
}

/* ------------------------------------------------------------------ *
 * madurez_senales — texto libre -> métricas
 *
 * Formatos vistos en el histórico, todos válidos:
 *   "**8.758★** · 1.320 forks · Python · creado 2026-06-11 · licencia **Apache-2.0**…"
 *   "⭐ 7,178 · 🍴 1,410 · JavaScript · 📅 2026-06-24 · 🔄 2026-06-27 · 📜 NOASSERTION"
 *   "10.556 estrellas, último push 2025-01-22, Python, sin licencia declarada"
 *   "3.599★, Apache-2.0, push 2026-07-19"
 * ------------------------------------------------------------------ */

export interface Senales {
  stars: number | null;
  forks: number | null;
  lang: string | null;
  license: string | null;
  issues: number | null;
  estado: string | null;
  creado: string | null;
  ultimoPush: string | null;
}

const LANGS = [
  'TypeScript', 'JavaScript', 'Jupyter Notebook', 'Objective-C', 'PowerShell', 'Dockerfile',
  'Makefile', 'Assembly', 'Clojure', 'Solidity', 'Markdown', 'Haskell', 'Kotlin', 'Elixir',
  'Erlang', 'Groovy', 'Verilog', 'OCaml', 'Scala', 'Svelte', 'Python', 'MATLAB', 'Batchfile',
  'Astro', 'Julia', 'Swift', 'Shell', 'Rust', 'Ruby', 'Java', 'Perl', 'Dart', 'Nix', 'Lua',
  'HTML', 'CSS', 'MDX', 'Vue', 'TeX', 'Zig', 'PHP', 'C++', 'C#', 'Go', 'R', 'C',
];

const LICENSES = [
  'Apache-2.0', 'AGPL-3.0', 'LGPL-3.0', 'LGPL-2.1', 'GPL-3.0', 'GPL-2.0', 'MPL-2.0',
  'BSD-3-Clause', 'BSD-2-Clause', 'Elastic-2.0', 'BSL-1.1', 'SSPL-1.0', 'EPL-2.0',
  'CC0-1.0', 'CC-BY-4.0', 'CC-BY-SA-4.0', 'Unlicense', 'NOASSERTION', 'MIT', 'ISC',
];

/** "33.364" / "7,178" / "57511" -> 33364 / 7178 / 57511 */
function parseNum(raw: string): number | null {
  const cleaned = raw.replace(/[.,](?=\d{3}\b)/g, '').replace(/[^\d]/g, '');
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

export function parseSenales(raw: string | undefined | null): Senales {
  const s = raw ?? '';
  const out: Senales = {
    stars: null, forks: null, lang: null, license: null,
    issues: null, estado: null, creado: null, ultimoPush: null,
  };
  if (!s) return out;

  // Ojo con \b: solo vale tras palabra ("estrellas"), nunca tras "★" —
  // "**8.758★**" pone un asterisco pegado al símbolo y ahí no hay boundary.
  const starMatch =
    s.match(/([\d][\d.,]*)\s*(?:★|⭐|estrellas?\b|stars?\b)/i) ??
    s.match(/(?:★|⭐)\s*([\d][\d.,]*)/);
  if (starMatch) out.stars = parseNum(starMatch[1]);

  const forkMatch =
    s.match(/([\d][\d.,]*)\s*forks?\b/i) ?? s.match(/🍴\s*([\d][\d.,]*)/);
  if (forkMatch) out.forks = parseNum(forkMatch[1]);

  const issueMatch = s.match(/([\d][\d.,]*)\s*issues?\b/i);
  if (issueMatch) out.issues = parseNum(issueMatch[1]);

  for (const l of LANGS) {
    // Delimitado por separadores, no por \b: "C" no debe capturar la C de
    // "Claude", y "Go" no debe capturar "Google".
    const re = new RegExp(`(^|[\\s·,(])${l.replace(/[+#.]/g, '\\$&')}([\\s·,).]|$)`, 'i');
    if (re.test(s)) { out.lang = l; break; }
  }

  for (const lic of LICENSES) {
    if (new RegExp(`\\b${lic.replace(/[.+]/g, '\\$&')}\\b`, 'i').test(s)) { out.license = lic; break; }
  }
  if (!out.license && /sin licencia|licencia no declarada|no license/i.test(s)) {
    out.license = 'sin licencia';
  }

  const estadoMatch = s.match(/\b(alpha|beta|experimental|preview|release candidate|rc\d?|wip|estable|stable)\b/i);
  if (estadoMatch) out.estado = estadoMatch[1].toLowerCase();

  const creadoMatch = s.match(/(?:creado|created|📅)\s*\*{0,2}(\d{4}-\d{2}-\d{2})/i);
  if (creadoMatch) out.creado = creadoMatch[1];

  const pushMatch =
    s.match(/(?:último\s+push|ultimo\s+push|last\s+push|push|🔄)\s*\*{0,2}(\d{4}-\d{2}-\d{2})/i);
  if (pushMatch) out.ultimoPush = pushMatch[1];

  return out;
}

/**
 * Topics de GitHub citados dentro de `madurez_senales`. Vienen como
 * "Topics: `ai`, `diagrams`…", "topics oficiales: …" o sin backticks, y
 * son la única lista de capacidades real que hay en los datos: alimentan
 * la banda de chips del diagrama de la ficha de repositorio.
 */
export function parseTopics(raw: string | undefined | null): string[] {
  const m = (raw ?? '').match(/topics?[^:]{0,14}:\s*([^.]+)/i);
  if (!m) return [];
  return m[1]
    .split(',')
    .map((t) => t.replace(/[`*_\s]/g, ''))
    .filter((t) => /^[a-z0-9][a-z0-9-]{1,38}$/i.test(t));
}

/** Número con separador de miles español ("8758" -> "8.758"). A mano, no
 *  con toLocaleString: el Node del build puede venir sin ICU completo y
 *  entonces 'es-ES' degrada en silencio a sin separador. */
export function fmtNum(n: number | null): string | null {
  if (n == null) return null;
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/** Línea de metadatos compacta: "8.758★ · 1.320 forks · Python · Apache-2.0". */
export function senalesLine(sen: Senales, opts: { estado?: boolean; issues?: boolean } = {}): string {
  const parts: string[] = [];
  if (sen.stars != null) parts.push(`${fmtNum(sen.stars)}★`);
  if (sen.forks != null) parts.push(`${fmtNum(sen.forks)} forks`);
  if (sen.lang) parts.push(sen.lang);
  if (sen.license) parts.push(sen.license);
  if (opts.estado !== false && sen.estado) parts.push(sen.estado);
  if (opts.issues !== false && sen.issues != null) parts.push(`${fmtNum(sen.issues)} issues`);
  return parts.join(' · ');
}

/* ------------------------------------------------------------------ *
 * Identidad de repositorio
 * ------------------------------------------------------------------ */

const REPO_RE = /^[\w.-]+\/[\w.-]+$/;

/** "owner/name" si el item es un repo de GitHub identificable; si no, null. */
export function repoSlug(item: Pick<BoletinItem, 'titulo' | 'url'>): string | null {
  if (item.titulo && REPO_RE.test(item.titulo)) return item.titulo;
  const m = (item.url ?? '').match(/github\.com\/([\w.-]+\/[\w.-]+?)(?:\.git)?(?:[/#?]|$)/);
  return m ? m[1] : null;
}

/** Id del nodo del grafo de conocimiento para un repo ("repo:owner/name"). */
export function repoNodeId(slug: string): string {
  return `repo:${slug}`;
}

/**
 * Tema del item para el chip "#tema". `clasificacion.tema_principal` es
 * siempre el propio nombre del repo slugificado ("omnigent-ai-omnigent"),
 * así que no aporta nada: se prefiere el primer concepto del grafo con el
 * que el item se relaciona, que sí es una categoría real.
 */
export function itemTema(item: BoletinItem): string | null {
  const rels = item.relacion_grafo ?? [];
  const concepts = rels.filter((r) => r.dst?.startsWith('concept:'));
  const implemented = concepts.find((r) => r.rel === 'implements') ?? concepts[0];
  if (implemented) return implemented.dst.slice('concept:'.length);

  const tema = item.clasificacion?.tema_principal;
  if (!tema) return null;
  const slugified = item.titulo?.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return tema === slugified ? null : tema;
}

/** "concept:agent-orchestration" -> "agent-orchestration" (para etiquetas). */
export function nodeLabel(id: string): string {
  return id.replace(/^(repo|concept|company|tool|framework|protocol|risk|problem|cluster|skill|pattern|license|arxiv|article_angle):/, '');
}

/** Tipo declarado en el prefijo del id de nodo ("concept:x" -> "concept"). */
export function nodeType(id: string): string {
  const m = id.match(/^([a-z_]+):/);
  return m ? m[1] : 'concept';
}

/**
 * Titular + entradilla del día.
 *
 * El enriquecedor no emite todavía un campo `titular`, así que se toma la
 * primera frase de `editorial.posicionamiento` (que es exactamente la tesis
 * del boletín) y el resto queda como entradilla. Si algún día la pipeline
 * añade `editorial.titular`, este helper lo usa sin tocar la plantilla.
 */
export function titularYEntradilla(editorial: Editorial | null): { titular: string | null; entradilla: string | null } {
  const custom = (editorial as { titular?: string } | null)?.titular;
  const pos = (editorial?.posicionamiento ?? '').trim();
  if (custom) return { titular: custom, entradilla: pos || null };
  if (!pos) return { titular: null, entradilla: null };

  const m = pos.match(/^([\s\S]*?[.!?])\s+([\s\S]+)$/);
  if (!m) return { titular: pos, entradilla: null };
  return { titular: m[1].trim(), entradilla: m[2].trim() };
}

/** Fecha larga en español: "2026-08-13" -> "jueves 13 ago 2026". */
export function fmtDateLong(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  if (!y || !m || !d) return date;
  // Date en UTC para que la fecha no se desplace un día según la zona del build.
  const dt = new Date(Date.UTC(y, m - 1, d));
  const s = new Intl.DateTimeFormat('es-ES', {
    weekday: 'long', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(dt);
  return s.replace(/\bde\b/g, '').replace(/\s{2,}/g, ' ').replace(/,/g, '').trim();
}

/** "2026-08-13" -> "08-13", para el raíl de fechas del triaje. */
export function fmtDateShort(date: string): string {
  return date.slice(5);
}

/**
 * "Salvatore Sanfilippo (antirez)" -> "Salvatore Sanfilippo": limpia el
 * alias entre paréntesis que clasificacion.medio/autor a veces incluye, para
 * que la misma organización o persona no cuente dos veces en /fuentes.
 */
export function normalizeFuente(raw: string): string {
  return raw.replace(/\s*\([^)]*\)\s*/g, '').trim();
}

const DIACRITICS_RE = new RegExp('[' + String.fromCharCode(0x0300) + '-' + String.fromCharCode(0x036f) + ']', 'g');

/** Slug apto para ancla de URL: "Y Combinator" -> "y-combinator". */
export function fuenteSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(DIACRITICS_RE, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
