#!/usr/bin/env python3
"""Migration idempotente de puttini.db (ADR-013 + geofencing #54, PR #66/#67).
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
    # Santé des services Android déclarée dans le heartbeat (issue #64).
    # Toutes nullables : NULL veut dire "l'appareil n'a rien déclaré", ce qui
    # est le cas de toutes les lignes déjà en base et de toutes les sources
    # autres que l'app Android — à ne pas confondre avec "service arrêté".
    ("positions", "foreground_service_active", "BOOLEAN"),
    ("positions", "work_manager_scheduled", "BOOLEAN"),
    ("positions", "missing_permissions", "TEXT"),
    ("positions", "run_attempt_count", "INTEGER"),
    ("positions", "last_heartbeat_success", "DATETIME"),
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
