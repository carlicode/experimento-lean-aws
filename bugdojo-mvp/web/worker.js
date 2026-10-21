// Corre el código de la persona en un hilo aparte de SU navegador.
// El servidor nunca ejecuta código ajeno. La página corta este worker si tarda demasiado.
const mostrar = (v) => (v === undefined ? "undefined" : JSON.stringify(v));

self.onmessage = (e) => {
  const { codigo, funcion, tests } = e.data;
  let fn;
  try {
    fn = new Function(`${codigo}\nreturn typeof ${funcion} === "function" ? ${funcion} : undefined;`)();
  } catch (err) {
    self.postMessage({ error: `Error de sintaxis: ${err.message}` });
    return;
  }
  if (!fn) {
    self.postMessage({ error: `No encontramos la función ${funcion}. Revisa el nombre.` });
    return;
  }

  const resultados = tests.map(([args, esperado]) => {
    const entrada = args.map(mostrar).join(", ");
    try {
      const obtenido = fn(...structuredClone(args));
      return {
        ok: mostrar(obtenido) === mostrar(esperado),
        entrada,
        esperado: mostrar(esperado),
        obtenido: mostrar(obtenido),
      };
    } catch (err) {
      return { ok: false, entrada, esperado: mostrar(esperado), obtenido: `Error: ${err.message}` };
    }
  });
  self.postMessage({ resultados });
};
