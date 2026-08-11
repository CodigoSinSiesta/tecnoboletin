# Despliegue

## URL pública

`https://codigosinsiesta.github.io/tecnoboletin/`

GitHub Pages usa la rama `main` del repo `CodigoSinSiesta/tecnoboletin`.

## Workflow automático

```
PR mergeado / push a main
   ↓
.github/workflows/deploy.yml
   ↓
[ubuntu-latest runner]
   - npm ci
   - npm run build (astro check + astro build)
   - upload artifact
   ↓
GitHub Pages
   ↓
URL pública disponible (~1 min total)
```

## Activar Pages (primera vez)

1. Repo en GitHub → **Settings** → **Pages**
2. **Source**: GitHub Actions
3. Listo. El siguiente push a `main` ya déploia.

## Custom domain (opcional, futuro)

Si en algún momento quieres `tecnoboletin.codigosinsiesta.com`:

1. En el repo DNS, crea CNAME `tecnoboletin` → `codigosinsiesta.github.io`
2. En el repo Settings → Pages → **Custom domain**: `tecnoboletin.codigosinsiesta.com`
3. Marca **Enforce HTTPS**

## Forzar rebuild manual

Si necesitas re-desplear sin tocar código:

1. Repo en GitHub → pestaña **Actions**
2. Selecciona "Build and Deploy to GitHub Pages"
3. Botón **Run workflow** → rama `main`

## Verificar el deploy

```bash
gh run list --workflow=deploy.yml --limit=5
gh run view <run_id> --log
```

O desde la web: `https://github.com/CodigoSinSiesta/tecnoboletin/actions`.

## Variables de entorno

Ninguna en producción. El sitio es 100% estático en fase 1.

En fase 3 (Supabase):

- `PUBLIC_SUPABASE_URL`
- `PUBLIC_SUPABASE_ANON_KEY`

Se definen en Settings → Secrets and variables → Actions → Variables.

## Rollback

```bash
git revert <commit-en-mal>
git push origin main
# El deploy anterior sigue accesible vía Actions → run anterior → artifact
```

O más rápido: desde Actions, re-ejecuta un run anterior para volver a desplegar el artefacto que tenía.
