# Plan por sprints · experimento-lean-aws

Objetivo: pasar de "demo de charla" a un proyecto de referencia de **Lean Startup en AWS**, sin romper la tesis de **menos de $10 al mes**.

Reglas para todos los sprints:
- **Un sprint = un PR** pequeño y revisable, con CI en verde (desde el Sprint 2).
- Ningún cambio agrega costo fijo mensual. Si algo cuesta, se discute antes (ejemplo: WAF, ~$6/mes, queda fuera).
- Los dos servidores locales (`scripts/servidor_local.py` y `bugdojo-mvp/scripts/servidor_local.py`) tienen que seguir funcionando sin AWS.
- No se inventan resultados, costos ni capturas en los docs: solo datos reales.

| Sprint | Tema | Resultado visible |
|---|---|---|
| 1 | Cimientos: bug + tests + lint | `make test` en verde y cobertura de la lógica de ambas APIs |
| 2 | CI/CD con GitHub Actions + OIDC | Cada PR se valida solo y el deploy sale de GitHub, sin access keys |
| 3 | Seguridad y privacidad | Headers seguros, mínimo privilegio, TTL de datos |
| 4 | Observabilidad | Alarmas por correo si algo falla en vivo |
| 5 | Escala del dashboard | Lecturas en O(1) y prueba de carga con 500 participantes |
| 6 | Rigor estadístico | Intervalos de confianza y cohortes D1/D7 en los dashboards |
| 7 | Menos duplicación | Infra compartida y una sola fuente para los retos |
| 8 | Pyodide pro | Corte de bucles infinitos sin recargar 13 MB, y caché inmutable |
| 9 | Etapa 3 Lean: ¿pagarían? | Fake door de plan pago con regla de muerte predefinida |
| 10 | Docs y charla | README de referencia, diagramas, ADRs y costos reales |

Orden sugerido: 1 → 2 son la base (todo lo demás se apoya en tests + CI). Después vienen 3 y 4 si hay una charla en vivo pronto, o 5 y 6 si la prioridad es el contenido. Del 7 al 10 el orden es flexible.

---

## Sprint 1 · Cimientos: bug + tests + lint

**Objetivo:** que cada cambio futuro sea seguro de hacer.

Tareas:
- **Bug:** las dos APIs devuelven 500 si el body es un JSON válido que no es un objeto (por ejemplo `[1]` o `"hola"`). Validar `isinstance(cuerpo, dict)` y responder `400 json_invalido`.
- Extraer la tabla DynamoDB falsa de los `servidor_local.py` a un módulo compartido de tests (sin agregar dependencias pesadas; `moto` es opcional).
- Tests con `pytest`:
  - Experimento: `calcular_grupo` (6-4, 4-6, empate 5-5), alias válidos e inválidos, un voto por alias (409), decisión sin respuesta previa, motivo obligatorio al decir "no", veredictos con el mínimo de 5 y el umbral de 30 %.
  - MVP: validación de `uid`, `reto` y `lang`, deduplicación de visitas por día (hora de Bolivia), activación, retención, `persevera` / `pivota` / `faltan_datos`, y datos antiguos sin lenguaje.
- `pyproject.toml` con configuración de `ruff` (y corregir los 3 avisos actuales) + `requirements-dev.txt`.
- `Makefile` con `make test`, `make lint`, `make local` y `make local-mvp`.

**Hecho cuando:** `make lint test` pasa y los tests cubren todas las rutas de ambas APIs.
**Necesito de ti:** nada.

Decisión que tomamos al implementarlo: los tests usan **moto** en lugar de la tabla
falsa de `scripts/servidor_local.py`, porque moto valida de verdad las
`ConditionExpression` y `UpdateExpression` de DynamoDB (un voto por alias, una sola
decisión, visitas deduplicadas). La tabla falsa de los servidores locales sigue sin
tests: solo existe para el ensayo local.

## Sprint 2 · CI/CD con GitHub Actions + OIDC

**Objetivo:** validación automática en cada PR y deploy sin credenciales guardadas (es una gran historia para contar en una charla de AWS).

Tareas:
- Workflow `ci.yml` en cada PR: `ruff`, `pytest`, `cfn-lint` y `sam validate` sobre los dos templates.
- Template `infra/github-oidc.yaml`: proveedor OIDC de GitHub + rol IAM limitado a este repo y a la rama `main` (o a un environment).
- Workflow `deploy.yml` manual (`workflow_dispatch`) que elige qué stack desplegar (`experimento-lean` o `bugdojo-mvp`) y usa un environment de GitHub con aprobación.
- Badges de CI en el README.

**Hecho cuando:** un PR muestra los checks en verde y un deploy de prueba funciona desde Actions.
**Necesito de ti:** desplegar una vez `infra/github-oidc.yaml` en tu cuenta (te dejo el comando) y guardar el ARN del rol como variable del repo.

## Sprint 3 · Seguridad y privacidad

**Objetivo:** buenas prácticas sin salir de los $10.

Tareas:
- CloudFront: response headers policy administrada (HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`), que es gratis, más una CSP básica para las páginas.
- IAM de mínimo privilegio: cambiar `DynamoDBCrudPolicy` por una política propia (`PutItem`, `UpdateItem`, `Scan` y `GetItem` según cada stack), sin `DeleteItem`.
- DynamoDB TTL: los eventos del MVP y las respuestas del experimento se borran solos (por ejemplo a los 90 días, configurable).
- Límite de tamaño del body en la API (rechazar más de unos pocos KB).
- Opcional, a decidir: `/api/respuesta` devuelve un token y `/api/decision` lo exige, para que nadie pueda decidir por el alias de otra persona.
- `reset.sh` con `batch-write-item` en lugar de un delete por ítem.
- Documentar el trade-off de WAF (por qué no lo usamos).

**Hecho cuando:** `curl -I` muestra los headers, `cfn-lint` sigue limpio y los tests cubren el límite de tamaño y el token (si se aprueba).
**Necesito de ti:** decidir el token de decisión (sí/no) y los días de TTL.

## Sprint 4 · Observabilidad

**Objetivo:** enterarnos de un problema antes que el público.

Tareas:
- Logs estructurados en JSON desde Lambda (ruta, status, latencia, sin alias ni uid).
- Alarmas de CloudWatch (dentro de las 10 gratis): errores de Lambda, 5xx de la API y throttling. Notificación por SNS al mismo `AlertEmail`.
- Un dashboard de CloudWatch pequeño (o una sección en el README con las consultas de Logs Insights).
- Probar las alarmas forzando un error en un entorno de prueba.

**Hecho cuando:** llega un correo de alarma al forzar un error.
**Necesito de ti:** confirmar el correo para SNS (AWS manda un mail de confirmación).

## Sprint 5 · Escala del dashboard

**Objetivo:** que el costo y la latencia no crezcan con cada pestaña abierta.

Hoy `/api/resultados` y `/api/metricas` escanean toda la tabla en cada refresco (cada 3 y 5 s, por pestaña).

Tareas:
- Experimento: contadores atómicos (`ADD`) en un ítem `totales` al registrar respuestas y decisiones, y `GetItem` para leer. Las escrituras siguen siendo condicionales (un voto por alias) dentro de una transacción.
- MVP: igual para los totales simples. Las métricas por usuario (retención) se calculan con caché.
- Microcaché de 2 a 3 s en CloudFront solo para las rutas de lectura (cache policy propia).
- `bugdojo-mvp/scripts/simular.py`, que hoy no existe (solo el experimento tiene simulador).
- Prueba de carga con 500 participantes simulados. Documentamos los resultados reales, sin inventar números.

**Hecho cuando:** el dashboard hace 1 lectura por refresco, los totales coinciden con un scan de control y la prueba de carga queda documentada.
**Necesito de ti:** nada (la prueba de carga corre contra un stack de prueba en tu cuenta, si me das acceso, o la corres tú con el script).

## Sprint 6 · Rigor estadístico (el corazón Lean)

**Objetivo:** que los veredictos enseñen a no engañarse con muestras chicas.

Tareas:
- Experimento: intervalo de **Wilson** al 95 % para la conversión de cada producto. Veredictos nuevos:
  - `vive` → el límite inferior es ≥ 30 %
  - `muere` → el límite superior es < 30 %
  - `incierto` → el intervalo cruza el 30 % (y "faltan datos" sigue existiendo)
- Dashboard: barra con el intervalo dibujado y la línea del 30 %. El modo `?demo` también lo muestra.
- MVP: retención por cohortes **D1 y D7** (según el primer día de visita) en lugar de "volvió algún otro día". El veredicto `persevera` / `pivota` usa intervalos.
- Nota en el README: por qué los grupos A/B no son comparables entre sí (se segmentan por el cuestionario, no por azar).
- Tests de las funciones estadísticas con valores conocidos.

**Hecho cuando:** los dashboards muestran intervalos y los tests validan Wilson con casos de referencia.
**Necesito de ti:** validar los nombres y textos de los nuevos veredictos para la charla.

## Sprint 7 · Menos duplicación

**Objetivo:** mantener un solo lugar para cada cosa.

Tareas:
- Extraer "sitio estático + API + presupuesto" a un template compartido (`AWS::Serverless::Application` o nested stack). Cada stack solo declara su tabla y sus rutas.
- Un solo `deploy.sh` / `destroy.sh` parametrizado por stack.
- Una sola fuente para los retos: un `retos.json` con ids, del que lee el frontend, y una variable de entorno en Lambda generada desde el template.
- Verificar que el deploy produce los mismos recursos (diff del changeset).

**Hecho cuando:** los dos stacks se despliegan desde el template común y el changeset no recrea recursos con datos.
**Necesito de ti:** nada, pero conviene hacerlo **después** de la charla (toca la infra).

## Sprint 8 · Pyodide pro

**Objetivo:** mejor experiencia en Python.

Tareas:
- Headers COOP/COEP en CloudFront (solo para el MVP) para habilitar `SharedArrayBuffer`.
- `pyodide.setInterruptBuffer` para cortar bucles infinitos con `KeyboardInterrupt` sin destruir el worker, y fallback al comportamiento actual si el navegador no lo soporta.
- `Cache-Control: public, max-age=31536000, immutable` para `pyodide/` en el `s3 sync`, y caché corta para el HTML.
- Precarga opcional de Pyodide al entrar a la lista de retos.

**Hecho cuando:** un `while True: pass` se corta en unos 2 s y el siguiente intento corre sin recargar Pyodide.
**Necesito de ti:** nada.

## Sprint 9 · Etapa 3 Lean: ¿pagarían?

**Objetivo:** cerrar el ciclo smoke test → MVP → disposición a pagar.

Tareas:
- Definir **antes** la hipótesis y la regla de muerte (por ejemplo: "X % de quienes se activan hacen clic en el plan pago").
- Fake door de un "BugDojo Pro" que se muestra solo a quienes completaron N retos. Botón de reservar y página de "era un experimento". Opcional: Stripe Payment Link en modo test.
- Nuevos eventos y su embudo en `/metricas.html`, con el veredicto de la etapa 3.
- Mantener el anonimato: sin correos, salvo que lo decidamos explícitamente.

**Hecho cuando:** el embudo de pago aparece en las métricas con su veredicto predefinido.
**Necesito de ti:** el precio, la regla de muerte y si queremos Stripe en modo test o solo fake door.

## Sprint 10 · Docs y charla

**Objetivo:** que cualquiera pueda replicar el proyecto y aprender de él.

Tareas:
- README de referencia: diagrama (Mermaid), flujo Construir → Medir → Aprender con las 3 etapas, y cómo replicar en 15 minutos.
- ADRs cortos: por qué SAM, por qué sin dominio propio, por qué no WAF, por qué el código corre en el navegador, por qué Wilson.
- Tabla de costos **reales** (desde Cost Explorer, después de un evento), sin estimaciones inventadas.
- `CONTRIBUTING.md` y plantilla de PR.

**Hecho cuando:** una persona nueva puede desplegar y entender el proyecto solo con el README.
**Necesito de ti:** los costos reales y las lecciones de la charla (no los invento).
