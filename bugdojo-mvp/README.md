# 🥋 BugDojo · MVP (etapa 2 del ciclo Lean)

Siguiente vuelta del ciclo **Construir → Medir → Aprender**, después del experimento en vivo.

| Etapa | Pregunta | Dónde |
|---|---|---|
| 1. Smoke test | ¿Les interesa lo suficiente? | `../` (experimento en vivo, en la charla) |
| **2. MVP funcional** | **¿Lo usan de verdad y vuelven?** | **esta carpeta, después de la charla** |

**No hay venta:** sin precios, sin correos, sin cuentas y sin pagos. Solo una prueba gratuita con 5 retos reales de JavaScript (del cinturón blanco al negro) y medición de uso **anónimo**.

## Hipótesis (definidas antes de ver datos)

| Métrica | Definición | Meta |
|---|---|---|
| **Activación** | % de personas que resuelven al menos 1 reto | **≥ 40 %** |
| **Retención** | % de personas que vuelven otro día | **≥ 20 %** |

- Si se cumplen las dos: **PERSEVERA**.
- Si falla alguna: **PIVOTA**.
- Con menos de 10 personas: **FALTAN DATOS**.

Como señal cualitativa, después de resolver un reto se pregunta *"¿Volverías mañana por un reto nuevo?"*.

## Si BugDojo muere en el experimento en vivo

Úsalo como **ejemplo de pivote**. Si el motivo más votado fue *"Es caro"*, la hipótesis de precio falló, pero quizá no la del problema. El siguiente experimento cambia una sola variable: quitamos el precio y medimos si al menos lo **usan** gratis. Si tampoco hay activación ni retención, el problema no era el precio.

## Cómo funciona

```
Navegador ─► CloudFront ─┬─► S3        (landing, retos, editor, métricas)
                         └─► /api/* ─► API Gateway ─► Lambda ─► DynamoDB
```

- **El código de la persona corre en SU navegador**, en un Web Worker con un corte a los 2 segundos (para bucles infinitos). El servidor nunca ejecuta código ajeno.
- **Identidad anónima:** un `uid` aleatorio en `localStorage`. El progreso y el código también se guardan solo en el navegador.
- **Al servidor llegan solo eventos:** `visita` (deduplicada por día, hora de Bolivia), `intento`, `resuelto` y `feedback`.
- **`/metricas.html`** muestra solo totales: activación, retención, embudo por reto y feedback.

### Retos

| # | Cinturón | Reto | Función |
|---|---|---|---|
| 1 | Blanco | Suma de pares | `sumarPares(numeros)` |
| 2 | Amarillo | ¿Es palíndromo? | `esPalindromo(texto)` |
| 3 | Naranja | Cuenta vocales | `contarVocales(texto)` |
| 4 | Verde | FizzBuzz | `fizzBuzz(n)` |
| 5 | Negro | Paréntesis balanceados | `estaBalanceado(texto)` |

Se editan en `web/retos.js`.

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

Eliminar todo:

```bash
./scripts/destroy.sh
```

**Costo:** el mismo stack del experimento (CloudFront, S3, Lambda y DynamoDB on-demand). Con cientos de personas sigue siendo de centavos.
