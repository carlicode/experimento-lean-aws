"""Fixtures compartidas: DynamoDB simulado con moto y carga de cada app.py.

Los dos stacks tienen un módulo llamado `app`, así que los cargamos con
nombres distintos para que no choquen entre sí.
"""
import importlib.util
import json
import os
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

RAIZ = Path(__file__).resolve().parent.parent


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(autouse=True)
def credenciales_falsas(monkeypatch):
    for var, valor in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "TABLA": "tabla-tests",
    }.items():
        monkeypatch.setenv(var, valor)


def _tabla(clave):
    atributos = [{"AttributeName": n, "AttributeType": "S"} for n, _ in clave]
    esquema = [{"AttributeName": n, "KeyType": t} for n, t in clave]
    return boto3.resource("dynamodb").create_table(
        TableName=os.environ["TABLA"], AttributeDefinitions=atributos,
        KeySchema=esquema, BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def experimento():
    """src/app.py con una tabla igual a la de template.yaml (clave: id)."""
    with mock_aws():
        _tabla([("id", "HASH")])
        yield _cargar("app_experimento", RAIZ / "src" / "app.py")


@pytest.fixture
def mvp():
    """bugdojo-mvp/src/app.py con una tabla igual a la de su template (uid + sk)."""
    with mock_aws():
        _tabla([("uid", "HASH"), ("sk", "RANGE")])
        yield _cargar("app_mvp", RAIZ / "bugdojo-mvp" / "src" / "app.py")


def llamar(app, ruta, cuerpo=None, *, crudo=None):
    """Invoca el handler como lo haría API Gateway y devuelve (status, json)."""
    body = crudo if crudo is not None else (None if cuerpo is None else json.dumps(cuerpo))
    res = app.handler({"routeKey": ruta, "body": body}, None)
    return res["statusCode"], json.loads(res["body"])
