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

// Progreso de un reto: { aprendido, armado, resuelto }
function progreso(id) {
  return (estado.leer().progreso || {})[id] || {};
}

// Marca una fase como completada y la reporta una sola vez.
function marcar(id, fase) {
  const todo = estado.leer().progreso || {};
  if (todo[id] && todo[id][fase]) return;
  estado.guardar({ progreso: { ...todo, [id]: { ...(todo[id] || {}), [fase]: true } } });
  evento(fase, { reto: id });
}

function guardarEn(clave, id, valor) {
  const todo = estado.leer()[clave] || {};
  estado.guardar({ [clave]: { ...todo, [id]: valor } });
}

function leerDe(clave, id) {
  return (estado.leer()[clave] || {})[id];
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
