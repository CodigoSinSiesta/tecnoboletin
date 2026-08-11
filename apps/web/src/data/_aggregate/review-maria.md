# Review agregada · todos los boletines · maría (interpretación del propio agente)

Soy civil, no programadora. Reviso los 131 items preguntándome: **¿podría yo recomendar a un familiar no-técnico?**

## Lo que sí me enganchó

### Items con interés difuso-civil

| Fecha | idx | Por qué me interesa | Triste que esté enterrado |
|---|---:|---|---|
| 2026-08-11 | 8 | dyad — 'vibe coding local' — "¿puedo crear una web sin saber programar?" | Está en idx 8, no destacada |
| 2026-08-11 | 5 | antvis/Infographic — "infografías bonitas sin diseñar" | Buried |
| 2026-08-11 | 4 | codex-router — privacidad de credenciales | OK |
| 2026-08-04 | 4 | trycompai/crm — "CRM que un agente rellena por ti" | Buried |
| 2026-08-04 | 3 | livekit/agents — voz para asistente | Muy enterrado |
| 2026-08-02 | 6 | Handy — voz-a-texto offline | Bien ubicado (idx 6) |
| 2026-08-02 | 5 | OpenCLI — "CLI para tus cuentas" | OK |

**Hallazgo**: los items con interés civil suelen estar en `idx` altos (radar secundario) en los boletines. Para audiencia civil, **deberían ir primero**, no tercero.

### Patrón de claims vagos = desconfianza
Cuando el resumen usa "podría" / "tal vez" / "es interesante", no me convence:

| Fecha | idx | Repo | Resumen actual | Lo que pensaba al leer |
|---|---:|---|---|---|
| 2026-08-04 | 1 | boldsoftware/meat | "reduce diffs a conceptos" | ¿Reduce los diffs o no los reduce? |
| 2026-08-06 | 0 | PrimeIntellect-ai/prime-agent | "se automejora" | ¿Sí o no? |
| 2026-08-08 | 7 | PrimeIntellect-ai/prime-agent | "self-improving RLM" | Claim vago #2 |

**Acción**: exigir concrete. La prueba de fuego: ¿puedo decir a un familiar "esta app hace X en Y minutos"? Si no, reescribir.

## Lo que NO me engancha pero merece atención

### Términos que suenan a enfermedad / cosmética / Slang de TikTok

| Fecha | idx | Término | Sugerencia |
|---|---:|---|---|
| 2026-08-04 | 0 | "sistema de archivos virtual" | "es como un USB virtual para tu IA" |
| 2026-08-07 | 4 | dream-num/univer "Office framework" | "una alternativa libre a Office que se adapta" |
| 2026-08-11 | 0 | "motor de inferencia multimodal en C" | "ejecuta un modelo de vídeo IA en tu Mac" |

**Acción**: añadir glosa civil en el `resumen_2_lineas` para cualquier término que requiera más de 5 segundos de entender.

## Lo que ignoro por completo

43 items. Patrones detectados de items que un civil descarta en <2s:

| Patrón | Ejemplos | Por qué ignoro |
|---|---|---|
| Lenguaje bajo nivel (Rust, C, Bash) sin valor claro | multica, axis-agentic, shepherd, FOSS | No sé qué gano |
| Acrónimos pegados sin espacios | `MiroFish`, `Panniantong` | Marcas que no conozco |
| Claims megaproyecto sin evidencia | "the Linear for AI agents" (paperclip) | Marketing-speak |
| "research-grade" + alpha | shepherd | Suena a "no production" |
| Items con notación técnica AST/MCP/graphrag | code-graph-rag, understanding-anything | Tres conceptos desconocidos juntos |

**Acción**: la página `/enriquecido/` debería tener un **filtro "para civiles"** o **vista simplificada**. Si la web es para mí y similares, el 67% del contenido es ruido.

## Conclusión maría

**Lo único que me importa**: poder decir "¿esto me sirve a mí o a alguien que conozco?". De los 131 items, 18 me interesan. **Porcentaje útil para civil**: 14%.

Causa principal: el formato está hecho para **rastrear tendencias técnicas**. No está mal si tu audiencia es programadores. Pero si en algún momento quieres que tu pareja, tu madre, o un periodista lean esto, **hay que añadir una capa civil**.

**Cambios mínimos para hacerlo legible a civiles**:
1. Campo `tema_humano` español
2. Campo `audiencia_recomendada: "dev" | "civil" | "ambos"`
3. Glosa inline de acrónimos al primer uso
4. Filtro en la web que priorice audiencia_recomendada=civil

Sin estos, el `/enriquecido/` actual es una página de programador con apariencia pública. Es engañoso.
