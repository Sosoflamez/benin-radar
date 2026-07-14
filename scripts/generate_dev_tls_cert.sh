#!/usr/bin/env bash
# Génère un certificat TLS auto-signé pour nginx en local/dev.
#
# ATTENTION : certificat auto-signé, uniquement pour valider la chaîne
# reverse-proxy TLS -> daphne en dev. À remplacer par un vrai certificat
# (Let's Encrypt ou autre autorité) avant toute mise en production réelle.
#
# Usage : ./scripts/generate_dev_tls_cert.sh [domaine]

set -euo pipefail

DOMAIN="${1:-localhost}"
CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/nginx/certs"

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -newkey rsa:2048 \
    -days 365 \
    -keyout "$CERT_DIR/dev.key" \
    -out "$CERT_DIR/dev.crt" \
    -subj "/C=BJ/ST=Littoral/L=Cotonou/O=Benin-radar/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN}"

echo "Certificat auto-signé généré dans ${CERT_DIR} (dev.crt, dev.key) pour ${DOMAIN}."
