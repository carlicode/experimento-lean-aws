"""Tests de la API del MVP de BugDojo (bugdojo-mvp/src/app.py)."""
import uuid
from datetime import UTC, datetime

import pytest
from conftest import llamar, tabla_con_paginas


def nuevo_uid():
    return str(uuid.uuid4())


def evento(app, uid, tipo, **extra):
    return llamar(app, "POST /api/evento", {"uid": uid, "tipo": tipo, **extra})


def metricas(app):
    status, datos = llamar(app, "GET /api/metricas")
    assert status == 200
    return datos


def visitar(app, monkeypatch, uid, dia):
    monkeypatch.setattr(app, "hoy", lambda: dia)
    assert evento(app, uid, "visita") == (200, {"ok": True})


# ---------- POST /api/evento: validación ----------

@pytest.mark.parametrize("uid", ["", "abc", "123", nuevo_uid().upper(), None])
def test_uid_invalido(mvp, uid):
    assert evento(mvp, uid, "visita") == (400, {"error": "uid_invalido"})


@pytest.mark.parametrize("tipo", ["armado", "aprendido", "resuelto", "intento"])
@pytest.mark.parametrize("reto", ["0", "6", "", None, "1#py"])
def test_reto_invalido(mvp, tipo, reto):
    assert evento(mvp, nuevo_uid(), tipo, reto=reto) == (400, {"error": "reto_invalido"})


def test_reto_numerico_se_acepta(mvp):
    assert evento(mvp, nuevo_uid(), "armado", reto=3) == (200, {"ok": True})


@pytest.mark.parametrize("lang", ["python", "JS", "", None])
def test_lenguaje_invalido(mvp, lang):
    assert evento(mvp, nuevo_uid(), "armado", reto="1", lang=lang) == (400, {"error": "lenguaje_invalido"})


@pytest.mark.parametrize("tipo", ["otro", "", None, "visitas"])
def test_tipo_invalido(mvp, tipo):
    assert evento(mvp, nuevo_uid(), tipo) == (400, {"error": "tipo_invalido"})


@pytest.mark.parametrize("valor", ["tal_vez", None, True])
def test_feedback_invalido(mvp, valor):
    assert evento(mvp, nuevo_uid(), "feedback", valor=valor) == (400, {"error": "valor_invalido"})


# ---------- visitas, activación y retención ----------

def test_visitas_se_deduplican_por_dia(mvp, monkeypatch):
    uid = nuevo_uid()
    visitar(mvp, monkeypatch, uid, "2026-10-21")
    visitar(mvp, monkeypatch, uid, "2026-10-21")
    datos = metricas(mvp)
    assert datos["usuarios"] == 1
    assert datos["retenidos"] == 0


def test_volver_otro_dia_cuenta_como_retencion(mvp, monkeypatch):
    uid = nuevo_uid()
    visitar(mvp, monkeypatch, uid, "2026-10-21")
    visitar(mvp, monkeypatch, uid, "2026-10-22")
    datos = metricas(mvp)
    assert datos["retenidos"] == 1
    assert datos["retencion"] == 1.0


def test_hoy_usa_hora_de_bolivia(mvp, monkeypatch):
    # 02:00 UTC del 22 son las 22:00 del 21 en Bolivia (UTC-4)
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 22, 2, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(mvp, "datetime", Reloj)
    assert mvp.hoy() == "2026-10-21"


def test_activacion_cuenta_cualquier_fase_completada(mvp, monkeypatch):
    solo_aprende, arma, escribe, solo_visita = nuevo_uid(), nuevo_uid(), nuevo_uid(), nuevo_uid()
    evento(mvp, solo_aprende, "aprendido", reto="1")
    evento(mvp, arma, "armado", reto="1")
    evento(mvp, escribe, "resuelto", reto="2", lang="py")
    visitar(mvp, monkeypatch, solo_visita, "2026-10-24")
    datos = metricas(mvp)
    assert datos["usuarios"] == 4
    assert datos["activados"] == 3
    assert datos["lenguajes"]["js"]["armaron"] == 1
    assert datos["lenguajes"]["py"]["armaron"] == 1


def test_intentos_no_cuentan_como_fase(mvp):
    uid = nuevo_uid()
    for _ in range(3):
        assert evento(mvp, uid, "intento", reto="4") == (200, {"ok": True})
    datos = metricas(mvp)
    assert datos["activados"] == 0
    assert datos["por_reto"]["4"] == {"aprendieron": 0, "armaron": 0, "escribieron": 0}


def test_embudo_por_reto_y_lenguaje_usa_usuarios_unicos(mvp):
    uid = nuevo_uid()
    for lang in ("js", "py"):
        evento(mvp, uid, "aprendido", reto="1", lang=lang)
        evento(mvp, uid, "armado", reto="1", lang=lang)
    evento(mvp, uid, "armado", reto="1", lang="js")  # repetido
    datos = metricas(mvp)
    assert datos["por_reto"]["1"] == {"aprendieron": 1, "armaron": 1, "escribieron": 0}
    assert datos["lenguajes"] == {"js": {"usuarios": 1, "armaron": 1}, "py": {"usuarios": 1, "armaron": 1}}


def test_lenguaje_por_defecto_es_js(mvp):
    evento(mvp, nuevo_uid(), "armado", reto="2")
    assert metricas(mvp)["lenguajes"]["js"]["armaron"] == 1


def test_datos_antiguos_sin_lenguaje_cuentan_como_js(mvp):
    mvp.tabla.put_item(Item={"uid": nuevo_uid(), "sk": "reto#3", "armado": True})
    datos = metricas(mvp)
    assert datos["lenguajes"]["js"]["armaron"] == 1
    assert datos["por_reto"]["3"]["armaron"] == 1


def test_feedback_se_guarda_una_vez_por_usuario(mvp):
    uid = nuevo_uid()
    evento(mvp, uid, "feedback", valor="no")
    evento(mvp, uid, "feedback", valor="si")  # reemplaza la anterior
    evento(mvp, nuevo_uid(), "feedback", valor="si")
    assert metricas(mvp)["feedback"] == {"si": 2, "no": 0}


# ---------- decisión: persevera / pivota ----------

def poblar(app, monkeypatch, usuarios, activados, retenidos):
    for i in range(usuarios):
        uid = nuevo_uid()
        visitar(app, monkeypatch, uid, "2026-10-21")
        if i < activados:
            evento(app, uid, "armado", reto="1")
        if i < retenidos:
            visitar(app, monkeypatch, uid, "2026-10-23")


@pytest.mark.parametrize("usuarios, activados, retenidos, decision", [
    (9, 9, 9, "faltan_datos"),   # menos que el mínimo (10)
    (10, 4, 2, "persevera"),     # 40 % y 20 % exactos
    (10, 3, 5, "pivota"),        # no llega a la activación
    (10, 8, 1, "pivota"),        # no llega a la retención
])
def test_decision(mvp, monkeypatch, usuarios, activados, retenidos, decision):
    poblar(mvp, monkeypatch, usuarios, activados, retenidos)
    datos = metricas(mvp)
    assert datos["usuarios"] == usuarios
    assert datos["activados"] == activados
    assert datos["retenidos"] == retenidos
    assert datos["decision"] == decision


def test_metricas_vacias(mvp):
    datos = metricas(mvp)
    assert datos["usuarios"] == 0
    assert datos["activacion"] == 0
    assert datos["decision"] == "faltan_datos"


# ---------- handler ----------

@pytest.mark.parametrize("crudo", ["{no es json", "[1]", '"hola"', "42", "null"])
def test_body_que_no_es_objeto_json(mvp, crudo):
    assert llamar(mvp, "POST /api/evento", crudo=crudo) == (400, {"error": "json_invalido"})


def test_ruta_desconocida(mvp):
    assert llamar(mvp, "POST /api/otra", {}) == (404, {"error": "no_encontrado"})

# ---------- paginación del scan ----------

def test_metricas_recorre_todas_las_paginas(mvp, monkeypatch):
    uids = [nuevo_uid() for _ in range(5)]
    for uid in uids:
        visitar(mvp, monkeypatch, uid, "2026-10-22")
    evento(mvp, uids[0], "armado", reto="1")
    monkeypatch.setattr(mvp, "tabla", tabla_con_paginas(mvp.tabla))
    datos = metricas(mvp)
    assert datos["usuarios"] == 5
    assert datos["activados"] == 1


# ---------- early access ----------

@pytest.mark.parametrize("nombre", ["Carla M.", "Carla M. F.", "josé r", "  Carla   M.  ", "Ñusta Q. P. R."])
def test_inscripcion_valida(mvp, nombre):
    assert evento(mvp, nuevo_uid(), "inscripcion", nombre=nombre) == (200, {"ok": True})
    assert metricas(mvp)["inscritos"] == 1


@pytest.mark.parametrize("nombre", ["", "Carla", "Carla Marquez", "C M.", "Carla M. F. G. H.",
                                    "carla@correo.com M.", "Carla 1.", None, 42])
def test_inscripcion_invalida(mvp, nombre):
    assert evento(mvp, nuevo_uid(), "inscripcion", nombre=nombre) == (400, {"error": "nombre_invalido"})


def test_inscripcion_una_vez_por_usuario(mvp, monkeypatch):
    uid = nuevo_uid()
    visitar(mvp, monkeypatch, uid, "2026-10-24")
    visitar(mvp, monkeypatch, nuevo_uid(), "2026-10-24")
    evento(mvp, uid, "inscripcion", nombre="Carla M.")
    evento(mvp, uid, "inscripcion", nombre="Carla M. F.")  # reemplaza la anterior
    datos = metricas(mvp)
    assert datos["inscritos"] == 1
    assert datos["inscripcion"] == 0.5


def test_metricas_no_devuelven_nombres(mvp):
    evento(mvp, nuevo_uid(), "inscripcion", nombre="Carla M.")
    _, cuerpo = llamar(mvp, "GET /api/metricas")
    assert "Carla" not in str(cuerpo)


def test_metricas_vacias_sin_inscritos(mvp):
    datos = metricas(mvp)
    assert datos["inscritos"] == 0
    assert datos["inscripcion"] == 0


# ---------- POST /api/reiniciar ----------

CLAVE = "clave-de-prueba-larga"


def reiniciar(app, clave):
    return llamar(app, "POST /api/reiniciar", {"clave": clave})


@pytest.mark.parametrize("configurada", [None, "", "corta", "1234567"])
def test_reinicio_desactivado_sin_clave_larga(mvp, monkeypatch, configurada):
    if configurada is None:
        monkeypatch.delenv("CLAVE_REINICIO", raising=False)
    else:
        monkeypatch.setenv("CLAVE_REINICIO", configurada)
    assert reiniciar(mvp, configurada or "") == (403, {"error": "reinicio_desactivado"})


@pytest.mark.parametrize("clave", ["otra-clave-larga-xx", "", None, CLAVE.upper()])
def test_reinicio_con_clave_incorrecta_no_borra(mvp, monkeypatch, clave):
    monkeypatch.setenv("CLAVE_REINICIO", CLAVE)
    visitar(mvp, monkeypatch, nuevo_uid(), "2026-10-24")
    assert reiniciar(mvp, clave) == (403, {"error": "clave_invalida"})
    assert metricas(mvp)["usuarios"] == 1


def test_reinicio_borra_todo_en_todas_las_paginas(mvp, monkeypatch):
    monkeypatch.setenv("CLAVE_REINICIO", CLAVE)
    for _ in range(3):
        uid = nuevo_uid()
        visitar(mvp, monkeypatch, uid, "2026-10-24")
        evento(mvp, uid, "armado", reto="1")
    evento(mvp, uid, "inscripcion", nombre="Carla M.")
    monkeypatch.setattr(mvp, "tabla", tabla_con_paginas(mvp.tabla))
    assert reiniciar(mvp, CLAVE) == (200, {"ok": True, "borrados": 7})
    datos = metricas(mvp)
    assert datos["usuarios"] == 0
    assert datos["inscritos"] == 0


def test_reinicio_con_body_invalido(mvp):
    assert llamar(mvp, "POST /api/reiniciar", crudo="[1]") == (400, {"error": "json_invalido"})
