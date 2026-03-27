# ================================================================
#  INFLABOOM — Servidor principal
#  Tecnología: Python + Flask + Twilio WhatsApp
# ================================================================

from flask import Flask, request, jsonify, send_from_directory
from twilio.rest import Client
from datetime import datetime, timedelta
import threading
import os
import json

app = Flask(__name__, static_folder='public', static_url_path='')

# ── Credenciales Twilio (se leen desde variables de entorno en Render) ──
TWILIO_SID    = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN  = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER = os.environ.get('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None

# ── Base de datos en memoria ──
# (se reemplaza por Supabase en la siguiente fase)
ninos     = {}   # id -> datos del niño/grupo activo
historial = []   # registro completo del día
inventario = {   # stock inicial
    'manillas': 100,
    'dibujos':  {},   # {'spiderman': 20, 'frozen': 15, ...}
    'pinturas': 50,
    'pinceles': 30,
}
clientes  = {}   # telefono -> {nombre, visitas, total_gastado, ultimo}
timers    = {}   # id -> [timer_aviso, timer_fin]

# ── Catálogo de servicios ──
SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',   'minutos': 15,  'precio': 5000,  'manilla': False, 'juegos': '1 juego a elección'},
    'combo_30':  {'nombre': '30 minutos',   'minutos': 30,  'precio': 8000,  'manilla': False, 'juegos': '2 juegos a elección'},
    'combo_1h':  {'nombre': '1 hora',       'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos (todos)'},
    'promo_2x1': {'nombre': 'Promo 2x1',    'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos (todos) — 2 niños'},
    'arte':      {'nombre': 'Estación arte', 'minutos': None,'precio': 5000,  'manilla': False, 'juegos': 'Pintura en caballete'},
}


# ================================================================
#  HELPERS
# ================================================================

def hora_legible(dt):
    return dt.strftime('%I:%M %p')

def es_sabado():
    return datetime.now().weekday() == 5

def pesos(n):
    return f'${n:,}'.replace(',', '.')

def enviar_wa(telefono, mensaje):
    if not twilio_client:
        print(f'[WA simulado] → {telefono}: {mensaje[:60]}...')
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
        print(f'[WA enviado] → {num} SID: {msg.sid}')
        return {'ok': True, 'sid': msg.sid}
    except Exception as e:
        print(f'[WA error] {e}')
        return {'ok': False, 'error': str(e)}

def registrar_cliente(telefono, nombre_acudiente):
    if telefono not in clientes:
        clientes[telefono] = {'nombre': nombre_acudiente, 'visitas': 0, 'total': 0, 'ultimo': None}
    clientes[telefono]['visitas'] += 1
    clientes[telefono]['ultimo'] = datetime.now().isoformat()

def descontar_inventario(servicio, ninos_lista):
    """Descuenta manillas si es combo 1h o promo 2x1, y dibujos si hay arte."""
    srv = SERVICIOS.get(servicio, {})
    if srv.get('manilla'):
        inventario['manillas'] = max(0, inventario['manillas'] - len(ninos_lista))
    for nino in ninos_lista:
        if nino.get('dibujo'):
            personaje = nino['dibujo'].lower()
            inventario['dibujos'][personaje] = max(0, inventario['dibujos'].get(personaje, 0) - 1)

def alerta_inventario_bajo():
    alertas = []
    if inventario['manillas'] < 10:
        alertas.append(f'⚠️ Manillas: solo {inventario["manillas"]} disponibles')
    for personaje, qty in inventario['dibujos'].items():
        if qty < 5:
            alertas.append(f'⚠️ Dibujo "{personaje}": solo {qty} disponibles')
    return alertas


# ================================================================
#  MENSAJES WHATSAPP
# ================================================================

def msg_bienvenida(grupo):
    srv = SERVICIOS[grupo['servicio']]
    ninos_nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    es_grupo = len(grupo['ninos']) > 1
    es_promo = grupo['servicio'] == 'promo_2x1'
    es_arte  = grupo['servicio'] == 'arte'

    if es_arte:
        dibujos = ', '.join([f"{n['nombre']} ({n.get('dibujo','?')})" for n in grupo['ninos']])
        return (
            f"🎨 *Inflaboom — Estación de Arte*\n\n"
            f"Hola {grupo['acudiente']} 👋\n\n"
            f"{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado a pintar.\n\n"
            f"🖌 *{'Niños' if es_grupo else 'Niño/a'}:* {dibujos}\n"
            f"💰 *Valor:* {pesos(grupo['precio_total'])} — {grupo['pago']}\n\n"
            f"¡A disfrutar la creatividad! 🌟"
        )

    salida = hora_legible(grupo['salida'])
    texto = (
        f"🎪 *Inflaboom — {'¡Promo 2x1!' if es_promo else 'Bienvenida'}*\n\n"
        f"Hola {grupo['acudiente']} 👋\n\n"
        f"*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado al parque.*\n\n"
        f"👦 *{'Niños' if es_grupo else 'Niño/a'}:* {ninos_nombres}\n"
        f"🎮 *Combo:* {srv['nombre']} — {srv['juegos']}\n"
        f"🕐 *Ingreso:* {hora_legible(grupo['entrada'])}\n"
        f"🕐 *Salida:* {salida}\n"
        f"💰 *Valor:* {pesos(grupo['precio_total'])} — {grupo['pago']}"
    )
    if es_promo:
        texto += f"\n\n🎉 *¡Promo sábado 2x1 aplicada!* Entraron 2 niños por el precio de 1."
    return texto

def msg_recibo(grupo):
    srv = SERVICIOS[grupo['servicio']]
    return (
        f"🧾 *Recibo — Inflaboom*\n\n"
        f"👦 {'Niños' if len(grupo['ninos'])>1 else 'Niño/a'}: "
        f"{', '.join([n['nombre'] for n in grupo['ninos']])}\n"
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
    promo = '\n\n🎉 *Promo sábados:* 2x1 en combo 1 hora. ¡Tráigale un amiguito la próxima!' if es_sabado() else ''
    return (
        f"🌟 *¡Hasta pronto! — Inflaboom*\n\n"
        f"Gracias por visitarnos hoy con *{nombres}*.\n"
        f"¡Esperamos que lo hayan disfrutado! 😊\n\n"
        f"📍 ¡Los esperamos pronto! Estamos abiertos todos los días.{promo}"
    )


# ================================================================
#  TEMPORIZADORES
# ================================================================

def programar_alertas(gid):
    grupo = ninos.get(gid)
    if not grupo or not grupo.get('salida'):
        return
    srv = SERVICIOS[grupo['servicio']]
    minutos = srv.get('minutos')
    if not minutos:
        return

    ahora = datetime.now()
    salida = grupo['salida']
    ms_total = (salida - ahora).total_seconds()
    ms_aviso = ms_total - 300  # 5 minutos antes

    def aviso():
        g = ninos.get(gid)
        if g and g.get('activo'):
            enviar_wa(g['telefono'], msg_aviso(g))

    def fin():
        g = ninos.get(gid)
        if g and g.get('activo'):
            enviar_wa(g['telefono'], msg_fin(g))

    t_aviso = None
    if ms_aviso > 0:
        t_aviso = threading.Timer(ms_aviso, aviso)
        t_aviso.start()

    t_fin = threading.Timer(max(ms_total, 1), fin)
    t_fin.start()

    timers[gid] = [t for t in [t_aviso, t_fin] if t]

def cancelar_timers(gid):
    for t in timers.pop(gid, []):
        t.cancel()


# ================================================================
#  RUTAS API
# ================================================================

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


# ── Registrar grupo/niño ──
@app.route('/api/registrar', methods=['POST'])
def registrar():
    data = request.json
    servicio  = data.get('servicio')
    acudiente = data.get('acudiente', '')
    telefono  = data.get('telefono', '')
    pago      = data.get('pago', 'Efectivo')
    ninos_data= data.get('ninos', [])  # [{nombre, dibujo?}]

    if not servicio or not telefono or not ninos_data:
        return jsonify({'ok': False, 'error': 'Faltan campos obligatorios'}), 400

    srv = SERVICIOS.get(servicio)
    if not srv:
        return jsonify({'ok': False, 'error': 'Servicio inválido'}), 400

    # Calcular precio total
    n_ninos = len(ninos_data)
    if servicio == 'promo_2x1':
        precio_total = srv['precio']  # paga 1, entran 2
    elif servicio == 'arte':
        precio_total = srv['precio'] * n_ninos
    else:
        precio_total = srv['precio'] * n_ninos

    # Calcular tiempos
    ahora = datetime.now()
    minutos = srv.get('minutos')
    salida = ahora + timedelta(minutes=minutos) if minutos else None

    gid = str(int(ahora.timestamp() * 1000))

    grupo = {
        'id':           gid,
        'servicio':     servicio,
        'acudiente':    acudiente,
        'telefono':     telefono,
        'pago':         pago,
        'ninos':        ninos_data,
        'precio_total': precio_total,
        'entrada':      ahora,
        'salida':       salida,
        'activo':       True,
    }

    ninos[gid] = grupo
    historial.append({**grupo, 'entrada': ahora.isoformat(), 'salida': salida.isoformat() if salida else None})

    # Descontar inventario
    descontar_inventario(servicio, ninos_data)

    # Registrar cliente
    registrar_cliente(telefono, acudiente)
    clientes[telefono]['total'] = clientes[telefono].get('total', 0) + precio_total

    # Programar alertas y enviar WA
    programar_alertas(gid)
    enviar_wa(telefono, msg_bienvenida(grupo))

    import time; time.sleep(1.5)
    enviar_wa(telefono, msg_recibo(grupo))

    alertas = alerta_inventario_bajo()

    return jsonify({
        'ok': True,
        'id': gid,
        'salida': salida.isoformat() if salida else None,
        'precio_total': precio_total,
        'alertas_inventario': alertas,
    })


# ── Retirar grupo ──
@app.route('/api/retirar', methods=['POST'])
def retirar():
    gid = request.json.get('id')
    grupo = ninos.pop(gid, None)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    grupo['activo'] = False
    cancelar_timers(gid)
    enviar_wa(grupo['telefono'], msg_despedida(grupo))
    return jsonify({'ok': True})


# ── Extender tiempo ──
@app.route('/api/extender', methods=['POST'])
def extender():
    data = request.json
    gid      = data.get('id')
    servicio = data.get('servicio', 'combo_1h')
    pago     = data.get('pago', 'Efectivo')

    grupo = ninos.get(gid)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404

    srv = SERVICIOS[servicio]
    cancelar_timers(gid)

    ahora = datetime.now()
    grupo['servicio'] = servicio
    grupo['entrada']  = ahora
    grupo['salida']   = ahora + timedelta(minutes=srv['minutos'])
    grupo['pago']     = pago
    grupo['activo']   = True

    programar_alertas(gid)

    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    msg = (
        f"⏱ *Tiempo extendido — Inflaboom*\n\n"
        f"*{nombres}* tiene {srv['nombre']} más.\n"
        f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
        f"💰 {pesos(srv['precio'])} — {pago}"
    )
    enviar_wa(grupo['telefono'], msg)

    return jsonify({'ok': True, 'salida': grupo['salida'].isoformat()})


# ── Lista de activos ──
@app.route('/api/activos')
def get_activos():
    ahora = datetime.now()
    resultado = []
    for gid, g in ninos.items():
        salida_iso = g['salida'].isoformat() if g['salida'] else None
        ms_rest = int((g['salida'] - ahora).total_seconds() * 1000) if g['salida'] else None
        resultado.append({
            'id':          gid,
            'servicio':    g['servicio'],
            'acudiente':   g['acudiente'],
            'telefono':    g['telefono'],
            'pago':        g['pago'],
            'ninos':       g['ninos'],
            'precio_total':g['precio_total'],
            'entrada':     g['entrada'].isoformat(),
            'salida':      salida_iso,
            'ms_restantes':max(ms_rest, 0) if ms_rest is not None else None,
        })
    return jsonify(resultado)


# ── Historial del día ──
@app.route('/api/historial')
def get_historial():
    return jsonify(historial)


# ── Inventario ──
@app.route('/api/inventario')
def get_inventario():
    return jsonify(inventario)

@app.route('/api/inventario/agregar', methods=['POST'])
def agregar_stock():
    data = request.json
    tipo     = data.get('tipo')    # 'manillas', 'pinturas', 'pinceles', 'dibujo'
    cantidad = int(data.get('cantidad', 0))
    personaje= data.get('personaje', '')  # solo para dibujos

    if tipo == 'dibujo' and personaje:
        inventario['dibujos'][personaje.lower()] = inventario['dibujos'].get(personaje.lower(), 0) + cantidad
    elif tipo in inventario:
        inventario[tipo] = inventario[tipo] + cantidad

    return jsonify({'ok': True, 'inventario': inventario})


# ── Clientes frecuentes ──
@app.route('/api/clientes')
def get_clientes():
    resultado = [
        {'telefono': tel, **data}
        for tel, data in sorted(clientes.items(), key=lambda x: -x[1].get('visitas', 0))
    ]
    return jsonify(resultado)


# ── Webhook WhatsApp (respuestas del cliente) ──
@app.route('/api/webhook-wa', methods=['POST'])
def webhook_wa():
    body   = request.form.get('Body', '').strip()
    from_  = request.form.get('From', '')
    tel    = from_.replace('whatsapp:+57', '').replace('whatsapp:+', '').replace('whatsapp:', '')

    # Buscar grupo activo del número
    grupo = next(
        (g for g in ninos.values() if g['activo'] and tel in g['telefono'].replace(' ', '')),
        None
    )

    if body == '1' and grupo:
        # Quiere continuar
        gid = grupo['id']
        srv = SERVICIOS[grupo['servicio']]
        cancelar_timers(gid)
        ahora = datetime.now()
        grupo['entrada'] = ahora
        grupo['salida']  = ahora + timedelta(minutes=srv['minutos'])
        programar_alertas(gid)
        nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
        msg = (
            f"⏱ *Tiempo renovado*\n\n"
            f"Listo, *{nombres}* tiene {srv['nombre']} más.\n"
            f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
            f"💰 {pesos(srv['precio'])} adicionales — acérquese a cancelar."
        )
        enviar_wa(grupo['telefono'], msg)

    elif body == '2' and grupo:
        # Quiere retirar
        gid = grupo['id']
        cancelar_timers(gid)
        grupo['activo'] = False
        ninos.pop(gid, None)
        enviar_wa(grupo['telefono'], msg_despedida(grupo))

    else:
        # Mensaje no reconocido — el agente IA responderá en la próxima fase
        respuesta = (
            f"Hola 👋 Soy el asistente de *Inflaboom*.\n\n"
            f"Para consultas escríbenos o visítanos en el parque. ¡Gracias!"
        )
        enviar_wa(tel, respuesta)

    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}


# ── KPIs rápidos del día ──
@app.route('/api/kpis')
def get_kpis():
    total_ventas   = sum(h['precio_total'] for h in historial)
    total_ninos    = sum(len(h['ninos']) for h in historial)
    activos_ahora  = len(ninos)
    efectivo       = sum(h['precio_total'] for h in historial if h['pago'] == 'Efectivo')
    transferencia  = total_ventas - efectivo
    return jsonify({
        'total_ventas':  total_ventas,
        'total_ninos':   total_ninos,
        'activos_ahora': activos_ahora,
        'efectivo':      efectivo,
        'transferencia': transferencia,
        'alertas':       alerta_inventario_bajo(),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
