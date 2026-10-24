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

// ?reiniciar=1 borra el estado de este navegador: vuelve a contar como persona nueva.
if (new URLSearchParams(location.search).has("reiniciar")) {
  try { localStorage.removeItem(CLAVE); } catch {}
  history.replaceState(null, "", location.pathname);
}

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
  avisoEarlyAccess();
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

// ---------- Early access: aviso amarillo desde que completa su primera fase ----------
const NOMBRE_EARLY = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,20}( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]\.){1,3}$/;

// "carla marquez f" → "Carla M. F.": del resto de palabras solo guardamos la inicial.
function normalizarNombre(texto) {
  const [nombre = "", ...resto] = texto.trim().split(/\s+/);
  const inicial = (p) => p.charAt(0).toUpperCase() + ".";
  return [nombre.charAt(0).toUpperCase() + nombre.slice(1).toLowerCase(), ...resto.map(inicial)].join(" ");
}

function fasesCompletadas() {
  return Object.values(estado.leer().progreso || {})
    .reduce((n, p) => n + FASES.filter((f) => p[f]).length, 0);
}

function avisoEarlyAccess() {
  const e = estado.leer();
  const hechas = fasesCompletadas();
  if (e.inscrito || hechas === 0 || hechas <= (e.earlyCerrado || 0) || document.getElementById("early")) return;

  const caja = document.createElement("aside");
  caja.id = "early";
  caja.className = "early";
  caja.innerHTML = `
    <button class="early-cerrar" aria-label="Cerrar">${icono("x")}</button>
    <button class="early-abrir">${icono("sparkles")}Inscribirme al early access</button>
    <form class="early-form" hidden>
      <label for="early-nombre">Tu nombre y la inicial de tu otro nombre o apellido</label>
      <div class="early-fila">
        <input id="early-nombre" maxlength="40" placeholder="Carla M." autocomplete="off" required>
        <button class="btn sm" type="submit">Inscribirme</button>
      </div>
      <p class="early-err" hidden></p>
    </form>`;
  document.body.append(caja);
  document.body.classList.add("con-early");

  const form = caja.querySelector("form");
  const input = caja.querySelector("input");
  const boton = form.querySelector("button");
  const err = caja.querySelector(".early-err");
  const cerrar = () => { caja.remove(); document.body.classList.remove("con-early"); };
  const error = (msg) => { err.textContent = msg; err.hidden = false; };
  input.addEventListener("input", () => { err.hidden = true; });

  // Si la cierra, vuelve a aparecer cuando complete otra fase.
  caja.querySelector(".early-cerrar").addEventListener("click", () => {
    estado.guardar({ earlyCerrado: fasesCompletadas() });
    cerrar();
  });
  caja.querySelector(".early-abrir").addEventListener("click", (ev) => {
    ev.currentTarget.hidden = true;
    form.hidden = false;
    input.focus();
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const nombre = normalizarNombre(input.value);
    if (!NOMBRE_EARLY.test(nombre)) return error("Escribe tu nombre y una inicial. Ejemplo: Carla M.");
    boton.disabled = true;
    try {
      const r = await fetch("/api/evento", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid: uid(), tipo: "inscripcion", nombre }),
      });
      if (!r.ok) throw new Error(String(r.status));
      estado.guardar({ inscrito: nombre });
      caja.innerHTML = `<p class="early-ok">${icono("circle-check")}¡Listo, ${escapar(nombre)}! Quedaste en la lista del early access.</p>`;
      setTimeout(cerrar, 4000);
    } catch {
      boton.disabled = false;
      error("No pudimos inscribirte. Revisa tu conexión e inténtalo otra vez.");
    }
  });
}

// Cada página cuenta como visita del día (el servidor la deduplica por día).
evento("visita");
avisoEarlyAccess();
