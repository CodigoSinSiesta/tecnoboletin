{
  "version": 1,
  "scope": "lote-completo-2026-08-02-al-11",
  "total_boletines": 10,
  "total_items": 131,
  "total_reviews_originales": 30,
  "total_reviews_agregadas": 3,
  "perfiles": {
    "carlos": "reviews-batch-aggregate/2026-08-02.md",
    "dani": "reviews-batch-aggregate/2026-08-03.md",
    "maria": "reviews-batch-aggregate/2026-08-04.md"
  },
  "honestidad_disclaimer": "Las tres reviews agregadas las escribe el propio agente (Ibid) interpretando los roles de Carlos/Dani/Maria. No son perfiles humanos reales. Su valor es estructural: detectan problemas sistemáticos que una persona real debería validar.",
  "hallazgos_criticos": [
    {
      "id": "tipo-taxonomia-rota",
      "severidad": "alta",
      "hallazgo": "100% de los items son tipo=repo. La taxonomía no se usa (hay 8 valores definidos pero el clasificador cae siempre en repo).",
      "evidencia": "131/131 items con clasificacion.tipo == 'repo'",
      "items_mal_clasificados": [
        {"date":"2026-08-09","idx":0,"repo":"TauricResearch/TradingAgents","correcto":"paper","motivo":"paper arXiv 2412.20138"},
        {"date":"2026-08-09","idx":1,"repo":"XYZ-AI-Lab/AxisAgentic","correcto":"paper","motivo":"paper propio en xyz-lab.ai"},
        {"date":"2026-08-09","idx":2,"repo":"shepherd-agents/shepherd","correcto":"paper","motivo":"paper arXiv 2605.10913"},
        {"date":"2026-08-02","idx":2,"repo":"esengine/DeepSeek-Reasonix","correcto":"tool","motivo":"binario ejecutable principal"}
      ],
      "accion_sugerida": "Taxonomía explícita: paper / repo / tool / framework / blog-post. Reclasificación por subagente o por humano para los 4 items identificados."
    },
    {
      "id": "tema-jerarquia-falta",
      "severidad": "alta",
      "hallazgo": "9/10 boletines tienen tema_principal único por item. No hay clustering editorial real.",
      "consecuencia": "La página /enriquecido/ lista atoms sueltos. El lector no ve secciones ('memoria', 'runtime', 'inferencia local').",
      "accion_sugerida": "Migrar a tema_principal = cluster macro (10-15 valores) + tema_secundario = sub-cluster (50-80 valores). Items del mismo cluster comparten principal."
    },
    {
      "id": "license-risks-inconsistentes",
      "severidad": "media",
      "hallazgo": "Items con license NOASSERTION / AGPL / Apache+Part I no tienen flag unificado de license risk.",
      "items_afectados": [
        "2026-08-04 idx 1 multica-ai/multica (Apache+Part I, confianza 0.85)",
        "2026-08-07 idx 10 FalkorDB/FalkorDB (NOASSERTION, confianza 0.80)",
        "2026-08-09 idx 10 666ghj/MiroFish (AGPL-3, confianza 0.85)"
      ],
      "accion_sugerida": "Campo `risk_flags: [\"license_unverified\" | \"agpl_self_hosted\" | \"part_i_clause\"]` para que la UI muestre la advertencia."
    },
    {
      "id": "glosa-civil-acronimos",
      "severidad": "alta",
      "hallazgo": "Items para audiencia civil usan acrónimos (MCP, RAG, tmux, MCP, etc.) sin glosar.",
      "accion_sugerida": "En resumen_2_lineas, primera mención de acrónimo → glosa inline. También campo `tema_humano` español para los temas kebab-case."
    },
    {
      "id": "audiencia-recomendada",
      "severidad": "media",
      "hallazgo": "Sin separación dev/civil. La web actual mezcla ambos y pierde a la audiencia civil.",
      "accion_sugerida": "Cada item lleva `audiencia_recomendada: 'dev' | 'civil' | 'ambos'`. La web principal filtra por audiencia."
    },
    {
      "id": "matriz-comparativa-faltante",
      "severidad": "media",
      "hallazgo": "Cuando 3+ items comparten tema_principal, no se genera automáticamente una mini-tabla comparativa. Competes_with edges existen pero la UI no los usa.",
      "accion_sugerida": "En la página /enriquecido/<date>/, generar bloque 'Comparativa head-to-head' cuando hay 3+ items con mismo tema."
    }
  ],
  "items_accionables": {
    "cuya_confianza_deberia_bajar": [
      {"date":"2026-08-02","idx":1,"repo":"multica-ai/multica","actual":0.85,"sugerido":0.65,"motivo":"Apache-2.0+Part I sin verificar"},
      {"date":"2026-08-02","idx":11,"repo":"arcships/aimux","actual":0.70,"sugerido":0.55,"motivo":"101 estrellas y claim sobredimensionado (172 proveedores)"},
      {"date":"2026-08-03","idx":2,"repo":"FareedKhan-dev/kimi-k3-in-c","actual":0.80,"sugerido":0.65,"motivo":"claim físico inverosímil (2.78T en 8GB)"},
      {"date":"2026-08-07","idx":10,"repo":"FalkorDB/FalkorDB","actual":0.80,"sugerido":0.7,"motivo":"NOASSERTION sin verificar LICENSE file"}
    ],
    "cuyo_resumen_mejoraria": [
      {"date":"2026-08-11","idx":0,"actual":"antirez publica motor de inferencia MiniMax-H3 en C para Apple Silicon","sugerido":"ejecuta un modelo de IA que genera vídeo en tu MacBook sin internet (sin Python, sin nube)"},
      {"date":"2026-08-04","idx":1,"actual":"boldsoftware/meat reduce diffs a los conceptos que un humano debe revisar","sugerido":"herramienta que resume los cambios de código hechos por la IA para que tú solo revises lo que importa"},
      {"date":"2026-08-09","idx":0,"actual":"TradingAgents consejo de agentes LLM analistas que debaten","sugerido":"cinco IAs analistas con roles especializados que debaten y emiten operaciones de trading en cadenas reales"}
    ]
  },
  "cumplimiento_schema_actual": {
    "schema_version": 1,
    "obligatorio_tipo": "definido pero siempre repo",
    "obligatorio_idioma": "definido, todos 'en'",
    "obligatorio_tema_principal": "definido, 1-1 con items",
    "obligatorio_resumen_2_lineas": "definido, presente en 100%",
    "obligatorio_confianza": "no estaba, se añadió",
    "audit_campos_no_usados": ["notas_proceso (Carlos sugirió quitar en su review)"]
  },
  "decision_pendiente_para_usuario": "¿Aplicar los fixes sugeridos ahora (modificar JSONs enriquecidos) o tratar esto como informe para iterar antes del cron?"
}
