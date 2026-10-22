"""Servidor local para ensayar sin AWS: sirve web/ y simula la API en memoria.

    python3 scripts/servidor_local.py        # http://localhost:8000

Reutiliza la misma lógica de src/app.py, con una tabla falsa en memoria.
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "web")


class ErrorCondicional(Exception):
    pass


class TablaMemoria:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if Item["id"] in self.items:
            raise ErrorCondicional()
        self.items[Item["id"]] = dict(Item)

    def update_item(self, Key, UpdateExpression, ConditionExpression,
                    ExpressionAttributeNames, ExpressionAttributeValues):
        item = self.items.get(Key["id"])
        if item is None or "decision" in item:
            raise ErrorCondicional()
        item["decision"] = ExpressionAttributeValues[":d"]
        if ":m" in ExpressionAttributeValues:
            item["motivo"] = ExpressionAttributeValues[":m"]

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}


# Carga app.py con dependencias de AWS reemplazadas
tabla = TablaMemoria()
os.environ["TABLA"] = "local"
sys.modules["boto3"] = SimpleNamespace(resource=lambda _n: SimpleNamespace(Table=lambda _t: tabla))


class ClientError(Exception):
    def __init__(self, codigo):
        self.response = {"Error": {"Code": codigo}}


sys.modules["botocore"] = SimpleNamespace()
sys.modules["botocore.exceptions"] = SimpleNamespace(ClientError=ClientError)
sys.path.insert(0, os.path.join(RAIZ, "src"))
import app  # noqa: E402

_put, _update = tabla.put_item, tabla.update_item


def _envolver(fn):
    def interno(*a, **k):
        try:
            return fn(*a, **k)
        except ErrorCondicional:
            raise ClientError("ConditionalCheckFailedException") from None
    return interno


tabla.put_item, tabla.update_item = _envolver(_put), _envolver(_update)


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
    puerto = int(os.environ.get("PORT", "8000"))
    print(f"Ensayo local en http://localhost:{puerto}  (dashboard: /resultados.html)")
    ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()
