# ================================================================
#  INFLABOOM — Servidor principal con Supabase
#  Python + Flask + Twilio + Supabase (PostgreSQL)
# ================================================================

from flask import Flask, request, jsonify, send_from_directory
from twilio.rest import Client
from datetime import datetime, timedelta
from supabase import create_client, Client as SupabaseClient
import threading
import os
import json

app = Flask(__name__, static_folder='public', static_url_path='')

# ── Credenciales (variables de entorno en Render) ──
TWILIO_SID    = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN  = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER = os.environ.get('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')
SUPABASE_URL  = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY  = os.environ.get('SUPABASE_KEY', '')

# ── Clientes externos ──
twilio_client   = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# ── Estado en memoria (activos, timers) ──
# Solo los niños ACTIVOS van en memoria — el historial persiste en Supabase
ninos_activos = {}   # id -> grupo activo
timers        = {}   # id -> [timer_aviso, timer_fin]

# ── Catálogo de servicios ──
SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',    'minutos': 15,  'precio': 5000,  'manilla': False, 'juegos': '1 juego a elección'},
    'combo_30':  {'nombre': '30 minutos',    'minutos': 30,  'precio': 8000,  'manilla': False, 'juegos': '2 juegos a elección'},
    'combo_1h':  {'nombre': '1 hora',        'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos (todos)'},
    'promo_2x1': {'nombre': 'Promo 2x1',     'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos (todos) — 2 niños'},
    'arte':      {'nombre': 'Estación arte',  'minutos': None,'precio': 5000,  'manilla': False, 'juegos': 'Pintura en caballete'},
}

# ── Inventario por defecto ──
INVENTARIO_DEFAULT = {
    'manillas': 100,
    'pinturas':  50,
    'pinceles':  30,
}


# ================================================================
#  INICIALIZACIÓN DE TABLAS EN SUPABASE
# ================================================================

def init_tablas():
    """Crea las tablas en Supabase si no existen usando SQL directo."""
    if not supabase:
        print('⚠ Supabase no configurado — corriendo en modo demo')
        return

    sql_tablas = """
    -- Tabla de registros (niños atendidos)
    CREATE TABLE IF NOT EXISTS registros (
        id          TEXT PRIMARY KEY,
        servicio    TEXT NOT NULL,
        acudiente   TEXT,
        telefono    TEXT,
        pago        TEXT,
        ninos       JSONB,
        precio_total INTEGER,
        entrada     TIMESTAMPTZ,
        salida      TIMESTAMPTZ,
        activo      BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Tabla de gastos operativos
    CREATE TABLE IF NOT EXISTS gastos (
        id          SERIAL PRIMARY KEY,
        categoria   TEXT,
        descripcion TEXT,
        valor       INTEGER,
        fecha       DATE DEFAULT CURRENT_DATE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Tabla de inventario
    CREATE TABLE IF NOT EXISTS inventario (
        id          SERIAL PRIMARY KEY,
        producto    TEXT UNIQUE,
        cantidad    INTEGER DEFAULT 0,
        umbral_alerta INTEGER DEFAULT 10,
        updated_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Tabla de clientes frecuentes
    CREATE TABLE IF NOT EXISTS clientes (
        telefono    TEXT PRIMARY KEY,
        nombre      TEXT,
        visitas     INTEGER DEFAULT 0,
        total_gastado INTEGER DEFAULT 0,
        ultimo_visita TIMESTAMPTZ,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Tabla de eventos y paquetes
    CREATE TABLE IF NOT EXISTS eventos (
        id          SERIAL PRIMARY KEY,
        tipo        TEXT DEFAULT 'evento',
        cliente     TEXT,
        telefono    TEXT,
        festejado   TEXT,
        anos        INTEGER,
        ninos_aprox INTEGER,
        fecha_evento DATE,
        lugar       TEXT,
        servicios   TEXT,
        observaciones TEXT,
        precio_total INTEGER,
        anticipo    INTEGER DEFAULT 0,
        estado      TEXT DEFAULT 'cotizado',
        pago        TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Insertar inventario inicial si está vacío
    INSERT INTO inventario (producto, cantidad, umbral_alerta)
    VALUES
        ('manillas', 100, 10),
        ('pinturas',  50, 10),
        ('pinceles',  30,  5)
    ON CONFLICT (producto) DO NOTHING;
    """

    try:
        supabase.rpc('exec_sql', {'sql': sql_tablas}).execute()
        print('✅ Tablas Supabase verificadas')
    except Exception as e:
        # Si el RPC no existe, usamos el SQL editor directamente
        print(f'⚠ Init tablas via RPC falló ({e}) — usa el SQL editor de Supabase')


# ================================================================
#  HELPERS
# ================================================================

def hora_legible(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime('%I:%M %p')

def es_sabado():
    return datetime.now().weekday() == 5

def pesos(n):
    return f'${int(n or 0):,}'.replace(',', '.')

def enviar_wa(telefono, mensaje):
    if not twilio_client:
        print(f'[WA simulado → {telefono}]: {mensaje[:80]}')
        return {'ok': True, 'simulado': True}
    try:
        num = telefono.replace(' ', '').replace('-', '')
        if not num.startswith('+'):
            num = '+57' + num.lstrip('0')
        msg = twilio_client.messages.create(
            from_=TWILIO_NUMBER,
            to=f'whatsapp:{num}',
            body=mensaje
        )
        print(f'[WA OK → {num}] {msg.sid}')
        return {'ok': True, 'sid': msg.sid}
    except Exception as e:
        print(f'[WA ERROR] {e}')
        return {'ok': False, 'error': str(e)}

# ── Supabase helpers ──
def sb_insert(tabla, data):
    if not supabase: return None
    try:
        return supabase.table(tabla).insert(data).execute()
    except Exception as e:
        print(f'[DB INSERT {tabla}] {e}')
        return None

def sb_update(tabla, data, match):
    if not supabase: return None
    try:
        q = supabase.table(tabla).update(data)
        for k, v in match.items():
            q = q.eq(k, v)
        return q.execute()
    except Exception as e:
        print(f'[DB UPDATE {tabla}] {e}')
        return None

def sb_select(tabla, filters=None, order=None, limit=None):
    if not supabase: return []
    try:
        q = supabase.table(tabla).select('*')
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        if order:
            q = q.order(order, desc=True)
        if limit:
            q = q.limit(limit)
        res = q.execute()
        return res.data or []
    except Exception as e:
        print(f'[DB SELECT {tabla}] {e}')
        return []

def registrar_cliente_db(telefono, nombre, precio):
    if not supabase: return
    try:
        existing = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
        if existing.data:
            c = existing.data[0]
            supabase.table('clientes').update({
                'visitas': c['visitas'] + 1,
                'total_gastado': c['total_gastado'] + precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).eq('telefono', telefono).execute()
        else:
            supabase.table('clientes').insert({
                'telefono': telefono,
                'nombre': nombre,
                'visitas': 1,
                'total_gastado': precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).execute()
    except Exception as e:
        print(f'[DB CLIENTE] {e}')

def descontar_inventario_db(servicio, ninos_lista):
    if not supabase: return
    try:
        srv = SERVICIOS.get(servicio, {})
        if srv.get('manilla'):
            res = supabase.table('inventario').select('cantidad').eq('producto', 'manillas').execute()
            if res.data:
                nueva_qty = max(0, res.data[0]['cantidad'] - len(ninos_lista))
                supabase.table('inventario').update({'cantidad': nueva_qty, 'updated_at': datetime.now().isoformat()}).eq('producto', 'manillas').execute()

        for nino in ninos_lista:
            if nino.get('dibujo'):
                personaje = nino['dibujo'].lower().strip()
                res = supabase.table('inventario').select('cantidad').eq('producto', f'dibujo_{personaje}').execute()
                if res.data:
                    nueva_qty = max(0, res.data[0]['cantidad'] - 1)
                    supabase.table('inventario').update({'cantidad': nueva_qty, 'updated_at': datetime.now().isoformat()}).eq('producto', f'dibujo_{personaje}').execute()
    except Exception as e:
        print(f'[DB INVENTARIO DESCUENTO] {e}')

def alertas_stock_db():
    if not supabase: return []
    try:
        res = supabase.table('inventario').select('*').execute()
        alertas = []
        for item in (res.data or []):
            if item['cantidad'] <= item['umbral_alerta']:
                alertas.append(f"⚠️ {item['producto']}: solo {item['cantidad']} disponibles")
        return alertas
    except:
        return []


# ================================================================
#  MENSAJES WHATSAPP
# ================================================================

def msg_bienvenida(grupo):
    srv = SERVICIOS[grupo['servicio']]
    ninos = grupo['ninos']
    nombres = ', '.join([n['nombre'] for n in ninos])
    es_grupo = len(ninos) > 1
    es_promo = grupo['servicio'] == 'promo_2x1'
    es_arte  = grupo['servicio'] == 'arte'
    acudiente = grupo.get('acudiente') or 'acudiente'

    if es_arte:
        dibujos = ', '.join([f"{n['nombre']} ({n.get('dibujo') or '?'})" for n in ninos])
        return (
            f"🎨 *Inflaboom — Estación de Arte*\n\n"
            f"Hola {acudiente} 👋\n\n"
            f"{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado a pintar.\n\n"
            f"🖌 *{'Niños' if es_grupo else 'Niño/a'}:* {dibujos}\n"
            f"💰 *Valor:* {pesos(grupo['precio_total'])} — {grupo['pago']}\n\n"
            f"¡A disfrutar la creatividad! 🌟"
        )

    salida = hora_legible(grupo['salida'])
    txt = (
        f"🎪 *Inflaboom — {'¡Promo 2x1!' if es_promo else 'Bienvenida'}*\n\n"
        f"Hola {acudiente} 👋\n\n"
        f"*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado al parque.*\n\n"
        f"👦 *{'Niños' if es_grupo else 'Niño/a'}:* {nombres}\n"
        f"🎮 *Combo:* {srv['nombre']} — {srv['juegos']}\n"
        f"🕐 *Ingreso:* {hora_legible(grupo['entrada'])}\n"
        f"🕐 *Salida:* {salida}\n"
        f"💰 *Valor:* {pesos(grupo['precio_total'])} — {grupo['pago']}"
    )
    if es_promo:
        txt += "\n\n🎉 *¡Promo sábado 2x1 aplicada!* Entraron 2 niños por el precio de 1."
    return txt

def msg_recibo(grupo):
    srv = SERVICIOS[grupo['servicio']]
    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    return (
        f"🧾 *Recibo — Inflaboom*\n\n"
        f"👦 {'Niños' if len(grupo['ninos'])>1 else 'Niño/a'}: {nombres}\n"
        f"🎮 Servicio: {srv['nombre']}\n"
        f"💵 Valor: {pesos(grupo['precio_total'])}\n"
        f"💳 Pago: {grupo['pago']}\n"
        f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"_Gracias por visitarnos_ ✅"
    )

def msg_aviso(grupo):
    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    return (
        f"⏰ *Recordatorio — Inflaboom*\n\n"
        f"Le quedan *5 minutos* a *{nombres}*.\n"
        f"Por favor acérquese a la zona de ingreso 🙏"
    )

def msg_fin(grupo):
    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    return (
        f"🔔 *Tiempo finalizado — Inflaboom*\n\n"
        f"El tiempo de *{nombres}* ha terminado.\n\n"
        f"¿Desea continuar?\n\n"
        f"Responde *1* → Más tiempo\n"
        f"Responde *2* → Los retiro ahora"
    )

def msg_despedida(grupo):
    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    promo = '\n\n🎉 *Promo sábados:* 2x1 en combo 1 hora. ¡Tráigale un amiguito!' if es_sabado() else ''
    return (
        f"🌟 *¡Hasta pronto! — Inflaboom*\n\n"
        f"Gracias por visitarnos con *{nombres}*.\n"
        f"¡Esperamos que lo hayan disfrutado! 😊\n\n"
        f"📍 ¡Los esperamos pronto! Estamos abiertos todos los días.{promo}"
    )


# ================================================================
#  TEMPORIZADORES
# ================================================================

def programar_alertas(gid):
    grupo = ninos_activos.get(gid)
    if not grupo or not grupo.get('salida'): return

    ahora = datetime.now()
    salida = grupo['salida'] if isinstance(grupo['salida'], datetime) else datetime.fromisoformat(str(grupo['salida']))
    ms_total = (salida - ahora).total_seconds()
    ms_aviso = ms_total - 300

    def aviso():
        g = ninos_activos.get(gid)
        if g: enviar_wa(g['telefono'], msg_aviso(g))

    def fin():
        g = ninos_activos.get(gid)
        if g: enviar_wa(g['telefono'], msg_fin(g))

    timers_list = []
    if ms_aviso > 0:
        t = threading.Timer(ms_aviso, aviso)
        t.start(); timers_list.append(t)

    t2 = threading.Timer(max(ms_total, 1), fin)
    t2.start(); timers_list.append(t2)
    timers[gid] = timers_list

def cancelar_timers(gid):
    for t in timers.pop(gid, []):
        t.cancel()


# ================================================================
#  RUTAS
# ================================================================

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


# ── Registrar grupo ──
@app.route('/api/registrar', methods=['POST'])
def registrar():
    data      = request.json
    servicio  = data.get('servicio')
    acudiente = data.get('acudiente', '')
    telefono  = data.get('telefono', '')
    pago      = data.get('pago', 'Efectivo')
    ninos     = data.get('ninos', [])

    if not servicio or not telefono or not ninos:
        return jsonify({'ok': False, 'error': 'Faltan campos obligatorios'}), 400

    srv = SERVICIOS.get(servicio)
    if not srv:
        return jsonify({'ok': False, 'error': 'Servicio inválido'}), 400

    n_ninos = len(ninos)
    precio_total = srv['precio'] if servicio == 'promo_2x1' else srv['precio'] * n_ninos

    ahora  = datetime.now()
    minutos = srv.get('minutos')
    salida  = ahora + timedelta(minutes=minutos) if minutos else None
    gid     = str(int(ahora.timestamp() * 1000))

    grupo = {
        'id':           gid,
        'servicio':     servicio,
        'acudiente':    acudiente,
        'telefono':     telefono,
        'pago':         pago,
        'ninos':        ninos,
        'precio_total': precio_total,
        'entrada':      ahora,
        'salida':       salida,
        'activo':       True,
    }

    # Guardar en Supabase
    sb_insert('registros', {
        'id':           gid,
        'servicio':     servicio,
        'acudiente':    acudiente,
        'telefono':     telefono,
        'pago':         pago,
        'ninos':        ninos,
        'precio_total': precio_total,
        'entrada':      ahora.isoformat(),
        'salida':       salida.isoformat() if salida else None,
        'activo':       True,
    })

    # Guardar en memoria (activos)
    ninos_activos[gid] = grupo

    # Operaciones secundarias
    descontar_inventario_db(servicio, ninos)
    registrar_cliente_db(telefono, acudiente, precio_total)
    programar_alertas(gid)

    # Enviar WhatsApp
    enviar_wa(telefono, msg_bienvenida(grupo))
    threading.Timer(2.0, lambda: enviar_wa(telefono, msg_recibo(grupo))).start()

    return jsonify({
        'ok':        True,
        'id':        gid,
        'salida':    salida.isoformat() if salida else None,
        'precio_total': precio_total,
        'alertas':   alertas_stock_db(),
    })


# ── Retirar ──
@app.route('/api/retirar', methods=['POST'])
def retirar():
    gid   = request.json.get('id')
    grupo = ninos_activos.pop(gid, None)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    cancelar_timers(gid)
    sb_update('registros', {'activo': False}, {'id': gid})
    enviar_wa(grupo['telefono'], msg_despedida(grupo))
    return jsonify({'ok': True})


# ── Extender tiempo ──
@app.route('/api/extender', methods=['POST'])
def extender():
    data     = request.json
    gid      = data.get('id')
    servicio = data.get('servicio', 'combo_1h')
    pago     = data.get('pago', 'Efectivo')
    grupo    = ninos_activos.get(gid)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404

    srv = SERVICIOS[servicio]
    cancelar_timers(gid)
    ahora = datetime.now()
    grupo.update({'servicio': servicio, 'entrada': ahora, 'salida': ahora + timedelta(minutes=srv['minutos']), 'pago': pago})
    programar_alertas(gid)

    sb_update('registros', {
        'servicio': servicio,
        'salida':   grupo['salida'].isoformat(),
        'pago':     pago,
    }, {'id': gid})

    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    enviar_wa(grupo['telefono'], (
        f"⏱ *Tiempo extendido — Inflaboom*\n\n"
        f"*{nombres}* tiene {srv['nombre']} más.\n"
        f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
        f"💰 {pesos(srv['precio'])} — {pago}"
    ))
    return jsonify({'ok': True, 'salida': grupo['salida'].isoformat()})


# ── Activos ──
@app.route('/api/activos')
def get_activos():
    ahora = datetime.now()
    resultado = []
    for gid, g in ninos_activos.items():
        salida = g['salida']
        ms_rest = int((salida - ahora).total_seconds() * 1000) if salida else None
        resultado.append({
            'id':          gid,
            'servicio':    g['servicio'],
            'acudiente':   g['acudiente'],
            'telefono':    g['telefono'],
            'pago':        g['pago'],
            'ninos':       g['ninos'],
            'precio_total':g['precio_total'],
            'entrada':     g['entrada'].isoformat(),
            'salida':      salida.isoformat() if salida else None,
            'ms_restantes':max(ms_rest, 0) if ms_rest is not None else None,
        })
    return jsonify(resultado)


# ── Historial (desde Supabase) ──
@app.route('/api/historial')
def get_historial():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('registros')\
                .select('*')\
                .gte('entrada', f'{fecha}T00:00:00')\
                .lte('entrada', f'{fecha}T23:59:59')\
                .order('entrada', desc=True)\
                .execute()
            return jsonify(res.data or [])
        except Exception as e:
            print(f'[HISTORIAL] {e}')
    return jsonify([])


# ── KPIs del día ──
@app.route('/api/kpis')
def get_kpis():
    fecha = datetime.now().strftime('%Y-%m-%d')
    total_ventas = total_ninos = efectivo = transferencia = 0
    if supabase:
        try:
            res = supabase.table('registros')\
                .select('precio_total,pago,ninos')\
                .gte('entrada', f'{fecha}T00:00:00')\
                .execute()
            for r in (res.data or []):
                total_ventas += r['precio_total'] or 0
                ninos_list = r['ninos'] if isinstance(r['ninos'], list) else json.loads(r['ninos'] or '[]')
                total_ninos += len(ninos_list)
                if r['pago'] == 'Efectivo':
                    efectivo += r['precio_total'] or 0
                else:
                    transferencia += r['precio_total'] or 0
        except Exception as e:
            print(f'[KPIS] {e}')

    return jsonify({
        'total_ventas':  total_ventas,
        'total_ninos':   total_ninos,
        'activos_ahora': len(ninos_activos),
        'efectivo':      efectivo,
        'transferencia': transferencia,
        'alertas':       alertas_stock_db(),
    })


# ── Inventario ──
@app.route('/api/inventario')
def get_inventario():
    if supabase:
        try:
            res = supabase.table('inventario').select('*').order('producto').execute()
            inv = {}
            for item in (res.data or []):
                inv[item['producto']] = {'cantidad': item['cantidad'], 'umbral': item['umbral_alerta']}
            return jsonify(inv)
        except Exception as e:
            print(f'[INVENTARIO GET] {e}')
    return jsonify(INVENTARIO_DEFAULT)

@app.route('/api/inventario/agregar', methods=['POST'])
def agregar_stock():
    data      = request.json
    tipo      = data.get('tipo')
    cantidad  = int(data.get('cantidad', 0))
    personaje = data.get('personaje', '').lower().strip()
    producto  = f'dibujo_{personaje}' if tipo == 'dibujo' and personaje else tipo

    if supabase:
        try:
            res = supabase.table('inventario').select('cantidad').eq('producto', producto).execute()
            if res.data:
                nueva = res.data[0]['cantidad'] + cantidad
                supabase.table('inventario').update({'cantidad': nueva, 'updated_at': datetime.now().isoformat()}).eq('producto', producto).execute()
            else:
                supabase.table('inventario').insert({'producto': producto, 'cantidad': cantidad, 'umbral_alerta': 5}).execute()
        except Exception as e:
            print(f'[INVENTARIO AGREGAR] {e}')

    return jsonify({'ok': True})


# ── Gastos ──
@app.route('/api/gastos', methods=['GET'])
def get_gastos():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    data  = sb_select('gastos', {'fecha': fecha}, order='created_at')
    return jsonify(data)

@app.route('/api/gastos', methods=['POST'])
def agregar_gasto():
    data = request.json
    sb_insert('gastos', {
        'categoria':   data.get('categoria'),
        'descripcion': data.get('descripcion'),
        'valor':       int(data.get('valor', 0)),
        'fecha':       data.get('fecha', datetime.now().strftime('%Y-%m-%d')),
    })
    return jsonify({'ok': True})


# ── Clientes frecuentes ──
@app.route('/api/clientes')
def get_clientes():
    if supabase:
        try:
            res = supabase.table('clientes').select('*').order('visitas', desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            print(f'[CLIENTES] {e}')
    return jsonify([])


# ── Eventos y paquetes ──
@app.route('/api/eventos', methods=['GET'])
def get_eventos():
    data = sb_select('eventos', order='created_at')
    return jsonify(data)

@app.route('/api/eventos', methods=['POST'])
def crear_evento():
    data = request.json
    sb_insert('eventos', {
        'tipo':          data.get('tipo', 'evento'),
        'cliente':       data.get('cliente'),
        'telefono':      data.get('telefono'),
        'festejado':     data.get('festejado'),
        'anos':          data.get('anos'),
        'ninos_aprox':   data.get('ninos_aprox'),
        'fecha_evento':  data.get('fecha_evento'),
        'lugar':         data.get('lugar'),
        'servicios':     data.get('servicios'),
        'observaciones': data.get('observaciones'),
        'precio_total':  int(data.get('precio_total', 0)),
        'anticipo':      int(data.get('anticipo', 0)),
        'estado':        data.get('estado', 'cotizado'),
        'pago':          data.get('pago', ''),
    })
    return jsonify({'ok': True})

@app.route('/api/eventos/<int:evento_id>', methods=['PATCH'])
def actualizar_evento(evento_id):
    data = request.json
    sb_update('eventos', data, {'id': evento_id})
    return jsonify({'ok': True})


# ── Webhook WhatsApp ──
@app.route('/api/webhook-wa', methods=['POST'])
def webhook_wa():
    body  = request.form.get('Body', '').strip()
    from_ = request.form.get('From', '')
    tel   = from_.replace('whatsapp:+57', '').replace('whatsapp:+', '').replace('whatsapp:', '')

    grupo = next(
        (g for g in ninos_activos.values() if tel in g['telefono'].replace(' ', '')),
        None
    )

    if body == '1' and grupo:
        srv = SERVICIOS[grupo['servicio']]
        cancelar_timers(grupo['id'])
        ahora = datetime.now()
        grupo['entrada'] = ahora
        grupo['salida']  = ahora + timedelta(minutes=srv['minutos'])
        programar_alertas(grupo['id'])
        nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
        enviar_wa(grupo['telefono'], (
            f"⏱ *Tiempo renovado*\n\n"
            f"Listo, *{nombres}* tiene {srv['nombre']} más.\n"
            f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
            f"💰 {pesos(srv['precio'])} adicionales — acérquese a cancelar."
        ))
    elif body == '2' and grupo:
        gid = grupo['id']
        cancelar_timers(gid)
        ninos_activos.pop(gid, None)
        sb_update('registros', {'activo': False}, {'id': gid})
        enviar_wa(grupo['telefono'], msg_despedida(grupo))
    else:
        # En la siguiente fase aquí entra el agente IA
        enviar_wa(tel, (
            "Hola 👋 Soy el asistente de *Inflaboom*.\n\n"
            "Para consultas escríbenos o visítanos en el parque. ¡Gracias!"
        ))

    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}


# ── Reportes consolidados (para el dashboard) ──
@app.route('/api/reportes/mes')
def reporte_mes():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    if not supabase:
        return jsonify({'ventas': [], 'gastos': [], 'eventos': []})
    try:
        inicio = f'{mes}-01T00:00:00'
        fin    = f'{mes}-31T23:59:59'

        ventas  = supabase.table('registros').select('*').gte('entrada', inicio).lte('entrada', fin).execute().data or []
        gastos  = supabase.table('gastos').select('*').gte('fecha', f'{mes}-01').lte('fecha', f'{mes}-31').execute().data or []
        eventos = supabase.table('eventos').select('*').gte('fecha_evento', f'{mes}-01').lte('fecha_evento', f'{mes}-31').execute().data or []

        return jsonify({'ventas': ventas, 'gastos': gastos, 'eventos': eventos})
    except Exception as e:
        print(f'[REPORTE MES] {e}')
        return jsonify({'ventas': [], 'gastos': [], 'eventos': []})


# ================================================================
#  ARRANQUE
# ================================================================

if __name__ == '__main__':
    init_tablas()
    port = int(os.environ.get('PORT', 3000))
    print(f'🎪 Inflaboom arrancando en puerto {port}')
    app.run(host='0.0.0.0', port=port, debug=False)
