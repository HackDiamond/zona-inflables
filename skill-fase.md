---
description: Al iniciar una nueva fase de desarrollo, analiza la tarea y recomienda el modelo óptimo (Sonnet o Opus)
disable-model-invocation: true
---

El usuario está a punto de comenzar una nueva fase de desarrollo. Analiza la descripción de la tarea y recomienda el modelo más adecuado siguiendo estos criterios:

## Usa **Sonnet** cuando la tarea sea:
- Editar HTML, CSS o JavaScript (ajustes de UI, nuevas secciones, estilos)
- Modificar código Python existente (rutas Flask, queries GAQL, funciones conocidas)
- Debug con pistas claras (error visible, log concreto, comportamiento conocido)
- Refactoring o renombrado de funciones/variables
- Añadir endpoints API similares a los existentes
- Ajustes de diseño o copy

## Usa **Opus** cuando la tarea sea:
- Diseñar una arquitectura nueva desde cero (módulo nuevo, sistema de autenticación, flujo complejo)
- Debug sin pistas claras (comportamiento extraño sin error visible, regresión difícil de reproducir)
- Razonamiento multi-paso con muchas dependencias cruzadas
- Decisiones estratégicas de producto o técnicas con múltiples trade-offs
- Análisis profundo de datos o lógica de negocio compleja

## Formato de respuesta

Responde siempre así:

**Modelo recomendado: [Sonnet / Opus]**

_Razón: [1 frase concisa]_

Para cambiar: `/model [sonnet/opus]`

---
Si la tarea actual no está clara, pide al usuario que la describa brevemente antes de recomendar.
