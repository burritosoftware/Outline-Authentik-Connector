#!/usr/bin/env bash
# Prepare the dev stack: generate a self-signed cert for oa-connector.internal
# and seed an empty .env. Idempotent — safe to re-run.
set -euo pipefail

cd "$(dirname "$0")"

# Cert: only generate if missing.
if [[ ! -f certs/cert.pem || ! -f certs/key.pem ]]; then
  mkdir -p certs
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout certs/key.pem -out certs/cert.pem -days 365 \
    -subj "/CN=oa-connector.internal" \
    -addext "subjectAltName=DNS:oa-connector.internal,DNS:oa-connector,DNS:localhost" \
    >/dev/null 2>&1
  echo "Generated certs/cert.pem and certs/key.pem"
else
  echo "Certs already present at certs/cert.pem"
fi

# .env: only create if missing.
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill in OUTLINE_TOKEN and OUTLINE_WEBHOOK_SECRET after creating the webhook in Outline"
else
  echo ".env already present"
fi
