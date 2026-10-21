"""API del MVP de BugDojo: registra uso anónimo y devuelve métricas agregadas.

No hay cuentas, correos ni pagos. Cada navegador tiene un uid aleatorio.

Rutas (HTTP API, detrás de CloudFront en /api/*):
  POST /api/evento    {uid, tipo: "visita"|"intento"|"resuelto"|"feedback", reto?, valor?}
  GET  /api/metricas  -> solo totales agregados
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3

tabla = boto3.resource("dynamodb").Table(os.environ["TABLA"])

UID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RETOS = {"1", "2", "3", "4", "5"}
BOLIVIA = timezone(timedelta(hours=-4))

# Hipótesis del MVP (se definen antes de ver datos)
META_ACTIVACION = 0.40   # resuelven al menos 1 reto
META_RETENCION = 0.20    # vuelven otro día
MINIMO_USUARIOS = 10


def respuesta(status, cuerpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(cuerpo),
    }


def hoy():
    return datetime.now(BOLIVIA).strftime("%Y-%m-%d")


def registrar_evento(cuerpo):
    uid = str(cuerpo.get("uid", ""))
    tipo = cuerpo.get("tipo")
    reto = str(cuerpo.get("reto", ""))
    if not UID_RE.fullmatch(uid):
        return respuesta(400, {"error": "uid_invalido"})

    if tipo == "visita":
        tabla.put_item(Item={"uid": uid, "sk": f"visita#{hoy()}"})
    elif tipo in ("intento", "resuelto"):
        if reto not in RETOS:
            return respuesta(400, {"error": "reto_invalido"})
        expr = "ADD #n :uno" if tipo == "intento" else "SET #r = :si"
        nombres = {"#n": "intentos"} if tipo == "intento" else {"#r": "resuelto"}
        valores = {":uno": 1} if tipo == "intento" else {":si": True}
        tabla.update_item(Key={"uid": uid, "sk": f"reto#{reto}"}, UpdateExpression=expr,
                          ExpressionAttributeNames=nombres, ExpressionAttributeValues=valores)
    elif tipo == "feedback":
        valor = cuerpo.get("valor")
        if valor not in ("si", "no"):
            return respuesta(400, {"error": "valor_invalido"})
        tabla.put_item(Item={"uid": uid, "sk": "feedback", "valor": valor})
    else:
        return respuesta(400, {"error": "tipo_invalido"})
    return respuesta(200, {"ok": True})


def veredicto(valor, meta, usuarios):
    if usuarios < MINIMO_USUARIOS:
        return "faltan_datos"
    return "cumple" if valor >= meta else "no_cumple"


def metricas():
    items, kwargs = [], {}
    while True:
        pagina = tabla.scan(**kwargs)
        items.extend(pagina["Items"])
        if "LastEvaluatedKey" not in pagina:
            break
        kwargs["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]

    dias, activados, feedback = {}, set(), {"si": 0, "no": 0}
    por_reto = {r: {"intentaron": 0, "resolvieron": 0} for r in sorted(RETOS)}
    for i in items:
        uid, sk = i["uid"], i["sk"]
        dias.setdefault(uid, set())
        if sk.startswith("visita#"):
            dias[uid].add(sk)
        elif sk.startswith("reto#"):
            r = sk.split("#", 1)[1]
            if r in por_reto:
                if i.get("intentos") or i.get("resuelto"):
                    por_reto[r]["intentaron"] += 1
                if i.get("resuelto"):
                    por_reto[r]["resolvieron"] += 1
                    activados.add(uid)
        elif sk == "feedback" and i.get("valor") in feedback:
            feedback[i["valor"]] += 1

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
        "feedback": feedback,
    })


def handler(event, _context):
    ruta = event.get("routeKey", "")
    if ruta == "GET /api/metricas":
        return metricas()
    if ruta == "POST /api/evento":
        try:
            cuerpo = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return respuesta(400, {"error": "json_invalido"})
        return registrar_evento(cuerpo)
    return respuesta(404, {"error": "no_encontrado"})
