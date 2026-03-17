// ============================================================
//  ZONA INFLABLES — Servidor principal
//  Tecnología: Node.js + Express + Twilio WhatsApp
// ============================================================

const express = require('express');
const twilio  = require('twilio');
const path    = require('path');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// ── Credenciales Twilio ──────────────────────────────────────
// Copia estos valores desde tu panel en twilio.com/console
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID || 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx';
const TWILIO_AUTH_TOKEN  = process.env.TWILIO_AUTH_TOKEN  || 'tu_auth_token_aqui';
const TWILIO_WA_NUMBER   = process.env.TWILIO_WA_NUMBER   || 'whatsapp:+14155238886'; // número sandbox Twilio

const client = twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);

// ── Base de datos en memoria (mientras no hay DB externa) ────
// En producción futura esto se reemplaza por PostgreSQL / Supabase
let ninos    = [];   // niños activos en el parque
let historial = [];  // registro completo del día

// ── Configuración de combos ──────────────────────────────────
const COMBOS = {
  1: { nombre: '15 minutos',  minutos: 15,  precio: 5000,  juegos: '1 juego a elección' },
  2: { nombre: '30 minutos',  minutos: 30,  precio: 8000,  juegos: '2 juegos a elección' },
  3: { nombre: '1 hora',      minutos: 60,  precio: 13000, juegos: '4 juegos (todos)' },
};

// ── Helpers ──────────────────────────────────────────────────
function horaLegible(date) {
  return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
}

function esSabado() {
  return new Date().getDay() === 6;
}

function formatPesos(n) {
  return '$' + n.toLocaleString('es-CO');
}

// ── Envío de mensajes WhatsApp vía Twilio ────────────────────
async function enviarWA(telefono, mensaje) {
  // Normaliza número colombiano: agrega +57 si no lo tiene
  let num = telefono.replace(/\D/g, '');
  if (num.startsWith('0')) num = num.slice(1);
  if (!num.startsWith('57')) num = '57' + num;
  const destino = 'whatsapp:+' + num;

  try {
    const msg = await client.messages.create({
      from: TWILIO_WA_NUMBER,
      to:   destino,
      body: mensaje,
    });
    console.log(`✅ WA enviado a ${destino} — SID: ${msg.sid}`);
    return { ok: true, sid: msg.sid };
  } catch (err) {
    console.error(`❌ Error enviando WA a ${destino}:`, err.message);
    return { ok: false, error: err.message };
  }
}

// ── Mensajes predefinidos ────────────────────────────────────
function msgBienvenida(nino, combo, salida) {
  const promo = esSabado() && nino.combo == 3
    ? '\n\n🎁 *Promo sábado 2x1 aplicada.* ¡Gracias por elegirnos!'
    : '';
  return (
    `🎪 *Zona Inflables — Bienvenida*\n\n` +
    `Hola ${nino.acudiente || 'acudiente'} 👋\n\n` +
    `*${nino.nombre}* acaba de ingresar al parque.\n\n` +
    `⏱ *Combo:* ${combo.nombre} — ${combo.juegos}\n` +
    `🕐 *Ingreso:* ${horaLegible(nino.entrada)}\n` +
    `🕐 *Salida:* ${horaLegible(salida)}\n` +
    `💰 *Valor:* ${formatPesos(combo.precio)} — ${nino.pago}` +
    promo
  );
}

function msgRecibo(nino, combo) {
  return (
    `🧾 *Recibo de pago — Zona Inflables*\n\n` +
    `👦 Nombre: ${nino.nombre}\n` +
    `🎮 Combo: ${combo.nombre}\n` +
    `🎪 Incluye: ${combo.juegos}\n` +
    `💵 Valor: ${formatPesos(combo.precio)}\n` +
    `💳 Pago: ${nino.pago}\n` +
    `📅 Fecha: ${new Date().toLocaleDateString('es-CO')}\n\n` +
    `_Gracias por su visita_ ✅`
  );
}

function msgAviso5(nino) {
  return (
    `⏰ *Recordatorio — Zona Inflables*\n\n` +
    `Hola, le quedan *5 minutos* al tiempo de *${nino.nombre}*.\n\n` +
    `Por favor acérquese a la zona de ingreso. 🙏`
  );
}

function msgTiempoTerminado(nino) {
  return (
    `🔔 *Tiempo finalizado — Zona Inflables*\n\n` +
    `El tiempo de *${nino.nombre}* ha terminado.\n\n` +
    `¿Desea continuar?\n\n` +
    `Responda:\n` +
    `*1* — Sí, quiero más tiempo\n` +
    `*2* — No, voy a retirarlo ahora`
  );
}

function msgDespedida(nino) {
  const promo = esSabado()
    ? '\n\n🎉 *Promo sábados:* 2x1 en combo 1 hora. ¡Tráigale un amiguito la próxima!'
    : '';
  return (
    `🌟 *¡Hasta pronto! — Zona Inflables*\n\n` +
    `Gracias por visitarnos hoy con *${nino.nombre}*.\n\n` +
    `Esperamos que lo haya disfrutado muchísimo 😊\n\n` +
    `📍 ¡Los esperamos pronto! Estamos abiertos todos los días.\n` +
    `📲 Guarda este número para estar al día con nuestras novedades.` +
    promo
  );
}

// ── Programar alertas de tiempo ──────────────────────────────
function programarAlertas(nino) {
  const combo    = COMBOS[nino.combo];
  const msTotal  = combo.minutos * 60 * 1000;
  const msAviso  = (combo.minutos - 5) * 60 * 1000;

  // Alerta 5 minutos antes
  if (msAviso > 0) {
    nino._timerAviso = setTimeout(async () => {
      const still = ninos.find(n => n.id === nino.id);
      if (still) await enviarWA(nino.telefono, msgAviso5(nino));
    }, msAviso);
  }

  // Tiempo terminado
  nino._timerFin = setTimeout(async () => {
    const still = ninos.find(n => n.id === nino.id);
    if (still) await enviarWA(nino.telefono, msgTiempoTerminado(nino));
  }, msTotal);
}

function cancelarTimers(nino) {
  clearTimeout(nino._timerAviso);
  clearTimeout(nino._timerFin);
}

// ══════════════════════════════════════════════════════════════
//  RUTAS API
// ══════════════════════════════════════════════════════════════

// ── POST /api/registrar — registra un niño ──────────────────
app.post('/api/registrar', async (req, res) => {
  const { nombre, acudiente, telefono, combo, pago } = req.body;

  if (!nombre || !telefono || !combo) {
    return res.status(400).json({ ok: false, error: 'Faltan campos obligatorios.' });
  }

  const c      = COMBOS[combo];
  if (!c) return res.status(400).json({ ok: false, error: 'Combo inválido.' });

  const ahora  = new Date();
  const salida = new Date(ahora.getTime() + c.minutos * 60 * 1000);
  const id     = Date.now();

  const nino = { id, nombre, acudiente, telefono, combo: Number(combo), pago, entrada: ahora, salida };
  ninos.push(nino);
  historial.push({ ...nino, _timerAviso: undefined, _timerFin: undefined });

  // Programar alertas automáticas
  programarAlertas(nino);

  // Enviar mensajes WhatsApp
  await enviarWA(telefono, msgBienvenida(nino, c, salida));
  setTimeout(() => enviarWA(telefono, msgRecibo(nino, c)), 2000);

  res.json({ ok: true, id, salida });
});

// ── POST /api/retirar — retira un niño ───────────────────────
app.post('/api/retirar', async (req, res) => {
  const { id } = req.body;
  const idx = ninos.findIndex(n => n.id === Number(id));
  if (idx === -1) return res.status(404).json({ ok: false, error: 'Niño no encontrado.' });

  const nino = ninos[idx];
  cancelarTimers(nino);
  ninos.splice(idx, 1);

  await enviarWA(nino.telefono, msgDespedida(nino));

  res.json({ ok: true });
});

// ── POST /api/extender — extiende tiempo ─────────────────────
app.post('/api/extender', async (req, res) => {
  const { id, combo } = req.body;
  const nino = ninos.find(n => n.id === Number(id));
  if (!nino) return res.status(404).json({ ok: false, error: 'Niño no encontrado.' });

  const c = COMBOS[combo];
  if (!c) return res.status(400).json({ ok: false, error: 'Combo inválido.' });

  cancelarTimers(nino);
  nino.combo  = Number(combo);
  nino.entrada = new Date();
  nino.salida  = new Date(Date.now() + c.minutos * 60 * 1000);
  programarAlertas(nino);

  const msg =
    `✅ *Tiempo extendido — Zona Inflables*\n\n` +
    `*${nino.nombre}* tiene ${c.nombre} adicionales.\n` +
    `🕐 Nueva salida: ${horaLegible(nino.salida)}\n` +
    `💰 Valor: ${formatPesos(c.precio)} — ${nino.pago}`;

  await enviarWA(nino.telefono, msg);
  res.json({ ok: true, salida: nino.salida });
});

// ── GET /api/activos — lista niños activos ───────────────────
app.get('/api/activos', (req, res) => {
  const ahora = Date.now();
  res.json(ninos.map(n => ({
    id:        n.id,
    nombre:    n.nombre,
    acudiente: n.acudiente,
    telefono:  n.telefono,
    combo:     n.combo,
    pago:      n.pago,
    entrada:   n.entrada,
    salida:    n.salida,
    msRestantes: Math.max(0, new Date(n.salida) - ahora),
  })));
});

// ── GET /api/historial — historial del día ───────────────────
app.get('/api/historial', (req, res) => {
  res.json(historial.map(n => ({
    id:       n.id,
    nombre:   n.nombre,
    combo:    n.combo,
    pago:     n.pago,
    entrada:  n.entrada,
    salida:   n.salida,
  })));
});

// ── POST /api/webhook-wa — respuestas del cliente ────────────
// Twilio llama este endpoint cuando el cliente responde "1" o "2"
app.post('/api/webhook-wa', async (req, res) => {
  const body   = (req.body.Body || '').trim();
  const fromWA = req.body.From || ''; // ej: whatsapp:+573001234567
  const tel    = fromWA.replace('whatsapp:+57', '').replace('whatsapp:+', '');

  // Buscar niño activo asociado a ese teléfono
  const nino = ninos.find(n => n.telefono.replace(/\D/g,'').endsWith(tel.replace(/\D/g,'')));

  if (body === '1' && nino) {
    // Quiere continuar — extender con mismo combo por defecto
    const c    = COMBOS[nino.combo];
    cancelarTimers(nino);
    nino.entrada = new Date();
    nino.salida  = new Date(Date.now() + c.minutos * 60 * 1000);
    programarAlertas(nino);
    const msg =
      `⏱ *Tiempo renovado*\n\n` +
      `Listo! *${nino.nombre}* tiene ${c.nombre} más.\n` +
      `🕐 Nueva salida: ${horaLegible(nino.salida)}\n` +
      `💰 ${formatPesos(c.precio)} adicionales — por favor acérquese a cancelar.`;
    await enviarWA(nino.telefono, msg);
  } else if (body === '2' && nino) {
    // Quiere retirar
    cancelarTimers(nino);
    ninos = ninos.filter(n => n.id !== nino.id);
    await enviarWA(nino.telefono, msgDespedida(nino));
  } else {
    // Mensaje no reconocido
    const respuesta =
      `Hola 👋 Soy el asistente de *Zona Inflables*.\n\n` +
      `Para consultas escríbenos o visítanos en el parque. ¡Gracias!`;
    await enviarWA(tel, respuesta);
  }

  // Twilio espera respuesta TwiML (puede ir vacía)
  res.set('Content-Type', 'text/xml');
  res.send('<Response></Response>');
});

// ── Iniciar servidor ─────────────────────────────────────────
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n🎪 Zona Inflables — Servidor corriendo en puerto ${PORT}`);
  console.log(`   Abre http://localhost:${PORT} en tu navegador\n`);
});
