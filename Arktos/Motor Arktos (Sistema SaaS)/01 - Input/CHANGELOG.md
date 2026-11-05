# CHANGELOG — Inflaboom
## Historial de versiones del sistema

> Este archivo se actualiza con cada versión o cambio significativo.
> Formato: versión → fecha → tipo de cambio → descripción.
> Referencia completa en las bitácoras individuales por versión.

---

## Convenciones

```
✅ Implementado y funcionando en producción
🔧 Corrección de bug o mejora técnica
📐 Cambio de arquitectura o modelo de datos
🎨 Cambio de UI o experiencia del operador
📋 Documentación
🔲 Diseñado, pendiente de implementar
⏸  Pausado
```

---

## [1.8.1] — 21 de mayo de 2026

### 🔧 Bug crítico corregido — orden de decoradores en 23 rutas
- `@api_key_required` estaba declarado **encima** de `@app.route` en todas las rutas protegidas
- Flask no registraba estas funciones como rutas válidas — cualquier llamada a `/api/...` caía al catch-all `/<path>` que devolvía el `index.html`
- Consecuencia visible: tab Reportes fallaba con `SyntaxError: Unexpected token '<'` (recibía HTML en vez de JSON)
- **Fix:** invertir orden en las 23 rutas afectadas → `@app.route` primero, `@api_key_required` segundo
- Este bug existía desde versiones anteriores y afectaba todas las rutas excepto las públicas

### ✅ Feature — Utilidad real del día en dashboard
- Nueva ruta `GET /api/utilidad-dia` en `app.py`
  - Lee ingresos del día desde `registros`
  - Lee gastos del día desde `gastos`
  - Retorna: ingresos, gastos, utilidad, margen (%), detalle de gastos
- Bloque visual en tab Activos (siempre visible al entrar)
  - 3 cifras: Ingresos / Gastos / Utilidad
  - Barra de margen con semáforo: verde ≥40% · amarillo 20-40% · rojo <20%
  - Estado textual: "✅ Buen día" / "⚠️ Margen ajustado" / "🔴 Día en rojo"
  - Lista de gastos registrados en el día
- Botón "+ Gasto" abre modal inline sin salir del tab operativo
  - Categorías: gasolina, peaje, operario, mantenimiento, materiales, comida, otro
  - Campo descripción opcional
  - Actualiza el bloque de utilidad inmediatamente al guardar
- Se refresca automáticamente cada 15 segundos junto con los activos

### 🔧 Robustez — manejo defensivo de respuestas
- `cargarReporte()`: ahora lee `res.text()` primero y parsea JSON manualmente — evita crash silencioso si el servidor devuelve error HTTP
- `cargarUtilidad()`: mismo patrón defensivo

---

## [1.8] — 6 de mayo de 2026

### 📐 Base de datos
- FK `cliente_telefono` agregada a `registros`, `eventos` y `ventas_jugueteria`
- Campo `costo_estimado` en `registros` (default 0)
- Campo `costo_total` en `eventos` (default 0)
- Constraint `eventos_estado_check` con 5 estados válidos: `cotizado`, `confirmado`, `en_proceso`, `finalizado`, `perdido`
- Índices creados: `idx_registros_cliente`, `idx_eventos_cliente`, `idx_eventos_estado`, `idx_ventas_jug_cliente`

### 🔧 Backend (app.py)
- `registrar_cliente_db()` ahora retorna `telefono` como FK
- `/api/registrar` incluye `cliente_telefono` y `costo_estimado` en el INSERT
- `/api/eventos` incluye `cliente_telefono` y `costo_total` en el INSERT
- `/api/jugueteria/venta` incluye `cliente_telefono` en ventas sueltas
- `_find_input_file()` actualizado para cargar `database_inflaboom.md` y `manifiesto_arquitectura.md`
- Bloque de código huérfano eliminado en `/api/extender`

### 📋 Documentación
- `database_inflaboom.md` reescrito desde cero — refleja esquema real de Supabase
- `manifiesto_arquitectura.md` creado — guía maestra para actualizaciones
- `CLAUDE.md` creado — reglas de trabajo del proyecto
- `SKILL.md` creado — skill personalizada para Claude Code
- `references/arquitectura.md` y `references/stack.md` creados como referencias técnicas

---

## [1.7] — 5 de mayo de 2026

### ✅ Módulo de reportes de ventas
- Nueva ruta `GET /api/reportes/ventas?periodo=dia|semana|mes`
- Desglose por categoría (juegos, arte, juguetería), por combo y por niño
- Ranking top 10 niños por ingresos generados
- Detalle de cada venta con líneas individuales y servicios adicionales
- Panel de reportes embebido — reemplaza link externo a `reportes.html`
- Selector de período con picker de fecha en el frontend

### ✅ Línea de juguetería completa
- Tablas `productos` y `ventas_jugueteria` creadas en Supabase
- Catálogo de productos con código de barras, precio y control de stock
- Escáner dual: lector USB (input directo) + cámara (BarcodeDetector API)
- Botón `+ Juguete` en cards de activos — agrega a venta consolidada
- Modal de venta suelta para compras sin visita al parque
- Sección catálogo en Config — registro y ajuste de stock
- Alertas de stock bajo integradas con las alertas existentes
- Precio variable por venta — catálogo es referencia, no restricción

### 🔧 Backend
- Rutas: `GET/POST /api/productos`, `GET /api/productos/buscar`, `PATCH /api/productos/<codigo>`, `POST /api/jugueteria/venta`
- `alertas_stock_db()` actualizada para incluir alertas de productos

---

## [1.6] — 3 de mayo de 2026

### 🎨 Nomenclatura comercial de combos
- Nombres oficiales: **Mini** (15 min) · **Clásico** (30 min) · **Full** (1 hora)
- Cards muestran nombre comercial grande + duración en texto secundario
- SRVS JS, selectores y opciones de historial actualizados

### 🔧 Correcciones
- Precio Estación de arte corregido a $6.000 en todo el sistema
- Cards de activos rediseñadas: layout dos columnas, botones apilados
- Temporizador en formato `Xm Ys` con colores: verde → amarillo (5 min) → rojo (2 min)
- Botón de retiro contextual: "Retirar" para 1 niño, "Retirar grupo" para 2+
- Dibujo del niño visible en card de arte: "Pintando: [nombre]"
- Campo de dibujo corregido para niños adicionales (2do en adelante)

---

## [1.5] — 30 de abril de 2026

### 🎨 UI de activos rediseñada
- Fila por línea de niño con timer, barra de progreso e info individual
- Badge visual "Arte" en líneas de categoría arte
- Botones `+ Arte`, `+ Tiempo`, `Salida` por línea individual
- Modal de arte adicional: campo dibujo + método de pago
- `getMsActual()` para descuento local de tiempo (1s entre syncs)
- Timer actualiza en tiempo real sin depender del servidor
- `getCOTime()` implementada — zona horaria Colombia UTC-5
- Nombre acudiente con etiqueta: "Acudiente: [nombre]"

### 🔧 Bug crítico resuelto
- `abrirExtender` tenía firma duplicada que rompía todo el JS
- `apiFetch` ahora envía `Content-Type: application/json` siempre
- Función `retirar(gid)` agregada (faltaba completamente)

---

## [1.4] — 29 de abril de 2026

### 📐 Refactorización — Modelo Venta + LineItems

**Cambio arquitectural más importante del proyecto.**

- Patrón POS profesional: `VENTA` como contenedor + `LINEA_VENTA` por servicio
- La venta permanece abierta hasta cierre manual del operador
- Cada línea tiene `id`, `nombre`, `servicio`, `categoria`, `precio`, `salida`, `activa`
- Campo `adicional: true` para servicios agregados después del registro inicial

### ✅ Nuevas rutas
- `POST /api/agregar-linea` — agrega servicio a venta activa sin cerrarla
- `POST /api/retirar-linea` — retira un niño sin cerrar la venta
- `/api/extender` actualizado — extiende tiempo de UNA línea específica
- `/api/activos` actualizado — devuelve `ms_restantes` por línea individual

### ✅ Casos de uso resueltos
- Niño va a arte en mitad del tiempo → línea nueva en la misma venta
- Solo algunos niños pintan → selección individual por línea
- Niño se va antes → `retirar-linea` sin afectar al grupo
- Cierre automático cuando todas las líneas se retiran

---

## [1.3] — 28 de abril de 2026

### ✅ Protección API key
- `@api_key_required` en todas las rutas operativas (15 rutas)
- `apiFetch()` en frontend envía `X-API-Key` automáticamente
- Webhook WhatsApp queda público (Meta no envía la key)
- Variable `API_KEY` en Render Environment

### 🔧 Correcciones
- Archivo `.env` con credenciales eliminado de GitHub (era público)
- Variables movidas a Render Environment
- Encoding UTF-8 corregido en todo el `index.html` (19 categorías de caracteres corruptos)
- Ruta `/` corregida: Flask ahora sirve `index.html` con `charset=utf-8` explícito

---

## [1.2] — 23-25 de abril de 2026

### 🔧 Tres bugs críticos resueltos

**Bug 1 — Reloj con tiempo incorrecto**
- Timer mostraba siempre +360 minutos sin importar el combo
- Causa: todos los niños compartían la misma `salida` del grupo
- Fix: cada niño tiene su propia `salida` calculada desde su combo

**Bug 2 — Agrupación con tiempos independientes**
- `/api/activos` ahora devuelve `ms_restantes` dentro de cada niño
- Cards muestran timer individual por niño dentro del grupo

**Bug 3 — Sin autenticación**
- Primer intento: Flask-Login + tabla `usuarios` en Supabase
- Problema: conflicto de versiones `werkzeug` entre PC y Render
- Decisión final: reemplazado por API key (más simple, sin dependencias)

### 🎨 Frontend
- Combo individual por niño (2do en adelante tiene su propio selector)
- Precios completos en selectores: `1 hora — $13.000` en vez de `13k`

---

## [1.1] — 18 de abril de 2026

### 📐 Diseño del modelo niño/adulto
- Modelo relacional: `Adulto` + `Nino` + tabla puente `nino_adulto`
- Teléfono del adulto como ancla de búsqueda
- Relación M:N entre niños y adultos (un niño puede tener varios adultos)
- Solución al "sesgo del sobrino" documentada

### 🎨 Flujo de registro progresivo
- Momento 1 (caja): teléfono + nombre + edad — 30 segundos
- Momento 2 (WhatsApp post-visita): cumpleaños + datos adicionales
- Momento 3 (visitas siguientes): preferencias y contexto social

### ✅ Programa Tiquete Ganador — diseñado
| Etapa | Tiquetes | Premio |
|---|---|---|
| 1 — Mini | 4 | Hora extra de juego |
| 2 — Aventurero | 8 | Entrada gratis |
| 3 — Campeón | 12 | Trampolín 1h en parque |
| 4 — Leyenda | 18 | 50% descuento alquiler |
| 5 — Inflaboom VIP | 28 | Alquiler 100% cubierto |

Regla: tiquete solo con combo de $13.000+. Máximo 1 premio mayor por mes.

### 📐 Decisión: n8n reemplaza Twilio
- Stack: `Flask → n8n → Meta Cloud API (WhatsApp)`
- 5 flujos diseñados para eventos y alquileres
- 6 flujos diseñados para punto de atención

---

## [1.0] — Versión inicial

### ✅ Sistema base funcionando
- Registro de niños en punto de atención (planilla digital)
- Timers con alertas WhatsApp (5 min antes + al finalizar)
- Dashboard de KPIs diarios
- Historial de ventas
- Gestión de inventario (manillas, pinturas)
- Gestión de gastos operativos
- Módulo de eventos y alquileres básico
- Agente IA en WhatsApp (claude-haiku) con contexto del negocio
- Deploy en Render con autodeploy desde GitHub

---

## Estado actual del sistema

| Línea de negocio | Registro | Reporte | Inventario | FK cliente |
|---|---|---|---|---|
| Zona de juegos | ✅ | ✅ | ✅ | ✅ |
| Estación de arte | ✅ | ✅ | ✅ | ✅ |
| Juguetería | ✅ | ✅ | ✅ | ✅ |
| Snacks | 🔲 | 🔲 | 🔲 | 🔲 |
| Eventos y alquileres | ✅ básico | 🔲 desglose | 🔲 | ✅ |
| Paquetes empresariales | 🔲 | 🔲 | — | 🔲 |

---

## Próximas versiones planificadas

### [1.8.x] — Fase 1 completa
- Fase 1.2: Precios base de eventos + calculadora de cotización
- Fase 1.3: Resumen diario automático por WhatsApp al dueño

### [1.9] — Modelo niño/adulto
- Tablas `ninos`, `adultos`, `nino_adulto` en Supabase
- Identificación persistente de niños entre visitas
- Resolución definitiva del sesgo del sobrino

### [2.0] — Automatización WhatsApp
- n8n + Meta Cloud API conectados
- Bot post-visita completa perfil del niño progresivamente
- Seguimiento: encuesta, cumpleaños, reactivación a 21 días

### [2.1] — Tiquete Ganador
- Acumulación automática de tiquetes por combo $13.000+
- Notificación de progreso por WhatsApp tras cada visita
- Gestión de premios desde el panel admin

---

*Inflaboom — Palmira, Colombia*
*Actualizar este archivo con cada versión desplegada en producción*
