// Identidad anónima y progreso: viven solo en el navegador de la persona.
const CLAVE = "bugdojo-mvp";
const FASES = ["aprendido", "armado", "resuelto"]; // Aprende → Arma → Escribe

function nuevoUid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
}

let memoria = {}; // por si el navegador bloquea localStorage

const estado = {
  leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE)) || memoria; } catch { return memoria; }
  },
  guardar(datos) {
    memoria = { ...estado.leer(), ...datos };
    try { localStorage.setItem(CLAVE, JSON.stringify(memoria)); } catch {}
  },
};

function uid() {
  let { uid } = estado.leer();
  if (!uid) {
    uid = nuevoUid();
    estado.guardar({ uid });
  }
  return uid;
}

// Clave de progreso: JavaScript conserva la clave original ("1"), Python usa "1:py".
function clave(id, lang = "js") {
  return lang === "py" ? `${id}:py` : id;
}

// Lenguaje elegido para un reto (o el último usado, o JavaScript).
function lenguajeDe(id) {
  const e = estado.leer();
  return (e.lang || {})[id] || e.langPref || "js";
}

function elegirLenguaje(id, lang) {
  estado.guardar({ lang: { ...(estado.leer().lang || {}), [id]: lang }, langPref: lang });
}

// Progreso de un reto en un lenguaje: { aprendido, armado, resuelto }
function progreso(id, lang = "js") {
  return (estado.leer().progreso || {})[clave(id, lang)] || {};
}

// Marca una fase como completada y la reporta una sola vez.
function marcar(id, fase, lang = "js") {
  const todo = estado.leer().progreso || {};
  const k = clave(id, lang);
  if (todo[k] && todo[k][fase]) return;
  estado.guardar({ progreso: { ...todo, [k]: { ...(todo[k] || {}), [fase]: true } } });
  evento(fase, { reto: id, lang });
}

function guardarEn(coleccion, id, valor, lang = "js") {
  const todo = estado.leer()[coleccion] || {};
  estado.guardar({ [coleccion]: { ...todo, [clave(id, lang)]: valor } });
}

function leerDe(coleccion, id, lang = "js") {
  return (estado.leer()[coleccion] || {})[clave(id, lang)];
}

// Fire-and-forget: las métricas nunca bloquean la experiencia.
function evento(tipo, extra = {}) {
  fetch("/api/evento", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: uid(), tipo, ...extra }),
    keepalive: true,
  }).catch(() => {});
}

// Cada página cuenta como visita del día (el servidor la deduplica por día).
evento("visita");
