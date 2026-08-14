# Image d'outils pour les scans externes glaurung (nmap, curl, dig, openssl).
# Reproduit l'image glaurung-scan:latest construite sur ramoth2 le 2026-08-01
# (cf. wiki/projets/glaurung-securite-plan.md § Résultats Phase 3) — à reconstruire
# sur chaque poste de contrôle (M6, ramoth2...) qui n'a pas encore l'image locale.
#
# Build : docker build -t glaurung-scan:latest scripts/glaurung-scan/

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        nmap \
        curl \
        dnsutils \
        openssl \
    && rm -rf /var/lib/apt/lists/*
