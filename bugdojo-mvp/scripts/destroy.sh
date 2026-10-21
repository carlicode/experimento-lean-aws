#!/usr/bin/env bash
# Elimina todo lo creado (sitio, API, base de datos, alerta). No se puede deshacer.
set -euo pipefail

STACK="bugdojo-mvp"
REGION="us-east-1"

read -r -p "¿Eliminar TODO el MVP ($STACK) y sus datos? (escribe 'si'): " ok
[ "$ok" = "si" ] || { echo "Cancelado."; exit 0; }

BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='Bucket'].OutputValue" --output text)

echo "→ Vaciando el bucket del sitio…"
aws s3 rm "s3://$BUCKET" --recursive --region "$REGION"

echo "→ Eliminando el stack…"
sam delete --stack-name "$STACK" --region "$REGION" --no-prompts
echo "🗑️  MVP eliminado."
