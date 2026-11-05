# Referencia: Arquitectura y Modelo de Datos — Inflaboom

## Modelo central: Venta Unificada

```
VENTA (registros)
  id · acudiente · telefono · pago · precio_total · activo
  cliente_telefono (FK) · costo_estimado · entrada · salida

  LINEA_VENTA (campo ninos — JSON array)
    id · venta_id · nombre · servicio · categoria
    precio · minutos · salida · activa · adicional · dibujo
```

**Regla de Oro:** todo cambio durante una visita activa es UPDATE, nunca INSERT paralelo.

```python
# Patrón correcto — siempre en este orden
with _lock:
    venta = ninos_activos.get(venta_id)
    venta['lineas'].append(nueva_linea)
    venta['precio_total'] += precio
sb_update('registros', {'ninos': venta['lineas'], 'precio_total': venta['precio_total']}, {'id': venta_id})
enviar_wa(venta['telefono'], mensaje)
```

---

## Tablas activas en Supabase

| Tabla | PK | FK | Notas |
|---|---|---|---|
| `clientes` | `telefono` | — | Ancla de identidad del sistema |
| `registros` | `id` (timestamp ms) | `cliente_telefono` | Venta del punto de atención |
| `eventos` | `id` serial | `cliente_telefono` | Alquileres y eventos externos |
| `productos` | `codigo_barras` | — | Catálogo de juguetería |
| `ventas_jugueteria` | `id` serial | `cliente_telefono`, `codigo_barras` | Ventas sueltas |
| `inventario` | `id` serial | — | Stock operativo |
| `gastos` | `id` serial | — | Gastos operativos |
| `usuarios` | `id` serial | — | Acceso al sistema |

**Pendientes v1.9:** `ninos`, `adultos`, `nino_adulto`

---

## Catálogo SERVICIOS

```python
SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',       'minutos': 15,  'precio': 5000,  'categoria': 'juegos'},
    'combo_30':  {'nombre': '30 minutos',       'minutos': 30,  'precio': 8000,  'categoria': 'juegos'},
    'combo_1h':  {'nombre': '1 hora',           'minutos': 60,  'precio': 13000, 'categoria': 'juegos'},
    'promo_2x1': {'nombre': 'Promo 2x1',        'minutos': 60,  'precio': 13000, 'categoria': 'juegos'},
    'arte':      {'nombre': 'Estación de arte', 'minutos': None,'precio': 6000,  'categoria': 'arte'},
}
# Pendiente: 'juguete', 'snack'
```

---

## Nombres comerciales de combos

| Key | Nombre comercial | Duración | Precio |
|---|---|---|---|
| `combo_15` | Mini | 15 min | $5.000 |
| `combo_30` | Clásico | 30 min | $8.000 |
| `combo_1h` | Full | 1 hora | $13.000 |
| `arte` | Estación de arte | Sin tiempo | $6.000 |

---

## Rutas activas (app.py)

**Registro y sesión:**
- `POST /api/registrar` — crea venta con líneas
- `POST /api/agregar-linea` — agrega servicio a venta activa
- `POST /api/retirar` — cierra venta completa
- `POST /api/retirar-linea` — retira un niño sin cerrar venta
- `POST /api/extender` — extiende tiempo de una línea
- `GET /api/activos` — ventas activas con ms_restantes por línea

**Datos:**
- `GET /api/kpis` — dashboard del día
- `GET /api/historial` — registros del día
- `GET /api/clientes` — lista de clientes
- `GET/POST /api/eventos` — gestión de eventos
- `GET/POST /api/gastos` — gastos operativos
- `GET/POST /api/inventario` — stock operativo

**Reportes:**
- `GET /api/reportes/ventas?periodo=dia|semana|mes&fecha=YYYY-MM-DD`
- `GET /api/reportes/mes?mes=YYYY-MM`

**Juguetería:**
- `GET /api/productos` — catálogo
- `GET /api/productos/buscar?codigo=X` — por código de barras
- `POST /api/productos` — crear/actualizar producto (upsert)
- `PATCH /api/productos/<codigo>` — actualizar stock/precio
- `POST /api/jugueteria/venta` — venta (activa o suelta)

**Sistema:**
- `POST /api/webhook-wa` — webhook WhatsApp (público)
- `GET /api/generate-system` — genera docs del agente

---

## Estado de implementación

| Principio | Estado |
|---|---|
| Venta Unificada | ✅ v1.4 |
| FK cliente_telefono | ✅ v1.8 |
| Flujos granulares por niño | ✅ v1.5 |
| Arte sin registro huérfano | ✅ v1.5 |
| Juguetería integrada | ✅ v1.7 |
| Reportes por período | ✅ v1.7 |
| Costos en registros/eventos | ✅ v1.8 |
| Modelo niño/adulto | 🔲 v1.9 |
| Bot WhatsApp n8n | 🔲 pendiente |
| Tiquete Ganador | 🔲 pendiente |
