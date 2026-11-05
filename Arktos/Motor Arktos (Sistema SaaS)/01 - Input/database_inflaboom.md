# DATABASE — INFLABOOM
## Esquema real de Supabase · Versión 1.8 · 6 de mayo de 2026

> ⚠️ Este archivo debe actualizarse cada vez que se ejecute una migración en Supabase.
> No modificar manualmente sin ejecutar primero el SQL correspondiente.
> Historial de versiones al final del documento.

---

## 🎯 Objetivo

Estructurar la base de datos para:
- Controlar ingresos y gastos por línea de negocio
- Registrar ventas en menos de 5 segundos
- Medir rentabilidad real (ingreso − costo = utilidad)
- Gestionar clientes, niños y eventos
- Automatizar seguimiento post-visita

---

## 🗂️ Índice de tablas

| Tabla | Propósito | Estado |
|---|---|---|
| `clientes` | Perfil del adulto responsable | ✅ Activa |
| `registros` | Ventas del punto de atención | ✅ Activa |
| `eventos` | Alquileres y eventos externos | ✅ Activa |
| `productos` | Catálogo de juguetería | ✅ Activa |
| `ventas_jugueteria` | Ventas sueltas sin visita | ✅ Activa |
| `inventario` | Stock operativo (manillas, pinturas) | ✅ Activa |
| `gastos` | Gastos operativos | ✅ Activa |
| `usuarios` | Acceso al sistema | ✅ Activa |
| `ninos` | Perfiles persistentes de niños | 🔲 Pendiente v1.9 |
| `adultos` | Adultos vinculados a niños | 🔲 Pendiente v1.9 |
| `nino_adulto` | Relación niño ↔ adulto | 🔲 Pendiente v1.9 |
| `seguimientos` | Automatización WhatsApp | 🔲 Pendiente v2.0 |

---

## 🧍 Tabla: `clientes`

Perfil del adulto responsable. Identificado por teléfono (clave natural del negocio).

```sql
create table clientes (
  telefono       text primary key,
  nombre         text,
  visitas        integer default 0,
  total_gastado  integer default 0,
  ultimo_visita  timestamptz,
  created_at     timestamptz default now()
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `telefono` | text PK | Identificador único — ancla de todo el sistema |
| `nombre` | text | Nombre del adulto responsable |
| `visitas` | integer | Contador de visitas acumuladas |
| `total_gastado` | integer | Suma histórica de todas las ventas |
| `ultimo_visita` | timestamptz | Fecha de la última visita |
| `created_at` | timestamptz | Fecha de registro en el sistema |

**Notas:**
- `telefono` es la FK referenciada por `registros`, `eventos` y `ventas_jugueteria`
- Se actualiza automáticamente en cada visita vía `registrar_cliente_db()`
- Clasificación VIP/frecuente/ocasional pendiente de campo `segmento` (v1.9)

---

## 💰 Tabla: `registros`

Ventas del punto de atención físico. Cada registro es una **Sesión de Venta** completa.

```sql
create table registros (
  id               text primary key,
  acudiente        text,
  telefono         text,
  pago             text,
  ninos            jsonb,
  precio_total     integer default 0,
  entrada          timestamptz,
  salida           timestamptz,
  activo           boolean default true,
  servicio         text,
  cliente_telefono text references clientes(telefono),
  costo_estimado   integer default 0
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | text PK | Timestamp en ms — generado por Flask |
| `acudiente` | text | Nombre del adulto responsable |
| `telefono` | text | Teléfono del adulto |
| `pago` | text | Efectivo / Nequi / Transferencia |
| `ninos` | jsonb | Array de LineItems (ver estructura abajo) |
| `precio_total` | integer | Suma de todas las líneas |
| `entrada` | timestamptz | Hora de ingreso al parque |
| `salida` | timestamptz | Hora de salida (la más tardía de las líneas) |
| `activo` | boolean | `true` mientras la sesión está abierta |
| `servicio` | text | Servicio del primer niño (compatibilidad) |
| `cliente_telefono` | text FK | Referencia a `clientes.telefono` |
| `costo_estimado` | integer | Costo operativo estimado de la visita |

**Estructura del campo `ninos` (JSON array de LineItems):**
```json
[
  {
    "id": "1746123456789_1",
    "venta_id": "1746123456789",
    "nombre": "Santiago",
    "servicio": "combo_1h",
    "combo": "Full",
    "categoria": "juegos",
    "minutos": 60,
    "precio": 13000,
    "salida": "2026-05-06T16:45:00",
    "activa": true,
    "adicional": false,
    "dibujo": null
  }
]
```

**Valores válidos de `categoria`:** `juegos` · `arte` · `jugueteria` · `snacks` (pendiente)

---

## 📅 Tabla: `eventos`

Alquileres de equipos y eventos externos (fiestas, colegios, empresas).

```sql
create table eventos (
  id               serial primary key,
  tipo             text default 'evento',
  cliente          text,
  telefono         text,
  festejado        text,
  anos             integer,
  ninos_aprox      integer,
  fecha_evento     date,
  lugar            text,
  servicios        jsonb,
  observaciones    text,
  precio_total     integer default 0,
  anticipo         integer default 0,
  pago             text,
  estado           text default 'cotizado',
  cliente_telefono text references clientes(telefono),
  costo_total      integer default 0,
  created_at       timestamptz default now(),

  constraint eventos_estado_check
    check (estado in ('cotizado','confirmado','en_proceso','finalizado','perdido'))
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | serial PK | Autoincremental |
| `tipo` | text | Tipo de evento |
| `cliente` | text | Nombre del cliente |
| `telefono` | text | Teléfono de contacto |
| `festejado` | text | Nombre del niño festejado |
| `anos` | integer | Edad del festejado |
| `ninos_aprox` | integer | Cantidad estimada de niños |
| `fecha_evento` | date | Fecha del evento |
| `lugar` | text | Dirección del evento |
| `servicios` | jsonb | Equipos y servicios contratados |
| `precio_total` | integer | Valor total del evento |
| `anticipo` | integer | Anticipo recibido |
| `pago` | text | Método de pago |
| `estado` | text | Estado del evento (ver valores válidos) |
| `cliente_telefono` | text FK | Referencia a `clientes.telefono` |
| `costo_total` | integer | Costo total del evento (gasolina, operarios, etc.) |

**Valores válidos de `estado`:**
- `cotizado` — propuesta enviada, sin confirmar
- `confirmado` — cliente aceptó, pendiente anticipo
- `en_proceso` — evento en curso
- `finalizado` — evento completado
- `perdido` — cliente no continuó

---

## 🧸 Tabla: `productos`

Catálogo de juguetería con control de stock.

```sql
create table productos (
  codigo_barras  text primary key,
  nombre         text not null,
  precio_venta   integer not null default 0,
  stock          integer not null default 0,
  stock_minimo   integer not null default 2,
  activo         boolean not null default true,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo_barras` | text PK | Código EAN-13 o similar |
| `nombre` | text | Nombre del producto |
| `precio_venta` | integer | Precio de venta (variable por venta) |
| `stock` | integer | Unidades disponibles |
| `stock_minimo` | integer | Umbral para alerta de stock bajo |
| `activo` | boolean | Visibilidad en el sistema |

---

## 🛒 Tabla: `ventas_jugueteria`

Ventas de juguetes sin visita activa al parque (excepción documentada al principio de Sesión Unificada).

```sql
create table ventas_jugueteria (
  id               serial primary key,
  codigo_barras    text references productos(codigo_barras),
  nombre_producto  text not null,
  precio_venta     integer not null,
  cantidad         integer not null default 1,
  comprador        text,
  pago             text default 'Efectivo',
  fecha            timestamptz default now(),
  cliente_telefono text references clientes(telefono)
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | serial PK | Autoincremental |
| `codigo_barras` | text FK | Referencia a `productos` |
| `nombre_producto` | text | Nombre del producto vendido |
| `precio_venta` | integer | Precio real de venta (puede diferir del catálogo) |
| `cantidad` | integer | Unidades vendidas |
| `comprador` | text | Nombre del comprador (opcional) |
| `pago` | text | Método de pago |
| `cliente_telefono` | text FK | Referencia a `clientes.telefono` (opcional) |

---

## 📦 Tabla: `inventario`

Stock operativo del parque (manillas, pinturas, insumos).

```sql
-- Estructura aproximada — verificar en Supabase
create table inventario (
  id              serial primary key,
  producto        text not null,
  cantidad        integer default 0,
  umbral_alerta   integer default 5,
  updated_at      timestamptz default now()
);
```

---

## 💸 Tabla: `gastos`

Gastos operativos del negocio.

```sql
create table gastos (
  id          serial primary key,
  fecha       date,
  tipo_gasto  text,
  descripcion text,
  monto       integer,
  created_at  timestamptz default now()
);
```

**Valores comunes de `tipo_gasto`:** `gasolina` · `peaje` · `operario` · `mantenimiento` · `materiales` · `comida`

---

## 👤 Tabla: `usuarios`

Control de acceso al sistema.

```sql
create table usuarios (
  id             serial primary key,
  usuario        text unique not null,
  nombre         text not null,
  password_hash  text not null,
  rol            text not null default 'operador',
  activo         boolean not null default true,
  ultimo_acceso  timestamptz,
  created_at     timestamptz default now(),

  constraint usuarios_rol_check
    check (rol in ('admin', 'operador'))
);
```

---

## 🔗 Relaciones activas

```
clientes.telefono (PK)
  ├── registros.cliente_telefono (FK)
  ├── eventos.cliente_telefono (FK)
  └── ventas_jugueteria.cliente_telefono (FK)

productos.codigo_barras (PK)
  └── ventas_jugueteria.codigo_barras (FK)
```

---

## 📊 Índices activos

```sql
idx_clientes_telefono          on clientes(telefono)
idx_registros_cliente          on registros(cliente_telefono)
idx_eventos_cliente            on eventos(cliente_telefono)
idx_eventos_estado             on eventos(estado)
idx_ventas_jug_cliente         on ventas_jugueteria(cliente_telefono)
idx_productos_nombre           on productos(nombre)
```

---

## 🔲 Tablas pendientes (v1.9)

### `ninos`
```sql
create table ninos (
  id               serial primary key,
  nombre           text not null,
  fecha_nacimiento date,
  created_at       timestamptz default now()
);
```

### `adultos`
```sql
create table adultos (
  telefono   text primary key,
  nombre     text,
  created_at timestamptz default now()
);
```

### `nino_adulto` (tabla puente)
```sql
create table nino_adulto (
  nino_id   integer references ninos(id),
  adulto_id text references adultos(telefono),
  relacion  text,  -- padre | madre | tio | amigo
  primary key (nino_id, adulto_id)
);
```

---

## ⚡ Reglas operativas

1. `telefono` del adulto es el identificador único que atraviesa todo el sistema
2. Todo cambio durante una visita activa se hace con `UPDATE`, no con `INSERT`
3. Registrar ventas en menos de 5 segundos — los campos opcionales no bloquean el flujo
4. El `precio_venta` en `ventas_jugueteria` es el precio real de venta, no necesariamente el del catálogo
5. El campo `costo_estimado` en registros y `costo_total` en eventos deben completarse para reportes de utilidad precisos
6. Antes de cualquier `ALTER TABLE` en producción, verificar que usa `ADD COLUMN IF NOT EXISTS`

---

## 📋 Historial de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | Inicial | Diseño original (ventas + detalle_ventas + productos_servicios) |
| 1.4 | abr 2026 | Reemplazado por modelo Venta + LineItems en tabla `registros` |
| 1.7 | abr 2026 | Tablas `productos` y `ventas_jugueteria` agregadas |
| 1.8 | may 2026 | FK `cliente_telefono` en registros, eventos y ventas_jugueteria · `costo_estimado` · `costo_total` · constraint estado en eventos |

---

*Inflaboom — Palmira, Colombia*
*Actualizar este archivo después de cada migración en Supabase*
