"""Servidor local del MVP para probar sin AWS: sirve web/ y simula la API en memoria.

    python3 bugdojo-mvp/scripts/servidor_local.py     # http://localhost:8001

Reutiliza src/app.py con una tabla falsa (clave uid + sk).
"""
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "web")


class TablaMemoria:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item["uid"], Item["sk"])] = dict(Item)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        item = self.items.setdefault((Key["uid"], Key["sk"]), dict(Key))
        for nombre, valor in re.findall(r"ADD (#\w+) (:\w+)", UpdateExpression):
            campo = ExpressionAttributeNames[nombre]
            item[campo] = item.get(campo, 0) + ExpressionAttributeValues[valor]
        for nombre, valor in re.findall(r"SET (#\w+) = (:\w+)", UpdateExpression):
            item[ExpressionAttributeNames[nombre]] = ExpressionAttributeValues[valor]

    def delete_item(self, Key):
        self.items.pop((Key["uid"], Key["sk"]), None)

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}


tabla = TablaMemoria()
os.environ["TABLA"] = "local"
os.environ.setdefault("CLAVE_REINICIO", "ensayo-local-bugdojo")
sys.modules["boto3"] = SimpleNamespace(resource=lambda _n: SimpleNamespace(Table=lambda _t: tabla))
sys.path.insert(0, os.path.join(RAIZ, "src"))
import app  # noqa: E402


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def _api(self, metodo):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo).decode() if largo else None
        ruta = self.path.split("?")[0]
        res = app.handler({"routeKey": f"{metodo} {ruta}", "body": cuerpo}, None)
        datos = res["body"].encode()
        self.send_response(res["statusCode"])
        for k, v in res["headers"].items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api("POST")
        self.send_error(404)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", "8001"))
    print(f"MVP BugDojo local en http://localhost:{puerto}  (métricas: /metricas.html)")
    print(f"Clave de \"Reiniciar datos\": {os.environ['CLAVE_REINICIO']}")
    ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()
