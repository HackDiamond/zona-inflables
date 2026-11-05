# Referencia: Stack, Convenciones y Patrones — Inflaboom

## Convenciones de código

### Python (app.py)
```python
# Naming
snake_case          # variables, funciones, parámetros
UPPER_CASE          # constantes (API_KEY, SERVICIOS, etc.)

# Errores — siempre con contexto en corchetes
log.error('[CONTEXTO_FUNCION] %s', e)   # ✅
log.error(str(e))                        # ❌

# Funciones helper existentes — usar antes de reinventar
sb_insert(tabla, data)                   # INSERT en Supabase
sb_update(tabla, data, match)            # UPDATE en Supabase
enviar_wa(telefono, mensaje)             # Enviar WhatsApp
pesos(n)                                 # Formatear como $X.XXX
hora_legible(dt)                         # Datetime → "10:30 AM"
normalizar_telefono(raw)                 # Limpiar número con +57
alertas_stock_db()                       # Lista de alertas de stock

# Seguridad en acceso concurrente
with _lock:
    # Solo aquí se lee/escribe ninos_activos
    venta = ninos_activos.get(venta_id)
```

### JavaScript (index.html)
```javascript
// Naming
camelCase           // variables, funciones
UPPER_CASE          // constantes (API_KEY, SRVS)

// Todas las llamadas a /api/ usan apiFetch — nunca fetch directo
const res = await apiFetch('/api/activos');           // ✅
const res = await fetch('/api/activos', {...});        // ❌

// Hora en timezone Colombia
getCOTime(date)     // Ajusta a UTC-5
getCOTime().toLocaleTimeString('es-CO', {hour:'2-digit', minute:'2-digit'})

// Toast de notificación
toast('Mensaje al operador');

// Formatear precio
pesos(13000)  // → "$13.000"
```

### SQL (Supabase)
```sql
-- Migraciones: siempre seguras para producción
ALTER TABLE tabla ADD COLUMN IF NOT EXISTS campo tipo DEFAULT valor;

-- Nunca en producción sin respaldo
DROP COLUMN campo;   -- ❌

-- Constraint: normalizar datos existentes ANTES de agregar
UPDATE tabla SET campo = 'default' WHERE campo IS NULL;
ALTER TABLE tabla ADD CONSTRAINT nombre CHECK (...);
```

---

## Patrones establecidos

### Agregar servicio a venta activa
```python
with _lock:
    venta = ninos_activos.get(venta_id)
if not venta:
    return jsonify({'ok': False, 'error': 'Venta no encontrada'}), 404

nueva_linea = { ...campos... }

with _lock:
    venta['lineas'].append(nueva_linea)
    venta['precio_total'] += precio

sb_update('registros', {
    'ninos': venta['lineas'],
    'precio_total': venta['precio_total'],
}, {'id': venta_id})
```

### Nueva ruta protegida
```python
@api_key_required
@app.route('/api/nueva-ruta', methods=['POST'])
def nueva_funcion():
    data = request.get_json(silent=True) or {}
    # validar campos obligatorios
    if not data.get('campo_requerido'):
        return jsonify({'ok': False, 'error': 'Falta campo_requerido'}), 400
    try:
        # lógica
        return jsonify({'ok': True})
    except Exception as e:
        log.error('[NUEVA_FUNCION] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500
```

### Llamada a API desde frontend
```javascript
async function miFuncion() {
    try {
        const res = await apiFetch('/api/endpoint', {
            method: 'POST',
            body: JSON.stringify({ campo: valor })
        });
        const d = await res.json();
        if (d.ok) {
            toast('Éxito');
            await cargarActivos();  // refrescar UI
        } else {
            toast(d.error || 'Error');
        }
    } catch(e) {
        toast('Error de conexion');
    }
}
```

---

## Estructura de archivos

```
zona-inflables/
├── app.py                    ← backend Flask (1 archivo)
├── public/
│   └── index.html            ← frontend completo (1 archivo)
├── Arktos/
│   └── Motor Arktos (Sistema SaaS)/
│       └── 01 - Input/
│           ├── database_inflaboom.md
│           ├── manifiesto_arquitectura.md
│           ├── conocimiento_inflaboom.md
│           └── CLAUDE.md
├── CLAUDE.md                 ← reglas de trabajo (raíz)
├── requirements.txt
├── runtime.txt
└── Procfile
```

---

## Variables de entorno (Render)

```
SUPABASE_URL        ← URL del proyecto Supabase
SUPABASE_KEY        ← anon key de Supabase
TWILIO_ACCOUNT_SID  ← para WhatsApp
TWILIO_AUTH_TOKEN   ← para WhatsApp
TWILIO_WA_NUMBER    ← número WhatsApp Twilio
ANTHROPIC_API_KEY   ← para el agente Claude
API_KEY             ← protección de rutas (default: inflaboom123)
```

---

## Flujo de deploy

```bash
# 1. Editar localmente
# 2. Verificar sintaxis Python
python3 -c "import ast; ast.parse(open('app.py').read()); print('OK')"

# 3. Commit y push
git add app.py public/index.html
git commit -m "tipo: descripción concisa"
git push origin main
# Render hace autodeploy en ~2 minutos
```

**Prefijos de commit:**
- `feat:` — nueva funcionalidad
- `fix:` — corrección de bug
- `refactor:` — mejora sin cambio de comportamiento
- `docs:` — documentación
- `sql:` — migración de base de datos

---

## Decisiones técnicas clave (no revertir sin discusión)

| Decisión | Razón |
|---|---|
| `telefono` como PK en clientes | Clave natural del negocio — evita joins innecesarios |
| `ninos` como JSON en `registros` | Modelo LineItems sin tabla separada — simplicidad en producción |
| Sin login por sesión actualmente | Reemplazado por API key — deuda técnica documentada |
| `ninos_activos` en memoria + Supabase | Velocidad de lectura en operación + persistencia ante reinicios |
| Un solo `app.py` | El proyecto es pequeño — modularizar solo cuando supere 2000 líneas |
