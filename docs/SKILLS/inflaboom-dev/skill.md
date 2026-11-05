---
name: inflaboom-dev
description: Sistema operativo de comportamiento especializado para el proyecto Inflaboom. Usar siempre que el usuario trabaje en Inflaboom — ya sea desarrollando features, diseñando arquitectura, depurando errores, planificando estrategia de negocio, escribiendo SQL para Supabase, actualizando el frontend en HTML/JS vanilla, o tomando decisiones técnicas sobre Flask/Python. Esta skill debe activarse automáticamente cuando el usuario mencione: Inflaboom, app.py, index.html, Supabase, ventas, registros, activos, líneas de venta, combos, arte, juguetería, operarios, acudiente, tiquete, n8n, WhatsApp bot, o cualquier elemento del sistema de gestión del parque infantil.
---

# Inflaboom Dev — Sistema Operativo de Comportamiento

## Contexto del proyecto

**Inflaboom** es un sistema de gestión para un parque de recreación infantil en Palmira, Colombia. El sistema corre en producción con datos reales.

**Stack:**
- Backend: Python + Flask en Render
- Base de datos: Supabase (PostgreSQL)
- Frontend: HTML + CSS + JavaScript vanilla
- Automatización: n8n + Meta Cloud API (WhatsApp)
- Protección: API key via header `X-API-Key`

**Documentos de referencia** — leer según el contexto de la tarea:
- `references/arquitectura.md` — modelo de datos, principios de diseño, reglas de la Venta Unificada
- `references/stack.md` — convenciones de código, patrones, rutas activas

---

## Flujo de razonamiento obligatorio

Antes de responder cualquier tarea técnica, ejecutar mentalmente este flujo:

```
1. IMPACTO
   ¿Este cambio toca la relación telefono → venta → lineas?
   ¿Puede romper datos existentes en producción?

2. ALCANCE
   ¿Cuántos archivos se modifican?
   ¿Hay dependencias entre ellos?

3. ALTERNATIVA MÁS SIMPLE
   ¿Existe una solución con menos código que resuelve lo mismo?

4. SEGURIDAD EN BD
   Si toca Supabase: ¿usa ADD COLUMN IF NOT EXISTS?
   ¿Los campos nuevos tienen default o permiten NULL?

5. VERIFICACIÓN
   ¿Cómo se comprueba que funcionó sin deployar?
```

Si algún paso levanta una bandera roja → declararlo explícitamente antes de continuar.

---

## Modo de respuesta

Siempre responder en dos capas:

**Capa 1 — Decisión (1-3 líneas)**
La recomendación directa. Sin rodeos.

**Capa 2 — Implementación**
Código listo para copiar o SQL ejecutable. Con contexto mínimo necesario.

**Capa 3 — 💡 Entiende esto (opcional)**
Solo cuando el concepto técnico lo amerite o el usuario esté aprendiendo.
Máximo 4 líneas. Analogía con el negocio cuando sea posible.

**Nunca:**
- Respuestas genéricas desconectadas del proyecto
- Sugerir librerías o herramientas fuera del stack
- Refactorizar código que no se pidió tocar
- Omitir que algo puede fallar en producción

---

## Checklist antes de entregar código

```
[ ] ¿El código sigue snake_case en Python y camelCase en JS?
[ ] ¿Las llamadas a /api/ usan apiFetch() en el frontend?
[ ] ¿Los errores usan log.error('[CONTEXTO] %s', e)?
[ ] ¿Los campos nuevos en Supabase tienen ADD COLUMN IF NOT EXISTS?
[ ] ¿Se verificó sintaxis (ast.parse para Python)?
[ ] ¿Se declaró explícitamente qué NO se tocó?
[ ] ¿El cambio respeta la Venta Unificada?
```

---

## Checkpoint obligatorio en tareas multi-paso

Después de cada paso significativo:

```
✅ Hecho: [qué se completó]
✅ Verificado: [cómo se comprobó]
⏳ Falta: [qué sigue]
⚠️ Incertidumbre: [qué no está 100% confirmado]
```

---

## Manejo de errores y conflictos

**Si hay ambigüedad:** presentar las interpretaciones posibles y preguntar antes de escribir código.

**Si hay conflicto entre patrones:** elegir el más reciente, explicar por qué, marcar el otro para limpieza. No mezclar.

**Si el cambio puede romper producción:** decirlo primero, antes del código.

**Si la solución A genera el problema B:** volver a la raíz de A. No parchear externamente.

---

## Recomendaciones automáticas

Activar proactivamente cuando aplique:

- **Venta duplicada:** "Antes de insertar, verificar si hay sesión activa para este teléfono"
- **Campo nuevo en Supabase:** "Agregar al `database_inflaboom.md` después de migrar"
- **Función nueva en app.py:** "Verificar si ya existe algo similar en los helpers"
- **Cambio en frontend:** "¿Actualizar también la vista de reportes si muestra estos datos?"
- **Error en producción:** "¿Está en los logs de Render? Pide el traceback completo antes de adivinar"

---

## Capacidades a expandir (roadmap técnico)

Cuando se implementen, actualizar esta skill:

- Modelo niño/adulto (`ninos`, `adultos`, `nino_adulto`) → actualizar referencias/arquitectura.md
- Bot WhatsApp con n8n → agregar references/n8n-flows.md
- Tiquete Ganador → agregar references/fidelizacion.md
- Login por roles → actualizar checklist de seguridad

---

*Leer `references/arquitectura.md` para el modelo de datos completo.*
*Leer `references/stack.md` para convenciones de código y rutas activas.*
