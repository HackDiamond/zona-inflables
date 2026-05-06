# ================================================================
#  INFLABOOM — Servidor con Agente WhatsApp Inteligente
#  Python + Flask + Twilio + Supabase + Claude (Anthropic)
# ================================================================

from flask import Flask, request, jsonify, send_from_directory
from twilio.rest import Client as TwilioClient
from twilio.request_validator import RequestValidator
from datetime import datetime, timedelta, date
from calendar import monthrange
from supabase import create_client
import anthropic
import threading
import logging
import os
import re
import json

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "Arktos", "Motor Arktos (Sistema SaaS)", "01 - Input")
OUTPUT_DIR = os.path.join(BASE_DIR, "Arktos", "Motor Arktos (Sistema SaaS)", "03 - Output")


def _find_input_file():
    """
    Busca el archivo de entrada en este orden:
    1. inflaboom_progreso_v1.1.md en Input dir
    2. Inflaboom.md en Input dir
    3. inflaboom_progreso_v1.1.md en raíz del proyecto
    4. inflaboom_progreso_v1.1 (sin extensión) en raíz
    """
    candidates = [
        os.path.join(INPUT_DIR, "inflaboom_progreso_v1.1.md"),
        os.path.join(INPUT_DIR, "Inflaboom.md"),
        os.path.join(BASE_DIR, "inflaboom_progreso_v1.1.md"),
        os.path.join(BASE_DIR, "inflaboom_progreso_v1.1"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _parse_sections(md_text):
    """
    Parsea ## y ### del markdown.
    Clave = título sin emojis ni puntuación, en minúsculas.
    """
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
    """Primera sección cuya clave contenga alguna keyword."""
    for key in sections:
        for kw in keywords:
            if kw.lower() in key:
                return sections[key]
    return ''


def _get_all(sections, *keywords):
    """Concatena todas las secciones cuyas claves contengan alguna keyword."""
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
    if not input_path:
        raise FileNotFoundError(
            f"Archivo de entrada no encontrado en {INPUT_DIR}. "
            "Se esperaba inflaboom_progreso_v1.1.md o Inflaboom.md"
        )

    with open(input_path, encoding='utf-8') as f:
        sec = _parse_sections(f.read())

    outputs = {
        "Clientes.md": (
            "# Clientes\n\n"
            "## Modelo de Datos\n\n"
            + _get(sec, 'modelo de dato', 'redise', '2 redise') +
            "\n\n## Sistema de Roles\n\n"
            + _get(sec, 'roles diferenciado', '3 sistema') +
            "\n\n## Lógica de Duplicados\n\n"
            + _get(sec, 'whatsapp para completar', '5 flujo de whatsapp',
                   'duplicado', 'segmento')
        ),
        "Finanzas.md": (
            "# Finanzas\n\n"
            "## Sistema de Tiquetes y Fidelización\n\n"
            + _get(sec, 'tiquete ganador', '6 programa tiquete') +
            "\n\n## Ticket Promedio\n\n"
            + _get(sec, 'p2', 'ticket promedio por debajo',
                   'modelo de ingreso', 'ingreso')
        ),
        "Operaciones.md": (
            "# Operaciones\n\n"
            "## Migración a n8n\n\n"
            + _get(sec, 'reemplazo de twilio', '1 reemplazo', 'orquestador') +
            "\n\n## Flujo de Caja — 3 Pasos\n\n"
            + _get(sec, 'flujo de registro', '4 flujo', 'caja') +
            "\n\n## Flujos n8n — Punto de Atención\n\n"
            + _get(sec, 'flujos de n8n', '7 flujos', 'n8n definidos') +
            "\n\n## Decisiones de Arquitectura\n\n"
            + _get(sec, 'arquitectura')
        ),
        "Problemas.md": (
            "# Problemas\n\n"
            "## Problemas Identificados\n\n"
            + _get_all(sec, 'p1 ', 'p2 ', 'p3 ', 'p4 ') +
            "\n\n## Próximos Pasos\n\n"
            + _get_all(sec, 'inmediato', 'corto plazo', 'mediano plazo',
                       'oportunidad', 'mejora')
        ),
    }

    generated = []
    for filename, content in outputs.items():
        with open(os.path.join(OUTPUT_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(content)
        generated.append(filename)

    return generated


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder='public', static_url_path='')


@app.route("/")
def home():
    from flask import Response
    import os
    path = os.path.join(app.static_folder, 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    return Response(html, content_type='text/html; charset=utf-8')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)
TWILIO_SID      = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER   = os.environ.get('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')
SUPABASE_URL    = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY    = os.environ.get('SUPABASE_KEY', '')
ANTHROPIC_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')
API_KEY         = os.environ.get('API_KEY', 'inflaboom123')

# ── Clientes externos ──
twilio   = TwilioClient(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
claude   = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ── Estado en memoria ──
_lock           = threading.Lock()
ninos_activos   = {}   # id -> grupo activo  (acceso siempre bajo _lock)
timers          = {}   # id -> [timers]       (acceso siempre bajo _lock)
conversaciones  = {}   # telefono -> [historial mensajes para el agente]

# ── Catálogo ──
SERVICIOS = {
    'combo_15':  {'nombre': '15 minutos',      'minutos': 15,  'precio': 5000,  'manilla': False, 'categoria': 'juegos'},
    'combo_30':  {'nombre': '30 minutos',      'minutos': 30,  'precio': 8000,  'manilla': False, 'categoria': 'juegos'},
    'combo_1h':  {'nombre': '1 hora',          'minutos': 60,  'precio': 13000, 'manilla': True,  'categoria': 'juegos'},
    'promo_2x1': {'nombre': 'Promo 2x1',       'minutos': 60,  'precio': 13000, 'manilla': True,  'categoria': 'juegos'},
    'arte':      {'nombre': 'Estación de arte','minutos': None,'precio': 6000,  'manilla': False, 'categoria': 'arte'},
}

# ================================================================
#  PROTECCIÓN API KEY
# ================================================================

from functools import wraps

def api_key_required(f):
    """Valida X-API-Key en header o api_key en body. Rutas públicas quedan libres."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = (request.headers.get('X-API-Key')
               or (request.get_json(silent=True) or {}).get('api_key')
               or request.args.get('api_key', ''))
        if key != API_KEY:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated


# ================================================================
#  SISTEMA PROMPT DEL AGENTE
# ================================================================

def get_system_prompt(telefono):
    """Genera el prompt del agente con contexto en tiempo real."""

    # Buscar si hay niños activos de este número
    with _lock:
        grupo_activo = next(
            (g for g in ninos_activos.values()
             if normalizar_telefono(g['telefono']) == normalizar_telefono(telefono)),
            None,
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
        except Exception as e:
            log.error('[SYSTEM PROMPT CLIENTE] %s', e)

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
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime('%I:%M %p')

def es_sabado():
    return datetime.now().weekday() == 5

def pesos(n):
    return f'${int(n or 0):,}'.replace(',', '.')

def normalizar_telefono(raw: str) -> str:
    """Devuelve número limpio con prefijo +57 si aplica (sin whatsapp:)."""
    num = raw.replace('whatsapp:', '').replace(' ', '').replace('-', '')
    num = num.lstrip('+')
    if num.startswith('57') and len(num) > 10:
        num = num[2:]
    return '+57' + num.lstrip('0') if not num.startswith('+') else '+' + num

def enviar_wa(telefono, mensaje):
    num = normalizar_telefono(telefono)
    if not twilio:
        log.info('[WA DEMO → %s]: %s', num, mensaje[:60])
        return {'ok': True}
    try:
        msg = twilio.messages.create(from_=TWILIO_NUMBER, to=f'whatsapp:{num}', body=mensaje)
        return {'ok': True, 'sid': msg.sid}
    except Exception as e:
        log.error('[WA ERROR] %s', e)
        return {'ok': False, 'error': str(e)}

def sb_insert(tabla, data):
    if not supabase:
        return None
    try:
        return supabase.table(tabla).insert(data).execute()
    except Exception as e:
        log.error('[DB INSERT %s] %s', tabla, e)

def sb_update(tabla, data, match):
    if not supabase:
        return None
    try:
        q = supabase.table(tabla).update(data)
        for k, v in match.items():
            q = q.eq(k, v)
        return q.execute()
    except Exception as e:
        log.error('[DB UPDATE %s] %s', tabla, e)

def registrar_cliente_db(telefono, nombre, precio):
    if not supabase:
        return
    try:
        res = supabase.table('clientes').select('*').eq('telefono', telefono).execute()
        if res.data:
            c = res.data[0]
            supabase.table('clientes').update({
                'visitas': c['visitas'] + 1,
                'total_gastado': c['total_gastado'] + precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).eq('telefono', telefono).execute()
        else:
            supabase.table('clientes').insert({
                'telefono': telefono, 'nombre': nombre,
                'visitas': 1, 'total_gastado': precio,
                'ultimo_visita': datetime.now().isoformat(),
            }).execute()
    except Exception as e:
        log.error('[DB CLIENTE] %s', e)

def descontar_inventario_db(servicio, ninos_lista):
    if not supabase:
        return
    try:
        srv = SERVICIOS.get(servicio, {})
        if srv.get('manilla'):
            res = supabase.table('inventario').select('cantidad').eq('producto', 'manillas').execute()
            if res.data:
                nueva = max(0, res.data[0]['cantidad'] - len(ninos_lista))
                supabase.table('inventario').update(
                    {'cantidad': nueva, 'updated_at': datetime.now().isoformat()}
                ).eq('producto', 'manillas').execute()
        for n in ninos_lista:
            if n.get('dibujo'):
                p = f"dibujo_{n['dibujo'].lower().strip()}"
                res = supabase.table('inventario').select('cantidad').eq('producto', p).execute()
                if res.data:
                    nueva = max(0, res.data[0]['cantidad'] - 1)
                    supabase.table('inventario').update(
                        {'cantidad': nueva, 'updated_at': datetime.now().isoformat()}
                    ).eq('producto', p).execute()
    except Exception as e:
        log.error('[DB INV] %s', e)

def alertas_stock_db():
    if not supabase:
        return []
    alertas = []
    try:
        # Alertas de inventario operativo (manillas, pinturas)
        res = supabase.table('inventario').select('*').execute()
        for r in (res.data or []):
            if r['cantidad'] <= r['umbral_alerta']:
                alertas.append(f"⚠️ {r['producto']}: solo {r['cantidad']} disponibles")
        # Alertas de productos (juguetería)
        res2 = supabase.table('productos').select('nombre,stock,stock_minimo').eq('activo', True).execute()
        for r in (res2.data or []):
            if r['stock'] <= r['stock_minimo']:
                alertas.append(f"🧸 {r['nombre']}: stock bajo ({r['stock']} unidades)")
    except Exception as e:
        log.error('[DB ALERTAS] %s', e)
    return alertas


# ================================================================
#  MENSAJES AUTOMÁTICOS
# ================================================================

def msg_bienvenida(v):
    acudiente = v.get('acudiente') or 'acudiente'
    lineas    = v.get('lineas', v.get('ninos', []))
    es_grupo  = len(lineas) > 1

    txt_lineas = ''
    for l in lineas:
        salida_str = hora_legible(l['salida']) if l.get('salida') else 'libre'
        txt_lineas += f"\n  • *{l['nombre']}* — {l['combo']} · sale {salida_str}"

    return (f"🎪 *Inflaboom — Bienvenida*\n\nHola {acudiente} 👋\n\n"
            f"*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado:*"
            f"{txt_lineas}\n\n"
            f"💰 *Total:* {pesos(v['precio_total'])} — {v['pago']}")

def msg_recibo(v):
    lineas    = v.get('lineas', v.get('ninos', []))
    es_grupo  = len(lineas) > 1
    txt_items = '\n'.join([
        f"  • {l['nombre']} — {l['combo']} ({pesos(l['precio'])})"
        + (" [adicional]" if l.get('adicional') else "")
        for l in lineas
    ])
    return (f"🧾 *Recibo — Inflaboom*\n\n"
            f"{'Niños' if es_grupo else 'Niño/a'}:\n{txt_items}\n\n"
            f"💵 *Total:* {pesos(v['precio_total'])}\n"
            f"💳 *Pago:* {v['pago']}\n"
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
    with _lock:
        g = ninos_activos.get(gid)
    if not g or not g.get('salida'):
        return
    ahora  = datetime.now()
    salida = g['salida'] if isinstance(g['salida'], datetime) else datetime.fromisoformat(str(g['salida']))
    seg_total = (salida - ahora).total_seconds()
    seg_aviso = seg_total - 300

    def aviso():
        with _lock:
            grp = ninos_activos.get(gid)
        if grp:
            enviar_wa(grp['telefono'], msg_aviso(grp))

    def fin():
        with _lock:
            grp = ninos_activos.get(gid)
        if grp:
            enviar_wa(grp['telefono'], msg_fin(grp))

    tlist = []
    if seg_aviso > 0:
        t = threading.Timer(seg_aviso, aviso)
        t.daemon = True
        t.start()
        tlist.append(t)
    t2 = threading.Timer(max(seg_total, 1), fin)
    t2.daemon = True
    t2.start()
    tlist.append(t2)
    with _lock:
        timers[gid] = tlist

def cancelar_timers(gid):
    with _lock:
        tlist = timers.pop(gid, [])
    for t in tlist:
        t.cancel()

def cargar_sesiones_activas():
    """Al arrancar, recarga sesiones activas de Supabase para no perder estado."""
    if not supabase:
        return
    try:
        res = supabase.table('registros').select('*').eq('activo', True).execute()
        count = 0
        for r in (res.data or []):
            salida = None
            if r.get('salida'):
                salida = datetime.fromisoformat(r['salida'].replace('Z', '+00:00')).replace(tzinfo=None)
                if salida < datetime.now():
                    # Sesión expirada: marcar como inactiva
                    sb_update('registros', {'activo': False}, {'id': r['id']})
                    continue
            ninos = r['ninos'] if isinstance(r['ninos'], list) else json.loads(r.get('ninos') or '[]')
            grupo = {
                'id': r['id'], 'servicio': r['servicio'], 'acudiente': r.get('acudiente', ''),
                'telefono': r['telefono'], 'pago': r.get('pago', 'Efectivo'), 'ninos': ninos,
                'precio_total': r.get('precio_total', 0),
                'entrada': datetime.fromisoformat(r['entrada'].replace('Z', '+00:00')).replace(tzinfo=None),
                'salida': salida, 'activo': True,
            }
            with _lock:
                ninos_activos[r['id']] = grupo
            programar_alertas(r['id'])
            count += 1
        log.info('Sesiones activas recuperadas de BD: %d', count)
    except Exception as e:
        log.error('[STARTUP RECOVERY] %s', e)


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
            model='claude-haiku-4-5-20251001',
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
        log.error('[AGENTE ERROR] %s', e)
        return "Hola 👋 En este momento no puedo procesar tu mensaje. Por favor visítanos en el parque o escribe de nuevo en un momento."


# ================================================================
#  RUTAS
# ================================================================

@app.route("/api/generate-system")
def api_generate_system():
    try:
        files = generate_system()
        return jsonify({"status": "ok", "files": files})
    except FileNotFoundError as e:
        return jsonify({"status": "error", "error": str(e)}), 404
    except Exception as e:
        log.error('[GENERATE SYSTEM] %s', e)
        return jsonify({"status": "error", "error": str(e)}), 500
@api_key_required
@app.route('/api/registrar', methods=['POST'])
def registrar():
    """
    Crea una VENTA nueva con sus LINEAS_VENTA.
    Body: {acudiente, telefono, pago, ninos:[{nombre, servicio, dibujo?}]}
    """
    data      = request.get_json(silent=True) or {}
    acudiente = data.get('acudiente', '')
    telefono  = data.get('telefono', '')
    pago      = data.get('pago', 'Efectivo')
    ninos     = data.get('ninos', [])

    if not telefono or not ninos:
        return jsonify({'ok': False, 'error': 'Faltan campos obligatorios'}), 400

    for n in ninos:
        if not SERVICIOS.get(n.get('servicio')):
            return jsonify({'ok': False, 'error': f'Servicio inválido para {n.get("nombre","?")}'}), 400

    ahora        = datetime.now()
    venta_id     = str(int(ahora.timestamp() * 1000))
    precio_total = 0
    lineas       = []

    for n in ninos:
        srv     = SERVICIOS[n['servicio']]
        minutos = srv.get('minutos')
        salida  = (ahora + timedelta(minutes=minutos)).isoformat() if minutos else None
        precio  = srv['precio']
        precio_total += precio
        linea_id = f"{venta_id}_{len(lineas)+1}"
        lineas.append({
            'id':       linea_id,
            'venta_id': venta_id,
            'nombre':   n.get('nombre', ''),
            'servicio': n['servicio'],
            'combo':    srv['nombre'],
            'categoria':srv.get('categoria', 'juegos'),
            'minutos':  minutos,
            'precio':   precio,
            'salida':   salida,
            'dibujo':   n.get('dibujo', ''),
            'activa':   True,
        })

    salidas_validas = [datetime.fromisoformat(l['salida']) for l in lineas if l['salida']]
    salida_grupo    = max(salidas_validas) if salidas_validas else None

    venta = {
        'id':           venta_id,
        'acudiente':    acudiente,
        'telefono':     telefono,
        'pago':         pago,
        'lineas':       lineas,
        'precio_total': precio_total,
        'entrada':      ahora,
        'salida':       salida_grupo,
        'activo':       True,
    }

    with _lock:
        ninos_activos[venta_id] = venta

    # Persistir en Supabase — tabla registros (compatible con esquema existente)
    sb_insert('registros', {
        'id':          venta_id,
        'acudiente':   acudiente,
        'telefono':    telefono,
        'pago':        pago,
        'ninos':       lineas,           # lineas reemplazan la lista ninos
        'precio_total':precio_total,
        'entrada':     ahora.isoformat(),
        'salida':      salida_grupo.isoformat() if salida_grupo else None,
        'activo':      True,
        'servicio':    lineas[0]['servicio'] if lineas else '',
    })

    descontar_inventario_db(lineas[0]['servicio'], lineas)
    registrar_cliente_db(telefono, acudiente, precio_total)
    programar_alertas(venta_id)
    enviar_wa(telefono, msg_bienvenida(venta))
    threading.Timer(2.0, lambda: enviar_wa(telefono, msg_recibo(venta))).start()

    return jsonify({
        'ok':          True,
        'id':          venta_id,
        'lineas':      lineas,
        'precio_total':precio_total,
        'alertas':     alertas_stock_db(),
    })


@api_key_required
@app.route('/api/agregar-linea', methods=['POST'])
def agregar_linea():
    """
    Agrega un servicio adicional a una VENTA activa sin cerrarla.
    Caso de uso: niño decide ir a arte en mitad del tiempo de juegos.
    Body: {id: venta_id, nombre, servicio, pago?}
    """
    data     = request.get_json(silent=True) or {}
    venta_id = data.get('id')
    nombre   = data.get('nombre', '')
    servicio = data.get('servicio', 'arte')
    pago     = data.get('pago', '')

    with _lock:
        venta = ninos_activos.get(venta_id)
    if not venta:
        return jsonify({'ok': False, 'error': 'Venta no encontrada'}), 404

    srv = SERVICIOS.get(servicio)
    if not srv:
        return jsonify({'ok': False, 'error': 'Servicio inválido'}), 400

    ahora    = datetime.now()
    minutos  = srv.get('minutos')
    salida   = (ahora + timedelta(minutes=minutos)).isoformat() if minutos else None
    linea_id = f"{venta_id}_{len(venta['lineas'])+1}"

    nueva_linea = {
        'id':       linea_id,
        'venta_id': venta_id,
        'nombre':   nombre,
        'servicio': servicio,
        'combo':    srv['nombre'],
        'categoria':srv.get('categoria', 'arte'),
        'minutos':  minutos,
        'precio':   srv['precio'],
        'salida':   salida,
        'dibujo':   data.get('dibujo', ''),
        'activa':   True,
        'adicional':True,   # marca que se agregó después del registro inicial
    }

    with _lock:
        venta['lineas'].append(nueva_linea)
        venta['precio_total'] += srv['precio']
        # Actualizar salida del grupo si esta línea dura más
        if salida:
            salida_dt = datetime.fromisoformat(salida)
            if not venta['salida'] or salida_dt > venta['salida']:
                venta['salida'] = salida_dt

    # Actualizar en Supabase
    sb_update('registros', {
        'ninos':        venta['lineas'],
        'precio_total': venta['precio_total'],
        'salida':       venta['salida'].isoformat() if venta['salida'] else None,
    }, {'id': venta_id})

    # Notificar al acudiente
    pago_txt = f' — {pago}' if pago else ''
    msg_adicional = ('\U0001f3a8 *Servicio adicional agregado*\n\n'
                     f'*{nombre}* paso a {srv["nombre"]}.\n'
                     f'{pesos(srv["precio"])}{pago_txt}\n'
                     f'Total actualizado: {pesos(venta["precio_total"])}')
    enviar_wa(venta['telefono'], msg_adicional)

    return jsonify({'ok': True, 'linea': nueva_linea, 'precio_total': venta['precio_total']})


@api_key_required
@app.route('/api/retirar', methods=['POST'])
def retirar():
    """
    Cierra una VENTA completa (retira al grupo entero).
    Body: {id: venta_id}
    """
    gid = (request.get_json(silent=True) or {}).get('id')
    with _lock:
        venta = ninos_activos.pop(gid, None)
    if not venta:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    cancelar_timers(gid)
    sb_update('registros', {'activo': False}, {'id': gid})
    enviar_wa(venta['telefono'], msg_despedida(venta))
    return jsonify({'ok': True})


@api_key_required
@app.route('/api/retirar-linea', methods=['POST'])
def retirar_linea():
    """
    Marca una LÍNEA como inactiva sin cerrar la venta.
    Caso de uso: un niño del grupo se va antes que el otro.
    Body: {id: venta_id, linea_id}
    """
    data     = request.get_json(silent=True) or {}
    venta_id = data.get('id')
    linea_id = data.get('linea_id')

    with _lock:
        venta = ninos_activos.get(venta_id)
    if not venta:
        return jsonify({'ok': False, 'error': 'Venta no encontrada'}), 404

    linea = next((l for l in venta['lineas'] if l['id'] == linea_id), None)
    if not linea:
        return jsonify({'ok': False, 'error': 'Línea no encontrada'}), 404

    with _lock:
        linea['activa'] = False
        linea['salida_real'] = datetime.now().isoformat()
        # Si todas las líneas están inactivas, cerrar la venta automáticamente
        todas_inactivas = all(not l.get('activa', True) for l in venta['lineas'])

    if todas_inactivas:
        with _lock:
            ninos_activos.pop(venta_id, None)
        cancelar_timers(venta_id)
        sb_update('registros', {'activo': False, 'ninos': venta['lineas']}, {'id': venta_id})
        enviar_wa(venta['telefono'], msg_despedida(venta))
        return jsonify({'ok': True, 'venta_cerrada': True})

    sb_update('registros', {'ninos': venta['lineas']}, {'id': venta_id})
    return jsonify({'ok': True, 'venta_cerrada': False, 'linea': linea})


@api_key_required
@app.route('/api/extender', methods=['POST'])
def extender():
    """
    Extiende el tiempo de UNA línea específica dentro de la venta.
    Body: {id: venta_id, linea_id, servicio, pago?}
    """
    data     = request.get_json(silent=True) or {}
    venta_id = data.get('id')
    linea_id = data.get('linea_id')
    nino_idx = data.get('nino_idx', 0)   # fallback compatibilidad
    servicio = data.get('servicio', 'combo_1h')
    pago     = data.get('pago', 'Efectivo')

    with _lock:
        venta = ninos_activos.get(venta_id)
    if not venta:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404

    srv = SERVICIOS.get(servicio)
    if not srv or not srv.get('minutos'):
        return jsonify({'ok': False, 'error': 'Servicio inválido para extensión'}), 400

    # Buscar línea por linea_id o por índice (compatibilidad)
    if linea_id:
        linea = next((l for l in venta['lineas'] if l['id'] == linea_id), None)
    else:
        linea = venta['lineas'][nino_idx] if 0 <= nino_idx < len(venta['lineas']) else None

    if not linea:
        return jsonify({'ok': False, 'error': 'Línea no encontrada'}), 404

    cancelar_timers(venta_id)
    ahora        = datetime.now()
    nueva_salida = ahora + timedelta(minutes=srv['minutos'])

    with _lock:
        linea['salida']   = nueva_salida.isoformat()
        linea['servicio'] = servicio
        linea['combo']    = srv['nombre']
        venta['precio_total'] += srv['precio']
        # Recalcular salida del grupo
        salidas = [datetime.fromisoformat(l['salida']) for l in venta['lineas'] if l.get('salida') and l.get('activa', True)]
        venta['salida'] = max(salidas) if salidas else None

    programar_alertas(venta_id)
    sb_update('registros', {
        'ninos':        venta['lineas'],
        'precio_total': venta['precio_total'],
        'salida':       venta['salida'].isoformat() if venta['salida'] else None,
    }, {'id': venta_id})

    msg_ext = ('\u23f1 *Tiempo extendido*\n\n'
               f'*{linea["nombre"]}* tiene {srv["nombre"]} mas.\n'
               f'Nueva salida: {hora_legible(nueva_salida)}\n'
               f'{pesos(srv["precio"])} - {pago}\n'
               f'Total actualizado: {pesos(venta["precio_total"])}')
    enviar_wa(venta['telefono'], msg_ext)
    return jsonify({'ok': True, 'salida': nueva_salida.isoformat(), 'precio_total': venta['precio_total']})

    try:
        res = supabase.table('registros').select('*')\
            .gte('entrada', f'{fecha}T00:00:00')\
            .lte('entrada', f'{fecha}T23:59:59')\
            .eq('operador_id', op_id)\
            .order('entrada', desc=True).execute()
        registros = res.data or []
        total = sum(r.get('precio_total', 0) for r in registros)
        ninos = sum(len(r['ninos']) if isinstance(r['ninos'], list) else len(json.loads(r.get('ninos') or '[]')) for r in registros)
        return jsonify({'registros': registros, 'total': total, 'ninos': ninos})
    except Exception as e:
        log.error('[REPORTE OPERADOR] %s', e)
        return jsonify([])


@api_key_required
@app.route('/api/activos')
def get_activos():
    ahora = datetime.now()
    with _lock:
        snapshot = list(ninos_activos.values())
    resultado = []
    for v in snapshot:
        lineas_con_tiempo = []
        for l in v.get('lineas', v.get('ninos', [])):
            if not l.get('activa', True):
                continue   # omitir líneas ya retiradas
            if l.get('salida'):
                salida_l = datetime.fromisoformat(l['salida']) if isinstance(l['salida'], str) else l['salida']
                ms       = max(0, int((salida_l - ahora).total_seconds() * 1000))
                activa_l = ms > 0
            else:
                ms       = None
                activa_l = True
            lineas_con_tiempo.append({
                **l,
                'ms_restantes': ms,
                'activa':       activa_l,
            })

        salida_grupo = v['salida']
        resultado.append({
            'id':          v['id'],
            'acudiente':   v['acudiente'],
            'telefono':    v['telefono'],
            'pago':        v['pago'],
            'precio_total':v['precio_total'],
            'entrada':     v['entrada'].isoformat() if hasattr(v['entrada'], 'isoformat') else v['entrada'],
            'salida':      salida_grupo.isoformat() if salida_grupo and hasattr(salida_grupo, 'isoformat') else salida_grupo,
            'lineas':      lineas_con_tiempo,
            'ninos':       lineas_con_tiempo,  # alias para compatibilidad con frontend actual
        })
    return jsonify(resultado)


@api_key_required
@app.route('/api/historial')
def get_historial():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('registros').select('*')\
                .gte('entrada',f'{fecha}T00:00:00').lte('entrada',f'{fecha}T23:59:59')\
                .order('entrada',desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[HISTORIAL] %s', e)
    return jsonify([])


@api_key_required
@app.route('/api/kpis')
def get_kpis():
    fecha = datetime.now().strftime('%Y-%m-%d')
    tv = tn = ef = tr = 0
    if supabase:
        try:
            res = supabase.table('registros').select('precio_total,pago,ninos') \
                .gte('entrada', f'{fecha}T00:00:00').execute()
            for r in (res.data or []):
                tv += r['precio_total'] or 0
                nl = r['ninos'] if isinstance(r['ninos'], list) else json.loads(r['ninos'] or '[]')
                tn += len(nl)
                if r['pago'] == 'Efectivo':
                    ef += r['precio_total'] or 0
                else:
                    tr += r['precio_total'] or 0
        except Exception as e:
            log.error('[KPIS] %s', e)
    with _lock:
        activos_count = len(ninos_activos)
    return jsonify({'total_ventas': tv, 'total_ninos': tn, 'activos_ahora': activos_count,
                    'efectivo': ef, 'transferencia': tr, 'alertas': alertas_stock_db()})


@api_key_required
@app.route('/api/inventario')
def get_inventario():
    if supabase:
        try:
            res = supabase.table('inventario').select('*').order('producto').execute()
            inv = {r['producto']: {'cantidad': r['cantidad'], 'umbral': r['umbral_alerta']} for r in (res.data or [])}
            return jsonify(inv)
        except Exception as e:
            log.error('[INV GET] %s', e)
    return jsonify({'manillas': {'cantidad': 100, 'umbral': 10}, 'pinturas': {'cantidad': 50, 'umbral': 10}})

@api_key_required
@app.route('/api/inventario/agregar', methods=['POST'])
def agregar_stock():
    data      = request.get_json(silent=True) or {}
    tipo      = data.get('tipo')
    cantidad  = int(data.get('cantidad', 0))
    personaje = data.get('personaje', '').lower().strip()
    producto  = f'dibujo_{personaje}' if tipo == 'dibujo' and personaje else tipo
    if supabase:
        try:
            res = supabase.table('inventario').select('cantidad').eq('producto', producto).execute()
            if res.data:
                supabase.table('inventario').update(
                    {'cantidad': res.data[0]['cantidad'] + cantidad, 'updated_at': datetime.now().isoformat()}
                ).eq('producto', producto).execute()
            else:
                supabase.table('inventario').insert(
                    {'producto': producto, 'cantidad': cantidad, 'umbral_alerta': 5}
                ).execute()
        except Exception as e:
            log.error('[INV ADD] %s', e)
    return jsonify({'ok': True})


@api_key_required
@app.route('/api/gastos', methods=['GET'])
def get_gastos():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('gastos').select('*').eq('fecha', fecha).order('created_at', desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[GASTOS GET] %s', e)
    return jsonify([])

@api_key_required
@app.route('/api/gastos', methods=['POST'])
def agregar_gasto():
    data = request.get_json(silent=True) or {}
    sb_insert('gastos', {
        'categoria': data.get('categoria'), 'descripcion': data.get('descripcion'),
        'valor': int(data.get('valor', 0)), 'fecha': data.get('fecha', datetime.now().strftime('%Y-%m-%d')),
    })
    return jsonify({'ok': True})


@api_key_required
@app.route('/api/clientes')
def get_clientes():
    if supabase:
        try:
            res = supabase.table('clientes').select('*').order('visitas', desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[CLIENTES] %s', e)
    return jsonify([])


@api_key_required
@app.route('/api/eventos', methods=['GET'])
def get_eventos():
    if supabase:
        try:
            res = supabase.table('eventos').select('*').order('created_at',desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[EVENTOS GET] %s', e)
    return jsonify([])

@api_key_required
@app.route('/api/eventos', methods=['POST'])
def crear_evento():
    d = request.get_json(silent=True) or {}
    sb_insert('eventos',{
        'tipo':d.get('tipo','evento'),'cliente':d.get('cliente'),'telefono':d.get('telefono'),
        'festejado':d.get('festejado'),'anos':d.get('anos'),'ninos_aprox':d.get('ninos_aprox'),
        'fecha_evento':d.get('fecha_evento'),'lugar':d.get('lugar'),'servicios':d.get('servicios'),
        'observaciones':d.get('observaciones'),'precio_total':int(d.get('precio_total',0)),
        'anticipo':int(d.get('anticipo',0)),'estado':d.get('estado','cotizado'),'pago':d.get('pago',''),
    })
    return jsonify({'ok':True})

@api_key_required
@app.route('/api/eventos/<int:evento_id>', methods=['PATCH'])
def actualizar_evento(evento_id):
    sb_update('eventos', request.get_json(silent=True) or {}, {'id':evento_id})
    return jsonify({'ok':True})


@api_key_required
@api_key_required
@app.route('/api/reportes/ventas')
def reporte_ventas():
    """
    Reporte de ventas desglosado por línea.
    Responde: totales del día/semana/mes + breakdown por combo, categoría y niño.
    ?periodo=dia|semana|mes  (default: dia)
    ?fecha=YYYY-MM-DD        (default: hoy)
    """
    periodo = request.args.get('periodo', 'dia')
    fecha   = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))

    # Calcular rango según período
    dt = datetime.strptime(fecha, '%Y-%m-%d')
    if periodo == 'semana':
        inicio_dt = dt - timedelta(days=dt.weekday())
        fin_dt    = inicio_dt + timedelta(days=6)
    elif periodo == 'mes':
        inicio_dt = dt.replace(day=1)
        ultimo    = monthrange(dt.year, dt.month)[1]
        fin_dt    = dt.replace(day=ultimo)
    else:  # dia
        inicio_dt = fin_dt = dt

    inicio = f"{inicio_dt.strftime('%Y-%m-%d')}T00:00:00"
    fin    = f"{fin_dt.strftime('%Y-%m-%d')}T23:59:59"

    if not supabase:
        return jsonify({'error': 'Sin conexión a base de datos'}), 500

    try:
        res = supabase.table('registros').select('*')\
            .gte('entrada', inicio).lte('entrada', fin)\
            .order('entrada', desc=True).execute()
        registros = res.data or []
    except Exception as e:
        log.error('[REPORTE VENTAS] %s', e)
        return jsonify({'error': str(e)}), 500

    # Acumuladores
    total_ingresos  = 0
    total_ninos     = 0
    total_efectivo  = 0
    total_transfer  = 0
    por_combo       = {}   # {combo: {cantidad, ingresos}}
    por_categoria   = {'juegos': {'cantidad': 0, 'ingresos': 0},
                       'arte':   {'cantidad': 0, 'ingresos': 0}}
    por_nino        = {}   # {nombre: {visitas, ingresos, combos:[]}}
    ventas_detalle  = []

    for r in registros:
        pago          = r.get('pago', 'Efectivo')
        precio_total  = r.get('precio_total', 0) or 0
        total_ingresos += precio_total
        if pago == 'Efectivo':
            total_efectivo  += precio_total
        else:
            total_transfer  += precio_total

        # Parsear líneas (campo ninos almacena las líneas v1.4+)
        raw_lineas = r.get('ninos', [])
        if isinstance(raw_lineas, str):
            try:
                raw_lineas = json.loads(raw_lineas)
            except Exception:
                raw_lineas = []

        lineas_detalle = []
        for l in (raw_lineas or []):
            nombre    = l.get('nombre', '?')
            combo     = l.get('servicio', '?')
            combo_nom = l.get('combo', combo)
            categoria = l.get('categoria', 'juegos' if combo != 'arte' else 'arte')
            precio_l  = l.get('precio', 0) or 0
            dibujo    = l.get('dibujo', '')

            total_ninos += 1

            # Por combo
            if combo not in por_combo:
                por_combo[combo] = {'nombre': combo_nom, 'cantidad': 0, 'ingresos': 0}
            por_combo[combo]['cantidad']  += 1
            por_combo[combo]['ingresos']  += precio_l

            # Por categoría
            cat = categoria if categoria in por_categoria else 'juegos'
            por_categoria[cat]['cantidad']  += 1
            por_categoria[cat]['ingresos']  += precio_l

            # Por niño
            if nombre not in por_nino:
                por_nino[nombre] = {'visitas': 0, 'ingresos': 0, 'combos': []}
            por_nino[nombre]['visitas']  += 1
            por_nino[nombre]['ingresos'] += precio_l
            por_nino[nombre]['combos'].append(combo_nom)

            lineas_detalle.append({
                'nombre': nombre, 'combo': combo_nom,
                'categoria': categoria, 'precio': precio_l,
                'dibujo': dibujo, 'adicional': l.get('adicional', False),
            })

        ventas_detalle.append({
            'id':          r.get('id'),
            'acudiente':   r.get('acudiente', ''),
            'telefono':    r.get('telefono', ''),
            'pago':        pago,
            'total':       precio_total,
            'entrada':     r.get('entrada', ''),
            'lineas':      lineas_detalle,
        })

    # Ordenar ranking niños por ingresos
    ranking_ninos = sorted(
        [{'nombre': k, **v} for k, v in por_nino.items()],
        key=lambda x: x['ingresos'], reverse=True
    )

    return jsonify({
        'periodo':         periodo,
        'fecha_inicio':    inicio_dt.strftime('%Y-%m-%d'),
        'fecha_fin':       fin_dt.strftime('%Y-%m-%d'),
        'resumen': {
            'total_ingresos':  total_ingresos,
            'total_ninos':     total_ninos,
            'total_ventas':    len(registros),
            'efectivo':        total_efectivo,
            'transferencia':   total_transfer,
        },
        'por_combo':       list(por_combo.values()),
        'por_categoria':   por_categoria,
        'ranking_ninos':   ranking_ninos[:10],  # top 10
        'detalle':         ventas_detalle,
    })


@app.route('/api/reportes/mes')
def reporte_mes():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    if not supabase:
        return jsonify({'ventas': [], 'gastos': [], 'eventos': []})
    try:
        year, month = int(mes[:4]), int(mes[5:7])
        ultimo_dia = monthrange(year, month)[1]
        inicio = f'{mes}-01T00:00:00'
        fin    = f'{mes}-{ultimo_dia:02d}T23:59:59'
        fecha_ini = f'{mes}-01'
        fecha_fin = f'{mes}-{ultimo_dia:02d}'
        ventas  = supabase.table('registros').select('*').gte('entrada', inicio).lte('entrada', fin).execute().data or []
        gastos  = supabase.table('gastos').select('*').gte('fecha', fecha_ini).lte('fecha', fecha_fin).execute().data or []
        eventos = supabase.table('eventos').select('*').gte('fecha_evento', fecha_ini).lte('fecha_evento', fecha_fin).execute().data or []
        return jsonify({'ventas': ventas, 'gastos': gastos, 'eventos': eventos})
    except Exception as e:
        log.error('[REPORTE] %s', e)
        return jsonify({'ventas': [], 'gastos': [], 'eventos': []})


# ================================================================
#  JUGUETERÍA — Catálogo y ventas
# ================================================================

@api_key_required
@app.route('/api/productos', methods=['GET'])
def get_productos():
    """Lista todos los productos activos del catálogo."""
    if not supabase:
        return jsonify([])
    try:
        res = supabase.table('productos').select('*').eq('activo', True).order('nombre').execute()
        return jsonify(res.data or [])
    except Exception as e:
        log.error('[PRODUCTOS GET] %s', e)
        return jsonify([])


@api_key_required
@app.route('/api/productos/buscar', methods=['GET'])
def buscar_producto():
    """Busca un producto por código de barras."""
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({'encontrado': False})
    try:
        res = supabase.table('productos').select('*').eq('codigo_barras', codigo).execute()
        if res.data:
            return jsonify({'encontrado': True, 'producto': res.data[0]})
        return jsonify({'encontrado': False, 'codigo': codigo})
    except Exception as e:
        log.error('[PRODUCTO BUSCAR] %s', e)
        return jsonify({'encontrado': False, 'error': str(e)})


@api_key_required
@app.route('/api/productos', methods=['POST'])
def crear_producto():
    """Crea o actualiza un producto en el catálogo."""
    data = request.get_json(silent=True) or {}
    codigo  = data.get('codigo_barras', '').strip()
    nombre  = data.get('nombre', '').strip()
    precio  = int(data.get('precio_venta', 0))
    stock   = int(data.get('stock', 0))
    stock_m = int(data.get('stock_minimo', 2))
    if not codigo or not nombre:
        return jsonify({'ok': False, 'error': 'Código y nombre son obligatorios'}), 400
    try:
        # Upsert — crea si no existe, actualiza si existe
        supabase.table('productos').upsert({
            'codigo_barras': codigo, 'nombre': nombre,
            'precio_venta': precio, 'stock': stock,
            'stock_minimo': stock_m, 'activo': True,
            'updated_at': datetime.now().isoformat(),
        }).execute()
        return jsonify({'ok': True})
    except Exception as e:
        log.error('[PRODUCTO CREATE] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500


@api_key_required
@app.route('/api/productos/<codigo>', methods=['PATCH'])
def actualizar_producto(codigo):
    """Actualiza precio o stock de un producto."""
    data = request.get_json(silent=True) or {}
    data['updated_at'] = datetime.now().isoformat()
    try:
        supabase.table('productos').update(data).eq('codigo_barras', codigo).execute()
        return jsonify({'ok': True})
    except Exception as e:
        log.error('[PRODUCTO UPDATE] %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500


@api_key_required
@app.route('/api/jugueteria/venta', methods=['POST'])
def venta_juguete():
    """
    Registra una venta de juguete.
    Si viene con venta_id → agrega línea a venta activa existente.
    Si no → crea venta suelta en ventas_jugueteria.
    Body: {codigo_barras, cantidad?, precio_override?, venta_id?, comprador?, pago?}
    """
    data          = request.get_json(silent=True) or {}
    codigo        = data.get('codigo_barras', '').strip()
    cantidad      = int(data.get('cantidad', 1))
    precio_override = data.get('precio_override')  # permite ajustar precio en el momento
    venta_id      = data.get('venta_id')           # si hay visita activa
    comprador     = data.get('comprador', '')
    pago          = data.get('pago', 'Efectivo')
    nombre_manual = data.get('nombre', '')         # si no hay código de barras

    if not codigo and not nombre_manual:
        return jsonify({'ok': False, 'error': 'Se requiere código o nombre del producto'}), 400

    # Buscar producto en catálogo
    producto = None
    if codigo and supabase:
        try:
            res = supabase.table('productos').select('*').eq('codigo_barras', codigo).execute()
            if res.data:
                producto = res.data[0]
        except Exception as e:
            log.error('[JUGUETE BUSCAR] %s', e)

    nombre_producto = nombre_manual or (producto['nombre'] if producto else codigo)
    precio_unitario = precio_override if precio_override is not None else (producto['precio_venta'] if producto else 0)
    precio_total    = precio_unitario * cantidad

    # Descontar stock si el producto está en catálogo
    if producto and supabase:
        try:
            nuevo_stock = max(0, producto['stock'] - cantidad)
            supabase.table('productos').update({
                'stock': nuevo_stock,
                'updated_at': datetime.now().isoformat()
            }).eq('codigo_barras', codigo).execute()
        except Exception as e:
            log.error('[JUGUETE STOCK] %s', e)

    # ── Caso A: agregar a venta activa ──
    if venta_id:
        with _lock:
            venta = ninos_activos.get(venta_id)
        if not venta:
            return jsonify({'ok': False, 'error': 'Venta activa no encontrada'}), 404

        nueva_linea = {
            'id':             f"{venta_id}_toy_{int(datetime.now().timestamp())}",
            'venta_id':       venta_id,
            'nombre':         comprador or venta.get('acudiente', ''),
            'servicio':       'juguete',
            'combo':          nombre_producto,
            'categoria':      'jugueteria',
            'minutos':        None,
            'precio':         precio_total,
            'salida':         None,
            'activa':         True,
            'adicional':      True,
            'codigo_barras':  codigo,
            'cantidad':       cantidad,
        }
        with _lock:
            venta['lineas'].append(nueva_linea)
            venta['precio_total'] += precio_total

        sb_update('registros', {
            'ninos':        venta['lineas'],
            'precio_total': venta['precio_total'],
        }, {'id': venta_id})

        enviar_wa(venta['telefono'],
            f"🧸 *Juguete agregado*\n\n"
            f"{nombre_producto} (x{cantidad})\n"
            f"💰 {pesos(precio_total)} — {pago}\n"
            f"Total actualizado: {pesos(venta['precio_total'])}")

        return jsonify({'ok': True, 'tipo': 'venta_activa',
                        'linea': nueva_linea, 'precio_total': venta['precio_total']})

    # ── Caso B: venta suelta ──
    if supabase:
        try:
            sb_insert('ventas_jugueteria', {
                'codigo_barras':  codigo or None,
                'nombre_producto': nombre_producto,
                'precio_venta':   precio_total,
                'cantidad':       cantidad,
                'comprador':      comprador,
                'pago':           pago,
                'fecha':          datetime.now().isoformat(),
            })
        except Exception as e:
            log.error('[JUGUETE VENTA SUELTA] %s', e)
            return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'tipo': 'venta_suelta',
                    'producto': nombre_producto, 'total': precio_total,
                    'alertas': alertas_stock_db()})


# ================================================================
#  WEBHOOK WHATSAPP — Mensajes automáticos + Agente IA
# ================================================================

@app.route('/api/webhook-wa', methods=['POST'])
def webhook_wa():
    # ── Validar firma de Twilio para rechazar requests no autorizados ──
    if twilio and TWILIO_TOKEN:
        validator = RequestValidator(TWILIO_TOKEN)
        url = request.url
        signature = request.headers.get('X-Twilio-Signature', '')
        if not validator.validate(url, request.form, signature):
            log.warning('[WEBHOOK] Firma Twilio inválida — request rechazado')
            return '<Response></Response>', 403, {'Content-Type': 'text/xml'}

    body  = request.form.get('Body', '').strip()
    from_ = request.form.get('From', '')
    tel   = normalizar_telefono(from_)

    # Buscar grupo activo de este número (comparando número normalizado)
    with _lock:
        grupo = next(
            (g for g in ninos_activos.values()
             if normalizar_telefono(g['telefono']) == tel),
            None,
        )

    # ── Respuestas numéricas (1 = continuar, 2 = retirar) ──
    if body == '1' and grupo:
        srv = SERVICIOS.get(grupo['servicio'])
        if srv and srv.get('minutos'):
            cancelar_timers(grupo['id'])
            ahora = datetime.now()
            nueva_salida = ahora + timedelta(minutes=srv['minutos'])
            with _lock:
                grupo['entrada'] = ahora
                grupo['salida']  = nueva_salida
            # Persistir en BD
            sb_update('registros', {
                'entrada': ahora.isoformat(),
                'salida': nueva_salida.isoformat(),
            }, {'id': grupo['id']})
            programar_alertas(grupo['id'])
            nombres = ', '.join([n['nombre'] for n in grupo['ninos']])
            enviar_wa(grupo['telefono'],
                f"⏱ *Tiempo renovado*\n\n*{nombres}* tiene {srv['nombre']} más.\n"
                f"🕐 Nueva salida: {hora_legible(nueva_salida)}\n"
                f"💰 {pesos(srv['precio'])} adicionales — acérquese a cancelar.")

    elif body == '2' and grupo:
        gid = grupo['id']
        cancelar_timers(gid)
        with _lock:
            ninos_activos.pop(gid, None)
        sb_update('registros', {'activo': False}, {'id': gid})
        enviar_wa(grupo['telefono'], msg_despedida(grupo))

    else:
        # ── Agente IA responde cualquier otro mensaje ──
        def responder_async():
            respuesta = respuesta_agente(tel, body)
            enviar_wa(tel, respuesta)
        t = threading.Thread(target=responder_async, daemon=True)
        t.start()

    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}


# ================================================================
#  ARRANQUE
# ================================================================

cargar_sesiones_activas()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)