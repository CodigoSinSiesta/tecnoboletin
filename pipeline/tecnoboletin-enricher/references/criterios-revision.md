# Criterios de revision editorial (3 lentes)

Reemplaza a `perfiles.md` (Carlos/Dani/Maria). Estas NO son personas ni
personajes con biografia -- son 3 criterios de revision que se aplican
sobre el BORRADOR COMPLETO del articulo del dia (todos los hallazgos +
la sintesis editorial juntos), no sobre items aislados. El objetivo es
mejorar el borrador antes de publicar, no generar contenido que se
publique con nombre y voz propia.

Importante (acordado con Alejandro): el resultado de estas 3 criticas
**no se persiste en disco ni se publica en ningun JSON**. Se usan en
memoria durante `synthesize_article.py` para producir la version final del
articulo y luego se descartan. No debe existir ningun `reviews.json` ni
artefacto equivalente en el output ni en el repo.

## 1. Rigor tecnico

Busca:
- Claims sin sustento (cifras o afirmaciones que no esten respaldadas en
  el propio texto extraido del boletin origen).
- Clasificacion incoherente con el contenido real del item (ej.
  `tipo=paper` para algo que es en realidad un blog tecnico sin peer
  review).
- Falta de contexto tecnico necesario para entender por que importa un
  hallazgo (ej. mencionar un termino sin la precision minima para que el
  lector entienda el nivel de madurez real).

No inventa datos nuevos -- solo senala que falta o que sobra en lo que ya
esta escrito.

## 2. Claridad / accesibilidad

Busca:
- Jerga sin glosar (terminos tecnicos usados sin una pizca de contexto).
- Frases que solo se entienden haciendo click al link original.
- Redaccion criptica, mal estructurada o con demasiadas subordinadas.

Sugiere como aclarar SIN diluir el contenido tecnico real -- el objetivo
no es "simplificar para todos los publicos" (el boletin es para audiencia
tecnica de Codigo Sin Siesta), sino eliminar bloqueos de comprension
innecesarios.

## 3. Relevancia editorial

Busca:
- Por que le importa esto a un lector de Codigo Sin Siesta -- no una
  razon generica ("es interesante"), sino una conexion concreta con la
  linea editorial, el stack de Alejandro, o un patron ya cubierto.
- Si las conexiones con boletines previos y con el grafo de conocimiento
  estan bien explicitadas (con fecha/boletin concreto) o son solo
  etiquetas sueltas sin sustancia.

## Como se usan

`synthesize_article.py` construye un borrador del dia completo, pasa las
3 lentes (una llamada LLM cada una, con el prompt de esta pagina como
instruccion), y usa el feedback conjunto para producir una reescritura
final del borrador -- tambien via LLM, con la instruccion explicita de no
inventar hechos nuevos. Las 3 criticas intermedias viven solo como
variables locales dentro de esa funcion y se descartan al terminar.

Si no hay backend LLM disponible en el runtime (ver SKILL.md, "Estado del
backend LLM"), este paso se salta y el articulo se publica con el
contenido ya preservado/pulido mecanicamente por `enrich_items.py` --
sigue siendo valido, solo le falta la capa de refinamiento editorial
adicional. Esto queda trazado en `stats.critica_lentes_aplicada` de cada
`enriched.json`.
