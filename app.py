# ================================================================
#  INFLABOOM — Servidor con Agente WhatsApp Inteligente
#  Python + Flask + Twilio + Supabase + Claude (Anthropic)
# ================================================================

from flask import Flask, request, jsonify, send_from_directory, session, g
from functools import wraps
from twilio.rest import Client as TwilioClient
from twilio.request_validator import RequestValidator
from datetime import datetime, timedelta, date
from calendar import monthrange
from supabase import create_client
from werkzeug.security import generate_password_hash, check_password_hash
import anthropic
import threading
import logging
import secrets
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
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))


@app.route("/")
def home():
    return "Servidor funcionando"

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
_lock           = threading.Lock()
ninos_activos   = {}   # id -> grupo activo  (acceso siempre bajo _lock)
timers          = {}   # id -> [timers]       (acceso siempre bajo _lock)
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
#  AUTENTICACIÓN Y ROLES
# ================================================================

ROLES = {'admin': 1, 'operador': 2}

def login_required(f):
    """Decorador — rechaza sin sesión activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorador — solo admin puede acceder."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        if session.get('rol') != 'admin':
            return jsonify({'ok': False, 'error': 'Acceso solo para administrador'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.get_json(silent=True) or {}
    usuario  = data.get('usuario', '').strip().lower()
    password = data.get('password', '')
    if not supabase:
        return jsonify({'ok': False, 'error': 'Sin conexión a base de datos'}), 500
    try:
        res = supabase.table('usuarios').select('*').eq('usuario', usuario).eq('activo', True).execute()
        if not res.data:
            return jsonify({'ok': False, 'error': 'Usuario o contraseña incorrectos'}), 401
        u = res.data[0]
        if not check_password_hash(u['password_hash'], password):
            return jsonify({'ok': False, 'error': 'Usuario o contraseña incorrectos'}), 401
        session.permanent = True
        session['usuario_id'] = u['id']
        session['usuario']    = u['usuario']
        session['nombre']     = u['nombre']
        session['rol']        = u['rol']
        supabase.table('usuarios').update({'ultimo_acceso': datetime.now().isoformat()}).eq('id', u['id']).execute()
        log.info('[LOGIN] %s (%s)', u['usuario'], u['rol'])
        return jsonify({'ok': True, 'nombre': u['nombre'], 'rol': u['rol']})
    except Exception as e:
        log.error('[LOGIN] %s', e)
        return jsonify({'ok': False, 'error': 'Error interno'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    usuario = session.get('usuario', 'desconocido')
    session.clear()
    log.info('[LOGOUT] %s', usuario)
    return jsonify({'ok': True})

@app.route('/api/auth/me')
def me():
    if 'usuario_id' not in session:
        return jsonify({'autenticado': False}), 401
    return jsonify({
        'autenticado': True,
        'usuario': session.get('usuario'),
        'nombre':  session.get('nombre'),
        'rol':     session.get('rol'),
    })

@app.route('/api/usuarios', methods=['GET'])
@admin_required
def get_usuarios():
    try:
        res = supabase.table('usuarios').select('id,usuario,nombre,rol,activo,ultimo_acceso').execute()
        return jsonify(res.data or [])
    except Exception as e:
        log.error('[USUARIOS GET] %s', e)
        return jsonify([])

@app.route('/api/usuarios', methods=['POST'])
@admin_required
def crear_usuario():
    data = request.get_json(silent=True) or {}
    usuario  = data.get('usuario', '').strip().lower()
    nombre   = data.get('nombre', '').strip()
    password = data.get('password', '')
    rol      = data.get('rol', 'operador')
    if not usuario or not nombre or not password:
        return jsonify({'ok': False, 'error': 'Faltan campos'}), 400
    if rol not in ROLES:
        return jsonify({'ok': False, 'error': 'Rol inválido'}), 400
    try:
        sb_insert('usuarios', {
            'usuario': usuario, 'nombre': nombre,
            'password_hash': generate_password_hash(password),
            'rol': rol, 'activo': True,
        })
        return jsonify({'ok': True})
    except Exception as e:
        log.error('[USUARIOS CREATE] %s', e)
        return jsonify({'ok': False, 'error': 'Error al crear usuario'}), 500

@app.route('/api/usuarios/<int:uid>/password', methods=['PATCH'])
@admin_required
def cambiar_password(uid):
    data = request.get_json(silent=True) or {}
    nueva = data.get('password', '')
    if not nueva:
        return jsonify({'ok': False, 'error': 'Contraseña vacía'}), 400
    sb_update('usuarios', {'password_hash': generate_password_hash(nueva)}, {'id': uid})
    return jsonify({'ok': True})

@app.route('/api/usuarios/<int:uid>/activar', methods=['PATCH'])
@admin_required
def activar_usuario(uid):
    activo = (request.get_json(silent=True) or {}).get('activo', True)
    sb_update('usuarios', {'activo': activo}, {'id': uid})
    return jsonify({'ok': True})


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
    try:
        res = supabase.table('inventario').select('*').execute()
        return [
            f"⚠️ {r['producto']}: solo {r['cantidad']} disponibles"
            for r in (res.data or []) if r['cantidad'] <= r['umbral_alerta']
        ]
    except Exception as e:
        log.error('[DB ALERTAS] %s', e)
        return []


# ================================================================
#  MENSAJES AUTOMÁTICOS
# ================================================================

def msg_bienvenida(g):
    acudiente = g.get('acudiente') or 'acudiente'
    ninos     = g['ninos']
    es_grupo  = len(ninos) > 1
    es_arte   = all(n.get('servicio') == 'arte' for n in ninos)

    if es_arte:
        dibujos = ', '.join([f"{n['nombre']} ({n.get('dibujo') or '?'})" for n in ninos])
        return (f"🎨 *Inflaboom — Estación de Arte*\n\nHola {acudiente} 👋\n\n"
                f"{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado a pintar.\n\n"
                f"🖌 *{'Niños' if es_grupo else 'Niño/a'}:* {dibujos}\n"
                f"💰 *Valor:* {pesos(g['precio_total'])} — {g['pago']}\n\n¡A disfrutar! 🌟")

    # Construir línea individual por niño con su propio tiempo
    lineas_ninos = ''
    for n in ninos:
        salida_str = hora_legible(n['salida']) if n.get('salida') else '—'
        lineas_ninos += f"\n  • *{n['nombre']}* — {n['combo']} · sale {salida_str}"

    return (f"🎪 *Inflaboom — Bienvenida*\n\nHola {acudiente} 👋\n\n"
            f"*{'Los niños han' if es_grupo else 'Tu hijo/a ha'} ingresado:*"
            f"{lineas_ninos}\n\n"
            f"💰 *Total:* {pesos(g['precio_total'])} — {g['pago']}")

def msg_recibo(g):
    ninos    = g['ninos']
    es_grupo = len(ninos) > 1
    lineas   = '\n'.join([f"  • {n['nombre']} — {n['combo']} ({pesos(n['precio'])})" for n in ninos])
    return (f"🧾 *Recibo — Inflaboom*\n\n"
            f"{'Niños' if es_grupo else 'Niño/a'}:\n{lineas}\n\n"
            f"💵 *Total:* {pesos(g['precio_total'])}\n"
            f"💳 *Pago:* {g['pago']}\n"
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
#@app.route('/')
#def index():
#    return send_from_directory('public', 'index.html')


#@app.route('/<path:path>')
#def static_files(path):
#    return send_from_directory('public', path)



@app.route('/api/registrar', methods=['POST'])
@login_required
def registrar():
    data      = request.get_json(silent=True) or {}
    acudiente = data.get('acudiente', '')
    telefono  = data.get('telefono', '')
    pago      = data.get('pago', 'Efectivo')
    ninos     = data.get('ninos', [])
    # ninos ahora es lista de objetos: [{nombre, servicio, dibujo?}, ...]

    if not telefono or not ninos:
        return jsonify({'ok': False, 'error': 'Faltan campos obligatorios'}), 400

    # Validar que cada niño tenga servicio válido
    for n in ninos:
        if not SERVICIOS.get(n.get('servicio')):
            return jsonify({'ok': False, 'error': f'Servicio inválido para {n.get("nombre","?")}'}), 400

    ahora = datetime.now()
    gid   = str(int(ahora.timestamp() * 1000))

    # ── Construir lista de niños con tiempo INDEPENDIENTE por cada uno ──
    precio_total = 0
    ninos_procesados = []
    for n in ninos:
        srv     = SERVICIOS[n['servicio']]
        minutos = srv.get('minutos')
        salida  = (ahora + timedelta(minutes=minutos)).isoformat() if minutos else None
        precio  = srv['precio']
        precio_total += precio
        ninos_procesados.append({
            'nombre':   n.get('nombre', ''),
            'servicio': n['servicio'],
            'combo':    srv['nombre'],
            'minutos':  minutos,
            'precio':   precio,
            'salida':   salida,         # ← salida individual por niño
            'dibujo':   n.get('dibujo', ''),
        })

    # El grupo usa la salida MÁS TARDÍA para los temporizadores grupales de WA
    salidas_validas = [datetime.fromisoformat(n['salida']) for n in ninos_procesados if n['salida']]
    salida_grupo    = max(salidas_validas) if salidas_validas else None

    grupo = {
        'id': gid, 'acudiente': acudiente, 'telefono': telefono,
        'pago': pago, 'ninos': ninos_procesados,
        'precio_total': precio_total,
        'entrada': ahora, 'salida': salida_grupo, 'activo': True,
        'operador_id':  session.get('usuario_id'),
        'operador':     session.get('nombre', ''),
    }
    with _lock:
        ninos_activos[gid] = grupo

    sb_insert('registros', {
        'id': gid, 'acudiente': acudiente, 'telefono': telefono,
        'pago': pago, 'ninos': ninos_procesados,
        'precio_total': precio_total,
        'entrada': ahora.isoformat(),
        'salida': salida_grupo.isoformat() if salida_grupo else None,
        'activo': True,
        'operador_id': session.get('usuario_id'),
        'operador':    session.get('nombre', ''),
        # servicio queda como el del primer niño por compatibilidad con historial
        'servicio': ninos_procesados[0]['servicio'] if ninos_procesados else '',
    })

    descontar_inventario_db(ninos_procesados[0]['servicio'], ninos_procesados)
    registrar_cliente_db(telefono, acudiente, precio_total)
    programar_alertas(gid)
    enviar_wa(telefono, msg_bienvenida(grupo))
    threading.Timer(2.0, lambda: enviar_wa(telefono, msg_recibo(grupo))).start()

    return jsonify({
        'ok': True, 'id': gid,
        'ninos': ninos_procesados,   # cada niño trae su salida individual
        'precio_total': precio_total,
        'alertas': alertas_stock_db(),
    })


@app.route('/api/retirar', methods=['POST'])
@login_required
def retirar():
    gid = (request.get_json(silent=True) or {}).get('id')
    with _lock:
        grupo = ninos_activos.pop(gid, None)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    cancelar_timers(gid)
    sb_update('registros', {'activo': False}, {'id': gid})
    enviar_wa(grupo['telefono'], msg_despedida(grupo))
    return jsonify({'ok': True})


@app.route('/api/extender', methods=['POST'])
@login_required
def extender():
    data     = request.get_json(silent=True) or {}
    gid      = data.get('id')
    nino_idx = data.get('nino_idx', 0)   # índice del niño a extender
    servicio = data.get('servicio', 'combo_1h')
    pago     = data.get('pago', 'Efectivo')
    with _lock:
        grupo = ninos_activos.get(gid)
    if not grupo:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404

    srv = SERVICIOS.get(servicio)
    if not srv:
        return jsonify({'ok': False, 'error': 'Servicio inválido'}), 400

    cancelar_timers(gid)
    ahora        = datetime.now()
    nueva_salida = ahora + timedelta(minutes=srv['minutos'])

    with _lock:
        # Extender solo el niño indicado por índice
        if 0 <= nino_idx < len(grupo['ninos']):
            grupo['ninos'][nino_idx]['salida']   = nueva_salida.isoformat()
            grupo['ninos'][nino_idx]['servicio'] = servicio
            grupo['ninos'][nino_idx]['combo']    = srv['nombre']
        # Recalcular salida del grupo (la más tardía)
        salidas = [datetime.fromisoformat(n['salida']) for n in grupo['ninos'] if n.get('salida')]
        grupo['salida'] = max(salidas) if salidas else None

    programar_alertas(gid)
    sb_update('registros', {
        'ninos':  grupo['ninos'],
        'salida': grupo['salida'].isoformat() if grupo['salida'] else None,
    }, {'id': gid})

    nombre_nino = grupo['ninos'][nino_idx]['nombre'] if 0 <= nino_idx < len(grupo['ninos']) else '?'
    enviar_wa(grupo['telefono'],
        f"⏱ *Tiempo extendido*\n\n*{nombre_nino}* tiene {srv['nombre']} más.\n"
        f"🕐 Nueva salida: {hora_legible(nueva_salida)}\n"
        f"💰 {pesos(srv['precio'])} — {pago}")
    return jsonify({'ok': True, 'salida': nueva_salida.isoformat()})


@app.route('/api/reportes/operador')
@login_required
def reporte_operador():
    """Ventas del operador en sesión para el día de hoy."""
    fecha     = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    op_id     = request.args.get('operador_id', session.get('usuario_id'))
    # Admin puede ver cualquier operador; operador solo ve el suyo
    if session.get('rol') != 'admin':
        op_id = session.get('usuario_id')
    if not supabase:
        return jsonify([])
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


@app.route('/api/activos')
@login_required
def get_activos():
    ahora = datetime.now()
    with _lock:
        snapshot = list(ninos_activos.values())
    resultado = []
    for g in snapshot:
        # Calcular ms_restantes INDIVIDUAL por niño
        ninos_con_tiempo = []
        for n in g['ninos']:
            if n.get('salida'):
                salida_n = datetime.fromisoformat(n['salida']) if isinstance(n['salida'], str) else n['salida']
                ms = max(0, int((salida_n - ahora).total_seconds() * 1000))
                activo_n = ms > 0
            else:
                ms       = None
                activo_n = True  # arte no tiene salida, siempre activo
            ninos_con_tiempo.append({
                **n,
                'ms_restantes': ms,
                'activo': activo_n,
            })

        salida_grupo = g['salida']
        resultado.append({
            'id':          g['id'],
            'acudiente':   g['acudiente'],
            'telefono':    g['telefono'],
            'pago':        g['pago'],
            'precio_total':g['precio_total'],
            'entrada':     g['entrada'].isoformat(),
            'salida':      salida_grupo.isoformat() if salida_grupo else None,
            'ninos':       ninos_con_tiempo,   # ← cada niño con su propio ms_restantes
            'operador':    g.get('operador', ''),
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
        except Exception as e:
            log.error('[HISTORIAL] %s', e)
    return jsonify([])


@app.route('/api/kpis')
@login_required
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


@app.route('/api/inventario')
@login_required
def get_inventario():
    if supabase:
        try:
            res = supabase.table('inventario').select('*').order('producto').execute()
            inv = {r['producto']: {'cantidad': r['cantidad'], 'umbral': r['umbral_alerta']} for r in (res.data or [])}
            return jsonify(inv)
        except Exception as e:
            log.error('[INV GET] %s', e)
    return jsonify({'manillas': {'cantidad': 100, 'umbral': 10}, 'pinturas': {'cantidad': 50, 'umbral': 10}})

@app.route('/api/inventario/agregar', methods=['POST'])
@login_required
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


@app.route('/api/gastos', methods=['GET'])
@login_required
def get_gastos():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    if supabase:
        try:
            res = supabase.table('gastos').select('*').eq('fecha', fecha).order('created_at', desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[GASTOS GET] %s', e)
    return jsonify([])

@app.route('/api/gastos', methods=['POST'])
@login_required
def agregar_gasto():
    data = request.get_json(silent=True) or {}
    sb_insert('gastos', {
        'categoria': data.get('categoria'), 'descripcion': data.get('descripcion'),
        'valor': int(data.get('valor', 0)), 'fecha': data.get('fecha', datetime.now().strftime('%Y-%m-%d')),
    })
    return jsonify({'ok': True})


@app.route('/api/clientes')
@login_required
def get_clientes():
    if supabase:
        try:
            res = supabase.table('clientes').select('*').order('visitas', desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[CLIENTES] %s', e)
    return jsonify([])


@app.route('/api/eventos', methods=['GET'])
@login_required
def get_eventos():
    if supabase:
        try:
            res = supabase.table('eventos').select('*').order('created_at',desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            log.error('[EVENTOS GET] %s', e)
    return jsonify([])

@app.route('/api/eventos', methods=['POST'])
@login_required
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

@app.route('/api/eventos/<int:evento_id>', methods=['PATCH'])
@login_required
def actualizar_evento(evento_id):
    sb_update('eventos', request.get_json(silent=True) or {}, {'id':evento_id})
    return jsonify({'ok':True})


@app.route('/api/reportes/mes')
@admin_required
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