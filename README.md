# ¿Qué producto vive? · Experimento Lean en vivo

Demo de la charla **Startup Lean en AWS: construye, valida y escala con menos de $10 al mes**
(AWS Student Community Day 2026, Santa Cruz).

La audiencia escanea un QR, crea un alias (`CarlaMFR`), responde 10 preguntas y cae en uno de dos productos:

| | Producto | Hipótesis |
|---|---|---|
| **A** | 🥋 **BugDojo**, retos de lógica de programación | Quienes programan seguido pagarían $5/mes por practicar lógica |
| **B** | 🦖 **Focusaurio**, app de productividad | Quienes no terminan lo que empiezan pagarían $5/mes por organizarse |

Cada landing es un **smoke test**: botón "Reservar acceso por $5/mes" o "No por ahora" (con motivo). No se cobra nada.

**Regla de muerte, dicha antes de empezar:** un producto **vive** si al menos el **30 %** de su grupo reserva. Si ninguno llega, mueren los dos.

> **Siguiente vuelta del ciclo:** [`bugdojo-mvp/`](bugdojo-mvp/README.md) es el MVP funcional de BugDojo (etapa 2): una prueba gratuita con retos reales, sin venta, que mide activación y retención. Se comparte **después** de la charla.

## Arquitectura

```
Celular ─┐
         ├─► CloudFront ─┬─► S3        (formulario, 2 landings, gracias, dashboard)
Pantalla ┘               └─► /api/* ─► API Gateway (HTTP) ─► Lambda (Python) ─► DynamoDB
```

- **Costo esperado** con 100 personas: centavos (casi todo dentro de la capa gratuita).
- **Sin dominio propio**: el QR esconde la URL de CloudFront, y eso nos mantiene bajo $10.

### Guardarraíles
- Un voto por alias: escritura condicional en DynamoDB.
- Alias de solo letras (3-25). Sin correo, sin teléfono.
- Límite de peticiones en la API (25 por segundo, ráfagas de 50).
- El dashboard solo recibe totales: ningún alias sale de la base.
- Logs con retención de 7 días y alerta de presupuesto opcional ($5 y $10).
- `destroy.sh` borra todo al terminar.

## Estructura

```
template.yaml            Infraestructura (AWS SAM)
src/app.py               API: respuesta, decisión, resultados
web/                     Sitio estático (HTML/CSS/JS sin frameworks)
  index.html             Alias + 10 preguntas
  bugdojo.html           Landing A
  focusaurio.html        Landing B
  gracias.html           "Era un experimento, no se cobró nada"
  resultados.html        Dashboard en vivo (?demo = modo sin internet)
tests/                   Tests de ambas APIs (pytest + DynamoDB simulado con moto)
docs/PLAN_SPRINTS.md     Plan de mejoras por sprints
scripts/
  deploy.sh              Despliega y sube el sitio
  reset.sh               Borra todas las respuestas
  simular.py             Simula N participantes
  servidor_local.py      Ensayo local sin AWS
  destroy.sh             Elimina todo
```

## Uso

Ensayo local, sin AWS:

```bash
python3 scripts/servidor_local.py
```

Abre http://localhost:8000 (formulario) y http://localhost:8000/resultados.html (dashboard).

Tests y lint (cubren las APIs del experimento y del MVP, sin tocar AWS):

```bash
make install   # crea .venv e instala requirements-dev.txt
make test      # pytest
make lint      # ruff
```

`make local` y `make local-mvp` levantan los dos servidores de ensayo.

Desplegar en AWS (la alerta de presupuesto es opcional):

```bash
ALERT_EMAIL=tu@correo.com ./scripts/deploy.sh
```

Probar con 100 personas simuladas y luego limpiar:

```bash
python3 scripts/simular.py https://TU-DISTRIBUCION.cloudfront.net 100
./scripts/reset.sh
```

Después de la charla:

```bash
./scripts/destroy.sh
```

## Checklist del día del evento

- [ ] Una semana antes: desplegar, simular 100 personas y revisar el dashboard en el proyector.
- [ ] Ejecutar `reset.sh` y abrir el formulario desde 2-3 celulares reales.
- [ ] El QR del slide 9 apunta a la URL de CloudFront.
- [ ] Avisar a la organización que el QR es de un experimento, sin venta.
- [ ] Grabar un video corto del flujo como respaldo.
- [ ] En el evento: dashboard abierto en otra pestaña. Si falla el wifi, usar `resultados.html?demo`.
- [ ] Decir las hipótesis y la regla del 30 % **antes** de que escaneen.
- [ ] Al terminar: `destroy.sh`.

> Para volver a responder desde el mismo celular durante los ensayos: `https://…/?reiniciar=1`.
