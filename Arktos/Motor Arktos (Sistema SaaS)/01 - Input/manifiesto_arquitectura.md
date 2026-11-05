# Manifiesto de Arquitectura — Inflaboom
## Guía maestra para actualizaciones, refactorizaciones y nuevas funcionalidades

> Toda IA o desarrollador que trabaje en este sistema debe leer este documento antes de proponer cualquier cambio.

---

## 1. Filosofía de la Venta Unificada

El sistema no gestiona tickets aislados. Gestiona **Experiencias de Grupo**.

### Estado actual (implementado en v1.4)

```
VENTA (contenedor abierto)
  └── id, acudiente, telefono, pago, precio_total, activo

  LINEA_VENTA (un servicio por niño)
    └── id, venta_id, nombre, servicio, categoria
    └── precio, minutos, salida, activa, adicional
```

La venta permanece abierta hasta que el operador la cierre manualmente. Cada línea tiene su propio ciclo de vida independiente.

### Regla de Oro

> Si un niño cambia de actividad, el sistema extiende la venta actual — nunca crea un registro huérfano.

**Correcto:**
```python
# Buscar venta activa del adulto y agregar línea
venta = ninos_activos.get(venta_id)
venta['lineas'].append(nueva_linea)
venta['precio_total'] += precio
sb_update('registros', {'ninos': venta['lineas'], 'precio_total': venta['precio_total']}, {'id': venta_id})
```

**Incorrecto:**
```python
# Nunca crear un registro paralelo para el mismo grupo
sb_insert('registros', {'telefono': telefono, ...})  # ← esto rompe la unificación
```

---

## 2. Estructura de la Verdad

### Jerarquía de entidades

```
Adulto (telefono = ancla financiera y de identidad)
  └── Venta (precio_total = suma de todas las líneas)
        └── Líneas (cada servicio consumido por cada niño)
```

### Identidad del adulto

El **teléfono del adulto** es el identificador único que atraviesa todo el sistema:

| Tabla | Campo | Propósito |
|---|---|---|
| `clientes` | `telefono` (PK) | Perfil del adulto con historial |
| `registros` | `telefono` + `cliente_telefono` | Venta del día vinculada al cliente |
| `eventos` | `telefono` + `cliente_telefono` | Evento vinculado al cliente |
| `ventas_jugueteria` | `cliente_telefono` | Compra suelta vinculada al cliente |

### Regla de actualización

Antes de proponer un `INSERT`, verificar:

```python
# ¿Existe una venta activa para este teléfono?
venta_activa = next(
    (v for v in ninos_activos.values() if v['telefono'] == telefono),
    None
)

if venta_activa:
    # UPDATE — agregar línea a la venta existente
    venta_activa['lineas'].append(nueva_linea)
else:
    # INSERT — crear nueva venta solo si no hay sesión abierta
    ninos_activos[venta_id] = nueva_venta
```

---

## 3. Lógica de Interfaz y UX

### Flujos granulares (implementado)

Cada niño dentro de un grupo tiene sus propios controles independientes. Nunca se asume que una acción aplica a todos.

| Botón | Acción | Alcance |
|---|---|---|
| `+ Arte` | Agrega línea de arte | Solo ese niño |
| `+ Juguete` | Agrega línea de juguetería | Solo ese niño |
| `+ Tiempo` | Extiende el timer | Solo esa línea |
| `Salida` | Cierra esa línea | Solo ese niño |
| `Retirar grupo` | Cierra toda la venta | Todos los niños |

### Salto de actividad (implementado parcialmente — v1.5)

Cuando un niño termina una actividad y pasa a otra:

- **Hoy:** El operador toca `+ Arte` o `+ Juguete` en la card del niño. Se agrega una nueva línea a la misma venta sin interrumpir otros timers.
- **Pendiente:** Flujo explícito de "Mover a Estación de Arte" con botón contextual que aparece cuando el timer llega a 0.

### Visibilidad de consumo (implementado en reporte — v1.7)

Antes de cerrar una venta el operador puede ver en la card:
```
Acudiente: Laura
Efectivo | entrada 04:21 p.m. | $27.000
  ├── Bravo      Clásico | sale 04:51     13m 22s   [+ Arte] [+ Juguete] [+ Tiempo] [Salida]
  └── Santiago   Arte    | Pintando: Spiderman               [+ Tiempo] [Salida]
```

En el módulo de Reportes el desglose completo muestra quién consumió qué con el precio individual de cada línea.

---

## 4. Protocolo para actualizaciones de código

Antes de implementar cualquier cambio, responder estas preguntas:

### Checklist de impacto

- [ ] ¿Este cambio rompe la relación entre `telefono` del adulto y el gasto de los niños?
- [ ] ¿Estoy creando un `INSERT` cuando debería hacer un `UPDATE` sobre una venta activa?
- [ ] ¿Los datos de múltiples niños están en formato JSON/Array para permitir selección individual posterior?
- [ ] ¿El campo nuevo en Supabase usa `ADD COLUMN IF NOT EXISTS` para no romper datos existentes?
- [ ] ¿El campo nuevo es opcional (`NULL` permitido) o tiene un valor por defecto seguro?

### Catálogo de categorías válidas en LineItems

```python
CATEGORIAS = {
    'juegos':      ['combo_15', 'combo_30', 'combo_1h', 'promo_2x1'],
    'arte':        ['arte'],
    'jugueteria':  ['juguete'],
    'snacks':      ['snack'],          # pendiente de implementar
}
```

### Rutas protegidas

Todas las rutas operativas requieren `@api_key_required`. Las únicas rutas públicas son:
- `GET /` — sirve el index.html
- `GET /<path>` — archivos estáticos
- `POST /api/webhook-wa` — webhook de WhatsApp (autenticado por Twilio/Meta)

---

## 5. Protocolo de debug

Si una solución A genera el problema B:

### Diagnóstico rápido

1. ¿Se perdió el `venta_id` o el `telefono` entre el frontend y el backend?
2. ¿La línea tiene su propio `id` único o comparte el del grupo?
3. ¿El `precio_total` de la venta se actualizó después del cambio?
4. ¿El campo `activa` de la línea refleja el estado correcto?

### Patrón correcto de extensión de venta

```python
# Toda modificación a una venta activa sigue este patrón
with _lock:
    venta = ninos_activos.get(venta_id)
    if not venta:
        return jsonify({'ok': False, 'error': 'Venta no encontrada'}), 404
    # 1. Modificar en memoria
    venta['lineas'].append(nueva_linea)
    venta['precio_total'] += precio
# 2. Persistir en Supabase
sb_update('registros', {
    'ninos':        venta['lineas'],
    'precio_total': venta['precio_total'],
}, {'id': venta_id})
# 3. Notificar al cliente
enviar_wa(venta['telefono'], mensaje)
```

---

## 6. Estado de implementación por principio

| Principio | Estado |
|---|---|
| Venta unificada (una venta por grupo) | ✅ Implementado v1.4 |
| Teléfono como ancla de identidad | ✅ Implementado v1.1 |
| FK cliente_telefono en todas las tablas | ✅ Implementado v1.8 |
| Flujos granulares por niño | ✅ Implementado v1.5 |
| Arte adicional sin registro huérfano | ✅ Implementado v1.5 |
| Juguetería integrada a venta activa | ✅ Implementado v1.7 |
| Visibilidad de consumo en reportes | ✅ Implementado v1.7 |
| Salto de actividad con botón contextual | 🔲 Parcial — falta flujo cuando timer llega a 0 |
| Modelo niño con perfil persistente | 🔲 Pendiente v1.9 |
| Bot WhatsApp completa perfil del niño | 🔲 Pendiente v1.9 |
| Tiquete Ganador sobre historial del niño | 🔲 Pendiente v1.9 |

---

## 6. Entidad Central: Sesión de Venta

> **Estado:** Implementado parcialmente — requiere decisión de negocio para completar.

Toda interacción durante una visita al parque pertenece a una **Sesión de Venta** activa.

### Qué agrupa una sesión

```
Sesión de Venta
  ├── Adulto responsable (telefono)
  ├── Niños (beneficiarios)
  ├── Servicios (juegos, arte, tiempo extra)
  ├── Consumos (juguetes, snacks)
  └── Estado: activa | cerrada
```

### Regla principal

No se crean registros paralelos para el mismo grupo mientras la sesión está activa. Todo se agrega como `LINEA_VENTA` a la sesión existente.

### Excepción documentada: ventas sueltas

Hoy existe la tabla `ventas_jugueteria` para compras sin visita al parque (un padre que solo compra un juguete). Estas ventas sueltas son la única excepción a la regla — no pertenecen a una sesión porque no hay visita.

**Decisión pendiente:** si se quiere eliminar esta excepción, se debe crear una "sesión mínima" para ventas sin tiempo de juego. Hasta que se tome esa decisión, las ventas sueltas se mantienen como caso separado documentado.

---

## 7. Lógica de Utilidad

> **Estado:** Campos migrados en v1.8 — lógica de cálculo pendiente de implementar.

Cada acción registrada debe tener impacto financiero medible.

### Campos disponibles en base de datos

| Tabla | Campo ingreso | Campo costo | Utilidad calculada |
|---|---|---|---|
| `registros` | `precio_total` | `costo_estimado` | `precio_total - costo_estimado` |
| `eventos` | `precio_total` | `costo_total` | `precio_total - costo_total` |
| `ventas_jugueteria` | `precio_venta * cantidad` | — (pendiente) | — |

### Regla

No se registra ninguna venta sin precio definido. El costo es opcional en el momento del registro pero debe completarse para que los reportes de utilidad sean precisos.

### Implementación pendiente

```python
# En /api/reportes/ventas — agregar utilidad al resumen
'resumen': {
    'total_ingresos':  total_ingresos,
    'total_costos':    total_costos,      # suma de costo_estimado
    'utilidad_bruta':  total_ingresos - total_costos,
    'margen':          round((total_ingresos - total_costos) / total_ingresos * 100, 1)
}
```

---

## 8. Automatización y Conversión de Datos en Ventas

> **Estado:** Diseñado — pendiente de implementar (requiere n8n + modelo niño/adulto).

Los datos acumulados deben convertirse en acciones comerciales automáticas.

### Tres niveles de automatización

**Nivel 1 — Seguimiento post-visita (inmediato tras cada sesión)**
- Encuesta de satisfacción por WhatsApp 20 minutos después del cierre
- Mensaje de cumpleaños 15 días antes con oferta de paquete
- Reactivación si no hay visita en 21 días

**Nivel 2 — Promociones por comportamiento (semanal)**
- Si un niño siempre elige el combo Mini → ofrecer upgrade a Clásico con descuento
- Si una familia nunca ha probado arte → enviar oferta de primera vez
- Si un cliente compra juguetes frecuentemente → notificar cuando llega nuevo stock

**Nivel 3 — Clasificación de clientes (mensual)**

| Segmento | Criterio | Acción |
|---|---|---|
| VIP | +8 visitas/mes o +$100k/mes | Acceso anticipado a eventos, descuentos |
| Frecuente | 4-7 visitas/mes | Tiquete Ganador doble en fechas especiales |
| Ocasional | 1-3 visitas/mes | Campaña de reactivación mensual |
| Inactivo | Sin visita en 30+ días | Oferta de regreso con incentivo |

### Dependencias antes de implementar

- [ ] Modelo niño/adulto en Supabase (perfiles persistentes)
- [ ] n8n conectado a Meta Cloud API
- [ ] Campo `segmento` en tabla `clientes`
- [ ] Cron job en n8n para clasificación mensual automática

### Regla

Los datos solo generan valor si se convierten en acción. Un reporte que nadie lee no sirve. Una automatización que envía el mensaje correcto en el momento correcto sí sirve.

---

## Estado de implementación por principio (actualizado)

| Principio | Estado |
|---|---|
| Venta unificada (una venta por grupo) | ✅ v1.4 |
| Teléfono como ancla de identidad | ✅ v1.1 |
| FK cliente_telefono en todas las tablas | ✅ v1.8 |
| Flujos granulares por niño | ✅ v1.5 |
| Arte adicional sin registro huérfano | ✅ v1.5 |
| Juguetería integrada a venta activa | ✅ v1.7 |
| Visibilidad de consumo en reportes | ✅ v1.7 |
| Campos costo en registros y eventos | ✅ v1.8 |
| Sesión de venta con estado activa/cerrada | 🔲 Parcial — falta campo estado en registros |
| Cálculo de utilidad bruta en reportes | 🔲 Pendiente |
| Salto de actividad con botón contextual | 🔲 Parcial |
| Seguimiento post-visita por WhatsApp | 🔲 Pendiente n8n |
| Clasificación VIP/frecuente/ocasional | 🔲 Pendiente modelo niño/adulto |
| Tiquete Ganador | 🔲 Pendiente n8n |
| Modelo niño con perfil persistente | 🔲 Pendiente v1.9 |

---

*Inflaboom — Palmira, Colombia*
*Versión del manifiesto: 1.1 — 6 de mayo de 2026*
*Actualizar este documento con cada versión mayor del sistema*
