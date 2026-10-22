// Corre el Python de la persona en un hilo aparte de SU navegador (Pyodide).
// El servidor nunca ejecuta código ajeno. La página mata este worker si tarda demasiado.
importScripts("pyodide/pyodide.js");

const mostrar = (v) => (v === undefined ? "undefined" : JSON.stringify(v));

const listo = loadPyodide({ indexURL: "pyodide/" }).then((py) => {
  self.postMessage({ listo: true });
  return py;
}).catch((err) => {
  self.postMessage({ errorCarga: String(err && err.message ? err.message : err) });
  throw err;
});

// Mensaje corto para quien está aprendiendo: solo la última línea del traceback.
function resumir(e) {
  const lineas = String(e.message || e).trim().split("\n").filter(Boolean);
  const ultima = lineas[lineas.length - 1] || "Error";
  return ultima;
}

function aJS(pyodide, valor) {
  if (valor && typeof valor === "object" && typeof valor.toJs === "function") {
    const js = valor.toJs({ dict_converter: Object.fromEntries });
    valor.destroy();
    return js;
  }
  return valor;
}

self.onmessage = async (e) => {
  const { codigo, funcion, tests } = e.data;
  let pyodide;
  try {
    pyodide = await listo;
  } catch {
    return;
  }

  // Espacio de nombres nuevo en cada ejecución, para no arrastrar nada entre intentos
  const ns = pyodide.globals.get("dict")();
  try {
    pyodide.runPython(codigo, { globals: ns });
  } catch (err) {
    const msg = resumir(err);
    const sintaxis = /SyntaxError|IndentationError|TabError/.test(String(err.message));
    self.postMessage({ error: sintaxis ? `Error de sintaxis: ${msg}` : msg });
    ns.destroy();
    return;
  }

  const fn = ns.get(funcion);
  if (!fn) {
    self.postMessage({ error: `No encontramos la función ${funcion}. Revisa el nombre.` });
    ns.destroy();
    return;
  }

  const resultados = tests.map(([args, esperado]) => {
    const entrada = args.map(mostrar).join(", ");
    try {
      const pyArgs = args.map((a) => pyodide.toPy(a));
      const obtenido = aJS(pyodide, fn(...pyArgs));
      pyArgs.forEach((p) => p && p.destroy && p.destroy());
      return {
        ok: mostrar(obtenido) === mostrar(esperado),
        entrada,
        esperado: mostrar(esperado),
        obtenido: mostrar(obtenido),
      };
    } catch (err) {
      return { ok: false, entrada, esperado: mostrar(esperado), obtenido: `Error: ${resumir(err)}` };
    }
  });
  fn.destroy && fn.destroy();
  ns.destroy();
  self.postMessage({ resultados });
};
