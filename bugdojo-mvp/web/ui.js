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

// Ejecuta el código en un Web Worker, con corte a los 2 segundos.
function correrTests(codigo, reto) {
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

function pintarTests(lista, reto, resultados) {
  lista.innerHTML = resultados.map((t) => `
    <li class="${t.ok ? "ok" : "mal"}">
      ${icono(t.ok ? "circle-check" : "x")}
      <span>${reto.funcion}(${escapar(t.entrada)})<br>esperado: ${escapar(t.esperado)}${t.ok ? "" : `<br>obtenido: ${escapar(t.obtenido)}`}</span>
    </li>`).join("");
}

document.addEventListener("DOMContentLoaded", () => pintarIconos());
