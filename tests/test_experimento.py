"""Tests de la API del experimento en vivo (src/app.py)."""
import pytest
from botocore.exceptions import ClientError
from conftest import llamar, tabla_con_paginas

A6 = ["A"] * 6 + ["B"] * 4
B6 = ["B"] * 6 + ["A"] * 4


def responder(app, alias, respuestas=A6):
    return llamar(app, "POST /api/respuesta", {"alias": alias, "respuestas": respuestas})


def decidir(app, alias, decision, motivo=None):
    cuerpo = {"alias": alias, "decision": decision}
    if motivo:
        cuerpo["motivo"] = motivo
    return llamar(app, "POST /api/decision", cuerpo)


def resultados(app):
    status, datos = llamar(app, "GET /api/resultados")
    assert status == 200
    return datos


# ---------- calcular_grupo ----------

@pytest.mark.parametrize("respuestas, grupo", [
    (["A"] * 10, "A"),
    (["A"] * 6 + ["B"] * 4, "A"),
    (["B"] * 6 + ["A"] * 4, "B"),
    (["B"] * 10, "B"),
    (["A"] * 5 + ["B"] * 5, "A"),   # empate: desempata la pregunta 1
    (["B"] * 5 + ["A"] * 5, "B"),
])
def test_calcular_grupo(experimento, respuestas, grupo):
    assert experimento.calcular_grupo(respuestas) == grupo


# ---------- POST /api/respuesta ----------

def test_respuesta_valida_devuelve_grupo(experimento):
    assert responder(experimento, "Carla") == (200, {"grupo": "A"})


@pytest.mark.parametrize("alias", ["", "ab", "a" * 26, "Carla1", "Carla M", "carla_f", 123, None])
def test_alias_invalido(experimento, alias):
    assert responder(experimento, alias) == (400, {"error": "alias_invalido"})


def test_alias_acepta_tildes_y_enie(experimento):
    assert responder(experimento, "Ñandúíéá")[0] == 200


@pytest.mark.parametrize("respuestas", [
    None, "AAAAAABBBB", ["A"] * 9, ["A"] * 11, ["A"] * 9 + ["C"], ["a"] * 10,
])
def test_respuestas_invalidas(experimento, respuestas):
    assert responder(experimento, "Carla", respuestas) == (400, {"error": "respuestas_invalidas"})


def test_un_voto_por_alias_sin_importar_mayusculas(experimento):
    assert responder(experimento, "Carla")[0] == 200
    assert responder(experimento, "CARLA") == (409, {"error": "alias_repetido"})
    assert resultados(experimento)["total"] == 1


# ---------- POST /api/decision ----------

def test_decision_si(experimento):
    responder(experimento, "Carla")
    assert decidir(experimento, "carla", "si") == (200, {"ok": True})


def test_decision_no_exige_motivo_valido(experimento):
    responder(experimento, "Carla")
    assert decidir(experimento, "Carla", "no") == (400, {"error": "motivo_invalido"})
    assert decidir(experimento, "Carla", "no", "otro") == (400, {"error": "motivo_invalido"})
    assert decidir(experimento, "Carla", "no", "caro") == (200, {"ok": True})


@pytest.mark.parametrize("alias, decision", [("Carla", "tal_vez"), ("Carla", None), ("x", "si")])
def test_decision_datos_invalidos(experimento, alias, decision):
    assert decidir(experimento, alias, decision) == (400, {"error": "datos_invalidos"})


def test_decision_sin_respuesta_previa(experimento):
    assert decidir(experimento, "Nadie", "si") == (409, {"error": "ya_decidido_o_sin_respuesta"})


def test_solo_se_decide_una_vez(experimento):
    responder(experimento, "Carla")
    assert decidir(experimento, "Carla", "si")[0] == 200
    assert decidir(experimento, "Carla", "no", "caro") == (409, {"error": "ya_decidido_o_sin_respuesta"})


# ---------- GET /api/resultados ----------

def test_resultados_vacios(experimento):
    datos = resultados(experimento)
    assert datos["total"] == 0
    assert datos["umbral"] == 0.30
    for g in ("A", "B"):
        assert datos["grupos"][g]["participantes"] == 0
        assert datos["grupos"][g]["veredicto"] == "faltan_datos"


def test_resultados_no_exponen_alias(experimento):
    responder(experimento, "Secreto")
    assert "secreto" not in str(resultados(experimento)).lower()


def poblar(app, grupo, si, no):
    respuestas = A6 if grupo == "A" else B6
    for i in range(si + no):
        alias = f"{grupo}persona" + "abcdefghijklmnopqrst"[i]
        responder(app, alias, respuestas)
        if i < si:
            decidir(app, alias, "si")
        else:
            decidir(app, alias, "no", "caro")


@pytest.mark.parametrize("si, no, veredicto", [
    (1, 3, "faltan_datos"),   # 4 participantes: menos que el mínimo (5)
    (3, 7, "vive"),           # 30 % exacto: vive
    (2, 8, "muere"),          # 20 %
    (5, 0, "vive"),
])
def test_veredicto(experimento, si, no, veredicto):
    poblar(experimento, "A", si, no)
    grupo = resultados(experimento)["grupos"]["A"]
    assert grupo["participantes"] == si + no
    assert grupo["si"] == si
    assert grupo["no"] == no
    assert grupo["veredicto"] == veredicto


def test_motivos_y_participantes_sin_decision(experimento):
    poblar(experimento, "B", 1, 2)
    responder(experimento, "Indecisa", B6)
    grupo = resultados(experimento)["grupos"]["B"]
    assert grupo["participantes"] == 4
    assert grupo["conversion"] == 0.25
    assert grupo["motivos"] == {"caro": 2, "no_necesito": 0, "otra_herramienta": 0}


# ---------- handler ----------

@pytest.mark.parametrize("crudo", ["{no es json", "[1]", '"hola"', "42", "null"])
def test_body_que_no_es_objeto_json(experimento, crudo):
    status, datos = llamar(experimento, "POST /api/respuesta", crudo=crudo)
    assert (status, datos) == (400, {"error": "json_invalido"})
    status, datos = llamar(experimento, "POST /api/decision", crudo=crudo)
    assert (status, datos) == (400, {"error": "json_invalido"})


def test_ruta_desconocida(experimento):
    assert llamar(experimento, "GET /api/otra") == (404, {"error": "no_encontrado"})


def test_respuestas_no_se_cachean(experimento):
    res = experimento.handler({"routeKey": "GET /api/resultados"}, None)
    assert res["headers"]["Cache-Control"] == "no-store"

# ---------- paginación del scan y errores inesperados ----------

def test_resultados_recorre_todas_las_paginas(experimento, monkeypatch):
    for alias in ("ana", "beto", "carla", "dora"):
        responder(experimento, alias, A6)
    for alias in ("emma", "fede", "gabi"):
        responder(experimento, alias, B6)
    decidir(experimento, "ana", "si")
    monkeypatch.setattr(experimento, "tabla", tabla_con_paginas(experimento.tabla))
    datos = resultados(experimento)
    assert datos["total"] == 7
    assert datos["grupos"]["A"]["participantes"] == 4
    assert datos["grupos"]["A"]["si"] == 1
    assert datos["grupos"]["B"]["participantes"] == 3


def _error_de_aws():
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "Operacion"
    )


def test_error_inesperado_al_guardar_respuesta(experimento, monkeypatch):
    def falla(**kwargs):
        raise _error_de_aws()
    monkeypatch.setattr(experimento.tabla, "put_item", falla)
    with pytest.raises(ClientError):
        responder(experimento, "carla")


def test_error_inesperado_al_guardar_decision(experimento, monkeypatch):
    responder(experimento, "carla")
    def falla(**kwargs):
        raise _error_de_aws()
    monkeypatch.setattr(experimento.tabla, "update_item", falla)
    with pytest.raises(ClientError):
        decidir(experimento, "carla", "si")
