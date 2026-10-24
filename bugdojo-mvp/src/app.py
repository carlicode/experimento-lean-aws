"""API del MVP de BugDojo: registra uso anónimo y devuelve métricas agregadas.

No hay cuentas, correos ni pagos. Cada navegador tiene un uid aleatorio.

Rutas (HTTP API, detrás de CloudFront en /api/*):
  POST /api/evento    {uid, tipo, reto?, lang?, valor?, nombre?}
                      tipo: visita | aprendido | armado | intento | resuelto | feedback | inscripcion
                      lang: js (por defecto) | py
  GET  /api/metricas  -> solo totales agregados (nunca nombres)
  POST /api/reiniciar {clave} -> borra todos los datos si la clave coincide con CLAVE_REINICIO
"""
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3

tabla = boto3.resource("dynamodb").Table(os.environ["TABLA"])

UID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RETOS = {"1", "2", "3", "4", "5"}
BOLIVIA = timezone(timedelta(hours=-4))
FASES = ("aprendido", "armado", "resuelto")  # Aprende → Arma → Escribe
LENGUAJES = ("js", "py")
# Early access: nombre + iniciales ("Carla M." o "Carla M. F."), nada más.
NOMBRE_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,20}( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]\.?){1,3}")
LARGO_MINIMO_CLAVE = 8   # con una clave más corta, el reinicio queda desactivado

# Hipótesis del MVP (se definen antes de ver datos)
META_ACTIVACION = 0.40   # completan la fase Aprende (3 preguntas) de al menos 1 reto
META_RETENCION = 0.20    # vuelven otro día
MINIMO_USUARIOS = 10


def respuesta(status, cuerpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(cuerpo),
    }


def leer_cuerpo(event):
    """Devuelve el body como dict, o None si no es un objeto JSON válido."""
    try:
        cuerpo = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None
    return cuerpo if isinstance(cuerpo, dict) else None


def hoy():
    return datetime.now(BOLIVIA).strftime("%Y-%m-%d")


def registrar_evento(cuerpo):
    uid = str(cuerpo.get("uid", ""))
    tipo = cuerpo.get("tipo")
    reto = str(cuerpo.get("reto", ""))
    lang = cuerpo.get("lang", "js")
    if lang not in LENGUAJES:
        return respuesta(400, {"error": "lenguaje_invalido"})
    if not UID_RE.fullmatch(uid):
        return respuesta(400, {"error": "uid_invalido"})

    if tipo == "visita":
        tabla.put_item(Item={"uid": uid, "sk": f"visita#{hoy()}"})
    elif tipo in FASES or tipo == "intento":
        if reto not in RETOS:
            return respuesta(400, {"error": "reto_invalido"})
        if tipo == "intento":
            expr, nombres, valores = "ADD #n :uno", {"#n": "intentos"}, {":uno": 1}
        else:
            expr, nombres, valores = "SET #f = :si", {"#f": tipo}, {":si": True}
        tabla.update_item(Key={"uid": uid, "sk": f"reto#{reto}#{lang}"}, UpdateExpression=expr,
                          ExpressionAttributeNames=nombres, ExpressionAttributeValues=valores)
    elif tipo == "feedback":
        valor = cuerpo.get("valor")
        if valor not in ("si", "no"):
            return respuesta(400, {"error": "valor_invalido"})
        tabla.put_item(Item={"uid": uid, "sk": "feedback", "valor": valor})
    elif tipo == "inscripcion":
        nombre = " ".join(str(cuerpo.get("nombre", "")).split())
        if not NOMBRE_RE.fullmatch(nombre):
            return respuesta(400, {"error": "nombre_invalido"})
        tabla.put_item(Item={"uid": uid, "sk": "inscripcion", "nombre": nombre})
    else:
        return respuesta(400, {"error": "tipo_invalido"})
    return respuesta(200, {"ok": True})


def veredicto(valor, meta, usuarios):
    if usuarios < MINIMO_USUARIOS:
        return "faltan_datos"
    return "cumple" if valor >= meta else "no_cumple"


def metricas():
    items = todos_los_items()
    dias, activados, feedback, inscritos = {}, set(), {"si": 0, "no": 0}, 0
    fase_por_reto = {r: {f: set() for f in FASES} for r in RETOS}   # usuarios únicos
    usuarios_lang = {lang: set() for lang in LENGUAJES}
    armaron_lang = {lang: set() for lang in LENGUAJES}
    for i in items:
        uid, sk = i["uid"], i["sk"]
        dias.setdefault(uid, set())
        if sk.startswith("visita#"):
            dias[uid].add(sk)
        elif sk.startswith("reto#"):
            _, r, *resto = sk.split("#")
            lang = resto[0] if resto else "js"   # datos anteriores no traían lenguaje
            if r not in fase_por_reto or lang not in LENGUAJES:
                continue
            for fase in FASES:
                if i.get(fase):
                    fase_por_reto[r][fase].add(uid)
                    usuarios_lang[lang].add(uid)
            if any(i.get(fase) for fase in FASES):
                activados.add(uid)
            if i.get("armado") or i.get("resuelto"):
                armaron_lang[lang].add(uid)
        elif sk == "feedback" and i.get("valor") in feedback:
            feedback[i["valor"]] += 1
        elif sk == "inscripcion":
            inscritos += 1
    por_reto = {r: {"aprendieron": len(f["aprendido"]), "armaron": len(f["armado"]),
                    "escribieron": len(f["resuelto"])} for r, f in sorted(fase_por_reto.items())}

    usuarios = len(dias)
    retenidos = sum(1 for d in dias.values() if len(d) >= 2)
    activacion = len(activados) / usuarios if usuarios else 0
    retencion = retenidos / usuarios if usuarios else 0
    v_act = veredicto(activacion, META_ACTIVACION, usuarios)
    v_ret = veredicto(retencion, META_RETENCION, usuarios)
    if "faltan_datos" in (v_act, v_ret):
        decision = "faltan_datos"
    else:
        decision = "persevera" if v_act == v_ret == "cumple" else "pivota"

    return respuesta(200, {
        "usuarios": usuarios,
        "activados": len(activados),
        "retenidos": retenidos,
        "activacion": round(activacion, 4),
        "retencion": round(retencion, 4),
        "metas": {"activacion": META_ACTIVACION, "retencion": META_RETENCION, "minimo": MINIMO_USUARIOS},
        "veredictos": {"activacion": v_act, "retencion": v_ret},
        "decision": decision,
        "por_reto": por_reto,
        "lenguajes": {lang: {"usuarios": len(usuarios_lang[lang]), "armaron": len(armaron_lang[lang])}
                      for lang in LENGUAJES},
        "feedback": feedback,
        "inscritos": inscritos,
        "inscripcion": round(inscritos / usuarios, 4) if usuarios else 0,
    })


def todos_los_items():
    items, kwargs = [], {}
    while True:
        pagina = tabla.scan(**kwargs)
        items.extend(pagina["Items"])
        if "LastEvaluatedKey" not in pagina:
            return items
        kwargs["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]


def reiniciar(cuerpo):
    """Borra todos los eventos. Solo con la clave configurada en el deploy."""
    esperada = os.environ.get("CLAVE_REINICIO", "")
    if len(esperada) < LARGO_MINIMO_CLAVE:
        return respuesta(403, {"error": "reinicio_desactivado"})
    if not hmac.compare_digest(str(cuerpo.get("clave", "")).encode(), esperada.encode()):
        return respuesta(403, {"error": "clave_invalida"})
    items = todos_los_items()
    for i in items:
        tabla.delete_item(Key={"uid": i["uid"], "sk": i["sk"]})
    return respuesta(200, {"ok": True, "borrados": len(items)})


def handler(event, _context):
    ruta = event.get("routeKey", "")
    if ruta == "GET /api/metricas":
        return metricas()
    if ruta == "POST /api/evento":
        cuerpo = leer_cuerpo(event)
        if cuerpo is None:
            return respuesta(400, {"error": "json_invalido"})
        return registrar_evento(cuerpo)
    if ruta == "POST /api/reiniciar":
        cuerpo = leer_cuerpo(event)
        if cuerpo is None:
            return respuesta(400, {"error": "json_invalido"})
        return reiniciar(cuerpo)
    return respuesta(404, {"error": "no_encontrado"})
