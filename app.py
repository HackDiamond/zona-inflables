# ================================================================
#  INFLABOOM — Servidor con Agente WhatsApp Inteligente
#  Python + Flask + Evolution API + Supabase + Claude (Anthropic)
#  v1.8.4 - Migración a Evolution API, PWA y Tiquete Ganador
# ================================================================

from flask import Flask, request, jsonify, send_from_directory, Response
from datetime import datetime, timedelta, date
from calendar import monthrange
from supabase import create_client
import anthropic
import threading
import logging
import os
import re
import json
import hashlib
import requests

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "Arktos", "Motor Arktos (Sistema SaaS)", "01 - Input")
OUTPUT_DIR = os.path.join(BASE_DIR, "Arktos", "Motor Arktos (Sistema SaaS)", "03 - Output")


def _find_input_file():
    candidates = [
        os.path.join(INPUT_DIR, "inflaboom_progreso_v1.1.md"),
        os.path.join(INPUT_DIR, "Inflaboom.md"),
        os.path.join(BASE_DIR, "inflaboom_progreso_v1.1.md"),
        os.path.join(BASE_DIR, "inflaboom_progreso_v1.1"),
    ]
    for path in candidates:
        if os.path.isfile(path): return path
    return None

def _parse_sections(md_text):
    pattern = re.compile(r'^#{2,3}\s+(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(md_text))
    sections = {}
    for i, match in enumerate(matches):
        raw_title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[start:end].strip()
        clean_key = re.sub(r'[^\w\s\-]', '', raw_title, flags=re.UNICODE).strip().lower()
        sections[clean_key] = content
    return sections

def _get(sections, *keywords):
    for key in sections:
        for kw in keywords:
            if kw.lower() in key: return sections[key]
    return ''

def _get_all(sections, *keywords):
    seen, results = set(), []
    for key in sections:
        for kw in keywords:
            if kw.lower() in key and key not in seen:
                results.append(sections[key])
                seen.add(key)
                break
    return '\n\n'.join(results)

def generate_system():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    input_path = _find_input_file()
    if not input_path: raise FileNotFoundError(f"Archivo de entrada no encontrado en {INPUT_DIR}.")

    with open(input_path, encoding='utf-8') as f:
        sec = _parse_sections(f.read())

    outputs = {
        "Clientes.md": ("# Clientes\n\n## Modelo de Datos\n\n" + _get(sec, 'modelo de dato', 'redise', '2 redise') + "\n\n## Sistema de Roles\n\n" + _get(sec, 'roles diferenciado', '3 sistema') + "\n\n## Lógica de Duplicados\n\n" + _get(sec, 'whatsapp para completar', '5 flujo de whatsapp', 'duplicado', 'segmento')),
        "Finanzas.md": ("# Finanzas\n\n## Sistema de Tiquetes y Fidelización\n\n" + _get(sec, 'tiquete ganador', '6 programa tiquete') + "\n\n## Ticket Promedio\n\n" + _get(sec, 'p2', 'ticket promedio por debajo', 'modelo de ingreso', 'ingreso')),
        "Operaciones.md": ("# Operaciones\n\n## Migración a n8n\n\n" + _get(sec, 'reemplazo de twilio', '1 reemplazo', 'orquestador') + "\n\n## Flujo de Caja — 3 Pasos\n\n" + _get(sec, 'flujo de registro', '4 flujo', 'caja') + "\n\n## Flujos n8n — Punto de Atención\n\n" + _get(sec, 'flujos de n8n', '7 flujos', 'n8n definidos') + "\n\n## Decisiones de Arquitectura\n\n" + _get(sec, 'arquitectura')),
        "Problemas.md": ("# Problemas\n\n## Problemas Identificados\n\n" + _get_all(sec, 'p1 ', 'p2 ', 'p3 ', 'p4 ') + "\n\n## Próximos Pasos\n\n" + _get_all(sec, 'inmediato', 'corto plazo', 'mediano plazo', 'oportunidad', 'mejora')),
    }
    generated = []
    for filename, content in outputs.items():
        with open(os.path.join(OUTPUT_DIR, filename), 'w', encoding='utf-8') as f: f.write(content)
        generated.append(filename)
    return generated

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder='public', static_url_path='')

@app.route("/")
def home():
    path = os.path.join(app.static_folder, 'index.html')
    with open(path, 'r', encoding='utf-8') as f: html = f.read()
    return Response(html, content_type='text/html; charset=utf-8')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

EVO_API_URL     = os.environ.get('EVO_API_URL', '').strip()
EVO_API_KEY     = os.environ.get('EVO_API_KEY', '').strip()
EVO_INSTANCE    = os.environ.get('EVO_INSTANCE', 'inflaboom').strip()
SUPABASE_URL    = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY    = os.environ.get('SUPABASE_KEY', '').strip()
ANTHROPIC_KEY   = os.environ.get('ANTHROPIC_API_KEY', '').strip()
API_KEY         = os.environ.get('API_KEY', 'inflaboom123').strip()
DUENO_WA        = os.environ.get('DUENO_WA', '+573000000000').strip()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
claude   = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

_lock           = threading.Lock()
ninos_activos   = {}
timers          = {}
conversaciones  = {}

SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',      'minutos': 15,  'precio': 5000,  'manilla': False, 'categoria': 'juegos'},
    'combo_30':  {'nombre': '30 minutos',      'minutos': 30,  'precio': 8000,  'manilla': False, 'categoria': 'juegos'},
    'combo_1h':  {'nombre': '1 hora',          'minutos': 60,  'precio': 13000, 'manilla': True,  'categoria': 'juegos'},
    'promo_2x1': {'nombre': 'Promo 2x1',       'minutos': 60,  'precio': 13000, 'manilla': True,  'categoria': 'juegos'},
    'arte':      {'nombre': 'Estación de arte','minutos': None,'precio': 6000,  'manilla': False, 'categoria': 'arte'},
}

from functools import wraps

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = (request.headers.get('X-API-Key') or (request.get_json(silent=True) or {}).get('api_key') or request.args.get('api_key', ''))
        if key != API_KEY: return jsonify({'ok': False, 'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

def get_system_prompt(telefono):
    with _lock: grupo_activo = next((g for g in ninos_activos.values() if normalizar_telefono(g['telefono']) == normalizar_telefono(telefono)), None)
    historial_cliente = ''
    if supabase:
        try:
            res = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
            if res.data:
                c = res.data[0]
                historial_cliente = f"- Cliente registrado: {c['nombre']}\n- Visitas totales: {c['visitas']}\n- Total gastado: ${c['total_gastado']:,}\n- Última visita: {c.get('ultimo_visita','')[:10]}"
        except Exception as e: log.error('[SYSTEM PROMPT CLIENTE] %s', e)

    estado_activo = ''
    if grupo_activo:
        ninos_nombres = ', '.join([n['nombre'] for n in grupo_activo['ninos']])
        salida = grupo_activo['salida']
        if salida:
            ahora = datetime.now()
            salida_dt = salida if isinstance(salida, datetime) else datetime.fromisoformat(str(salida))
            restantes = max(0, int((salida_dt - ahora).total_seconds() / 60))
            estado_activo = f"- NIÑO(S) ACTIVO(S): {ninos_nombres}\n- Combo: {SERVICIOS[grupo_activo['servicio']]['nombre']}\n- Minutos restantes: {restantes}\n- Salida programada: {salida_dt.strftime('%I:%M %p')}"
        else: estado_activo = f"- NIÑO(S) EN ESTACIÓN ARTE: {ninos_nombres}"

    hoy = datetime.now()
    es_sabado = hoy.weekday() == 5

    return f"""Eres el asistente virtual de *Inflaboom*, un parque de recreación infantil en Palmira, Colombia.
Tu nombre es *Boom* 🎪 Eres amable, rápido y profesional. Respondes en español, de forma corta y clara.
═══ CLIENTE ACTUAL ═══
{historial_cliente if historial_cliente else "- Cliente nuevo (sin historial previo)"}
═══ ESTADO EN TIEMPO REAL ═══
{estado_activo if estado_activo else "- No hay niños activos de este número en este momento"}
═══ REGLAS DE RESPUESTA ═══
1. Sé breve: máximo 3-4 líneas por respuesta
2. Usa emojis con moderación (máximo 2-3 por mensaje)
3. Si preguntan por tiempo restante y hay niño activo, dilo exactamente
4. Si quieren extender tiempo, diles que respondan con el número 1
5. Si quieren retirar al niño, diles que respondan con el número 2
6. Para pagos acepta: Efectivo, Nequi, Daviplata y Transferencia"""

def hora_legible(dt):
    if isinstance(dt, str): dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime('%I:%M %p')

def es_sabado(): return datetime.now().weekday() == 5
def pesos(n): return f'${int(n or 0):,}'.replace(',', '.')

def normalizar_telefono(raw: str) -> str:
    num = raw.replace('whatsapp:', '').replace(' ', '').replace('-', '').lstrip('+')
    if num.startswith('57') and len(num) > 10: num = num[2:]
    return '+57' + num.lstrip('0') if not num.startswith('+') else '+' + num

def enviar_wa(telefono, mensaje):
    """Envía mensaje vía Evolution API"""
    num = normalizar_telefono(telefono).replace('+', '')
    
    if not EVO_API_URL or not EVO_API_KEY:
        log.info('[WA DEMO → %s]: %s', num, mensaje[:60])
        return {'ok': True}
        
    url = f"{EVO_API_URL.rstrip('/')}/message/sendText/{EVO_INSTANCE}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    data = {"number": num, "options": {"delay": 1500}, "textMessage": {"text": mensaje}}
    
    try:
        res = requests.post(url, headers=headers, json=data)
        if res.status_code in [200, 201]: return {'ok': True}
        log.error('[WA EVO ERROR] %s', res.text)
        return {'ok': False, 'error': res.text}
    except Exception as e:
        log.error('[WA HTTP ERROR] %s', e)
        return {'ok': False, 'error': str(e)}

def sb_insert(tabla, data):
    if not supabase: return None
    try: return supabase.table(tabla).insert(data).execute()
    except Exception as e: log.error('[DB INSERT %s] %s', tabla, e)

def sb_update(tabla, data, match):
    if not supabase: return None
    try:
        q = supabase.table(tabla).update(data)
        for k, v in match.items(): q = q.eq(k, v)
        return q.execute()
    except Exception as e: log.error('[DB UPDATE %s] %s', tabla, e)

def registrar_cliente_db(telefono, nombre, precio):
    if not supabase or not telefono: return 1
    try:
        res = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
        if res.data:
            c = res.data[0]
            nuevas_visitas = c['visitas'] + 1
            supabase.table('clientes').update({'visitas': nuevas_visitas, 'total_gastado': c['total_gastado'] + precio, 'ultimo_visita': datetime.now().isoformat()}).eq('telefono', telefono).execute()
            return nuevas_visitas
        else:
            supabase.table('clientes').insert({'telefono': telefono, 'nombre': nombre, 'visitas': 1, 'total_gastado': precio, 'ultimo_visita': datetime.now().isoformat()}).execute()
            return 1
    except Exception as e:
        log.error('[DB CLIENTE] %s', e)
        return 1

def descontar_inventario_db(servicio, ninos_lista):
    if not supabase: return
    try:
        srv = SERVICIOS.get(servicio, {})
        if srv.get('manilla'):
            res = supabase.table('inventario').select('cantidad').eq('producto', 'manillas').execute()
            if res.data: supabase.table('inventario').update({'cantidad': max(0, res.data[0]['cantidad'] - len(ninos_lista)), 'updated_at': datetime.now().isoformat()}).eq('producto', 'manillas').execute()
        for n in ninos_lista:
            if n.get('dibujo'):
                p = f"dibujo_{n['dibujo'].lower().strip()}"
                res = supabase.table('inventario').select('cantidad').eq('producto', p).execute()
                if res.data: supabase.table('inventario').update({'cantidad': max(0, res.data[0]['cantidad'] - 1), 'updated_at': datetime.now().isoformat()}).eq('producto', p).execute()
    except Exception as e: log.error('[DB INV] %s', e)

def alertas_stock_db():
    if not supabase: return []
    alertas = []
    try:
        res = supabase.table('inventario').select('*').execute()
        for r in (res.data or []):
            if r['cantidad'] <= r['umbral_alerta']: alertas.append(f"⚠️ {r['producto']}: solo {r['cantidad']} disponibles")
        res2 = supabase.table('productos').select('nombre,stock,stock_minimo').eq('activo', True).execute()
        for r in (res2.data or []):
            if r['stock'] <= r['stock_minimo']: alertas.append(f"🧸 {r['nombre']}: stock bajo ({r['stock']} unidades)")
    except Exception as e: log.error('[DB ALERTAS] %s', e)
    return alertas

def calcular_estado_fidelizacion(visitas):
    if visitas < 4: return f"🎟️ *Sellos Inflaboom:* {visitas} visita(s).\n¡Faltan {4 - visitas} para 1 HORA EXTRA GRATIS!"
    elif visitas == 4: return f"🎁 *¡PREMIO DESBLOQUEADO!* Tienes 1 HORA EXTRA GRATIS por tus 4 visitas."
    elif visitas < 8: return f"🎟️ *Sellos Inflaboom:* {visitas} visita(s).\n¡Faltan {8 - visitas} para 1 ENTRADA GRATIS!"
    elif visitas == 8: return f"🎁 *¡PREMIO DESBLOQUEADO!* Ganaste 1 ENTRADA GRATIS por tus 8 visitas."
    elif visitas < 12: return f"🎟️ *Sellos Inflaboom:* {visitas} visita(s).\n¡Faltan {12 - visitas} para 1 HORA DE TRAMPOLÍN!"
    elif visitas == 12: return f"🎁 *¡PREMIO DESBLOQUEADO!* Ganaste 1 HORA DE TRAMPOLÍN por tus 12 visitas."
    elif visitas < 18: return f"🎟️ *Sellos Inflaboom:* {visitas} visita(s).\n¡Faltan {18 - visitas} para 50% DESC. ALQUILER!"
    elif visitas == 18: return f"🎁 *¡PREMIO DESBLOQUEADO!* Ganaste 50% de descuento en alquiler de eventos."
    else: return f"🌟 *Cliente VIP:* ¡Llevas {visitas} visitas con nosotros!"

def generar_token_cliente(telefono): return hashlib.md5(f"{telefono}{API_KEY}".encode()).hexdigest()[:10]

def msg_bienvenida(v):
    acudiente = v.get('acudiente') or 'acudiente'
    lineas    = v.get('lineas', v.get('ninos', []))
    es_grupo  = len(lineas) > 1
    txt_lineas = ''
    for l in lineas:
        salida_str = hora_legible(l['salida']) if l.get('salida') else 'libre'
        txt_lineas += f"\n  • *{l['nombre']}* — {l['combo']} · sale {salida_str}"

    txt_fidelizacion = f"\n\n{calcular_estado_fidelizacion(v['visitas'])}" if v.get('visitas') else ""
    num_limpio = normalizar_telefono(v['telefono']).replace('+57', '')
    enlace_app = f"{request.host_url.rstrip('/')}/app/cliente/{num_limpio}/{generar_token_cliente(num_limpio)}"

    return (f"🎪 *Inflaboom — Bienvenida*\n\nHola {acudiente} 👋\n\n*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado:*{txt_lineas}\n\n💰 *Total:* {pesos(v['precio_total'])} — {v['pago']}{txt_fidelizacion}\n\n📱 *Abre tu App Inflaboom aquí para ver el tiempo en vivo y tus premios:*\n{enlace_app}")

def msg_recibo(v):
    lineas    = v.get('lineas', v.get('ninos', []))
    es_grupo  = len(lineas) > 1
    txt_items = '\n'.join([f"  • {l['nombre']} — {l['combo']} ({pesos(l['precio'])})" + (" [adicional]" if l.get('adicional') else "") for l in lineas])
    return (f"🧾 *Recibo — Inflaboom*\n\n{'Niños' if es_grupo else 'Niño/a'}:\n{txt_items}\n\n💵 *Total:* {pesos(v['precio_total'])}\n💳 *Pago:* {v['pago']}\n📅 {datetime.now().strftime('%d/%m/%Y')}\n\n_Gracias_ ✅")

def msg_aviso(g): return (f"⏰ *Recordatorio — Inflaboom*\n\nLe quedan *5 minutos* a *{', '.join([n['nombre'] for n in g['ninos']])}*.\nPor favor acérquese a la zona de ingreso 🙏")
def msg_fin(g): return (f"🔔 *Tiempo finalizado — Inflaboom*\n\nEl tiempo de *{', '.join([n['nombre'] for n in g['ninos']])}* ha terminado.\n\nResponde:\n*1* → Más tiempo\n*2* → Los retiro ahora")
def msg_despedida(g): return (f"🌟 *¡Hasta pronto! — Inflaboom*\n\nGracias por visitarnos con *{', '.join([n['nombre'] for n in g['ninos']])}*. ¡Que lo hayan disfrutado! 😊\n\n📍 ¡Los esperamos pronto!{'\n\n🎉 *Promo sábados:* 2x1 en combo 1h. ¡Tráigale un amiguito!' if es_sabado() else ''}")

def programar_alertas(gid):
    with _lock: g = ninos_activos.get(gid)
    if not g or not g.get('salida'): return
    ahora, salida = datetime.now(), g['salida'] if isinstance(g['salida'], datetime) else datetime.fromisoformat(str(g['salida']))
    seg_total = (salida - ahora).total_seconds()
    seg_aviso = seg_total - 300
    
    def aviso():
        with _lock: grp = ninos_activos.get(gid)
        if grp: enviar_wa(grp['telefono'], msg_aviso(grp))
    def fin():
        with _lock: grp = ninos_activos.get(gid)
        if grp: enviar_wa(grp['telefono'], msg_fin(grp))

    tlist = []
    if seg_aviso > 0:
        t = threading.Timer(seg_aviso, aviso); t.daemon = True; t.start(); tlist.append(t)
    t2 = threading.Timer(max(seg_total, 1), fin); t2.daemon = True; t2.start(); tlist.append(t2)
    with _lock: timers[gid] = tlist

def cancelar_timers(gid):
    with _lock: tlist = timers.pop(gid, [])
    for t in tlist: t.cancel()

def cargar_sesiones_activas():
    if not supabase: return
    try:
        res = supabase.table('registros').select('*').eq('activo', True).execute()
        count = 0
        for r in (res.data or []):
            salida = None
            if r.get('salida'):
                salida = datetime.fromisoformat(r['salida'].replace('Z', '+00:00')).replace(tzinfo=None)
                if salida < datetime.now():
                    sb_update('registros', {'activo': False}, {'id': r['id']})
                    continue
            ninos = r['ninos'] if isinstance(r['ninos'], list) else json.loads(r.get('ninos') or '[]')
            grupo = {'id': r['id'], 'servicio': r['servicio'], 'acudiente': r.get('acudiente', ''), 'telefono': r['telefono'], 'pago': r.get('pago', 'Efectivo'), 'ninos': ninos, 'precio_total': r.get('precio_total', 0), 'entrada': datetime.fromisoformat(r['entrada'].replace('Z', '+00:00')).replace(tzinfo=None), 'salida': salida, 'activo': True}
            with _lock: ninos_activos[r['id']] = grupo
            programar_alertas(r['id'])
            count += 1
        log.info('Sesiones activas recuperadas de BD: %d', count)
    except Exception as e: log.error('[STARTUP RECOVERY] %s', e)

def respuesta_agente(telefono, mensaje_usuario):
    if not claude: return "Hola 👋 Soy el asistente de Inflaboom. ¡Visítanos en el parque!"
    if telefono not in conversaciones: conversaciones[telefono] = []
    conversaciones[telefono].append({'role': 'user', 'content': mensaje_usuario})
    historial = conversaciones[telefono][-10:]
    try:
        response = claude.messages.create(model='claude-haiku-4-5-20251001', max_tokens=300, system=get_system_prompt(telefono), messages=historial)
        respuesta = response.content[0].text
        conversaciones[telefono].append({'role': 'assistant', 'content': respuesta})
        return respuesta
    except Exception as e:
        log.error('[AGENTE ERROR] %s', e)
        return "Hola 👋 En este momento no puedo procesar tu mensaje. Por favor visítanos en el parque."

# ── PWA CLIENTE ──
@app.route('/app/cliente/<telefono>/<token>')
def app_cliente(telefono, token):
    if token != generar_token_cliente(telefono): return "Enlace inválido o expirado", 403
    path = os.path.join(app.static_folder, 'cliente.html')
    if not os.path.exists(path):
        return """<html style="background:#0E0E10; color:#fff; font-family:sans-serif; text-align:center; padding:50px;"><h1 style="color:#19C7F7">INFLABOOM APP</h1><p>¡Estamos armando tu panel interactivo!</p></html>""", 200
    with open(path, 'r', encoding='utf-8') as f: html = f.read()
    return Response(html, content_type='text/html; charset=utf-8')

# ── NUEVA API: DATOS EXCLUSIVOS PARA PWA CLIENTE ──
@app.route('/api/app-cliente/datos/<telefono>/<token>')
def api_cliente_datos(telefono, token):
    if token != generar_token_cliente(telefono):
        return jsonify({'ok': False, 'error': 'Enlace inválido o expirado'}), 403

    visitas = 0
    nombre_cliente = "Cliente VIP"
    if supabase:
        try:
            res = supabase.table('clientes').select('visitas,nombre').eq('telefono', telefono).execute()
            if res.data:
                visitas = res.data[0]['visitas']
                nombre_cliente = res.data[0]['nombre']
        except Exception as e:
            log.error('[API CLIENTE PWA] %s', e)

    activos_cliente = []
    ahora = datetime.now()
    with _lock:
        for g in ninos_activos.values():
            if normalizar_telefono(g['telefono']).replace('+57', '') == telefono:
                for l in g.get('lineas', []):
                    if not l.get('activa', True): continue
                    ms = max(0, int((datetime.fromisoformat(l['salida']) - ahora).total_seconds() * 1000)) if l.get('salida') else None
                    activos_cliente.append({
                        'nombre': l['nombre'],
                        'combo': l['combo'],
                        'ms_restantes': ms
                    })

    return jsonify({'ok': True, 'nombre': nombre_cliente, 'visitas': visitas, 'activos': activos_cliente})
    
# ── CIERRE DE CAJA ──
@app.route('/api/resumen-dia', methods=['POST'])
@api_key_required
def cerrar_dia():
    fecha = datetime.now().strftime('%Y-%m-%d')
    try:
        ingresos, ninos_atendidos, gastos = 0, 0, 0
        if supabase:
            res = supabase.table('registros').select('precio_total, ninos').gte('entrada', f'{fecha}T00:00:00').execute()
            for r in (res.data or []):
                ingresos += r.get('precio_total', 0) or 0
                ninos_atendidos += len(json.loads(r['ninos']) if isinstance(r.get('ninos'), str) else (r.get('ninos') or []))
            res_g = supabase.table('gastos').select('valor').eq('fecha', fecha).execute()
            gastos = sum(g.get('valor', 0) or 0 for g in (res_g.data or []))
        utilidad = ingresos - gastos
        margen = round((utilidad / ingresos * 100) if ingresos > 0 else 0, 1)
        enviar_wa(DUENO_WA, f"📊 *CIERRE DE CAJA — {fecha}*\n\n📈 Ingresos: {pesos(ingresos)}\n📉 Gastos: {pesos(gastos)}\n💵 *UTILIDAD NETA:* {pesos(utilidad)}\n📊 Margen: {margen}%\n🎪 Niños atendidos: {ninos_atendidos}")
        return jsonify({'ok': True, 'mensaje': 'Resumen enviado a WhatsApp', 'utilidad': utilidad})
    except Exception as e:
        log.error('[CERRAR_DIA] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/generate-system")
def api_generate_system():
    try: return jsonify({"status": "ok", "files": generate_system()})
    except Exception as e: return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/registrar', methods=['POST'])
@api_key_required
def registrar():
    data = request.get_json(silent=True) or {}
    acudiente, telefono, pago, ninos = data.get('acudiente', ''), data.get('telefono', ''), data.get('pago', 'Efectivo'), data.get('ninos', [])
    if not telefono or not ninos: return jsonify({'ok': False, 'error': 'Faltan campos obligatorios'}), 400

    try:
        ahora, venta_id, precio_total, lineas = datetime.now(), str(int(datetime.now().timestamp() * 1000)), 0, []
        for n in ninos:
            srv = SERVICIOS[n['servicio']]
            minutos, precio = srv.get('minutos'), srv['precio']
            salida = (ahora + timedelta(minutes=minutos)).isoformat() if minutos else None
            precio_total += precio
            lineas.append({'id': f"{venta_id}_{len(lineas)+1}", 'venta_id': venta_id, 'nombre': n.get('nombre', ''), 'servicio': n['servicio'], 'combo': srv['nombre'], 'categoria': srv.get('categoria', 'juegos'), 'minutos': minutos, 'precio': precio, 'salida': salida, 'dibujo': n.get('dibujo', ''), 'activa': True})

        salidas_validas = [datetime.fromisoformat(l['salida']) for l in lineas if l['salida']]
        salida_grupo = max(salidas_validas) if salidas_validas else None
        venta = {'id': venta_id, 'acudiente': acudiente, 'telefono': telefono, 'pago': pago, 'lineas': lineas, 'precio_total': precio_total, 'entrada': ahora, 'salida': salida_grupo, 'activo': True}

        with _lock: ninos_activos[venta_id] = venta

        venta['visitas'] = registrar_cliente_db(telefono, acudiente, precio_total)
        sb_insert('registros', {'id': venta_id, 'acudiente': acudiente, 'telefono': telefono, 'pago': pago, 'ninos': lineas, 'precio_total': precio_total, 'entrada': ahora.isoformat(), 'salida': salida_grupo.isoformat() if salida_grupo else None, 'activo': True, 'servicio': lineas[0]['servicio'] if lineas else '', 'cliente_telefono': telefono or None, 'costo_estimado': 0})
        descontar_inventario_db(lineas[0]['servicio'], lineas)

        programar_alertas(venta_id)
        enviar_wa(telefono, msg_bienvenida(venta))
        threading.Timer(2.0, lambda: enviar_wa(telefono, msg_recibo(venta))).start()
        return jsonify({'ok': True, 'id': venta_id, 'lineas': lineas, 'precio_total': precio_total, 'alertas': alertas_stock_db()})
    except Exception as e:
        log.error('[REGISTRAR] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/agregar-linea', methods=['POST'])
@api_key_required
def agregar_linea():
    data = request.get_json(silent=True) or {}
    venta_id, nombre, servicio, pago = data.get('id'), data.get('nombre', ''), data.get('servicio', 'arte'), data.get('pago', '')
    with _lock: venta = ninos_activos.get(venta_id)
    if not venta: return jsonify({'ok': False, 'error': 'Venta no encontrada'}), 404
    srv = SERVICIOS.get(servicio)
    ahora, minutos = datetime.now(), srv.get('minutos')
    salida = (ahora + timedelta(minutes=minutos)).isoformat() if minutos else None
    nueva_linea = {'id': f"{venta_id}_{len(venta['lineas'])+1}", 'venta_id': venta_id, 'nombre': nombre, 'servicio': servicio, 'combo': srv['nombre'], 'categoria': srv.get('categoria', 'arte'), 'minutos': minutos, 'precio': srv['precio'], 'salida': salida, 'dibujo': data.get('dibujo', ''), 'activa': True, 'adicional': True}

    with _lock:
        venta['lineas'].append(nueva_linea)
        venta['precio_total'] += srv['precio']
        if salida:
            salida_dt = datetime.fromisoformat(salida)
            if not venta['salida'] or salida_dt > venta['salida']: venta['salida'] = salida_dt

    sb_update('registros', {'ninos': venta['lineas'], 'precio_total': venta['precio_total'], 'salida': venta['salida'].isoformat() if venta['salida'] else None}, {'id': venta_id})
    enviar_wa(venta['telefono'], f'\U0001f3a8 *Servicio adicional*\n\n*{nombre}* paso a {srv["nombre"]}.\n{pesos(srv["precio"])}\nTotal actualizado: {pesos(venta["precio_total"])}')
    return jsonify({'ok': True, 'linea': nueva_linea, 'precio_total': venta['precio_total']})

@app.route('/api/retirar', methods=['POST'])
@api_key_required
def retirar():
    gid = (request.get_json(silent=True) or {}).get('id')
    with _lock: venta = ninos_activos.pop(gid, None)
    if not venta: return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    cancelar_timers(gid)
    sb_update('registros', {'activo': False}, {'id': gid})
    enviar_wa(venta['telefono'], msg_despedida(venta))
    return jsonify({'ok': True})

@app.route('/api/retirar-linea', methods=['POST'])
@api_key_required
def retirar_linea():
    data = request.get_json(silent=True) or {}
    venta_id, linea_id = data.get('id'), data.get('linea_id')
    with _lock: venta = ninos_activos.get(venta_id)
    if not venta: return jsonify({'ok': False}), 404
    linea = next((l for l in venta['lineas'] if l['id'] == linea_id), None)
    with _lock:
        linea['activa'] = False
        linea['salida_real'] = datetime.now().isoformat()
        if all(not l.get('activa', True) for l in venta['lineas']):
            ninos_activos.pop(venta_id, None)
            cancelar_timers(venta_id)
            sb_update('registros', {'activo': False, 'ninos': venta['lineas']}, {'id': venta_id})
            enviar_wa(venta['telefono'], msg_despedida(venta))
            return jsonify({'ok': True, 'venta_cerrada': True})
    sb_update('registros', {'ninos': venta['lineas']}, {'id': venta_id})
    return jsonify({'ok': True, 'venta_cerrada': False, 'linea': linea})

@app.route('/api/extender', methods=['POST'])
@api_key_required
def extender():
    data = request.get_json(silent=True) or {}
    venta_id, linea_id, servicio, pago = data.get('id'), data.get('linea_id'), data.get('servicio', 'combo_1h'), data.get('pago', 'Efectivo')
    with _lock: venta = ninos_activos.get(venta_id)
    if not venta: return jsonify({'ok': False}), 404
    srv = SERVICIOS.get(servicio)
    linea = next((l for l in venta['lineas'] if l['id'] == linea_id), None)
    cancelar_timers(venta_id)
    ahora = datetime.now()
    nueva_salida = ahora + timedelta(minutes=srv['minutos'])

    with _lock:
        linea['salida'], linea['servicio'], linea['combo'] = nueva_salida.isoformat(), servicio, srv['nombre']
        venta['precio_total'] += srv['precio']
        salidas = [datetime.fromisoformat(l['salida']) for l in venta['lineas'] if l.get('salida') and l.get('activa', True)]
        venta['salida'] = max(salidas) if salidas else None

    programar_alertas(venta_id)
    sb_update('registros', {'ninos': venta['lineas'], 'precio_total': venta['precio_total'], 'salida': venta['salida'].isoformat() if venta['salida'] else None}, {'id': venta_id})
    enviar_wa(venta['telefono'], f'\u23f1 *Tiempo extendido*\n\n*{linea["nombre"]}* tiene {srv["nombre"]} mas.\nNueva salida: {hora_legible(nueva_salida)}\n{pesos(srv["precio"])} - {pago}\nTotal actualizado: {pesos(venta["precio_total"])}')
    return jsonify({'ok': True, 'salida': nueva_salida.isoformat(), 'precio_total': venta['precio_total']})

@app.route('/api/activos')
@api_key_required
def get_activos():
    ahora = datetime.now()
    with _lock: snapshot = list(ninos_activos.values())
    resultado = []
    for v in snapshot:
        lineas_con_tiempo = []
        for l in v.get('lineas', v.get('ninos', [])):
            if not l.get('activa', True): continue
            ms = max(0, int((datetime.fromisoformat(l['salida']) - ahora).total_seconds() * 1000)) if l.get('salida') else None
            lineas_con_tiempo.append({**l, 'ms_restantes': ms, 'activa': ms > 0 if ms is not None else True})
        resultado.append({**v, 'salida': v['salida'].isoformat() if v.get('salida') else None, 'lineas': lineas_con_tiempo, 'ninos': lineas_con_tiempo})
    return jsonify(resultado)

@app.route('/api/historial')
@api_key_required
def get_historial():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase: return jsonify(supabase.table('registros').select('*').gte('entrada',f'{fecha}T00:00:00').lte('entrada',f'{fecha}T23:59:59').order('entrada',desc=True).execute().data or [])
    return jsonify([])

@app.route('/api/kpis')
@api_key_required
def get_kpis():
    try:
        fecha = datetime.now().strftime('%Y-%m-%d')
        tv = tn = ef = tr = 0
        if supabase:
            res = supabase.table('registros').select('precio_total,pago,ninos').gte('entrada', f'{fecha}T00:00:00').execute()
            for r in (res.data or []):
                tv += r['precio_total'] or 0
                tn += len(json.loads(r['ninos']) if isinstance(r['ninos'], str) else r['ninos'])
                if r['pago'] == 'Efectivo': ef += r['precio_total'] or 0
                else: tr += r['precio_total'] or 0
        with _lock: activos_count = len(ninos_activos)
        return jsonify({'total_ventas': tv, 'total_ninos': tn, 'activos_ahora': activos_count, 'efectivo': ef, 'transferencia': tr, 'alertas': alertas_stock_db()})
    except Exception as e:
        log.error('[KPIS] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/utilidad-dia')
@api_key_required
def get_utilidad_dia():
    try:
        fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        ingresos, gastos_total, gastos_lista = 0, 0, []
        if supabase:
            res = supabase.table('registros').select('precio_total').gte('entrada', f'{fecha}T00:00:00').lte('entrada', f'{fecha}T23:59:59').execute()
            ingresos = sum(r.get('precio_total', 0) or 0 for r in (res.data or []))
            res2 = supabase.table('gastos').select('*').eq('fecha', fecha).execute()
            gastos_lista, gastos_total = res2.data or [], sum(g.get('valor', 0) or 0 for g in (res2.data or []))
        utilidad = ingresos - gastos_total
        return jsonify({'ingresos': ingresos, 'gastos': gastos_total, 'utilidad': utilidad, 'margen': round(utilidad / ingresos * 100, 1) if ingresos > 0 else 0, 'gastos_detalle': gastos_lista})
    except Exception as e:
        log.error('[UTILIDAD_DIA] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/inventario', methods=['GET'])
@api_key_required
def get_inventario():
    if supabase: return jsonify({r['producto']: {'cantidad': r['cantidad'], 'umbral': r['umbral_alerta']} for r in (supabase.table('inventario').select('*').order('producto').execute().data or [])})
    return jsonify({})

@app.route('/api/inventario/agregar', methods=['POST'])
@api_key_required
def agregar_stock():
    data = request.get_json(silent=True) or {}
    tipo, cantidad, personaje = data.get('tipo'), int(data.get('cantidad', 0)), data.get('personaje', '').lower().strip()
    producto = f'dibujo_{personaje}' if tipo == 'dibujo' and personaje else tipo
    if supabase:
        res = supabase.table('inventario').select('cantidad').eq('producto', producto).execute()
        if res.data: supabase.table('inventario').update({'cantidad': res.data[0]['cantidad'] + cantidad, 'updated_at': datetime.now().isoformat()}).eq('producto', producto).execute()
        else: supabase.table('inventario').insert({'producto': producto, 'cantidad': cantidad, 'umbral_alerta': 5}).execute()
    return jsonify({'ok': True})

@app.route('/api/gastos', methods=['GET', 'POST'])
@api_key_required
def endpoint_gastos():
    if request.method == 'GET':
        fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        if supabase: return jsonify(supabase.table('gastos').select('*').eq('fecha', fecha).order('created_at', desc=True).execute().data or [])
        return jsonify([])
    else:
        data = request.get_json(silent=True) or {}
        sb_insert('gastos', {'categoria': data.get('categoria'), 'descripcion': data.get('descripcion'), 'valor': int(data.get('valor', 0)), 'fecha': data.get('fecha', datetime.now().strftime('%Y-%m-%d'))})
        return jsonify({'ok': True})

@app.route('/api/clientes')
@api_key_required
def get_clientes():
    if supabase: return jsonify(supabase.table('clientes').select('*').order('visitas', desc=True).execute().data or [])
    return jsonify([])

# ── WEBHOOK EVOLUTION API (MODIFICADO) ──
@app.route('/api/webhook-wa', methods=['POST'])
def webhook_wa():
    payload = request.get_json(silent=True) or {}
    
    # 1. Filtrar solo mensajes nuevos (ignorar updates, lectura, etc.)
    if payload.get('event') != 'messages.upsert': return jsonify({'ok': True})
        
    data = payload.get('data', {})
    key = data.get('key', {})
    
    # 2. Ignorar mensajes enviados por nosotros mismos o provenientes de grupos
    if key.get('fromMe') or '@g.us' in key.get('remoteJid', ''): return jsonify({'ok': True})
        
    tel = normalizar_telefono(key.get('remoteJid', '').split('@')[0])
    
    # 3. Extraer el texto real (ya sea texto plano o respuesta citada)
    msg_obj = data.get('message', {})
    body = msg_obj.get('conversation', '').strip()
    if not body: body = msg_obj.get('extendedTextMessage', {}).get('text', '').strip()
    if not body: return jsonify({'ok': True}) # Ignorar fotos, audios por ahora

    with _lock: grupo = next((g for g in ninos_activos.values() if normalizar_telefono(g['telefono']) == tel), None)

    if body == '1' and grupo:
        srv = SERVICIOS.get(grupo['servicio'])
        if srv and srv.get('minutos'):
            cancelar_timers(grupo['id'])
            ahora, nueva_salida = datetime.now(), datetime.now() + timedelta(minutes=srv['minutos'])
            with _lock: grupo['entrada'], grupo['salida'] = ahora, nueva_salida
            sb_update('registros', {'entrada': ahora.isoformat(), 'salida': nueva_salida.isoformat()}, {'id': grupo['id']})
            programar_alertas(grupo['id'])
            enviar_wa(grupo['telefono'], f"⏱ *Tiempo renovado*\n\n*{', '.join([n['nombre'] for n in grupo['ninos']])}* tiene {srv['nombre']} más.\n🕐 Nueva salida: {hora_legible(nueva_salida)}\n💰 {pesos(srv['precio'])} adicionales — acérquese a cancelar.")
    elif body == '2' and grupo:
        gid = grupo['id']
        cancelar_timers(gid)
        with _lock: ninos_activos.pop(gid, None)
        sb_update('registros', {'activo': False}, {'id': gid})
        enviar_wa(grupo['telefono'], msg_despedida(grupo))
    else:
        threading.Thread(target=lambda: enviar_wa(tel, respuesta_agente(tel, body)), daemon=True).start()

    return jsonify({'ok': True})

# ── API ADMIN: CONSULTA RÁPIDA DE CLIENTE (CAJA) ──
@app.route('/api/admin/cliente/<telefono>')
def admin_cliente(telefono):
    if not supabase: return jsonify({'visitas': 0, 'nombre': ''})
    try:
        res = supabase.table('clientes').select('visitas,nombre').eq('telefono', telefono).execute()
        if res.data:
            return jsonify({'visitas': res.data[0]['visitas'], 'nombre': res.data[0]['nombre']})
    except Exception as e:
        log.error('[API ADMIN CLIENTE] %s', e)
    return jsonify({'visitas': 0, 'nombre': ''})
cargar_sesiones_activas()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)