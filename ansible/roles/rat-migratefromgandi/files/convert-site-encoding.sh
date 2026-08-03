#!/usr/bin/env bash
# Convertit ISO-8859-1 -> UTF-8 (round-trip byte-exact) les fichiers texte
# d'un site rat_sites synchronisé depuis Gandi, et corrige le meta charset
# des documents HTML complets qui le déclarent explicitement.
#
# Contexte : rat_code/admin (générique) sont déjà en UTF-8 depuis les
# tickets 2B/2C du repo rat-git. Les données spécifiques par site
# (rat_sites/<nom>/modeles/, etc.) sont hors de ce repo et restaient en
# ISO-8859-1 -- mojibake constaté sur toutes les pages utilisant un
# template encore en ISO-8859-1 (voir wiki migration-rat-docker.md,
# section "Mojibake confirmé sur les templates spécifiques par site").
#
# Usage : convert-site-encoding.sh <répertoire>
#
# Idempotent : un fichier déjà en UTF-8 valide est laissé intact (détecté
# via `iconv -f UTF-8 -t UTF-8`, qui échoue sur du latin1 pur contenant des
# octets hauts). Ne touche qu'aux extensions texte connues (php/html/htm/
# txt/css/js/xml) -- jamais aux images/archives/binaires.

set -euo pipefail

TARGET_DIR="${1:?usage: convert-site-encoding.sh <répertoire>}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "ERREUR : répertoire introuvable : $TARGET_DIR" >&2
  exit 1
fi

converted=0
skipped=0
failed=0

while IFS= read -r -d '' f; do
  if iconv -f UTF-8 -t UTF-8 "$f" >/dev/null 2>&1; then
    skipped=$((skipped + 1))
    continue
  fi

  tmp="$(mktemp "${f}.XXXXXX")"
  if iconv -f ISO-8859-1 -t UTF-8 "$f" -o "$tmp" 2>/dev/null; then
    chmod --reference="$f" "$tmp"
    mv "$tmp" "$f"
    # Corrige le meta charset s'il est déclaré explicitement (documents
    # HTML complets uniquement -- les fragments de template XTemplate
    # n'ont pas de balise <head>, donc jamais de meta charset à corriger).
    sed -i 's/charset=iso-8859-1/charset=utf-8/Ig' "$f"
    converted=$((converted + 1))
    echo "CONVERTI: $f"
  else
    rm -f "$tmp"
    failed=$((failed + 1))
    echo "ECHEC (ni UTF-8 ni ISO-8859-1 valide, ignoré) : $f" >&2
  fi
done < <(find "$TARGET_DIR" -type f \( \
    -iname "*.php" -o -iname "*.html" -o -iname "*.htm" -o \
    -iname "*.txt" -o -iname "*.css" -o -iname "*.js" -o -iname "*.xml" \
  \) -print0)

echo "Résumé : $converted fichier(s) converti(s), $skipped déjà en UTF-8, $failed échec(s)."
