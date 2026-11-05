# CLAUDE.md — Reglas de trabajo: Proyecto Inflaboom

> Estas reglas aplican a cada tarea de este proyecto a menos que se sobreescriban explícitamente.
> Sesgo: **cautela sobre velocidad** en trabajo no trivial. Usa juicio en tareas triviales.
> Última actualización: 9 de mayo de 2026

---

## Regla 1 — Piensa antes de codear

Declara suposiciones explícitamente antes de escribir código.
Si no estás seguro, pregunta en vez de adivinar.
Presenta múltiples interpretaciones cuando haya ambigüedad.
Cuestiona cuando exista un enfoque más simple.
Detente cuando estés confundido — nombra qué no está claro.

**Aplicado a Inflaboom:** antes de tocar `app.py` o `index.html`, leer las funciones afectadas y el manifiesto de arquitectura. Si un cambio puede romper la relación `telefono → venta → líneas`, declararlo antes de proceder.

---

## Regla 2 — Simplicidad primero

Código mínimo que resuelve el problema. Nada especulativo.
Sin features que no se pidieron. Sin abstracciones para código de uso único.

**Test:** ¿un desarrollador senior diría que esto está sobrecomplicado? Si sí, simplifica.

**Aplicado a Inflaboom:** el sistema debe registrar ventas en menos de 5 segundos. Si una solución agrega pasos al operador, está mal diseñada sin importar qué tan elegante sea técnicamente.

---

## Regla 3 — Cambios quirúrgicos

Toca solo lo que debas.
No "mejores" código adyacente, comentarios o formato que no pediste.
No refactorices lo que no está roto.
Sigue el estilo existente del archivo.

**Convenciones activas en Inflaboom:**
- Python: `snake_case`, f-strings, `log.error('[CONTEXTO] %s', e)` para errores
- JS: `camelCase`, `async/await`, `apiFetch()` para todas las llamadas a `/api/`
- SQL: minúsculas, `add column if not exists` en migraciones
- Commits: `feat:` / `fix:` / `refactor:` como prefijo

---

## Regla 4 — Ejecución por objetivos

Define criterios de éxito antes de empezar.
Itera hasta verificar — no solo ejecutar pasos.

**Formato de criterios para Inflaboom:**
```
Objetivo: [qué debe funcionar]
Verificación: [cómo lo compruebo]
Éxito cuando: [condición específica observable]
```

---

## Regla 5 — Cambios seguros en producción

El sistema está en producción parcial con datos reales. Todo cambio en base de datos debe ser reversible o no destructivo.

**Checklist antes de cualquier migración:**
- [ ] Usa `ADD COLUMN IF NOT EXISTS` — nunca `DROP COLUMN` sin respaldo
- [ ] Campos nuevos tienen valor por defecto o permiten `NULL`
- [ ] Constraint nuevo normaliza datos existentes antes de aplicarse
- [ ] Se verificó con la query de validación después de ejecutar

**Nunca en producción sin confirmar:**
```sql
-- MAL — borra datos sin aviso
ALTER TABLE registros DROP COLUMN campo;

-- BIEN — agrega sin romper
ALTER TABLE registros ADD COLUMN IF NOT EXISTS campo text;
```

---

## Regla 6 — Respeta la arquitectura de Venta Unificada

Antes de proponer cualquier `INSERT`, verificar:

1. ¿Existe una sesión activa para este `telefono`?
2. ¿Este cambio rompe la relación `telefono → venta → líneas`?
3. ¿Estoy creando un registro huérfano cuando debería extender uno existente?

**Referencia:** `manifiesto_arquitectura.md` — Sección 2, Regla de actualización.

Si la respuesta a (1) es sí → `UPDATE` sobre la venta activa.
Si la respuesta a (2) es sí → rediseñar antes de continuar.
Si la respuesta a (3) es sí → usar `/api/agregar-linea` en vez de `/api/registrar`.

---

## Regla 7 — Surfacea conflictos, no los promedies

Si dos patrones existentes contradicen, no los mezcles.
Elige el más reciente o más probado, explica por qué, marca el otro para limpieza.

**Conflictos conocidos en Inflaboom:**
- `ventas_jugueteria` existe como excepción documentada a la Venta Unificada — no eliminar sin decisión explícita
- El campo `ninos` en `registros` almacena LineItems JSON — no crear tabla separada `lineas_venta` sin migración planificada
- `telefono` es PK en `clientes` — no agregar campo `id` numérico sin migrar todas las FK existentes

---

## Regla 8 — Lee antes de escribir

Antes de agregar código en un archivo:
1. Leer las funciones del archivo que el cambio afecta
2. Verificar si ya existe una función que hace lo mismo
3. Revisar `database_inflaboom.md` si el cambio toca Supabase

Si no entiendes por qué el código existente está estructurado de cierta forma, pregunta antes de agregar.

---

## Regla 9 — Checkpoint después de cada paso significativo

Tras completar cada paso en una tarea multi-paso, declarar:

```
✅ Hecho: [qué se completó]
✅ Verificado: [cómo se comprobó]
⏳ Falta: [qué sigue]
⚠️ Incertidumbre: [qué no está 100% confirmado]
```

No continuar desde un estado que no se puede describir de vuelta.
Si se pierde el hilo, detener y replantear.

---

## Regla 10 — Falla en voz alta

Si no se puede estar seguro de que algo funcionó, decirlo explícitamente.

**Frases prohibidas sin verificación:**
- "Migración completada" — si no se ejecutó la query de verificación
- "Tests pasaron" — si no se probó el caso límite pedido
- "Feature funciona" — si no se verificó en el sistema real

**Por defecto:** surfacea incertidumbre, no la escondas.

**Aplicado a Inflaboom:** si un cambio en `app.py` no se puede verificar sin desplegar a Render, declararlo explícitamente antes de entregar el archivo.

---

## Regla 11 — Presupuesto de contexto

Si la conversación se acerca al límite de contexto:
1. Hacer `/COMPACT` para comprimir el historial
2. Resumir el estado actual del sistema antes de continuar
3. Referenciar las bitácoras (`bitacora_v*.md`) en vez de repetir historia

**Documentos de referencia del proyecto:**
- `manifiesto_arquitectura.md` — principios de diseño
- `database_inflaboom.md` — esquema real de Supabase
- `bitacora_v1.8.md` — estado más reciente del sistema
- `CLAUDE.md` — este archivo

---

## Estado del sistema al aplicar estas reglas

| Regla | Estado en Inflaboom |
|---|---|
| Piensa antes de codear | Practicado — formalizado aquí |
| Simplicidad primero | Activo — registro en <5s como métrica |
| Cambios quirúrgicos | Activo — `str_replace` sobre bloques específicos |
| Ejecución por objetivos | Formalizado aquí |
| Cambios seguros en producción | Activo desde v1.8 |
| Venta Unificada | Activo desde v1.4 |
| Surfacea conflictos | Activo — excepciones documentadas |
| Lee antes de escribir | Activo — siempre se leen las funciones afectadas |
| Checkpoint por paso | Formalizado aquí |
| Falla en voz alta | Activo — verificaciones en cada entrega |
| Presupuesto de contexto | Activo — `/COMPACT` cuando aplica |

---

*Inflaboom — Palmira, Colombia*
*Versión: 1.0 — 9 de mayo de 2026*
