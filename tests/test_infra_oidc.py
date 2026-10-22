"""Comprueba que los roles del stack OIDC no caigan en los patrones
`role/experimento-lean-*` / `role/bugdojo-mvp-*` de la política de
RolCloudFormation: si cayeran dentro, ese rol podría reescribir la confianza
o las políticas de los roles del propio OIDC."""
import re
from pathlib import Path

OIDC = Path(__file__).resolve().parent.parent / "infra" / "github-oidc.yaml"
STACK = "github-oidc-experimento"   # el nombre que sugiere el README
PATRONES = ("experimento-lean-", "bugdojo-mvp-")


def test_el_nombre_del_stack_no_choca_con_los_patrones():
    assert not STACK.startswith(PATRONES)


def test_los_roles_del_stack_oidc_quedan_fuera_de_los_patrones():
    texto = OIDC.read_text()
    logicos = re.findall(r"^  (\w+):\n    Type: AWS::IAM::Role", texto, re.M)
    assert logicos, "no encontré roles IAM en el template"
    for logico in logicos:
        # CloudFormation nombra los recursos <stack>-<IdLogico>-<aleatorio>
        fisico = f"{STACK}-{logico}-AAAA"
        assert not fisico.startswith(PATRONES), fisico
