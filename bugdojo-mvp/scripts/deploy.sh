#!/usr/bin/env bash
# Despliega la infraestructura (SAM) y sube el sitio. Uso:
#   ./scripts/deploy.sh                      # sin alerta de presupuesto
#   ALERT_EMAIL=tu@correo.com ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

STACK="bugdojo-mvp"
REGION="us-east-1"

echo "→ Desplegando infraestructura con SAM…"
if [ -n "${ALERT_EMAIL:-}" ]; then
  sam deploy --parameter-overrides "AlertEmail=$ALERT_EMAIL"
else
  sam deploy
fi

salida() {
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BUCKET=$(salida Bucket)
DIST=$(salida DistribucionId)
URL=$(salida Url)

./scripts/descargar_pyodide.sh

echo "→ Subiendo el sitio a S3…"
aws s3 sync web/ "s3://$BUCKET" --delete --region "$REGION"

echo "→ Invalidando la caché de CloudFront…"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" --query "Invalidation.Id" --output text

echo
echo "✅ Listo"
echo "   MVP:       $URL"
echo "   Métricas:  $URL/metricas.html"
