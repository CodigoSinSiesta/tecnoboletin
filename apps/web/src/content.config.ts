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
    // El enriquecido se mete en otro archivo adyacente: *.enriched.json
  }),
});

export const collections = { boletines };
