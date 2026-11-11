#!/usr/bin/env python3
<<<<<<< HEAD
"""Migration idempotente de puttini.db (ADR-013 + geofencing #54, PR #66/#67, clé lecture seule ADR-014 #92, état réseau #108).
=======
"""Migration idempotente de puttini.db (ADR-013 + geofencing #54, PR #66/#67, clé lecture seule ADR-014 #92, notification par liaison #109).
>>>>>>> origin/master
Base.metadata.create_all() ne crée que les tables manquantes, jamais les
colonnes manquantes sur une table existante — d'où ce script, exécuté dans le
conteneur en cours (docker exec) avant le redémarrage sur la nouvelle image."""
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = "/data/puttini.db"

MIGRATIONS = [
    ("devices", "battery_alert_threshold_pct", "INTEGER"),
    ("device_zones", "inside", "BOOLEAN"),
    # Clé API en lecture seule pour c3po (ADR-014 puttini, PR #92) : fausse pour les clés existantes
    ("api_keys", "lecture_seule", "BOOLEAN NOT NULL DEFAULT 0"),
    # Notification en temps réel par liaison zone ↔ appareil (puttini#109) : désactivée
    # pour les liaisons existantes comme pour les nouvelles (décision du 07/11/2026)
    ("device_zones", "notify", "BOOLEAN NOT NULL DEFAULT 0"),
    # Dernier état notifié par liaison (puttini#112, revue du 11/11) : NULL pour les liaisons
    # existantes, aligné sans notification au premier relevé
    ("device_zones", "notified_inside", "BOOLEAN"),
    # État réseau de la remontée (puttini#108) : wifi / wifi_masque / mobile / ethernet / aucun ;
    # NULL pour les lignes existantes et les sources qui ne le déclarent pas (pyicloud)
    ("positions", "network", "TEXT"),
]


def column_exists(conn, table, column):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def main():
    backup_path = f"{DB_PATH}.bak-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup créé : {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        for table, column, coltype in MIGRATIONS:
            if column_exists(conn, table, column):
                print(f"SKIP — {table}.{column} existe déjà")
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            conn.commit()
            print(f"OK — {table}.{column} ({coltype}) ajoutée")

        for table, column, _ in MIGRATIONS:
            assert column_exists(conn, table, column), f"{table}.{column} toujours absente après migration"
        print("Vérification post-migration OK")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(1)
