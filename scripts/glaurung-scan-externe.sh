#!/bin/bash
# glaurung-scan-externe.sh — scan externe glaurung (ports TCP + TLS + headers de sécurité)
#
# À lancer depuis un poste de contrôle (M6, ramoth2...) — JAMAIS depuis glaurung
# lui-même (sinon on ne teste que la route loopback, pas ce qu'internet voit
# réellement). Cf. wiki/projets/glaurung-securite-plan.md Phase 3.
#
# Sondes passives uniquement (connexion TCP complète, négociation TLS standard) —
# pas de --script vuln nmap, pas de brute-force (cf. plan § "Ce qui n'a pas été fait").
# Ne modifie rien sur glaurung.
#
# Prérequis sur ce poste :
#   - Docker
#   - Image locale glaurung-scan:latest — si absente :
#       docker build -t glaurung-scan:latest scripts/glaurung-scan/
#   - Image drwetter/testssl.sh (pull automatique au premier `docker run`)
#   - Token ntfy dans ~/.config/glaurung-scan/ntfy-token (chmod 600, NON versionné) —
#     même token que ntfy_healthcheck_token (ansible/group_vars/all/vault.yml,
#     ansible-vault view pour le récupérer) : compte admin ntfy, accès à tous les
#     topics dont glaurung-security.
#
# Fréquence proposée (cf. tâche d'origine) : mensuel + systématique après tout
# déploiement Ansible touchant firewall/vhosts. Entrée cron à valider par Cédric,
# pas installée par ce script.

set -uo pipefail

TARGET_HOST="glaurung.daneel.net"
NTFY_URL="https://ntfy.daneel.net:8787/glaurung-security"
NTFY_TOKEN_FILE="$HOME/.config/glaurung-scan/ntfy-token"
CERT_WARN_DAYS=14

# Ports attendus depuis L'EXTÉRIEUR (FIREWALL.md § "Liste des ports", DOCKER-USER +
# INPUT ouverts au monde — 3306 volontairement absent : il ne doit PAS répondre
# depuis internet, cf. "Leçon 3306"). ⚠️ FIREWALL.md est signalé périmé au-delà de
# la ligne réseau dans le CLAUDE.md du repo (ntfy 8081 backend interne non listé,
# rat/phpbb-integralsport absents) — un écart peut être un trou de doc, à vérifier
# avant de traiter comme incident.
EXPECTED_TCP_PORTS="22 80 443 8000 8001 8002 8787 21115 21116 21117 22000"

HTTPS_ENDPOINTS=(
  "reader.daneel.net:443"
  "bots.plcoder.net:443"
  "mindwtr.daneel.net:8787"
  "vault.daneel.net:8787"
  "ntfy.daneel.net:8787"
)

if [ ! -r "$NTFY_TOKEN_FILE" ]; then
  echo "Token ntfy introuvable ($NTFY_TOKEN_FILE) — voir en-tête du script." >&2
  exit 1
fi
NTFY_TOKEN=$(cat "$NTFY_TOKEN_FILE")

alert() {
  local priority="$1" title="$2" message="$3"
  curl -s -o /dev/null -H "Authorization: Bearer $NTFY_TOKEN" -H "Priority: $priority" -H "Title: $title" -d "$message" "$NTFY_URL"
}

echo "=== Scan ports TCP (nmap -sT -p-) sur $TARGET_HOST ==="
nmap_out=$(docker run --rm glaurung-scan:latest nmap -sT -p- -T4 "$TARGET_HOST" 2>&1)
echo "$nmap_out"

open_ports=$(echo "$nmap_out" | grep -E '^[0-9]+/tcp[[:space:]]+open' | sed -E 's#^([0-9]+)/tcp.*#\1#' | sort -un)
unexpected=""
for p in $open_ports; do
  if ! grep -qw "$p" <<<"$EXPECTED_TCP_PORTS"; then
    unexpected="${unexpected}${p} "
  fi
done
if [ -n "$unexpected" ]; then
  alert "urgent" "Glaurung — scan externe : port(s) TCP inattendu(s)" "Port(s) ouvert(s) absent(s) de FIREWALL.md : $unexpected"
fi

echo "=== Audit TLS (testssl.sh --fast) sur ${#HTTPS_ENDPOINTS[@]} endpoints ==="
for endpoint in "${HTTPS_ENDPOINTS[@]}"; do
  echo "--- $endpoint ---"
  ts_out=$(docker run --rm drwetter/testssl.sh --fast --protocols --server-defaults --headers "$endpoint" 2>&1)
  echo "$ts_out"

  # Protocoles obsolètes réellement OFFERTS (pas "not offered (OK)") — ne matche
  # jamais "TLS 1.2"/"TLS 1.3" (le \s après "TLS 1" exige une fin de mot).
  obsolete=$(echo "$ts_out" | grep -E '^[[:space:]]*(SSLv2|SSLv3|TLS 1)[[:space:]]' | grep -v 'not offered' | grep 'offered' || true)
  if [ -n "$obsolete" ]; then
    alert "high" "Glaurung — TLS obsolète sur $endpoint" "$obsolete"
  fi

  # Format de sortie testssl.sh non vérifié en pratique par ce script (pas encore
  # lancé, cf. consigne "NE PAS lancer maintenant) — à confirmer/ajuster au premier
  # run réel contre la sortie exacte de la version testssl.sh utilisée.
  cert_days=$(echo "$ts_out" | grep -Eo 'expires in[[:space:]]+[0-9]+ day' | grep -Eo '[0-9]+' || true)
  if [ -n "$cert_days" ] && [ "$cert_days" -lt "$CERT_WARN_DAYS" ]; then
    alert "high" "Glaurung — certificat proche expiration ($endpoint)" "Expire dans ${cert_days}j (seuil ${CERT_WARN_DAYS}j)"
  fi

  hsts_line=$(echo "$ts_out" | grep -E '^[[:space:]]*HSTS[[:space:]]' || true)
  if [ -z "$hsts_line" ] || echo "$hsts_line" | grep -qi 'not offered'; then
    alert "default" "Glaurung — HSTS absent sur $endpoint" "Aucun header Strict-Transport-Security détecté."
  fi
done

echo "=== Scan terminé ==="
