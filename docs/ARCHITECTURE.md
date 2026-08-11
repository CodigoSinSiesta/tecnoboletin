# Arquitectura

## Diseño general

Tecnoboletín es una **capa de presentación sobre un archivo Markdown plano**. Su único requisito de despliegue es un servidor de archivos estáticos. No hay runtime servidor en producción, salvo que en fase 3 metamos SSR con Supabase.

```
┌──────────────────────────────────────────────────────────────────┐
│                         MÁQUINA DE ALEJANDRO                     │
│                  (vmi3166146, usuario ibid)                       │
│                                                                  │
│  ~/obsidian-vault/Research/Boletines/*.md                       │
│        ▲                                                         │
│        │ escribe manual (a diario)                               │
│        │                                                         │
│        │ cron blogwatcher 08:00 + boletín 09:10                  │
│        │ (generan nuevos .md en el vault)                        │
│        │                                                         │
│  scripts/sync-vault.sh  ───── copia ─────►  ~/proyectos/         │
│        ▼                              tecnoboletin/apps/web/     │
│   git add + commit                          src/content/         │
│   git push origin main                      boletines/           │
│                                                  ▼               │
│                                          GitHub Actions           │
│                                              (ubuntu-latest)     │
│                                                  ▼               │
│                                          GitHub Pages             │
│                                          (cdn mundial)           │
└──────────────────────────────────────────────────────────────────┘
```

## Capas

### 1. Fuente de verdad: Obsidian vault
**`~/obsidian-vault/Research/Boletines/<YYYY-MM-DD>-trending.md`** y **`...-blogs.md`** (formato del boletín de Telegram) más lo que genere el blogwatcher. **Estos archivos son sagrados**. Nunca se modifican desde tecnoboletín.

### 2. Capa de sincronización
**`scripts/sync-vault.sh`** — copia los `.md` al directorio `apps/web/src/content/boletines/` del repo. Es idempotente: solo copia si hay cambios.

### 3. Capa de enriquecimiento (fase 2)
**`scripts/enrich.py`** — lee cada `.md`, extrae items (URL + título + descripción), llama a Ollama con DeepSeek-V4-Pro, y genera **`*.enriched.json` adyacente**. No modifica el `.md`.

**Estructura prevista de `*.enriched.json`**:

```json
{
  "version": 1,
  "fecha": "2026-07-26",
  "items": [
    {
      "titulo": "...",
      "url": "https://...",
      "tipo": "blog | paper | noticia | repo | video | podcast",
      "idioma": "es | en | ...",
      "autor": "...",
      "medio": "...",
      "temas": ["agentes", "mcp"],
      "resumen_2_lineas": "..."
    }
  ],
  "manifesto": {
    "fuentes_recurrentes": [...],
    "temas_dominantes": [...]
  }
}
```

### 4. Capa de presentación: Astro
- **Astro 5** con **content collections** (define en `apps/web/src/content.config.ts`)
- **Markdown rendering** vía `@astrojs/mdx` equivalente
- **Estilo**: Tailwind v4 + tokens CSS propios en `global.css`
- **Tipografía**: Inter (sans), IBM Plex Serif (lectura), JetBrains Mono (código)
- **Sin JavaScript de cliente** salvo lo imprescindible (menú, modo oscuro)

### 5. Capa de deploy: GitHub Pages
- Cada push a `main` dispara `deploy.yml`
- Build con `npm ci && npm run build` en ubuntu-latest
- Artefacto subido a Pages
- URL pública: `https://codigosinsiesta.github.io/tecnoboletin/`

## Decisiones técnicas clave

### ¿Por qué Astro y no Svelte?
Porque es un sitio de **lectura**, no de interacción. Svelte encaja en presentaciones. Astro produce HTML estático, es más simple, más rápido de TTFB, y no añade peso de runtime.

### ¿Por qué Tailwind v4 y no un CSS plano?
Consistencia visual con `codigosinsiesta.github.io` (el blog principal de la org). v4 reduce boilerplate con `@theme` y CSS-first config.

### ¿Por qué no iCloud, Google Drive, ni similares?
Boletines son contenido público. Sync local-first con Git como pieza de versionado: si falla un commit, hay diff y rollback.

### ¿Por qué content collections y no cargar .md dinámicamente?
Astro valida el frontmatter con Zod. Errores en tiempo de build, no en producción. Tipos generados automáticamente.

## Decisiones diferidas (fase 3)

| Tema | Decisión pendiente |
|---|---|
| Auth provider | Email only vs Google/GitHub OAuth |
| Tiers de usuario | ¿Gratis + un posible premium? ¿Sin tiers? |
| Marcadores privados | Visibles solo en `/cuenta`, ninguno público |
| Comentarios | ¿Boton GitHub Discussions vs Supabase realtime? |
| Newsletter mail | ¿Salida desde el sitio o sigue Telegram solo? |
