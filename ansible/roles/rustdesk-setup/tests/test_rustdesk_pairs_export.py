# -*- coding: utf-8 -*-
"""Tests du script d'export des pairs RustDesk (monserveur#39).

Lancer depuis ansible/roles/rustdesk-setup :
    python3 -m unittest discover -s tests -v
Sans réseau ni Docker : faux hbbs local (socket) et base SQLite générée.
"""

import importlib.util
import json
import os
import shutil
import socket
import sqlite3
import tempfile
import threading
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(ICI, "..", "files", "rustdesk-pairs-export.py")
_spec = importlib.util.spec_from_file_location("rustdesk_pairs_export", SCRIPT)
rpe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rpe)

SCHEMA_HBBS = """CREATE TABLE peer (
    guid blob primary key not null, id varchar(100) not null, uuid blob not null,
    pk blob not null, created_at datetime not null default(current_timestamp),
    user blob, status tinyint, note varchar(300), info text not null) without rowid"""


def creer_base(chemin, pairs):
    c = sqlite3.connect(chemin)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(SCHEMA_HBBS)
    for i, (pid, note) in enumerate(pairs):
        c.execute("INSERT INTO peer (guid,id,uuid,pk,created_at,note,info) VALUES (?,?,?,?,?,?,?)",
                  (bytes([i]) * 16, pid, b"u", b"k", "2026-07-11 22:33:55", note, "{}"))
    c.commit()
    return c  # laissée ouverte : les écritures restent dans le WAL


class FauxHbbs(threading.Thread):
    """Répond à une OnlineRequest : en ligne = ID présent dans `en_ligne`."""

    def __init__(self, en_ligne):
        super().__init__(daemon=True)
        self.en_ligne = set(en_ligne)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.demande = None

    def run(self):
        conn, _ = self.sock.accept()
        with conn:
            msg = rpe.lire_trame(conn)
            ids = []
            for n, _, v in rpe._champs(msg):
                if n == rpe.CHAMP_ONLINE_REQUEST:
                    ids = [bytes(v2).decode() for n2, _, v2 in rpe._champs(v)
                           if n2 == rpe.CHAMP_OR_PEERS]
            self.demande = ids
            etats = bytearray((len(ids) + 7) // 8)
            for i, pid in enumerate(ids):
                if pid in self.en_ligne:
                    etats[i // 8] |= 0x80 >> (i % 8)
            reponse = rpe._champ_bytes(rpe.CHAMP_ONLINE_RESPONSE,
                                       rpe._champ_bytes(rpe.CHAMP_ORESP_STATES, bytes(etats)))
            conn.sendall(rpe.encadrer(reponse))
        self.sock.close()


class TestCodec(unittest.TestCase):
    def test_encadrement_aller_retour(self):
        for n in (0, 1, 0x3F, 0x40, 0x3FFF, 0x4000):
            donnees = b"x" * n
            a, b = socket.socketpair()
            with a, b:
                a.sendall(rpe.encadrer(donnees))
                self.assertEqual(rpe.lire_trame(b), donnees)

    def test_ordre_des_bits_plus_de_8_pairs(self):
        etats = [i in (0, 7, 8, 10) for i in range(11)]
        octets = bytearray(2)
        for i, e in enumerate(etats):
            if e:
                octets[i // 8] |= 0x80 >> (i % 8)
        msg = rpe._champ_bytes(rpe.CHAMP_ONLINE_RESPONSE,
                               rpe._champ_bytes(rpe.CHAMP_ORESP_STATES, bytes(octets)))
        self.assertEqual(rpe.decoder_online_response(msg, 11), etats)

    def test_reponse_sans_online_response(self):
        with self.assertRaises(ValueError):
            rpe.decoder_online_response(rpe._champ_bytes(7, b""), 1)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.base = os.path.join(self.dir, "db_v2.sqlite3")
        self.weyr = os.path.join(self.dir, "Weyr")
        os.mkdir(self.weyr)
        self.autre = os.path.join(self.weyr, "juiz.txt")
        with open(self.autre, "w") as f:
            f.write("ne pas toucher\n")
        self.sortie = os.path.join(self.weyr, "rustdesk-pairs.json")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def lancer(self, en_ligne):
        hbbs = FauxHbbs(en_ligne)
        hbbs.start()
        rc = rpe.main(["--base", self.base, "--hbbs", "127.0.0.1:%d" % hbbs.port,
                       "--sortie", self.sortie, "--delai", "5"])
        hbbs.join(5)
        return rc, hbbs

    def test_export_complet_et_vu_le_conserve(self):
        conn = creer_base(self.base, [("111111111", None), ("idperso", " Téléphone "),
                                      ("222222222", "")])
        try:
            with open(self.base, "rb") as f:
                avant = f.read()
            rc, hbbs = self.lancer({"111111111", "idperso"})
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(hbbs.demande), ["111111111", "222222222", "idperso"])
            with open(self.sortie, encoding="utf-8") as f:
                e1 = json.load(f)
            self.assertEqual(e1["version"], 1)
            p = {x["id"]: x for x in e1["pairs"]}
            self.assertEqual(len(p), 3)  # tous les ID, y compris ceux restés dans le WAL
            self.assertTrue(p["111111111"]["en_ligne"])
            self.assertEqual(p["111111111"]["vu_le"], e1["genere_le"])
            self.assertEqual(p["idperso"]["nom"], "Téléphone")
            self.assertIsNone(p["222222222"]["nom"])
            self.assertFalse(p["222222222"]["en_ligne"])
            self.assertIsNone(p["222222222"]["vu_le"])
            self.assertEqual(p["111111111"]["cree_le"], "2026-07-11T22:33:55+00:00")

            # Deuxième passage : 111111111 hors ligne, garde son vu_le précédent.
            rc, _ = self.lancer({"idperso"})
            self.assertEqual(rc, 0)
            with open(self.sortie, encoding="utf-8") as f:
                p2 = {x["id"]: x for x in json.load(f)["pairs"]}
            self.assertFalse(p2["111111111"]["en_ligne"])
            self.assertEqual(p2["111111111"]["vu_le"], e1["genere_le"])

            # Base vivante intacte, autres fichiers du dossier intacts, pas de temporaire.
            with open(self.base, "rb") as f:
                self.assertEqual(f.read(), avant)
            with open(self.autre) as f:
                self.assertEqual(f.read(), "ne pas toucher\n")
            self.assertEqual(sorted(os.listdir(self.weyr)), ["juiz.txt", "rustdesk-pairs.json"])
        finally:
            conn.close()

    def test_hbbs_injoignable_rien_ecrit(self):
        creer_base(self.base, [("111111111", None)]).close()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()  # port libre, personne n'écoute
        rc = rpe.main(["--base", self.base, "--hbbs", "127.0.0.1:%d" % port,
                       "--sortie", self.sortie, "--delai", "2"])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self.sortie))
        self.assertEqual(os.listdir(self.weyr), ["juiz.txt"])

    def test_dossier_de_sortie_absent_non_cree(self):
        creer_base(self.base, [("111111111", None)]).close()
        hbbs = FauxHbbs(set())
        hbbs.start()
        sortie = os.path.join(self.dir, "absent", "x.json")
        rc = rpe.main(["--base", self.base, "--hbbs", "127.0.0.1:%d" % hbbs.port,
                       "--sortie", sortie])
        hbbs.join(5)
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(os.path.dirname(sortie)))

    def test_precedent_illisible_ignore(self):
        with open(self.sortie, "w") as f:
            f.write("{pas du json")
        self.assertEqual(rpe.vus_precedents(self.sortie), {})


if __name__ == "__main__":
    unittest.main()
