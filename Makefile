VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: install test lint format local local-mvp

$(PY):
	python3 -m venv $(VENV)

install: $(PY)  ## Crea el entorno virtual e instala las dependencias de desarrollo
	$(PY) -m pip install -q -r requirements-dev.txt

test:  ## Corre los tests de ambas APIs
	$(PY) -m pytest

lint:  ## Revisa estilo y errores comunes
	$(PY) -m ruff check .
	$(VENV)/bin/cfn-lint template.yaml bugdojo-mvp/template.yaml infra/*.yaml

format:  ## Corrige automáticamente lo que ruff puede arreglar
	$(PY) -m ruff check . --fix

local:  ## Experimento en vivo sin AWS (http://localhost:8000)
	python3 scripts/servidor_local.py

local-mvp:  ## MVP de BugDojo sin AWS (http://localhost:8001)
	python3 bugdojo-mvp/scripts/servidor_local.py
