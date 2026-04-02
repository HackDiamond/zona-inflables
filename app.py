# ================================================================
#  INFLABOOM — Servidor con Agente WhatsApp Inteligente
#  Python + Flask + Twilio + Supabase + Claude (Anthropic)
# ================================================================

from flask import Flask, request, jsonify, send_from_directory
from twilio.rest import Client as TwilioClient
from datetime import datetime, timedelta
from supabase import create_client
import anthropic
import threading
import os
import json

app = Flask(__name__, static_folder='public', static_url_path='')

# ── Credenciales ──
TWILIO_SID      = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER   = os.environ.get('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')
SUPABASE_URL    = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY    = os.environ.get('SUPABASE_KEY', '')
ANTHROPIC_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')

# ── Clientes externos ──
twilio   = TwilioClient(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
claude   = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ── Estado en memoria ──
ninos_activos   = {}   # id -> grupo activo
timers          = {}   # id -> [timers]
conversaciones  = {}   # telefono -> [historial mensajes para el agente]

# ── Catálogo ──
SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',   'minutos': 15,  'precio': 5000,  'manilla': False, 'juegos': '1 juego a elección'},
    'combo_30':  {'nombre': '30 minutos',   'minutos': 30,  'precio': 8000,  'manilla': False, 'juegos': '2 juegos a elección'},
    'combo_1h':  {'nombre': '1 hora',       'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos (todos)'},
    'promo_2x1': {'nombre': 'Promo 2x1',    'minutos': 60,  'precio': 13000, 'manilla': True,  'juegos': '4 juegos — 2 niños'},
    'arte':      {'nombre': 'Estación arte', 'minutos': None,'precio': 5000,  'manilla': False, 'juegos': 'Pintura en caballete'},
}


# ================================================================
#  SISTEMA PROMPT DEL AGENTE
# ================================================================

def get_system_prompt(telefono):
    """Genera el prompt del agente con contexto en tiempo real."""

    # Buscar si hay niños activos de este número
    grupo_activo = next(
        (g for g in ninos_activos.values() if telefono in g['telefono'].replace(' ','')),
        None
    )

    # Buscar historial del cliente en Supabase
    historial_cliente = ''
    if supabase:
        try:
            res = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
            if res.data:
                c = res.data[0]
                historial_cliente = (
                    f"- Cliente registrado: {c['nombre']}\n"
                    f"- Visitas totales: {c['visitas']}\n"
                    f"- Total gastado: ${c['total_gastado']:,}\n"
                    f"- Última visita: {c.get('ultimo_visita','')[:10]}"
                )
        except:
            pass

    # Estado del niño activo
    estado_activo = ''
    if grupo_activo:
        ninos_nombres = ', '.join([n['nombre'] for n in grupo_activo['ninos']])
        salida = grupo_activo['salida']
        if salida:
            ahora = datetime.now()
            salida_dt = salida if isinstance(salida, datetime) else datetime.fromisoformat(str(salida))
            restantes = max(0, int((salida_dt - ahora).total_seconds() / 60))
            estado_activo = (
                f"- NIÑO(S) ACTIVO(S): {ninos_nombres}\n"
                f"- Combo: {SERVICIOS[grupo_activo['servicio']]['nombre']}\n"
                f"- Minutos restantes: {restantes}\n"
                f"- Salida programada: {salida_dt.strftime('%I:%M %p')}"
            )
        else:
            estado_activo = f"- NIÑO(S) EN ESTACIÓN ARTE: {ninos_nombres}"

    hoy = datetime.now()
    es_sabado = hoy.weekday() == 5

    return f"""Eres el asistente virtual de *Inflaboom*, un parque de recreación infantil en Palmira, Colombia.
Tu nombre es *Boom* 🎪 Eres amable, rápido y profesional. Respondes en español, de forma corta y clara.

═══ INFORMACIÓN DEL NEGOCIO ═══
📍 Ubicación: Parque principal de Palmira, Colombia
🕐 Horario: Todos los días (zona abierta al público)
📞 Atención en punto y por WhatsApp

═══ SERVICIOS EN EL PUNTO ═══
• 15 minutos — $5.000 (1 juego a elección)
• 30 minutos — $8.000 (2 juegos a elección) 
• 1 hora — $13.000 (4 juegos: Trampolín, Piscina pelotas, Mega inflable Minecraft, Inflable grande)
• Estación de arte — $5.000 por niño (pintura en caballete con dibujo de personaje)
{f"• 🎉 PROMO SÁBADO 2x1: Combo 1 hora, paga 1 y entran 2 niños — $13.000" if es_sabado else "• Promo 2x1: Solo sábados — combo 1 hora, paga 1 y entran 2 niños"}

═══ ATRACCIONES ═══
1. Trampolín
2. Piscina de pelotas
3. Mega inflable Minecraft
4. Inflable grande

═══ ALQUILERES Y EVENTOS ═══
Ofrecemos alquiler de inflables para fiestas y eventos:
• Inflables medianos, grandes y mega inflables
• Mínimo 3 horas de alquiler
• Trampolín disponible (tarde completa: 2:30 a 7:30 pm)
• Inflables acuáticos disponibles
• Palo loco (servicio premium)
• Estación de arte para eventos
• Descuentos por combinar 2 o más servicios
• Paquetes de recreación desde $200.000 (entre semana) y $220.000 (sábados, domingos y festivos)
Cada cotización es personalizada. Para cotizar un evento, solicita: fecha, lugar, servicios que te interesan y número de niños.

═══ CLIENTE ACTUAL ═══
{historial_cliente if historial_cliente else "- Cliente nuevo (sin historial previo)"}

═══ ESTADO EN TIEMPO REAL ═══
{estado_activo if estado_activo else "- No hay niños activos de este número en este momento"}

═══ REGLAS DE RESPUESTA ═══
1. Sé breve: máximo 3-4 líneas por respuesta
2. Usa emojis con moderación (máximo 2-3 por mensaje)
3. Si preguntan por tiempo restante y hay niño activo, dilo exactamente
4. Si quieren cotizar un evento, pide: fecha, lugar, servicios y número de niños
5. Si quieren extender tiempo, diles que respondan con el número 1
6. Si quieren retirar al niño, diles que respondan con el número 2
7. Para pagos acepta: Efectivo, Nequi, Daviplata y Transferencia
8. No inventes precios ni servicios que no estén en este prompt
9. Si no sabes algo, di "Te comunico con el equipo de Inflaboom para más info"
10. Siempre cierra con una frase amable y breve"""


# ================================================================
#  HELPERS
# ================================================================

def hora_legible(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z','+00:00'))
    return dt.strftime('%I:%M %p')

def es_sabado():
    return datetime.now().weekday() == 5

def pesos(n):
    return f'${int(n or 0):,}'.replace(',','.')

def enviar_wa(telefono, mensaje):
    if not twilio:
        print(f'[WA DEMO → {telefono}]: {mensaje[:60]}')
        return {'ok': True}
    try:
        num = telefono.replace(' ','').replace('-','')
        if not num.startswith('+'): num = '+57' + num.lstrip('0')
        msg = twilio.messages.create(from_=TWILIO_NUMBER, to=f'whatsapp:{num}', body=mensaje)
        return {'ok': True, 'sid': msg.sid}
    except Exception as e:
        print(f'[WA ERROR] {e}')
        return {'ok': False, 'error': str(e)}

def sb_insert(tabla, data):
    if not supabase: return None
    try: return supabase.table(tabla).insert(data).execute()
    except Exception as e: print(f'[DB INSERT {tabla}] {e}')

def sb_update(tabla, data, match):
    if not supabase: return None
    try:
        q = supabase.table(tabla).update(data)
        for k,v in match.items(): q = q.eq(k,v)
        return q.execute()
    except Exception as e: print(f'[DB UPDATE {tabla}] {e}')

def registrar_cliente_db(telefono, nombre, precio):
    if not supabase: return
    try:
        res = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
        if res.data:
            c = res.data[0]
            supabase.table('clientes').update({
                'visitas': c['visitas']+1,
                'total_gastado': c['total_gastado']+precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).eq('telefono', telefono).execute()
        else:
            supabase.table('clientes').insert({
                'telefono': telefono, 'nombre': nombre,
                'visitas': 1, 'total_gastado': precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).execute()
    except Exception as e: print(f'[DB CLIENTE] {e}')

def descontar_inventario_db(servicio, ninos_lista):
    if not supabase: return
    try:
        srv = SERVICIOS.get(servicio,{})
        if srv.get('manilla'):
            res = supabase.table('inventario').select('cantidad').eq('producto','manillas').execute()
            if res.data:
                nueva = max(0, res.data[0]['cantidad'] - len(ninos_lista))
                supabase.table('inventario').update({'cantidad':nueva,'updated_at':datetime.now().isoformat()}).eq('producto','manillas').execute()
        for n in ninos_lista:
            if n.get('dibujo'):
                p = f"dibujo_{n['dibujo'].lower().strip()}"
                res = supabase.table('inventario').select('cantidad').eq('producto',p).execute()
                if res.data:
                    nueva = max(0, res.data[0]['cantidad']-1)
                    supabase.table('inventario').update({'cantidad':nueva,'updated_at':datetime.now().isoformat()}).eq('producto',p).execute()
    except Exception as e: print(f'[DB INV] {e}')

def alertas_stock_db():
    if not supabase: return []
    try:
        res = supabase.table('inventario').select('*').execute()
        return [f"⚠️ {r['producto']}: solo {r['cantidad']} disponibles"
                for r in (res.data or []) if r['cantidad'] <= r['umbral_alerta']]
    except: return []


# ================================================================
#  MENSAJES AUTOMÁTICOS
# ================================================================

def msg_bienvenida(g):
    srv = SERVICIOS[g['servicio']]
    nombres = ', '.join([n['nombre'] for n in g['ninos']])
    es_grupo = len(g['ninos']) > 1
    acudiente = g.get('acudiente') or 'acudiente'
    es_promo = g['servicio'] == 'promo_2x1'
    es_arte  = g['servicio'] == 'arte'

    if es_arte:
        dibujos = ', '.join([f"{n['nombre']} ({n.get('dibujo') or '?'})" for n in g['ninos']])
        return (f"🎨 *Inflaboom — Estación de Arte*\n\nHola {acudiente} 👋\n\n"
                f"{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado a pintar.\n\n"
                f"🖌 *{'Niños' if es_grupo else 'Niño/a'}:* {dibujos}\n"
                f"💰 *Valor:* {pesos(g['precio_total'])} — {g['pago']}\n\n¡A disfrutar! 🌟")

    salida = hora_legible(g['salida'])
    txt = (f"🎪 *Inflaboom — {'¡Promo 2x1!' if es_promo else 'Bienvenida'}*\n\nHola {acudiente} 👋\n\n"
           f"*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado.*\n\n"
           f"👦 *{'Niños' if es_grupo else 'Niño/a'}:* {nombres}\n"
           f"🎮 *Combo:* {srv['nombre']} — {srv['juegos']}\n"
           f"🕐 *Ingreso:* {hora_legible(g['entrada'])}\n"
           f"🕐 *Salida:* {salida}\n"
           f"💰 *Valor:* {pesos(g['precio_total'])} — {g['pago']}")
    if es_promo: txt += "\n\n🎉 *¡Promo 2x1 aplicada!*"
    return txt

def msg_recibo(g):
    srv = SERVICIOS[g['servicio']]
    nombres = ', '.join([n['nombre'] for n in g['ninos']])
    return (f"🧾 *Recibo — Inflaboom*\n\n"
            f"👦 {'Niños' if len(g['ninos'])>1 else 'Niño/a'}: {nombres}\n"
            f"🎮 Servicio: {srv['nombre']}\n"
            f"💵 Valor: {pesos(g['precio_total'])}\n"
            f"💳 Pago: {g['pago']}\n"
            f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n_Gracias_ ✅")

def msg_aviso(g):
    nombres = ', '.join([n['nombre'] for n in g['ninos']])
    return (f"⏰ *Recordatorio — Inflaboom*\n\n"
            f"Le quedan *5 minutos* a *{nombres}*.\n"
            f"Por favor acérquese a la zona de ingreso 🙏")

def msg_fin(g):
    nombres = ', '.join([n['nombre'] for n in g['ninos']])
    return (f"🔔 *Tiempo finalizado — Inflaboom*\n\n"
            f"El tiempo de *{nombres}* ha terminado.\n\n"
            f"Responde:\n*1* → Más tiempo\n*2* → Los retiro ahora")

def msg_despedida(g):
    nombres = ', '.join([n['nombre'] for n in g['ninos']])
    promo = '\n\n🎉 *Promo sábados:* 2x1 en combo 1h. ¡Tráigale un amiguito!' if es_sabado() else ''
    return (f"🌟 *¡Hasta pronto! — Inflaboom*\n\n"
            f"Gracias por visitarnos con *{nombres}*. ¡Que lo hayan disfrutado! 😊\n\n"
            f"📍 ¡Los esperamos pronto!{promo}")


# ================================================================
#  TEMPORIZADORES
# ================================================================

def programar_alertas(gid):
    g = ninos_activos.get(gid)
    if not g or not g.get('salida'): return
    ahora  = datetime.now()
    salida = g['salida'] if isinstance(g['salida'], datetime) else datetime.fromisoformat(str(g['salida']))
    seg_total = (salida - ahora).total_seconds()
    seg_aviso = seg_total - 300

    def aviso():
        grp = ninos_activos.get(gid)
        if grp: enviar_wa(grp['telefono'], msg_aviso(grp))

    def fin():
        grp = ninos_activos.get(gid)
        if grp: enviar_wa(grp['telefono'], msg_fin(grp))

    tlist = []
    if seg_aviso > 0:
        t = threading.Timer(seg_aviso, aviso); t.start(); tlist.append(t)
    t2 = threading.Timer(max(seg_total,1), fin); t2.start(); tlist.append(t2)
    timers[gid] = tlist

def cancelar_timers(gid):
    for t in timers.pop(gid, []): t.cancel()


# ================================================================
#  AGENTE IA — Claude responde mensajes de WhatsApp
# ================================================================

def respuesta_agente(telefono, mensaje_usuario):
    """Llama a Claude con contexto completo del negocio y del cliente."""
    if not claude:
        return "Hola 👋 Soy el asistente de Inflaboom. Por el momento estoy en modo demo. ¡Visítanos en el parque!"

    # Mantener historial de conversación (máximo 10 mensajes)
    if telefono not in conversaciones:
        conversaciones[telefono] = []

    conversaciones[telefono].append({
        'role': 'user',
        'content': mensaje_usuario
    })

    # Limitar a últimos 10 mensajes para no gastar tokens
    historial = conversaciones[telefono][-10:]

    try:
        response = claude.messages.create(
            model='claude-opus-4-5',
            max_tokens=300,
            system=get_system_prompt(telefono),
            messages=historial
        )
        respuesta = response.content[0].text

        # Guardar respuesta en el historial
        conversaciones[telefono].append({
            'role': 'assistant',
            'content': respuesta
        })

        return respuesta

    except Exception as e:
        print(f'[AGENTE ERROR] {e}')
        return "Hola 👋 En este momento no puedo procesar tu mensaje. Por favor visítanos en el parque o escribe de nuevo en un momento."


# ================================================================
#  RUTAS
# ================================================================

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


@app.route('/api/registrar', methods=['POST'])
def registrar():
    data      = request.json
    servicio  = data.get('servicio')
    acudiente = data.get('acudiente','')
    telefono  = data.get('telefono','')
    pago      = data.get('pago','Efectivo')
    ninos     = data.get('ninos',[])

    if not servicio or not telefono or not ninos:
        return jsonify({'ok':False,'error':'Faltan campos obligatorios'}), 400

    srv = SERVICIOS.get(servicio)
    if not srv: return jsonify({'ok':False,'error':'Servicio inválido'}), 400

    precio_total = srv['precio'] if servicio=='promo_2x1' else srv['precio']*len(ninos)
    ahora  = datetime.now()
    minutos= srv.get('minutos')
    salida = ahora + timedelta(minutes=minutos) if minutos else None
    gid    = str(int(ahora.timestamp()*1000))

    grupo = {
        'id': gid, 'servicio': servicio, 'acudiente': acudiente,
        'telefono': telefono, 'pago': pago, 'ninos': ninos,
        'precio_total': precio_total, 'entrada': ahora, 'salida': salida, 'activo': True,
    }
    ninos_activos[gid] = grupo

    sb_insert('registros', {
        'id': gid, 'servicio': servicio, 'acudiente': acudiente,
        'telefono': telefono, 'pago': pago, 'ninos': ninos,
        'precio_total': precio_total, 'entrada': ahora.isoformat(),
        'salida': salida.isoformat() if salida else None, 'activo': True,
    })

    descontar_inventario_db(servicio, ninos)
    registrar_cliente_db(telefono, acudiente, precio_total)
    programar_alertas(gid)
    enviar_wa(telefono, msg_bienvenida(grupo))
    threading.Timer(2.0, lambda: enviar_wa(telefono, msg_recibo(grupo))).start()

    return jsonify({'ok':True,'id':gid,'salida':salida.isoformat() if salida else None,
                    'precio_total':precio_total,'alertas':alertas_stock_db()})


@app.route('/api/retirar', methods=['POST'])
def retirar():
    gid   = request.json.get('id')
    grupo = ninos_activos.pop(gid, None)
    if not grupo: return jsonify({'ok':False,'error':'No encontrado'}), 404
    cancelar_timers(gid)
    sb_update('registros',{'activo':False},{'id':gid})
    enviar_wa(grupo['telefono'], msg_despedida(grupo))
    return jsonify({'ok':True})


@app.route('/api/extender', methods=['POST'])
def extender():
    data     = request.json
    gid      = data.get('id')
    servicio = data.get('servicio','combo_1h')
    pago     = data.get('pago','Efectivo')
    grupo    = ninos_activos.get(gid)
    if not grupo: return jsonify({'ok':False,'error':'No encontrado'}), 404

    srv   = SERVICIOS[servicio]
    cancelar_timers(gid)
    ahora = datetime.now()
    grupo.update({'servicio':servicio,'entrada':ahora,
                  'salida':ahora+timedelta(minutes=srv['minutos']),'pago':pago})
    programar_alertas(gid)
    sb_update('registros',{'servicio':servicio,'salida':grupo['salida'].isoformat(),'pago':pago},{'id':gid})

    nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
    enviar_wa(grupo['telefono'],
        f"⏱ *Tiempo extendido*\n\n*{nombres}* tiene {srv['nombre']} más.\n"
        f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
        f"💰 {pesos(srv['precio'])} — {pago}")
    return jsonify({'ok':True,'salida':grupo['salida'].isoformat()})


@app.route('/api/activos')
def get_activos():
    ahora = datetime.now()
    resultado = []
    for gid, g in ninos_activos.items():
        salida = g['salida']
        ms = int((salida-ahora).total_seconds()*1000) if salida else None
        resultado.append({
            'id':gid,'servicio':g['servicio'],'acudiente':g['acudiente'],
            'telefono':g['telefono'],'pago':g['pago'],'ninos':g['ninos'],
            'precio_total':g['precio_total'],'entrada':g['entrada'].isoformat(),
            'salida':salida.isoformat() if salida else None,
            'ms_restantes':max(ms,0) if ms is not None else None,
        })
    return jsonify(resultado)


@app.route('/api/historial')
def get_historial():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('registros').select('*')\
                .gte('entrada',f'{fecha}T00:00:00').lte('entrada',f'{fecha}T23:59:59')\
                .order('entrada',desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e: print(f'[HISTORIAL] {e}')
    return jsonify([])


@app.route('/api/kpis')
def get_kpis():
    fecha = datetime.now().strftime('%Y-%m-%d')
    tv=tn=ef=tr=0
    if supabase:
        try:
            res = supabase.table('registros').select('precio_total,pago,ninos')\
                .gte('entrada',f'{fecha}T00:00:00').execute()
            for r in (res.data or []):
                tv += r['precio_total'] or 0
                nl = r['ninos'] if isinstance(r['ninos'],list) else json.loads(r['ninos'] or '[]')
                tn += len(nl)
                if r['pago']=='Efectivo': ef += r['precio_total'] or 0
                else: tr += r['precio_total'] or 0
        except Exception as e: print(f'[KPIS] {e}')
    return jsonify({'total_ventas':tv,'total_ninos':tn,'activos_ahora':len(ninos_activos),
                    'efectivo':ef,'transferencia':tr,'alertas':alertas_stock_db()})


@app.route('/api/inventario')
def get_inventario():
    if supabase:
        try:
            res = supabase.table('inventario').select('*').order('producto').execute()
            inv = {r['producto']:{'cantidad':r['cantidad'],'umbral':r['umbral_alerta']} for r in (res.data or [])}
            return jsonify(inv)
        except Exception as e: print(f'[INV GET] {e}')
    return jsonify({'manillas':{'cantidad':100,'umbral':10},'pinturas':{'cantidad':50,'umbral':10}})

@app.route('/api/inventario/agregar', methods=['POST'])
def agregar_stock():
    data     = request.json
    tipo     = data.get('tipo')
    cantidad = int(data.get('cantidad',0))
    personaje= data.get('personaje','').lower().strip()
    producto = f'dibujo_{personaje}' if tipo=='dibujo' and personaje else tipo
    if supabase:
        try:
            res = supabase.table('inventario').select('cantidad').eq('producto',producto).execute()
            if res.data:
                supabase.table('inventario').update({'cantidad':res.data[0]['cantidad']+cantidad,'updated_at':datetime.now().isoformat()}).eq('producto',producto).execute()
            else:
                supabase.table('inventario').insert({'producto':producto,'cantidad':cantidad,'umbral_alerta':5}).execute()
        except Exception as e: print(f'[INV ADD] {e}')
    return jsonify({'ok':True})


@app.route('/api/gastos', methods=['GET'])
def get_gastos():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('gastos').select('*').eq('fecha',fecha).order('created_at',desc=True).execute()
            return jsonify(res.data or [])
        except: pass
    return jsonify([])

@app.route('/api/gastos', methods=['POST'])
def agregar_gasto():
    data = request.json
    sb_insert('gastos',{'categoria':data.get('categoria'),'descripcion':data.get('descripcion'),
                         'valor':int(data.get('valor',0)),'fecha':data.get('fecha',datetime.now().strftime('%Y-%m-%d'))})
    return jsonify({'ok':True})


@app.route('/api/clientes')
def get_clientes():
    if supabase:
        try:
            res = supabase.table('clientes').select('*').order('visitas',desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e: print(f'[CLIENTES] {e}')
    return jsonify([])


@app.route('/api/eventos', methods=['GET'])
def get_eventos():
    if supabase:
        try:
            res = supabase.table('eventos').select('*').order('created_at',desc=True).execute()
            return jsonify(res.data or [])
        except: pass
    return jsonify([])

@app.route('/api/eventos', methods=['POST'])
def crear_evento():
    d = request.json
    sb_insert('eventos',{
        'tipo':d.get('tipo','evento'),'cliente':d.get('cliente'),'telefono':d.get('telefono'),
        'festejado':d.get('festejado'),'anos':d.get('anos'),'ninos_aprox':d.get('ninos_aprox'),
        'fecha_evento':d.get('fecha_evento'),'lugar':d.get('lugar'),'servicios':d.get('servicios'),
        'observaciones':d.get('observaciones'),'precio_total':int(d.get('precio_total',0)),
        'anticipo':int(d.get('anticipo',0)),'estado':d.get('estado','cotizado'),'pago':d.get('pago',''),
    })
    return jsonify({'ok':True})

@app.route('/api/eventos/<int:evento_id>', methods=['PATCH'])
def actualizar_evento(evento_id):
    sb_update('eventos', request.json, {'id':evento_id})
    return jsonify({'ok':True})


@app.route('/api/reportes/mes')
def reporte_mes():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    if not supabase: return jsonify({'ventas':[],'gastos':[],'eventos':[]})
    try:
        inicio=f'{mes}-01T00:00:00'; fin=f'{mes}-31T23:59:59'
        ventas  = supabase.table('registros').select('*').gte('entrada',inicio).lte('entrada',fin).execute().data or []
        gastos  = supabase.table('gastos').select('*').gte('fecha',f'{mes}-01').lte('fecha',f'{mes}-31').execute().data or []
        eventos = supabase.table('eventos').select('*').gte('fecha_evento',f'{mes}-01').lte('fecha_evento',f'{mes}-31').execute().data or []
        return jsonify({'ventas':ventas,'gastos':gastos,'eventos':eventos})
    except Exception as e:
        print(f'[REPORTE] {e}')
        return jsonify({'ventas':[],'gastos':[],'eventos':[]})


# ================================================================
#  WEBHOOK WHATSAPP — Mensajes automáticos + Agente IA
# ================================================================

@app.route('/api/webhook-wa', methods=['POST'])
def webhook_wa():
    body  = request.form.get('Body','').strip()
    from_ = request.form.get('From','')
    tel   = from_.replace('whatsapp:+57','').replace('whatsapp:+','').replace('whatsapp:','')

    # Buscar grupo activo de este número
    grupo = next(
        (g for g in ninos_activos.values() if tel in g['telefono'].replace(' ','')),
        None
    )

    # ── Respuestas numéricas (1 = continuar, 2 = retirar) ──
    if body == '1' and grupo:
        srv = SERVICIOS[grupo['servicio']]
        cancelar_timers(grupo['id'])
        ahora = datetime.now()
        grupo['entrada'] = ahora
        grupo['salida']  = ahora + timedelta(minutes=srv['minutos'])
        programar_alertas(grupo['id'])
        nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
        enviar_wa(grupo['telefono'],
            f"⏱ *Tiempo renovado*\n\n*{nombres}* tiene {srv['nombre']} más.\n"
            f"🕐 Nueva salida: {hora_legible(grupo['salida'])}\n"
            f"💰 {pesos(srv['precio'])} adicionales — acérquese a cancelar.")

    elif body == '2' and grupo:
        gid = grupo['id']
        cancelar_timers(gid)
        ninos_activos.pop(gid, None)
        sb_update('registros',{'activo':False},{'id':gid})
        enviar_wa(grupo['telefono'], msg_despedida(grupo))

    else:
        # ── Agente IA responde cualquier otro mensaje ──
        def responder_async():
            respuesta = respuesta_agente(tel, body)
            enviar_wa(tel, respuesta)
        threading.Thread(target=responder_async).start()

    return '<Response></Response>', 200, {'Content-Type':'text/xml'}


# ================================================================
#  ARRANQUE
# ================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f'🎪 Inflaboom + Agente IA arrancando en puerto {port}')
    print(f'   Claude: {"✅ conectado" if claude else "⚠ no configurado"}')
    print(f'   Supabase: {"✅ conectado" if supabase else "⚠ no configurado"}')
    print(f'   Twilio: {"✅ conectado" if twilio else "⚠ no configurado"}')
    app.run(host='0.0.0.0', port=port, debug=False)
