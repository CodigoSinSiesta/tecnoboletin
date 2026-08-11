# Review agregada · todos los boletines · dani (interpretación del propio agente)

Como junior, reviso los 131 items preguntándome: **¿entendería yo qué hace cada uno sin abrir la URL?**

## Lo que va bien

- Los items con **URL de marca conocida** (OpenAI, Microsoft, Cloudflare, YC, Stanford) me dan安心感 (sic — seguridad) porque conozco la marca, aunque no entienda el detalle. Esto es bueno para juniors.
- Los items de **paperclip vs ORG2** (2026-08-11) están bien diferenciados aunque comparten tema. Sé que uno es "Linear para IAs" y el otro es más técnico. OK.
- El item de **Hands-On** (2026-08-02 idx 6) sobre voz-a-texto offline es entendible: "app que escucha lo que dices y lo escribe". Llegué a entenderlo en 5 segundos.

## Lo que NO me funciona

### 1. Resúmenes demasiado densos en items con estrellas infladas
3 items con > 100k estrellas tienen resumen que NO me dice por qué debería importarme:

| Fecha | idx | Repo | Estrellas | Por qué falla |
|---|---:|---|---:|---|
| 2026-08-10 | 6 | garrytan/gstack | 127k | "23 opinionated tools para CEO/Designer/..." — y a mí qué |
| 2026-08-10 | 7 | msitarzewski/agency-agents | 141k | "una agencia AI completa" — suena comercial fraudulento |
| 2026-08-04 | 10 | DietrichGebert/ponytail | 96k | "YAGNI aplicado" — sin saber qué es YAGNI, paso |

**Acción**: para items con muchas estrellas, el `resumen_2_lineas` debería **restar** énfasis a las estrellas y **sumar** énfasis a "¿te afecta a ti?".

### 2. Items que asumen conocimiento de otro item
Hay dependencias implícitas que rompen el flujo:

- 2026-08-10 idx 0 (hindsight) me pide entender qué son "embeddings" para captar el valor. Pero embeddings no se explican en el resumen.
- 2026-08-09 idx 5 (iFixAi) menciona "MCP" sin definirlo.
- 2026-08-09 idx 7 (Herdrdev) menciona "tmux" sin definirlo.

**Acción**: cuando el resumen usa un acrónimo, **primera mención** debería tener glosa inline corta (no enlace externo). ej. "MCP (protocolo de contexto para IAs)".

### 3. Diferencias entre items parecidas pero invisibles

Tomemos los items de "skills":

- mattpocock/skills (2026-08-08) — ¿es lo mismo que obra/superpowers?
- obra/superpowers (2026-08-08) — ¿es lo mismo que mattpocock/skills?
- google/skills (2026-08-08) — ¿es lo mismo que los anteriores?
- addyosmani/agent-skills (re-entradas) — ¿es lo mismo?

Leo los 4 resúmenes y sigo sin entender cuál elegir. Los autores lo dicen en `competes_with` pero **no es accesible al lector**.

**Acción**: cuando hay 3+ items con mismo `tema_principal`, generar automáticamente una sección "comparativa head-to-head" en la página del boletín. La skill ya tiene `competes_with` edges en el JSON; usarlos para construir una mini-tabla inline.

### 4. Términos kebab-case sin traducir

Los `tema_principal` son siempre kebab-case en inglés:
- `agent-memory`
- `claude-code-skill-pack`
- `abridged-diff-viewer`
- `two-shot-warm-pool-glm-5-2`

Como junior, **no encuentro** estos términos buscando en Google. Son etiquetas internas.

**Acción**: añadir campo `tema_humano` legible para UI:
```json
"tema_principal": "agent-memory",
"tema_humano": "memoria para tu IA"
```

Esto es **separación contenido/presentación**: el dato interno sigue siendo kebab-case; la UI muestra español.

## Conclusión dani

Si me diesen a mí solo estos 131 items para decidir qué probar primero, **elegiría al azar**. No porque sean malos sino porque la información que necesito para decidir está dispersa:
- Estrellas → no me dice madurez real
- Tipo=repo → no me dice si es instalable o solo referencia
- Tema en kebab-case → no me dice cuál se parece a cuál
- Resumen_2_lineas → denso, asume conocimiento

**Lo que más echo de menos**: una **matriz comparativa** al inicio de cada página de boletín con items en filas y columnas como "stars/último push/license/adoptable/dificultad-setup" (1-3 estrellas, fácil/media/difícil). Una sola tabla al inicio reduciría 80% del trabajo de "qué pruebo primero".

Si tuviera que priorizar: añadir `tema_humano` (cambio de 30 min, gran efecto). Después, `adoptable: bool` flag. Lo del taxón tipo, secundarios.
