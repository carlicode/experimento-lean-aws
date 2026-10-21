"""API del experimento: guarda respuestas, decisiones y devuelve totales.

Rutas (HTTP API, servidas detrás de CloudFront en /api/*):
  POST /api/respuesta   {alias, respuestas: ["A"|"B" x10]}  -> {grupo}
  POST /api/decision    {alias, decision: "si"|"no", motivo?} -> {ok}
  GET  /api/resultados  -> solo totales agregados, nunca alias
"""
import json
import os
import re
import time

import boto3
from botocore.exceptions import ClientError

tabla = boto3.resource("dynamodb").Table(os.environ["TABLA"])

ALIAS_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,25}")
MOTIVOS = {"caro", "no_necesito", "otra_herramienta"}
UMBRAL = 0.30
MINIMO_VEREDICTO = 5
NUM_PREGUNTAS = 10


def respuesta(status, cuerpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(cuerpo),
    }


def leer_cuerpo(event):
    try:
        return json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None


def calcular_grupo(respuestas):
    votos_a = respuestas.count("A")
    if votos_a >= 6:
        return "A"
    if votos_a <= 4:
        return "B"
    return respuestas[0]  # empate 5-5: desempata la pregunta 1


def guardar_respuesta(cuerpo):
    alias = str(cuerpo.get("alias", "")).strip()
    respuestas = cuerpo.get("respuestas")
    if not ALIAS_RE.fullmatch(alias):
        return respuesta(400, {"error": "alias_invalido"})
    if (not isinstance(respuestas, list) or len(respuestas) != NUM_PREGUNTAS
            or any(r not in ("A", "B") for r in respuestas)):
        return respuesta(400, {"error": "respuestas_invalidas"})

    grupo = calcular_grupo(respuestas)
    try:
        # Un voto por alias: escritura condicional
        tabla.put_item(
            Item={"id": alias.lower(), "grupo": grupo,
                  "respuestas": "".join(respuestas), "ts": int(time.time())},
            ConditionExpression="attribute_not_exists(id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respuesta(409, {"error": "alias_repetido"})
        raise
    return respuesta(200, {"grupo": grupo})


def guardar_decision(cuerpo):
    alias = str(cuerpo.get("alias", "")).strip()
    decision = cuerpo.get("decision")
    motivo = cuerpo.get("motivo")
    if not ALIAS_RE.fullmatch(alias) or decision not in ("si", "no"):
        return respuesta(400, {"error": "datos_invalidos"})
    if decision == "no" and motivo not in MOTIVOS:
        return respuesta(400, {"error": "motivo_invalido"})

    expr = "SET #d = :d"
    valores = {":d": decision}
    if decision == "no":
        expr += ", #m = :m"
        valores[":m"] = motivo
    try:
        tabla.update_item(
            Key={"id": alias.lower()},
            UpdateExpression=expr,
            ConditionExpression="attribute_exists(id) AND attribute_not_exists(#d)",
            ExpressionAttributeNames={"#d": "decision", **({"#m": "motivo"} if decision == "no" else {})},
            ExpressionAttributeValues=valores,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respuesta(409, {"error": "ya_decidido_o_sin_respuesta"})
        raise
    return respuesta(200, {"ok": True})


def resultados():
    items, kwargs = [], {
        "ProjectionExpression": "#g, #d, #m",
        "ExpressionAttributeNames": {"#g": "grupo", "#d": "decision", "#m": "motivo"},
    }
    while True:
        pagina = tabla.scan(**kwargs)
        items.extend(pagina["Items"])
        if "LastEvaluatedKey" not in pagina:
            break
        kwargs["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]

    grupos = {}
    for g in ("A", "B"):
        del_grupo = [i for i in items if i.get("grupo") == g]
        si = sum(1 for i in del_grupo if i.get("decision") == "si")
        no = sum(1 for i in del_grupo if i.get("decision") == "no")
        participantes = len(del_grupo)
        conversion = si / participantes if participantes else 0
        if participantes < MINIMO_VEREDICTO:
            veredicto = "faltan_datos"
        else:
            veredicto = "vive" if conversion >= UMBRAL else "muere"
        grupos[g] = {
            "participantes": participantes,
            "si": si,
            "no": no,
            "conversion": round(conversion, 4),
            "veredicto": veredicto,
            "motivos": {m: sum(1 for i in del_grupo if i.get("motivo") == m) for m in sorted(MOTIVOS)},
        }
    return respuesta(200, {"total": len(items), "umbral": UMBRAL,
                           "minimo": MINIMO_VEREDICTO, "grupos": grupos})


def handler(event, _context):
    ruta = event.get("routeKey", "")
    if ruta == "GET /api/resultados":
        return resultados()
    cuerpo = leer_cuerpo(event)
    if cuerpo is None:
        return respuesta(400, {"error": "json_invalido"})
    if ruta == "POST /api/respuesta":
        return guardar_respuesta(cuerpo)
    if ruta == "POST /api/decision":
        return guardar_decision(cuerpo)
    return respuesta(404, {"error": "no_encontrado"})
