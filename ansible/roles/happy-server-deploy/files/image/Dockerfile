# Relais happy auto-hébergé : mode « standalone » du serveur (PGlite embarqué, fichiers
# sur disque local) — ni Postgres, ni Redis, ni S3. Paquet npm officiel du projet
# slopus/happy : happy-server-self-host (packages/happy-server-self-host/README.md),
# binaire happy-server (migrate | serve). Construit en local et publié sur ghcr.io,
# jamais construit sur glaurung (cf. puttini-deploy / rat-setup).
FROM node:22-bookworm-slim

# openssl : sans lui, Prisma ne détecte pas la version de libssl (avertissement au
# démarrage, constaté sur l'essai local du 2026-11-07).
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ARG HAPPY_SERVER_SELF_HOST_VERSION
RUN test -n "$HAPPY_SERVER_SELF_HOST_VERSION" \
 && npm install -g --omit=dev "happy-server-self-host@${HAPPY_SERVER_SELF_HOST_VERSION}" \
 && npm cache clean --force

# Variables lues par dist/standalone.mjs (aide de « happy-server », vérifiée sur la
# 1.1.11) : DATA_DIR (fichiers téléversés dans DATA_DIR/files), PGLITE_DIR, PORT, HOST.
# HANDY_MASTER_SECRET est fourni à l'exécution (env_file généré sur l'hôte), jamais ici.
ENV NODE_ENV=production \
    DATA_DIR=/data \
    PGLITE_DIR=/data/pglite \
    PORT=3005 \
    HOST=0.0.0.0

RUN mkdir -p /data && chown node:node /data
USER node
VOLUME ["/data"]
EXPOSE 3005

# Migrations PGlite idempotentes (table _prisma_migrations) puis serveur au premier plan.
ENTRYPOINT ["/bin/sh", "-c", "happy-server migrate && exec happy-server serve"]
