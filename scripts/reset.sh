#!/usr/bin/env bash
# Borra todas las respuestas (úsalo después de ensayar y antes de la charla).
set -euo pipefail

STACK="experimento-lean"
REGION="us-east-1"
TABLA=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='TablaNombre'].OutputValue" --output text)

read -r -p "¿Borrar TODAS las respuestas de $TABLA? (escribe 'si'): " ok
[ "$ok" = "si" ] || { echo "Cancelado."; exit 0; }

IDS=$(aws dynamodb scan --table-name "$TABLA" --region "$REGION" \
  --projection-expression id --query "Items[].id.S" --output text)

n=0
for id in $IDS; do
  aws dynamodb delete-item --table-name "$TABLA" --region "$REGION" \
    --key "{\"id\": {\"S\": \"$id\"}}"
  n=$((n + 1))
done
echo "🧹 $n respuestas borradas."
