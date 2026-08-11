# Tecnoboletín

Lectura cómoda de los boletines (Telegram + blogwatcher) para [Código Sin Siesta](https://codigosinsiesta.github.io/).

Hecho con **Astro 5** + TypeScript + Tailwind v4. Alojado en **GitHub Pages**. Listo para Supabase en fase 3.

🔗 **Demo en vivo**: [codigosinsiesta.github.io/tecnoboletin](https://codigosinsiesta.github.io/tecnoboletin/)

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│         ~/obsidian-vault/Research/          │
│              Boletines/*.md                 │
│              (fuente de verdad)              │
└────────────────────┬────────────────────────┘
                     │ sync-vault.sh
                     ▼
┌─────────────────────────────────────────────┐
│   apps/web/src/content/boletines/*.md       │
│                  + *.enriched.json          │
│              (astro content collections)    │
└────────────────────┬────────────────────────┘
                     │ astro build
                     ▼
              static site (dist/)
                     │
                     ▼
       github.io/tecnoboletin (Pages)
```

**Tres fases**:

1. **Hoy** — base pública, sync manual desde el vault, sin enriquecimiento.
2. **Próxima semana** — enriquecedor Python con Ollama/DeepSeek. 1h después de cada boletín genera `*.enriched.json`. NO toca los `.md`.
3. **Futuro** — Supabase Auth + marcadores privados + historial por usuario.

Ver detalles en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) y [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Stack

| Pieza | Tecnología | Por qué |
|---|---|---|
| SSG | Astro 5 | Markdown-first, content collections, sin BD |
| Tipografía | Inter + IBM Plex Serif + JetBrains Mono | Legibilidad larga duración |
| Estilo | Tailwind v4 + tokens CSS propios | Consistente con codigosinsiesta.github.io |
| Deploy | GitHub Actions + Pages | $0, controlado por GitOps |
| Auth (fase 3) | Supabase + `@supabase/ssr` | Hueco arquitectónico preparado |
| Enriquecedor (fase 2) | Python + Ollama/DeepSeek-V4-Pro | Local-first |

## Estructura

```
.
├── apps/
│   └── web/                  # Astro app
│       ├── src/
│       │   ├── content.config.ts
│       │   ├── content/boletines/   # sync desde vault
│       │   ├── layouts/BaseLayout.astro
│       │   ├── components/BoletinCard.astro
│       │   ├── pages/index.astro
│       │   ├── pages/boletines/[slug].astro
│       │   ├── pages/fuentes/index.astro   # fase 2
│       │   ├── pages/temas/index.astro     # fase 2
│       │   └── styles/global.css
│       ├── astro.config.mjs
│       ├── package.json
│       └── tsconfig.json
├── scripts/
│   ├── sync-vault.sh         # copia vault → repo
│   └── enrich.py             # fase 2
├── docs/
│   ├── ARCHITECTURE.md
│   └── DEPLOY.md
├── .github/workflows/deploy.yml
└── README.md
```

## Setup local

```bash
cd apps/web
npm install
npm run dev      # http://localhost:4321
```

Sin servicios externos. Todo estático. El sync exige el Obsidian vault en `~/obsidian-vault/`.

## Sync Obsidian vault → repo

```bash
./scripts/sync-vault.sh              # copia y muestra cambios
./scripts/sync-vault.sh --auto-commit  # copia + commit + push
```

El script está en el repo, pero **no está en cron** todavía. Cuando hagas `./scripts/sync-vault.sh --auto-commit`, los boletines nuevos aparecen en el sitio en el siguiente deploy de Actions.

## Licencia

MIT — ver [LICENSE](LICENSE).
