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
 * El enriquecedor no emite todavía un campo `titular`, así que se extrae
 * la primera frase con valor de `editorial.posicionamiento`. La mecánica:
 *
 *  1. Descarta oraciones iniciales que son muletilla ("El boletín de hoy
 *     X", "Hoy...", "Este boletín...") y escoge la primera con tesis.
 *  2. Si esa oración útil es muy larga, se corta SOLO por una frontera
 *     natural (`:`, `—`, `;`). Nunca a media frase: un titular que
 *     ocupa dos líneas se lee; uno mutilado con '…', no.
 *  3. Si la pipeline algún día añade `editorial.titular`, se usa tal cual.
 *
 * El objetivo es llegar a titulares que caben en 1 línea de h1 sin
 * recortar contenido: la frase completa puede seguir leyéndose en la
 * entradilla expandible.
 */

// A partir de aquí una oración es demasiado larga para un titular y se
// busca un corte por frontera natural (`:`, `—`, `;`). Si no la hay, se
// deja entera y el h1 hace dos líneas: un titular que envuelve se lee
// bien, uno cortado a media frase no.
const TITULAR_LARGO = 120;
// Hasta dónde se busca la frontera. Es mayor que TITULAR_LARGO a
// propósito: si la coma que cierra la idea cae en el carácter 121, cortar
// ahí da un titular completo, y no hacerlo deja el párrafo entero.
const CORTE_MAX = 180;

// Muletillas con las que los posicionamientos arrancan a menudo. Se
// descartan cuando la primera oración del `posicionamiento` empieza
// por alguna de ellas (case-insensitive, tras trim).
//
// El caso "El boletín del lunes 17 de agosto..." se colaba: la variante
// con fecha en texto (día de la semana + número + mes) no estaba
// contemplada, solo la ISO y "de hoy".
const MESES = 'enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre';
const DIAS = 'lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo';
const FILLER_PREFIXES = [
  // "El boletín de hoy…", "El boletín del 2026-08-17…"
  /^el[ \u00A0]+boletín[ \u00A0]+(?:de[ \u00A0]+hoy|del[ \u00A0]+\d{4}-\d{2}-\d{2}|[a-záéíóúñ0-9 ]+de[ \u00A0]+\d{4})\b/i,
  // "El boletín del lunes 17 de agosto…", "El boletín del 17 de agosto…"
  new RegExp(`^el[ \u00A0]+bolet[ií]n[ \u00A0]+del?[ \u00A0]+(?:(?:${DIAS})[ \u00A0]+)?\\d{1,2}[ \u00A0]+de[ \u00A0]+(?:${MESES})\\b`, 'i'),
  // "El boletín de este lunes…", "El boletín de esta semana…"
  new RegExp(`^el[ \u00A0]+bolet[ií]n[ \u00A0]+de[ \u00A0]+est[ae][ \u00A0]+(?:${DIAS}|semana|jornada)\\b`, 'i'),
  /^este[ \u00A0]+boletín\b/i,
  /^el[ \u00A0]+boletín[ \u00A0]+de[ \u00A0]+hoy\b/i,
  /^hoy[ \u00A0]+,\s*el[ \u00A0]+boletín\b/i,
  /^hoy[ \u00A0]+,\s+el\b/i,
  /^hoy[ \u00A0]+,\s+/i,
  /^hoy\b/i,
  // Meta sobre el propio boletín, no tesis: "Los seis hallazgos
  // principales dibujan…", "La lectura editorial no es…"
  /^(?:los|las)[ \u00A0]+\w+[ \u00A0]+hallazgos\b/i,
  /^la[ \u00A0]+lectura[ \u00A0]+editorial\b/i,
];

/** Devuelve true si la oración es puro relleno (no tesis). */
function isFillerSentence(s: string): boolean {
  const t = s.trim();
  if (t.length < 8) return true;
  return FILLER_PREFIXES.some((re) => re.test(t));
}

/**
 * Parte un texto en oraciones.
 *
 * Solo partimos en `.!?` cuando van seguidos de espacio + mayúscula o
 * dígito (frontera de oración natural). Esto evita romper acrónimos
 * tipo "BAML", "DSL", "v1.1", "oss/v1" o números con punto decimal.
 */
function splitSentences(text: string): string[] {
  const out: string[] = [];
  // Split por delimitadores seguidos de espacio + mayúscula/dígito.
  const re = /([.!?])(\s+)(?=[A-ZÁÉÍÓÚÑ0-9])/g;
  const parts = text.split(re);
  // parts se intercala: [chunk, delim, ws, chunk, delim, ws, ...]
  let buf = '';
  for (let i = 0; i < parts.length; i++) {
    buf += parts[i];
    if (i + 2 < parts.length && /^[.!?]$/.test(parts[i + 1])) {
      out.push(buf.trim());
      buf = '';
      i += 2; // saltar delim + ws
    }
  }
  if (buf.trim()) out.push(buf.trim());
  return out.filter((s) => s.length > 0);
}

/** Quita la primera oración de un texto y devuelve el resto. Si solo había
 * una oración, devuelve el texto vacío. */
function dropFirstSentence(text: string, first: string): string {
  const idx = text.indexOf(first);
  if (idx < 0) return text;
  let cut = idx + first.length;
  while (cut < text.length && /[\s.;:!?]/.test(text[cut])) cut++;
  return text.slice(cut).trim();
}

/** Acorta una oración a las primeras N palabras + '…' si fue recortada. */
/**
 * Acorta una oración larga SIN cortarla a media frase.
 *
 * Antes se recortaba a 12 palabras y se pegaba un '…', que producía
 * titulares mutilados del tipo "La capa de agentes sale del taller y
 * entra a producción por…". Ahora solo se corta si hay una frontera
 * natural (dos puntos, raya o punto y coma) que deje un titular con
 * sentido completo; si no la hay, se devuelve la oración entera y el
 * titular ocupa dos líneas, que es preferible a mutilarlo.
 */
function acortarPorFrontera(s: string): string {
  const t = s.trim().replace(/[.,;:\s]+$/, '');
  if (t.length <= TITULAR_LARGO) return t;

  // Se busca la frontera más tardía que siga dejando un titular legible.
  // Primero las fuertes (cierran idea), luego la coma como último
  // recurso: cortar en coma da una oración completa, no un muñón.
  for (const seps of [[':', '—', ';', ' - '], [', ']]) {
    let mejor = -1;
    for (const sep of seps) {
      const idx = t.lastIndexOf(sep, CORTE_MAX);
      if (idx > mejor) mejor = idx;
    }
    if (mejor >= 40) return t.slice(0, mejor).trim().replace(/[.,;:\s]+$/, '');
  }

  return t;
}

export function titularYEntradilla(editorial: Editorial | null): { titular: string | null; entradilla: string | null } {
  const custom = (editorial as { titular?: string } | null)?.titular;
  const pos = (editorial?.posicionamiento ?? '').trim();
  if (custom) return { titular: custom, entradilla: pos || null };
  if (!pos) return { titular: null, entradilla: null };

  const sentences = splitSentences(pos);
  if (sentences.length === 0) return { titular: null, entradilla: null };

  // Descarta oraciones de relleno iniciales hasta dar con la primera útil.
  let pickIdx = 0;
  while (pickIdx < sentences.length && isFillerSentence(sentences[pickIdx])) {
    pickIdx++;
  }

  // Si tras descartar relleno no queda nada, vuelve al texto completo.
  if (pickIdx >= sentences.length) {
    return { titular: null, entradilla: pos };
  }

  const fullTesis = sentences[pickIdx];
  const titular = acortarPorFrontera(fullTesis);

  // Entradilla: posicionamiento SIN la primera oración original (no la
  // recortada), para que si el lector quiere leer la frase completa la
  // encuentre desplegada.
  const entradilla = dropFirstSentence(pos, sentences[0]).trim();

  // Si la oración recortada dejó texto idéntico al titular, no repitas.
  const entradillaFinal = entradilla && !entradilla.startsWith(titular) ? entradilla : null;

  return { titular, entradilla: entradillaFinal };
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
