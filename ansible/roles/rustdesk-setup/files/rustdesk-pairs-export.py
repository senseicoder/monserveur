#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export de l'état en ligne des pairs RustDesk connus de hbbs (monserveur#39).

Écrit un JSON :
  {"version": 1, "genere_le": "...", "pairs": [
     {"id": "...", "nom": null, "en_ligne": true, "vu_le": "...", "cree_le": "...",
      "ip": "..."}]}

- Liste des pairs : table `peer` de la base hbbs (db_v2.sqlite3), lue sur une
  COPIE (base + journal WAL) dans un dossier temporaire : la base vivante n'est
  jamais ouverte, donc jamais modifiée.
- État en ligne : requête OnlineRequest du protocole rendezvous envoyée à hbbs
  (port TCP 21115, celui du test NAT), la même que le client RustDesk utilise
  pour ses pastilles vertes. hbbs répond « en ligne » si le pair s'est
  enregistré depuis moins de 30 s (REG_TIMEOUT de rustdesk-server).
- vu_le : date de cet export si le pair est en ligne, sinon la valeur de
  l'export précédent (relu dans le fichier de sortie), sinon null.
- nom : la version open source de hbbs ne stocke pas le nom de la machine ;
  on reprend la colonne `note` si elle est remplie, sinon null.
- ip : champ `ip` de la colonne `info` de hbbs, réécrit par hbbs quand un pair
  réenregistre sa clé depuis une autre IP (donc IP du dernier enregistrement de
  clé, pas forcément l'IP courante). Préfixe IPv4 mappé `::ffff:` retiré, null
  si absente ou illisible. Sert au rapprochement avec les appareils (c3po#190).

En cas d'échec (base illisible, hbbs injoignable), rien n'est écrit et le code
retour est 1 : le consommateur voit `genere_le` vieillir au lieu de recevoir un
faux « tout hors ligne ».

Écriture atomique : fichier temporaire dans le même dossier puis os.replace().
Le temporaire est préfixé `.syncthing.` et suffixé `.tmp`, motif que Syncthing
traite comme ses propres temporaires et ne synchronise pas.

Compatible Python 3.5 (glaurung : Debian Stretch), bibliothèque standard seule.
"""

import argparse
import ipaddress
import datetime
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile

VERSION_FORMAT = 1

# Numéros de champs protobuf (hbb_common/protos/rendezvous.proto)
CHAMP_ONLINE_REQUEST = 23   # RendezvousMessage.online_request
CHAMP_ONLINE_RESPONSE = 24  # RendezvousMessage.online_response
CHAMP_OR_ID = 1             # OnlineRequest.id
CHAMP_OR_PEERS = 2          # OnlineRequest.peers (repeated string)
CHAMP_ORESP_STATES = 1      # OnlineResponse.states (bytes, bit à 1 = en ligne)


# --- protobuf minimal ---------------------------------------------------------

def _varint(n):
    out = bytearray()
    while True:
        octet = n & 0x7F
        n >>= 7
        if n:
            out.append(octet | 0x80)
        else:
            out.append(octet)
            return bytes(out)


def _lire_varint(buf, pos):
    resultat = 0
    decalage = 0
    while True:
        if pos >= len(buf):
            raise ValueError("varint tronqué")
        octet = buf[pos]
        pos += 1
        resultat |= (octet & 0x7F) << decalage
        if not octet & 0x80:
            return resultat, pos
        decalage += 7


def _champ_bytes(numero, valeur):
    return _varint((numero << 3) | 2) + _varint(len(valeur)) + valeur


def _champs(buf):
    """Itère sur (numero, type, valeur) d'un message protobuf."""
    pos = 0
    while pos < len(buf):
        cle, pos = _lire_varint(buf, pos)
        numero, type_fil = cle >> 3, cle & 7
        if type_fil == 0:
            valeur, pos = _lire_varint(buf, pos)
        elif type_fil == 2:
            longueur, pos = _lire_varint(buf, pos)
            valeur = buf[pos:pos + longueur]
            if len(valeur) != longueur:
                raise ValueError("champ tronqué")
            pos += longueur
        elif type_fil == 1:
            valeur, pos = buf[pos:pos + 8], pos + 8
        elif type_fil == 5:
            valeur, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError("type protobuf inattendu : %d" % type_fil)
        yield numero, type_fil, valeur


def encoder_online_request(ids, demandeur=""):
    corps = _champ_bytes(CHAMP_OR_ID, demandeur.encode("utf-8"))
    for pair_id in ids:
        corps += _champ_bytes(CHAMP_OR_PEERS, pair_id.encode("utf-8"))
    return _champ_bytes(CHAMP_ONLINE_REQUEST, corps)


def decoder_online_response(message, nb_pairs):
    for numero, type_fil, valeur in _champs(message):
        if numero == CHAMP_ONLINE_RESPONSE and type_fil == 2:
            etats = b""
            for n2, t2, v2 in _champs(valeur):
                if n2 == CHAMP_ORESP_STATES and t2 == 2:
                    etats = bytes(v2)
            # octets lus de gauche à droite, bit de poids fort = premier pair
            return [bool(i // 8 < len(etats) and etats[i // 8] & (0x80 >> (i % 8)))
                    for i in range(nb_pairs)]
    raise ValueError("pas d'OnlineResponse dans la réponse de hbbs")


# --- trame hbb_common (BytesCodec) ---------------------------------------------

def encadrer(donnees):
    n = len(donnees)
    if n <= 0x3F:
        entete = bytes([n << 2])
    elif n <= 0x3FFF:
        v = (n << 2) | 1
        entete = bytes([v & 0xFF, (v >> 8) & 0xFF])
    elif n <= 0x3FFFFF:
        v = (n << 2) | 2
        entete = bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
    else:
        v = (n << 2) | 3
        entete = bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])
    return entete + donnees


def _recevoir(sock, n):
    buf = b""
    while len(buf) < n:
        morceau = sock.recv(n - len(buf))
        if not morceau:
            raise ValueError("connexion fermée par hbbs")
        buf += morceau
    return buf


def lire_trame(sock):
    premier = _recevoir(sock, 1)
    taille_entete = (premier[0] & 0x3) + 1
    entete = premier + _recevoir(sock, taille_entete - 1)
    n = 0
    for i, octet in enumerate(entete):
        n |= octet << (8 * i)
    return _recevoir(sock, n >> 2)


def interroger_hbbs(hote, port, ids, delai=10.0):
    """Renvoie la liste des états en ligne (bool) dans l'ordre de `ids`."""
    if not ids:
        return []
    sock = socket.create_connection((hote, port), timeout=delai)
    try:
        sock.sendall(encadrer(encoder_online_request(ids)))
        return decoder_online_response(lire_trame(sock), len(ids))
    finally:
        sock.close()


# --- base hbbs -----------------------------------------------------------------

def lire_pairs(chemin_base):
    """Lit la table peer sur une copie de la base (et de son journal WAL)."""
    dossier = tempfile.mkdtemp(prefix="rustdesk-pairs-export.")
    try:
        copie = os.path.join(dossier, "db.sqlite3")
        shutil.copyfile(chemin_base, copie)
        if os.path.exists(chemin_base + "-wal"):
            shutil.copyfile(chemin_base + "-wal", copie + "-wal")
        connexion = sqlite3.connect(copie)
        try:
            lignes = connexion.execute(
                "SELECT id, note, created_at, info FROM peer ORDER BY id").fetchall()
        finally:
            connexion.close()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    return [{"id": l[0], "note": l[1], "created_at": l[2], "info": l[3]} for l in lignes]


def ip_depuis_info(info):
    """Colonne info de hbbs ('{"ip":"::ffff:a.b.c.d"}') → IP normalisée ou None."""
    try:
        valeur = json.loads(info).get("ip")
        if not isinstance(valeur, str):
            return None
        adresse = ipaddress.ip_address(valeur)
    except (TypeError, ValueError, AttributeError):
        return None
    mappee = getattr(adresse, "ipv4_mapped", None)
    return str(mappee or adresse)


# --- export --------------------------------------------------------------------

def maintenant_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def date_base_iso(valeur):
    """created_at de hbbs (« AAAA-MM-JJ HH:MM:SS », UTC) → ISO 8601."""
    if not valeur:
        return None
    try:
        d = datetime.datetime.strptime(valeur, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return valeur
    return d.replace(tzinfo=datetime.timezone.utc).isoformat()


def vus_precedents(chemin_sortie):
    try:
        with open(chemin_sortie, encoding="utf-8") as f:
            precedent = json.load(f)
        return {p["id"]: p.get("vu_le") for p in precedent.get("pairs", []) if "id" in p}
    except (OSError, ValueError, AttributeError, TypeError, KeyError):
        return {}


def construire_export(pairs, etats, vus, genere_le):
    sortie = []
    for pair, en_ligne in zip(pairs, etats):
        note = (pair["note"] or "").strip() or None
        sortie.append({
            "id": pair["id"],
            "nom": note,
            "en_ligne": en_ligne,
            "vu_le": genere_le if en_ligne else vus.get(pair["id"]),
            "cree_le": date_base_iso(pair["created_at"]),
            "ip": ip_depuis_info(pair.get("info")),
        })
    return {"version": VERSION_FORMAT, "genere_le": genere_le, "pairs": sortie}


def ecrire_atomique(chemin, contenu):
    dossier = os.path.dirname(os.path.abspath(chemin))
    if not os.path.isdir(dossier):
        # Ne jamais créer le dossier Syncthing : son absence est une anomalie.
        raise OSError("dossier de sortie absent : %s" % dossier)
    st = os.stat(dossier)
    fd, temporaire = tempfile.mkstemp(
        prefix=".syncthing." + os.path.basename(chemin) + ".", suffix=".tmp", dir=dossier)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contenu)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporaire, 0o644)
        if os.geteuid() == 0:
            # Le fichier appartient au propriétaire du dossier (l'utilisateur Syncthing).
            os.chown(temporaire, st.st_uid, st.st_gid)
        os.replace(temporaire, chemin)
    except BaseException:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", required=True, help="db_v2.sqlite3 de hbbs (lu sur copie)")
    p.add_argument("--hbbs", default="127.0.0.1:21115", help="hôte:port TCP de hbbs (port NAT)")
    p.add_argument("--sortie", required=True, help="fichier JSON à écrire (dossier existant)")
    p.add_argument("--delai", type=float, default=10.0, help="délai réseau en secondes")
    a = p.parse_args(argv)

    hote, _, port = a.hbbs.rpartition(":")
    try:
        pairs = lire_pairs(a.base)
        etats = interroger_hbbs(hote.strip("[]"), int(port), [x["id"] for x in pairs], a.delai)
        genere_le = maintenant_iso()
        export = construire_export(pairs, etats, vus_precedents(a.sortie), genere_le)
        ecrire_atomique(a.sortie, json.dumps(export, ensure_ascii=False, indent=1) + "\n")
    except Exception as e:  # noqa: BLE001 — journal cron, une ligne par échec
        sys.stderr.write("%s rustdesk-pairs-export : échec, rien écrit : %s: %s\n"
                         % (maintenant_iso(), type(e).__name__, e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
