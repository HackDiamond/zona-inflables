---
description: Evalúa si es buen momento para cerrar esta conversación e iniciar una nueva, para preservar contexto y eficiencia de tokens
disable-model-invocation: true
allowed-tools: Bash
---

El usuario quiere saber si conviene cerrar esta conversación e iniciar una nueva. Tu objetivo es evaluar señales objetivas y dar una recomendación clara.

## Paso 1 — Recoger señales

Ejecuta en silencio (sin mostrar los comandos):

```bash
cd /Users/anto/avidoos && git log --oneline -10 && echo "---" && git status --short && echo "---" && wc -l app/templates/index.html
```

## Paso 2 — Evaluar

Puntúa estos factores:

**Señales de que SÍ conviene nuevo hilo:**
- El contexto de esta conversación ya fue comprimido automáticamente (lo sabes porque ves "Summary:" al inicio) → señal fuerte
- Se han hecho 3+ commits en esta sesión → sesión larga
- Hemos cambiado de área de trabajo (ej. de Creatividades a otro módulo distinto)
- Hay cambios sin commit pendientes que complican el estado
- La conversación lleva más de ~40 mensajes

**Señales de que NO conviene:**
- Estamos en medio de una tarea sin terminar
- Acabamos de hacer commit limpio y seguimos en el mismo módulo
- La sesión es corta y el contexto está fresco

## Paso 3 — Responder

Si recomiendas nuevo hilo:

```
✦ Buen momento para un nuevo hilo

Por qué: [razón principal en 1 frase]

Antes de cerrar:
□ git commit (si hay cambios pendientes)
□ Actualizar CONTEXT.md con: [qué añadir — estado actual, último commit, próximo paso]
□ [cualquier otra cosa específica del estado actual]

Para continuar en el nuevo hilo, empieza con:
"Continuamos el desarrollo de Avidoos. Lee CLAUDE.md y CONTEXT.md para el contexto."
```

Si NO recomiendas nuevo hilo:

```
✦ Podemos seguir aquí

Por qué: [razón en 1 frase]
Tokens: sesión corta, contexto fresco.
```

Sé directo. No expliques el proceso de evaluación, solo el resultado.
