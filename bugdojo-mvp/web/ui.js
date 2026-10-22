// Utilidades de interfaz compartidas (sin métricas).

// Icono del sprite de Lucide: icono("play"), icono("check", "i-lg")
function icono(nombre, clase = "") {
  return `<svg class="i ${clase}" aria-hidden="true"><use href="icons/sprite.svg#${nombre}"></use></svg>`;
}

// Reemplaza <i data-icono="nombre"></i> por el SVG correspondiente.
function pintarIconos(raiz = document) {
  raiz.querySelectorAll("[data-icono]").forEach((el) => {
    el.outerHTML = icono(el.dataset.icono, el.className);
  });
}

function escapar(t) {
  return String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- JavaScript: Web Worker nuevo en cada ejecución, con corte a los 2 s ----------
function correrJS(codigo, reto) {
  return new Promise((resolve) => {
    const w = new Worker("worker.js");
    const corte = setTimeout(() => {
      w.terminate();
      resolve({ error: "Tu código tardó más de 2 segundos. ¿Hay un bucle infinito?" });
    }, 2000);
    w.onmessage = (e) => { clearTimeout(corte); w.terminate(); resolve(e.data); };
    w.onerror = (e) => { clearTimeout(corte); w.terminate(); resolve({ error: e.message }); };
    w.postMessage({ codigo, funcion: reto.funcion, tests: reto.tests });
  });
}

// ---------- Python: Pyodide en un worker que se carga una vez y se reutiliza ----------
let pyWorker = null;
let pyListo = null;

function iniciarPython() {
  if (pyListo) return pyListo;
  pyListo = new Promise((resolve, reject) => {
    const w = new Worker("worker-py.js");
    pyWorker = w;
    w.addEventListener("message", function alCargar(e) {
      if (e.data.listo) { w.removeEventListener("message", alCargar); resolve(w); }
      if (e.data.errorCarga) { reject(new Error(e.data.errorCarga)); }
    });
    w.addEventListener("error", (e) => reject(new Error(e.message || "No se pudo cargar Python")));
  });
  pyListo.catch(() => { pyWorker = null; pyListo = null; });
  return pyListo;
}

async function correrPython(codigo, reto) {
  let w;
  try {
    w = await iniciarPython();
  } catch {
    return { error: "No pudimos cargar Python. Revisa tu conexión e inténtalo otra vez." };
  }
  return new Promise((resolve) => {
    const corte = setTimeout(() => {
      w.terminate();
      pyWorker = null;
      pyListo = null;
      resolve({ error: "Tu código tardó más de 2 segundos. ¿Hay un bucle infinito?" });
      iniciarPython().catch(() => {}); // deja listo un worker nuevo para el siguiente intento
    }, 2000);
    w.addEventListener("message", function alTerminar(e) {
      if (e.data.listo || e.data.errorCarga) return;
      clearTimeout(corte);
      w.removeEventListener("message", alTerminar);
      resolve(e.data);
    });
    w.postMessage({ codigo, funcion: reto.funcion, tests: reto.tests });
  });
}

function correrTests(codigo, reto) {
  return reto.lang === "py" ? correrPython(codigo, reto) : correrJS(codigo, reto);
}

function pintarTests(lista, reto, resultados) {
  lista.innerHTML = resultados.map((t) => `
    <li class="${t.ok ? "ok" : "mal"}">
      ${icono(t.ok ? "circle-check" : "x")}
      <span>${reto.funcion}(${escapar(t.entrada)})<br>esperado: ${escapar(t.esperado)}${t.ok ? "" : `<br>obtenido: ${escapar(t.obtenido)}`}</span>
    </li>`).join("");
}

document.addEventListener("DOMContentLoaded", () => pintarIconos());
