#!/usr/bin/env bash
# Descarga Pyodide (Python en el navegador) a web/pyodide/. No se guarda en git (~13 MB).
# Se ejecuta solo desde deploy.sh si la carpeta no existe.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="0.27.8"
DESTINO="web/pyodide"
[ -f "$DESTINO/pyodide.asm.wasm" ] && { echo "✓ Pyodide $VERSION ya está en $DESTINO"; exit 0; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "→ Descargando Pyodide $VERSION…"
(cd "$TMP" && npm pack "pyodide@$VERSION" --silent && tar -xzf pyodide-*.tgz)

mkdir -p "$DESTINO"
for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  cp "$TMP/package/$f" "$DESTINO/$f"
done
echo "✓ Pyodide listo en $DESTINO ($(du -sh "$DESTINO" | cut -f1))"
