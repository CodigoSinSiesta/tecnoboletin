# Review agregada · todos los boletines · carlos (interpretación del propio agente)

## Volumen
10 boletines · 131 items · 30 reviews individuales · 878 edges

## Hallazgos críticos (revisar YA)

### Sesgo de tipo = repo (131/131 = 100%)
**Todos los items son tipo `repo`**. Eso no encaja con boletines que mencionan papers, blogs, podcasts, news.

Casos detectados que deberían ser **distintos**:

| Boletín | idx | URL actual | Tipo correcto sugerido | Por qué |
|---|---:|---|---|---|
| 2026-08-09 | 0 | TauricResearch/TradingAgents | **paper** | "paper arXiv 2412.20138" en el .md — el repo es implementación, pero la referencia canónica es el paper |
| 2026-08-09 | 1 | XYZ-AI-Lab/AxisAgentic | **paper** | "paper propio en xyz-lab.ai" |
| 2026-08-09 | 2 | shepherd-agents/shepherd | **paper** | "paper arXiv 2605.10913" |
| 2026-08-02 | 2 | esengine/DeepSeek-Reasonix | **tool** | No es "repo" en sentido estricto, es la implementación ejecutable. La taxonomía `tool` encajaría mejor (cualidad: ejecutable vs. referencia) |

**Acción**: añadir `tipo` secundario como tag. Por ejemplo `tipos: ["repo", "paper-implementacion"]`. O crear una taxonomía nueva con `repo` / `paper` / `tool` / `framework` claramente separados. La taxonomía actual con 8 valores nunca selecciona nada distinto de `repo`.

### Confianza inflada en items NOASSERTION
Items con license NOASSERTION no deberían tener confianza > 0.75 sin flag explícito.

| Fecha | idx | Repo | Confianza actual | Esperado |
|---|---:|---|---:|---|
| 2026-08-05 | 9 | WeaveMindAI/weft | 0.70 | OK |
| 2026-08-04 | 5 | multica-ai/multica (Apache+Part I) | 0.85 | debería ser 0.65 o flag `pending license verification` |
| 2026-08-02 | 4 | antirez/ds4 | 0.88 | OK (pero self-reported AI-assisted development merece flag) |
| 2026-08-07 | 10 | FalkorDB/FalkorDB | 0.80 | debería ser 0.7 hasta verificar LICENSE file |
| 2026-08-09 | 10 | 666ghj/MiroFish (AGPL-3) | 0.85 | OK pero el taxón no marca AGPL explícitamente. AGPL-3 es restrictivo, debería nota |

**Acción**: añadir flag `risk_flags: ["license_unverified"]` o bajar confianza < 0.7 cuando NOASSERTION aparece.

## Hallazgos editoriales

### Tema_principal 1-1 con el item (no hay clustering editorial)
9 de los 10 boletines tienen **cada item con tema_principal único**. Eso significa que **no hay agrupamiento editorial explícito**. Los clusters se forman vía edges `competes_with`, pero el tema_principal mismo no los agrupa.

**Consecuencia**: la página `/enriquecido/` lista 13 items con 13 temas distintos para 2026-08-02. El lector no ve "sección de memoria", "sección de agentes", "sección de inferencia local". Ve atomos sueltos.

**Acción**: forzar jerarquía. Ejemplo de taxonomía:
- `tema_principal`: cluster macro (ej. `agent-memory`, `coding-agent`, `agent-runtime`)
- `tema_secundario`: sub-cluster (ej. `vector-store`, `competing-framework`, `kanban-native`)
- Los items de un cluster comparten `tema_principal` y se diferencian en secundarios.

Esto sí permitiría vistas tipo "todos los items sobre memoria persistente" cruzando boletines.

### Confianza media por boletín: rando 0.80-0.90
Sin outliers sospechosos. La distribución es coherente con el dominio (más confianza en OSS maduros MIT/Apache, menos en NOASSERTION o reciente).

## Hallazgos por item (críticos)

### 2026-08-02 idx 12: karpathy/autoresearch
- Confianza 0.55 — bien baja.
- Tema principal `ai-research-agent` con NOASSERTION — debería marcarse como `not-adoptable`.
- **Acción**: añadir campo `adoptable: false` para que la UI lo marque visualmente.

### 2026-08-03 idx 2: FareedKhan-dev/kimi-k3-in-c
- Confianza 0.80 con claim "2.78T params en CPU con 8 GB RAM" — esos números son físicamente inverosímiles (un solo params de 32-bit necesita >10GB). El repo probablemente carga solo capas activadas o es un experimento de cuantización extrema.
- **Acción**: añadir `note: "claim pending verification"` y bajar a 0.65.

### 2026-08-05 idx 11: magicrew/doc7
- Confianza 0.78 pero el .md dice "VLM multimodal con capacidad visual" — es decir, hace OCR con visión, **no es comparable 1:1 con firecrawl/anydoc**. La comparación puede ser injusta con cualquierdoc.
- **Acción**: nota editorial en el tema principal: `document-visual-markdown` (ya lo tiene) pero añadir nota `not-comparable-to-anydoc-due-to-vision-pipeline`.

### 2026-08-08 idx 0 vs idx 1: mattpocock vs obra
- Mismo `tema_principal` distinto (`claude-code-skills` vs `agentic-skills-framework`). Es editorialmente correcto separarlos. Sin acción.

### 2026-08-11 idx 1 y 2: paperclip vs ORG2
- Mismo `tema_principal` `agent-company-os` — esto es la **demuestra** que la decisión "mismo tema_principal" funciona. Sin acción.

## Conclusión carlos

El dataset está **bien para ser beta**. Los 3 problemas críticos son:
1. **Tipo = repo en 100%** — debe ser distinto por taxonomía real
2. **Clusters editoriales débiles** — falta jerarquía 1-N en `tema_principal`
3. **Flags de license risk no son consistentes** — deberían estar siempre que NOASSERTION/AGPL/SSPL aparezca

Si tuviera que priorizar una iteración, es (1): la taxonomía de `tipo` está mal modelada. Aún siendo repos, todos los items son `repo` por defecto; un sistema real diferenciaría `repo` (código a leer), `tool` (binario ejecutable), `framework` (librería integrable), `paper` (referencia académica), `doc` (conocimiento sin código).
