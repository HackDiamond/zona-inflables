# ROADMAP — INFLABOOM / ARKTOS OS
## Priorizado por impacto en ingresos y operación

> Criterio de priorización: ¿Qué genera más dinero o ahorra más tiempo?
> Última actualización: 21 de mayo de 2026

---

## Principio de priorización

```
Impacto en ingresos   >   Ahorro de tiempo   >   Mejora técnica
```

Ningún feature entra al roadmap sin responder: **¿cuánto dinero adicional genera o cuánto costo elimina?**

---

## 🔴 FASE 1 — Dinero inmediato (0–4 semanas)
*Features que generan o protegen ingresos esta semana*

### ✅ 1.1 — Utilidad real diaria visible en dashboard
**Completado: 21 de mayo de 2026**

- Ruta `GET /api/utilidad-dia` en backend
- Bloque visual en tab Activos: ingresos / gastos / utilidad / barra semáforo
- Modal gasto rápido "+ Gasto" integrado en la operación
- Semáforo: verde ≥40% · amarillo 20-40% · rojo <20%
- Refresco automático cada 15 segundos

**Bug corregido en la misma sesión:** orden de decoradores `@app.route` / `@api_key_required` invertido en 23 rutas — los reportes y otras rutas no funcionaban desde versiones anteriores.

---

### 1.2 — Precios reales de servicios de eventos
**Impacto:** Sin precios base definidos, cada cotización sale de la intuición. Definir precios mínimos por ítem permite cotizar más rápido, evitar pérdidas y escalar el módulo de eventos.

**Qué implementar:**
- Tabla de precios base por servicio en `conocimiento_inflaboom.md` (trabajo de negocio, no de código)
- Calculadora de cotización en el módulo de Eventos: seleccionar servicios → precio sugerido automático
- Campo `precio_sugerido` calculado en el formulario de nuevo evento

**Esfuerzo:** 1 sesión de negocio (definir precios) + 2-3 horas de código

---

### 1.3 — Resumen diario automático por WhatsApp al dueño
**Impacto:** Al cerrar el día, recibes en WhatsApp: ingresos totales, niños atendidos, gastos del día, utilidad estimada. Sin abrir el sistema. Tomas decisiones desde el celular.

**Qué implementar:**
- Ruta `GET /api/resumen-dia` que retorna resumen estructurado del día
- Botón "Cerrar día" en tab Activos que envía el resumen al número del dueño vía WhatsApp
- Mensaje formateado: ingresos / gastos / utilidad / margen / niños atendidos / eventos del día

**Esfuerzo:** 2-3 horas | **Archivos:** `app.py`, `index.html`

---

## 🟠 FASE 2 — Retención y recurrencia (1–2 meses)
*Features que traen clientes de vuelta*

### 2.1 — Migración Twilio → Meta Business API
**Impacto:** Con Twilio Sandbox solo puedes enviar mensajes a números que han hecho opt-in. Con Meta Business API puedes contactar a cualquier cliente. Esto desbloquea todas las automatizaciones de seguimiento.

**Bloqueante para:** 2.2, 2.3, 2.4, todo el módulo de fidelización.

**Esfuerzo:** 1 sesión técnica (configuración Meta) + ajuste en `app.py`

---

### 2.2 — Seguimiento post-visita automático
**Impacto directo en recurrencia.** Un mensaje 3 días después de la visita con una oferta específica puede traer de vuelta entre 15-25% de clientes que no volverían solos.

**Flujo:**
1. Visita termina → se registra fecha en `clientes.ultimo_visita`
2. A los 3 días → mensaje: "¡Hola [nombre]! ¿Cómo está [niño]? Este sábado tenemos promo 2x1..."
3. A los 21 días sin visita → mensaje de reactivación con oferta

**Requiere:** Meta Business API (2.1) + n8n o cron en app.py

**Esfuerzo:** 2-3 sesiones | **Alto impacto**

---

### 2.3 — Modelo niño/adulto (perfiles persistentes)
**Impacto:** Hoy no sabes cuántas veces vino "Mateo" específicamente, solo cuántas veces llamó el teléfono de su mamá. Con perfiles de niños puedes personalizar mensajes, medir qué combos prefiere, y activar el Tiquete Ganador.

**Tablas a crear:**
```sql
ninos (id, nombre, fecha_nacimiento)
adultos (telefono PK, nombre)
nino_adulto (nino_id, adulto_id, relacion)
```

**Esfuerzo:** 1 sesión técnica (migración BD + ajuste registro) | v1.9

---

### 2.4 — Tiquete Ganador (fidelización)
**Impacto:** Programa de lealtad probado en negocios de recreación. Cada combo $13.000+ = 1 tiquete. A 12 tiquetes = entrada gratis. Genera recurrencia y diferenciación competitiva.

**Regla de negocio:**
| Etapa | Tiquetes | Premio |
|---|---|---|
| Mini Aventurero | 4 | 1 hora extra de juego |
| Aventurero | 8 | Entrada gratis |
| Campeón | 12 | Trampolín 1h en parque |
| Leyenda | 18 | 50% desc. alquiler |
| Inflaboom VIP | 28 | Alquiler 100% cubierto |

**Requiere:** Modelo niño/adulto (2.3) + Meta Business API (2.1)

---

## 🟡 FASE 3 — Escala y nuevos ingresos (2–4 meses)
*Features que abren nuevas líneas de ingresos*

### 3.1 — Módulo de paquetes empresariales
**Impacto:** Colegios, empresas y entidades son el segmento de mayor ticket. Un evento empresarial puede valer $500k-$2M. Sin un módulo de cotización estructurado, se pierden ventas por falta de respuesta rápida.

**Qué implementar:**
- Formulario de cotización con catálogo de servicios y precios base
- Generación de propuesta en PDF descargable
- Seguimiento de estado (enviada → vista → aceptada → ejecutada)
- Registro automático en cliente si acepta

---

### 3.2 — Clasificación automática de clientes (VIP/Frecuente/Ocasional/Inactivo)
**Impacto:** Permite enviar mensajes diferentes a cada segmento. VIPs reciben acceso anticipado a eventos. Inactivos reciben oferta de regreso. Frecuentes reciben el Tiquete Ganador doble en fechas especiales.

| Segmento | Criterio | Acción automática |
|---|---|---|
| VIP | +8 visitas/mes o +$100k/mes | Acceso anticipado, descuentos exclusivos |
| Frecuente | 4-7 visitas/mes | Tiquete Ganador doble en fechas especiales |
| Ocasional | 1-3 visitas/mes | Campaña de reactivación mensual |
| Inactivo | Sin visita en 30+ días | Oferta de regreso con incentivo |

---

### 3.3 — Dashboard de rentabilidad por línea de negocio
**Impacto:** Responde la pregunta más importante del negocio: ¿qué línea genera más utilidad neta (no solo ingresos)? Puede revelar que los eventos dan más dinero que el punto físico, o lo contrario.

**Métricas a mostrar:**
- Ingresos por línea (punto físico / eventos / juguetería)
- Costos asociados por línea
- Utilidad bruta y margen por línea
- Tendencia semana a semana

---

### 3.4 — Login por roles (admin / operario)
**Impacto operativo:** Permite delegar operación del punto físico a un empleado sin darle acceso a finanzas, configuración o reportes históricos.

**Roles:**
- `admin` (Breycod): acceso total
- `operario`: solo registrar ventas, ver activos e inventario

**Requiere:** Tabla `usuarios` ya existe en Supabase.

---

## 🔵 FASE 4 — Optimización continua (en curso)
*Mejoras basadas en datos reales de operación*

- Optimización del flujo de cotización de eventos (reducir tiempo de respuesta)
- A/B de mensajes WhatsApp (qué mensaje convierte más)
- Análisis de combos más rentables (precio × volumen × costo)
- Módulo de snacks con control de inventario y caja
- App offline-first para punto físico (funcionamiento sin internet)

---

## 📊 Métricas de éxito del roadmap

| Fase | Métrica objetivo |
|---|---|
| Fase 1 | Conocer utilidad real del día en menos de 30 segundos ✅ |
| Fase 2 | Tasa de retorno de clientes > 30% en 30 días |
| Fase 3 | Al menos 2 eventos empresariales por mes cerrados vía el sistema |
| Fase 4 | Decisiones semanales basadas en datos, no intuición |

---

## ⚡ Siguiente acción recomendada

**Hoy:** Fase 1.3 — Resumen diario por WhatsApp al dueño.

Con la utilidad ya visible en pantalla (1.1 ✅), el siguiente paso natural es recibirla en WhatsApp al cerrar el día — sin tener que abrir el sistema. Esfuerzo bajo, impacto inmediato en control del negocio.

Alternativa si primero quieres datos más sólidos: Fase 1.2 — definir precios base de eventos para cotizar más rápido y cerrar más ventas de alto ticket.

---

*Inflaboom — Palmira, Colombia*
*Actualizar este roadmap cuando se complete un ítem o cambie la prioridad estratégica*
