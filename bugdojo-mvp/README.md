# 🥋 BugDojo · MVP (etapa 2 del ciclo Lean)

Siguiente vuelta del ciclo **Construir → Medir → Aprender**, después del experimento en vivo.

| Etapa | Pregunta | Dónde |
|---|---|---|
| 1. Smoke test | ¿Les interesa lo suficiente? | `../` (experimento en vivo, en la charla) |
| **2. MVP funcional** | **¿Lo usan de verdad y vuelven?** | **esta carpeta, después de la charla** |

**No hay venta:** sin precios, sin correos, sin cuentas y sin pagos. Solo una prueba gratuita con 5 retos reales de JavaScript (del cinturón blanco al negro) y medición de uso **anónimo**.

## Cómo se aprende: 3 fases por reto

Nadie empieza frente a una pantalla en blanco:

| Fase | Qué hace la persona |
|---|---|
| **1. Aprende** | 3 tarjetas de conceptos con ejemplo de código y una pregunta para comprobar que se entendió. |
| **2. Arma** | Ordena bloques de código **estilo Scratch** (colores por tipo: variable, bucle, condición, acción, devolver, cierre). Hay bloques trampa, una **guía paso a paso** y botón de **pista**. Se toca para agregar o quitar; en la compu también se arrastra. |
| **3. Escribe** | Opcional: escribe la función en el editor, sin bloques (puede partir de lo que armó). |

### JavaScript o Python, en cada reto

La persona elige el lenguaje **en cada reto** (con un selector arriba) y el progreso se guarda por separado. Los conceptos, los bloques y las trampas están reescritos para cada lenguaje; el enunciado y los tests son los mismos.

- **JavaScript:** corre en un Web Worker nuevo en cada ejecución.
- **Python:** corre en el navegador con [Pyodide](https://pyodide.org) (Python compilado a WebAssembly). Pesa ~13 MB la primera vez, se sirve desde tu propio S3 y queda en caché. Empieza a cargar en cuanto se elige Python.
- En Python no hay llaves: la sangría marca la estructura, así que el taller de bloques tiene menos piezas.
- En ambos casos el código corre **en el navegador de la persona**, con corte a los 2 segundos; si hay un bucle infinito, el worker se descarta y se crea uno nuevo.

El diseño es mobile first, con layout de 3 columnas en pantallas grandes (paleta · programa · guía) para proyectar. Los iconos son de [Lucide](https://lucide.dev) (ISC), incluidos en `web/icons/`.

## Hipótesis (definidas antes de ver datos)

| Métrica | Definición | Meta |
|---|---|---|
| **Activación** | % de personas que completan **Aprende** (las 3 preguntas) en al menos 1 reto | **≥ 40 %** |
| **Retención** | % de personas que vuelven otro día | **≥ 20 %** |

- Si se cumplen las dos: **PERSEVERA**.
- Si falla alguna: **PIVOTA**.
- Con menos de 10 personas: **FALTAN DATOS**.

Como señal cualitativa, después de armar un programa se pregunta *"¿Volverías mañana por un reto nuevo?"*. El embudo por reto muestra cuántos **aprendieron**, **armaron** y **escribieron**.

## Si BugDojo muere en el experimento en vivo

Úsalo como **ejemplo de pivote**. Si el motivo más votado fue *"Es caro"*, la hipótesis de precio falló, pero quizá no la del problema. El siguiente experimento cambia una sola variable: quitamos el precio y medimos si al menos lo **usan** gratis. Si tampoco hay activación ni retención, el problema no era el precio.

## Cómo funciona

```
Navegador ─► CloudFront ─┬─► S3        (landing, retos, editor, métricas)
                         └─► /api/* ─► API Gateway ─► Lambda ─► DynamoDB
```

- **El código de la persona corre en SU navegador**, en un Web Worker con un corte a los 2 segundos (para bucles infinitos). El servidor nunca ejecuta código ajeno.
- **Identidad anónima:** un `uid` aleatorio en `localStorage`. El progreso y el código también se guardan solo en el navegador.
- **Al servidor llegan solo eventos:** `visita` (deduplicada por día, hora de Bolivia), `aprendido`, `armado`, `intento`, `resuelto`, `feedback` e `inscripcion`, con el lenguaje (`js` o `py`).
- **`/metricas.html`** muestra solo totales: activación, retención, lenguaje elegido, embudo por fase y reto, y feedback.

### Retos

| # | Cinturón | Reto | Función |
|---|---|---|---|
| 1 | Blanco | Suma de pares | `sumarPares(numeros)` · `suma_pares(numeros)` |
| 2 | Amarillo | ¿Es palíndromo? | `esPalindromo(texto)` · `es_palindromo(texto)` |
| 3 | Naranja | Cuenta vocales | `contarVocales(texto)` · `contar_vocales(texto)` |
| 4 | Verde | FizzBuzz | `fizzBuzz(n)` · `fizz_buzz(n)` |
| 5 | Negro | Paréntesis balanceados | `estaBalanceado(texto)` · `esta_balanceado(texto)` |

Conceptos, bloques, guía, trampas y tests se editan en `web/retos.js` (JavaScript arriba y `PY` para Python).

## Uso

Probar en local, sin AWS:

```bash
python3 scripts/servidor_local.py
```

Abre http://localhost:8001 y, para las métricas, http://localhost:8001/metricas.html.

Desplegar en AWS (stack separado: `bugdojo-mvp`):

```bash
./scripts/deploy.sh
```

### Early access

Desde que la persona completa su primera fase aparece un aviso amarillo, **"Inscribirme al early access"**. Ahí escribe su nombre y las iniciales de su otro nombre o apellido (`Carla M.`). Si escribe un apellido entero, solo guardamos la inicial. Es una señal de compromiso más fuerte que responder "volvería".

`metricas.html` muestra solo cuántas personas se inscribieron, nunca los nombres. Para verlos:

```bash
TABLA=$(aws cloudformation describe-stacks --stack-name bugdojo-mvp --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TablaNombre'].OutputValue" --output text)
aws dynamodb scan --table-name "$TABLA" --region us-east-1 --filter-expression "sk = :s" --expression-attribute-values '{":s":{"S":"inscripcion"}}' --query "Items[].nombre.S" --output text
```

### Reiniciar datos

El botón **Reiniciar datos** de `metricas.html` borra todos los datos del servidor. Como el dashboard es público, pide una clave que el servidor comprueba. La clave es el parámetro `ClaveReinicio` (en GitHub, el secret `CLAVE_REINICIO`, de 8 caracteres como mínimo). Si no hay clave, el botón está desactivado. En el servidor local, la clave es `ensayo-local-bugdojo`.

Reiniciar no borra el progreso guardado en cada navegador. Para volver a probar como una persona nueva, abre `/?reiniciar=1`.

Eliminar todo:

```bash
./scripts/destroy.sh
```

**Costo:** el mismo stack del experimento (CloudFront, S3, Lambda y DynamoDB on-demand). Con cientos de personas sigue siendo de centavos. Python suma ~13 MB de transferencia por persona la primera vez que lo elige (la capa gratuita de CloudFront cubre 1 TB al mes).

`deploy.sh` descarga Pyodide automáticamente (`scripts/descargar_pyodide.sh`, versión 0.27.8) y lo sube con el sitio. No está en git.
