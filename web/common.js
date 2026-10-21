// Estado del participante en su propio celular (nunca sale de aquí salvo el alias).
const CLAVE = "experimento-lean";

const estado = {
  leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE)) || {}; } catch { return {}; }
  },
  guardar(datos) {
    try { localStorage.setItem(CLAVE, JSON.stringify({ ...estado.leer(), ...datos })); } catch {}
  },
  borrar() {
    try { localStorage.removeItem(CLAVE); } catch {}
  },
};

const PRODUCTOS = {
  A: { nombre: "BugDojo", pagina: "bugdojo.html" },
  B: { nombre: "Focusaurio", pagina: "focusaurio.html" },
};

const ALIAS_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,25}$/;

async function api(ruta, cuerpo) {
  const opciones = cuerpo
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) }
    : { cache: "no-store" };
  try {
    const r = await fetch("/api/" + ruta, opciones);
    let data = {};
    try { data = await r.json(); } catch {}
    return { ok: r.ok, status: r.status, data };
  } catch {
    return { ok: false, status: 0, data: {} };
  }
}

// Lógica compartida por las dos landings (el smoke test).
function iniciarLanding(grupo) {
  const s = estado.leer();
  const cta = document.getElementById("cta");
  const motivos = document.getElementById("motivos");
  const err = document.getElementById("err");

  if (s.decidido) { location.replace("gracias.html"); return; }
  if (!s.alias) {
    cta.innerHTML = '<a class="btn" href="index.html" style="text-align:center;text-decoration:none">Responde primero las 10 preguntas</a>';
    return;
  }

  const mostrarError = (msg) => { err.textContent = msg; err.hidden = false; };

  async function enviar(decision, motivo) {
    document.querySelectorAll("#cta button, #motivos button").forEach((b) => (b.disabled = true));
    const r = await api("decision", { alias: s.alias, decision, motivo });
    if (r.ok || r.status === 409) {
      estado.guardar({ decidido: decision });
      location.href = "gracias.html";
    } else {
      document.querySelectorAll("#cta button, #motivos button").forEach((b) => (b.disabled = false));
      mostrarError("No pudimos guardar tu respuesta. Intenta otra vez.");
    }
  }

  document.getElementById("si").addEventListener("click", () => enviar("si"));
  document.getElementById("no").addEventListener("click", () => {
    cta.hidden = true;
    motivos.hidden = false;
  });
  motivos.querySelectorAll("button[data-m]").forEach((b) =>
    b.addEventListener("click", () => enviar("no", b.dataset.m))
  );
}
