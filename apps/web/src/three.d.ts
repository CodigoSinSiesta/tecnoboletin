// `three` 0.185 se resuelve al bundle ESM, que no arrastra sus .d.ts, y
// `astro check` falla con ts(7016). El grafo solo usa Sprite,
// SpriteMaterial y CanvasTexture, y ya se manejan como `any` (igual que el
// factory de 3d-force-graph), así que declarar el módulo suelto basta y
// evita añadir @types/three al árbol de dependencias.
declare module 'three';
