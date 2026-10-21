"""Simula participantes para ensayar. Solo usa la librería estándar.

    python3 scripts/simular.py https://xxxx.cloudfront.net 100
    python3 scripts/simular.py http://localhost:8000 100

Luego borra los datos con ./scripts/reset.sh antes de la charla.
"""
import json
import random
import string
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def post(base, ruta, cuerpo):
    req = urllib.request.Request(
        f"{base}/api/{ruta}",
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def participante(base, i):
    alias = "Sim" + "".join(random.choices(string.ascii_letters, k=6))
    tira_a = random.random() < 0.55
    respuestas = ["A" if random.random() < (0.7 if tira_a else 0.3) else "B" for _ in range(10)]
    status, data = post(base, "respuesta", {"alias": alias, "respuestas": respuestas})
    if status != 200:
        return f"respuesta {status}"
    grupo = data["grupo"]
    if random.random() < (0.4 if grupo == "A" else 0.2):
        status, _ = post(base, "decision", {"alias": alias, "decision": "si"})
    else:
        motivo = random.choice(["caro", "no_necesito", "otra_herramienta"])
        status, _ = post(base, "decision", {"alias": alias, "decision": "no", "motivo": motivo})
    return "ok" if status == 200 else f"decision {status}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    base = sys.argv[1].rstrip("/")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(lambda i: participante(base, i), range(n)))
    ok = resultados.count("ok")
    print(f"{ok}/{n} participantes simulados correctamente")
    errores = [r for r in resultados if r != "ok"]
    if errores:
        print("Errores:", {e: errores.count(e) for e in set(errores)})


if __name__ == "__main__":
    main()
