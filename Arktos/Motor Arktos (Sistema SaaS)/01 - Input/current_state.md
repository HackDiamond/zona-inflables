# CURRENT STATE — INFLABOOM / ARKTOS OS
## Estado real del sistema · Actualizar después de cada sesión significativa

> Este archivo es la fuente de verdad del estado actual.
> Leer al inicio de cada sesión. Actualizar al cerrar.
> Última actualización: 21 de mayo de 2026

---

## 🟢 Sistema en producción

**URL:** Render (autodeploy desde GitHub)
**Versión activa:** 1.8.1
**Estado general:** Operativo con datos reales

---

## ✅ Módulos funcionando

### Punto de atención
- Registro de ventas con grupos de niños
- Timers individuales por línea (con alertas 5 min antes)
- Mensajes WhatsApp automáticos: bienvenida, recibo, aviso, fin, despedida
- Extensión de tiempo por línea individual
- Retiro individual (sin cerrar la venta del grupo)
- Agregado de arte adicional en mitad de visita
- Venta de juguetes vinculada a visita activa

### Dashboard y reportes
- KPIs del día: ingresos, niños atendidos, efectivo vs transferencia
- **Utilidad del día: ingresos / gastos / utilidad / barra semáforo (verde ≥40% · amarillo 20-40% · rojo <20%)** ← nuevo v1.8.1
- **Botón "+ Gasto" en tab Activos: registro rápido sin salir de la operación** ← nuevo v1.8.1
- Reporte por período: día / semana / mes
- Desglose por categoría (juegos, arte, juguetería)
- Desglose por combo (Mini, Clásico, Full)
- Ranking de niños por ingresos
- Historial de ventas del día

### Inventario
- Stock operativo: manillas, pinturas, pinceles, dibujos por personaje
- Alertas de stock bajo
- Descuento automático al registrar venta

### Clientes
- Upsert automático en cada visita
- Contador de visitas y total gastado
- Historial visible en el agente WhatsApp

### Eventos y alquileres
- Registro de cotizaciones con estado (cotizado → confirmado → finalizado)
- Campos: cliente, fecha, lugar, servicios, precio, anticipo, costo
- FK a tabla clientes

### Juguetería
- Catálogo con código de barras, precio y stock
- Escáner USB + cámara (BarcodeDetector API)
- Venta vinculada a visita activa o venta suelta
- Ajuste de stock desde Config

### Agente WhatsApp "Boom"
- Modelo: `claude-haiku-4-5-20251001`
- Maneja: consultas de servicios, precios, horarios, cotizaciones de eventos
- Contexto en tiempo real: estado del niño activo, historial del cliente
- Respuestas 1 y 2 para extender/retirar tiempo

---

## 🟡 Implementado parcialmente

| Feature | Estado | Bloqueado por |
|---|---|---|
| Flujo de salto de actividad | Parcial — falta botón contextual cuando timer llega a 0 | Decisión de UX |
| Estado `activa/cerrada` en registros | Sin campo `estado` formal | Migración pendiente |

---

## 🔲 Sin implementar

| Feature | Versión | Prioridad |
|---|---|---|
| Resumen diario por WhatsApp al dueño | v1.8.x (Fase 1.3) | Alta |
| Precios base de eventos + calculadora cotización | v1.8.x (Fase 1.2) | Alta |
| Modelo niño/adulto (perfiles persistentes) | v1.9 | Alta |
| Migración Twilio → Meta Business API | v2.0 | Alta |
| Bot post-visita con n8n | v2.0 | Alta |
| Seguimiento automático (encuesta, reactivación) | v2.0 | Media |
| Tiquete Ganador (fidelización) | v2.1 | Media |
| Clasificación VIP/frecuente/ocasional | v2.1 | Media |
| Módulo de snacks | v2.x | Baja |
| Paquetes empresariales (cotización estructurada) | v2.x | Media |
| Login por roles (admin/operario) | v2.x | Media |

---

## 🗄️ Base de datos (Supabase)

### Tablas activas
| Tabla | Estado | Registros aprox |
|---|---|---|
| `clientes` | ✅ Activa | Creciendo |
| `registros` | ✅ Activa | Creciendo |
| `eventos` | ✅ Activa | Creciendo |
| `productos` | ✅ Activa | Manual |
| `ventas_jugueteria` | ✅ Activa | Creciendo |
| `inventario` | ✅ Activa | Manual |
| `gastos` | ✅ Activa | Creciendo |
| `usuarios` | ✅ Activa | 1 (admin) |

### Tablas pendientes
- `ninos`, `adultos`, `nino_adulto` — v1.9
- `seguimientos` — v2.0

---

## 🔗 Integraciones activas

| Servicio | Estado | Notas |
|---|---|---|
| Supabase | ✅ Activo | PostgreSQL en producción |
| Twilio WhatsApp | ✅ Activo | Sandbox — número +1 415 523 8886 |
| Anthropic API | ✅ Activo | claude-haiku-4-5 para agente Boom |
| Render | ✅ Activo | Autodeploy desde GitHub |
| Meta Business API | 🔲 Pendiente | Reemplazará Twilio Sandbox |
| n8n | 🔲 Pendiente | Orquestador de automatizaciones |

---

## 💸 Deuda técnica conocida

| Deuda | Impacto | Prioridad de pago |
|---|---|---|
| Sin login por sesión (solo API key) | Seguridad media | Media — antes de abrir a operarios |
| `ninos` como JSON en `registros` | No permite queries por niño | Alta — bloquea fidelización |
| Twilio Sandbox (límite de números) | Solo números verificados pueden recibir mensajes | Alta — bloquea escala |
| Sin campo `estado` formal en `registros` | Reportes de utilidad incompletos | Media |
| `costo_estimado` no se llena en operación | Margen real desconocido | Media — ahora visible en dashboard |
| `/api/productos/buscar` llama con slash final en un caso | Puede dar 404 en Render | Baja |

---

## 📊 Métricas clave (llenar con datos reales)

| Métrica | Valor actual | Objetivo |
|---|---|---|
| Ticket promedio punto físico | Por definir | $11.000+ |
| Niños atendidos / fin de semana | Por definir | — |
| % ventas en transferencia | Por definir | — |
| Conversión WhatsApp → evento | Por definir | — |
| Eventos confirmados / mes | Por definir | — |
| Margen operativo día típico | Por definir | ≥40% |

---

## 🔧 Última sesión de desarrollo

**Fecha:** 21 de mayo de 2026
**Cambios:**
- ✅ Bug crítico corregido: orden de decoradores `@api_key_required` / `@app.route` invertido en 23 rutas — Flask no las registraba, devolvía HTML en lugar de JSON
- ✅ Nueva ruta `GET /api/utilidad-dia` en `app.py`
- ✅ Bloque utilidad del día en tab Activos (ingresos / gastos / utilidad / barra semáforo)
- ✅ Modal gasto rápido "+ Gasto" integrado en dashboard operativo
- ✅ `cargarReporte` y `cargarUtilidad` con manejo defensivo de respuestas no-JSON

**Commit sugerido:** `fix: orden decoradores 23 rutas + feat: utilidad diaria en dashboard`
**Próxima sesión:** Fase 1.3 — Resumen diario por WhatsApp, o Fase 1.2 — Precios base de eventos

---

*Actualizar este archivo al cerrar cada sesión con: fecha, cambios realizados, commit, próxima tarea.*
