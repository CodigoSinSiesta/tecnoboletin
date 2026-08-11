import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const boletines = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/boletines' }),
  schema: z.object({
    title: z.string(),
    fecha: z.coerce.date(),
    fuente: z.string().optional(),
    tipo: z.enum(['tendencias', 'blogwatcher', 'arxiv', 'mixto']).default('mixto'),
    items: z.number().int().nonnegative().optional(),
    resumen: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
});

// Datos enriquecidos: por boletín, { enriched, reviews, edges } generados por
// la skill tecnoboletin-enricher. Cada carpeta apps/web/src/data/boletines/<date>/
// contiene los archivos JSON/JSONL. Astro los lee directamente via node:fs en cada
// página dinámica (no se modelan como collection para evitar problemas de path).

export const collections = { boletines };
