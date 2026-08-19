// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Página publicada en https://codigosinsiesta.github.io/tecnoboletin/
// Tailwind v4 trae su propia versión de Vite; el cast a 'any' evita el conflicto de tipos entre Vite versions.
export default defineConfig({
  site: 'https://codigosinsiesta.github.io',
  base: '/tecnoboletin',
  integrations: [sitemap()],
  vite: {
    // peer dep mismatch entre vite de Astro y vite de @tailwindcss/vite — wrapper runtime evita el conflicto
    plugins: [/** @type {any} */ (tailwindcss)],
  },
});
