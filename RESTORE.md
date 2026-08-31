# RESTORE.md

Procédure de restauration du backup glaurung (cf. `TODO.md` § Backup des données et
mémoire `project_glaurung_backup_plan`). **Statut au 2026-08-31** : l'export M6→pCloud
ne fonctionnait pas depuis le 02/08 (voir incident `Informatique/20260831_glaurung_backup_pcloud_jamais_pousse.md`),
corrigé ce jour. **Étape 1 (déchiffrement) testée avec succès** sur un backup réel
(2026-08-30, `fs.tar.gz.gpg` + les deux dumps SQL) — voir § Test de déchiffrement
ci-dessous. Le reste de la procédure (restauration DB, Ansible, Docker, test complet
sur VM VirtualBox) **n'a toujours pas été testé de bout en bout**.

**⚠️ Point bloquant découvert le 2026-08-31** : le seul backup FULL disponible
(2026-08-02) a été purgé par la logique de rétention pCloud — le marqueur `FULL` que
cette logique attend dans le dossier daté n'a jamais été trouvé dans
`/opt/backup-export/<date>/` sur aucun jour vérifié (27→31 août). Tant que ce bug n'est
pas corrigé côté `backup.sh` (glaurung, root), il n'existe **aucun FULL exploitable** :
seuls des diffs quotidiens existent, insuffisants pour une restauration complète.
Prochain FULL théorique : 2026-09-01 — à vérifier ce jour-là (tâche notée dans
`orga.perso.md`).

## Test de déchiffrement (2026-08-31)

Déchiffrement réel testé sur `fs.tar.gz.gpg`, `mariadb.sql.gz.gpg` et
`ttrss-postgres.sql.gz.gpg` du 2026-08-30 (récupérés directement depuis
`glaurung:/opt/backup-export/2026-08-30/`) :

```bash
gpg --batch --yes --output fs.tar.gz --decrypt fs.tar.gz.gpg
tar tzf fs.tar.gz | less

gpg --batch --yes --output mariadb.sql.gz --decrypt mariadb.sql.gz.gpg
zcat mariadb.sql.gz | grep -i "^CREATE TABLE\|^-- Current Database"

gpg --batch --yes --output ttrss-postgres.sql.gz --decrypt ttrss-postgres.sql.gz.gpg
zcat ttrss-postgres.sql.gz | grep -i "^CREATE TABLE"
```

Résultat : déchiffrement OK, contenu cohérent et non vide — `mariadb.sql.gz` contient
bien les deux bases `VOOSO` et `ttrss` avec des données réelles (tables `sb_*` remplies,
`ttrss_entries` avec des articles réels) ; `ttrss-postgres.sql.gz` contient le schéma
TT-RSS complet. `fs.tar.gz` contient `etc/letsencrypt/` (7 vhosts), `opt/rat/data/`
(plcoder.net + placedusport2.com complets), `opt/mindwtr/data/{cloud,ntfy,vaultwarden}`,
les dossiers home (`bot1`, `chatbot`, `chatbots`, `inbox0`).

**Points de vigilance relevés** :
- `opt/pub-daneel-net/data/` et `mbox` (périmètre documenté dans `CLAUDE.md` § Sauvegardes
  critiques) n'apparaissent dans aucun diff récent — normal si non modifiés depuis le
  FULL, mais **invérifiable tant qu'aucun FULL n'existe** (cf. point bloquant ci-dessus).
- Seul `db.sqlite3-wal` de Vaultwarden apparaît dans le diff, jamais `db.sqlite3`
  (fichier principal) ni `db.sqlite3-shm` — cohérent avec une copie de fichiers WAL
  SQLite pendant que la base est active. À vérifier lors d'un vrai test de restauration :
  une copie brute (tar) sans checkpoint SQLite préalable peut donner un état incohérent
  entre le fichier principal et le WAL. Envisager un `sqlite3 <db> "PRAGMA wal_checkpoint(TRUNCATE);"`
  avant le dump, ou documenter que la restauration doit tolérer ce cas (SQLite rejoue le
  WAL normalement à l'ouverture si les deux fichiers sont cohérents entre eux).

## Prérequis

- Accès au remote `pcloud:` (rclone, déjà configuré sur M6 — `pcloud:Glaurung/<date>/`)
- Clé privée de déchiffrement : pass perso, `hebergement/glaurung/backup_decrypt`
- Une VM/hôte cible (Debian, proche de la version de glaurung — vérifier
  `/etc/os-release` sur glaurung au moment du test) avec Docker installé
- Ce repo (`monserveur`) cloné sur la VM cible ou accessible depuis le poste de contrôle

## 1. Récupérer et déchiffrer les archives

```bash
# Depuis un poste avec l'accès pCloud (ex. M6)
rclone copy "pcloud:Glaurung/<date-du-dernier-FULL>/" /tmp/restore/full/
rclone copy "pcloud:Glaurung/<date-la-plus-recente>/" /tmp/restore/latest/

# Déchiffrement (clé privée exportée temporairement depuis le pass, cf. § Sécurité)
gpg --batch --yes --decrypt --output /tmp/restore/full/fs.tar.gz /tmp/restore/full/fs.tar.gz.gpg
gpg --batch --yes --decrypt --output /tmp/restore/full/mariadb.sql.gz /tmp/restore/full/mariadb.sql.gz.gpg
gpg --batch --yes --decrypt --output /tmp/restore/full/ttrss-postgres.sql.gz /tmp/restore/full/ttrss-postgres.sql.gz.gpg
# … idem pour /tmp/restore/latest/ si différent du full (cas normal, sauf test le jour du 1er du mois)
```

**Sécurité** : n'exporter la clé privée en clair que le temps du déchiffrement, dans un
répertoire non synchronisé (pas `~/Sync/`), puis la supprimer immédiatement après usage.

```bash
pass show hebergement/glaurung/backup_decrypt > /tmp/restore/backup_decrypt.asc
gpg --import /tmp/restore/backup_decrypt.asc
# ... déchiffrement ...
shred -u /tmp/restore/backup_decrypt.asc
```

## 2. Restaurer le filesystem (différentiel)

Le backup est **différentiel recalculé contre le full du mois** (pas en chaîne, cf.
TODO.md) : il suffit d'extraire le FULL puis le dernier DIFF disponible par-dessus —
pas besoin de rejouer toute la chaîne de diffs intermédiaires.

```bash
cd /  # ou la racine de restauration cible
tar --extract --listed-incremental=/dev/null --gzip --file=/tmp/restore/full/fs.tar.gz
tar --extract --listed-incremental=/dev/null --gzip --file=/tmp/restore/latest/fs.tar.gz
```

Restaure notamment `/opt/mindwtr/data/{cloud,vaultwarden,ntfy}`, `/etc/letsencrypt`,
`/opt/rat/data`, et les dossiers home (`bot1`, `chatbot`, `chatbots`, `inbox0`,
`oneclickpocket`, `mbox`, `discord_bot.py`).

## 3. Restaurer les bases de données

```bash
# MariaDB (installer/configurer MariaDB au préalable — pas encore couvert par un
# rôle Ansible, cf. TODO.md § Gaps de reconstruction)
zcat /tmp/restore/latest/mariadb.sql.gz | mysql

# Postgres TT-RSS (conteneur ttrss-docker_db démarré au préalable, cf. ~/ttrss-docker/)
zcat /tmp/restore/latest/ttrss-postgres.sql.gz | docker exec -i ttrss-docker-db-1 \
  psql -U "$TTRSS_DB_USER" "$TTRSS_DB_NAME"
```

## 4. Redéployer l'infrastructure (Ansible)

```bash
cd ~/www/c/monserveur/ansible
./run list glaurung.list run   # reconstruit Docker, réseau, Traefik, vhosts, rôles applicatifs
```

Certains éléments restent hors périmètre Ansible (cf. TODO.md § Gaps de reconstruction) :
Certbot (snap) lui-même, MariaDB natif (installation), 5 vhosts Apache
(`reader`, `bots.plcoder.net`, `lescoursdesophie.com` + variantes) — à réinstaller/
reconfigurer manuellement en attendant que ces gaps soient comblés.

## 5. Cas particulier — RustDesk

La clé privée `/opt/rustdesk/data/id_ed25519` est **hors du backup automatisé**, mais
sauvegardée une fois manuellement par Cédric dans le pass perso
(`weyr/rustdesk_clef_privee` — la clé publique correspondante est dans
`weyr/rustdesk_clef`, décision 2026-08-02). Restauration = réinjecter le fichier,
**pas** régénérer une nouvelle identité (ce qui casserait tous les clients déjà
configurés) :

1. Redéployer `rustdesk-setup` (inclus dans `glaurung.list`) — crée la structure
   `/opt/rustdesk/data/` (une nouvelle clé y est générée au premier démarrage)
2. **Avant** le premier démarrage du conteneur (ou en l'arrêtant s'il a déjà tourné) :
   `pass show weyr/rustdesk_clef_privee > /opt/rustdesk/data/id_ed25519`, permissions
   cohérentes avec le reste de `/opt/rustdesk/data/`, puis démarrer/redémarrer
   hbbs/hbbr
3. Vérifier que la clé publique effective correspond bien à `weyr/rustdesk_clef` (pas
   de redéploiement client nécessaire si c'est le cas)

## 6. Backup ponctuel du code des vhosts

Si le tag `vhost-code-once` a été joué au moins une fois avant l'incident, une archive
`vhosts-code-<date>.tar.gz.gpg` existe dans l'export pCloud — même procédure de
déchiffrement (§1), à extraire vers `/space/www/apps/`, `/var/www/bots.plcoder.net`,
`/var/www/relaibruno.daneel.net`, `/etc/apache2/sites-available`,
`/etc/apache2/sites-archive`.

## Checklist de validation post-restauration

- [ ] Conteneurs Docker tous `Up`/`healthy` (`docker ps -a`)
- [ ] Vaultwarden accessible, connexion avec un compte existant OK
- [ ] MindWTR accessible (`curl -sk https://mindwtr.daneel.net:8787/health`)
- [ ] ntfy accessible, topics existants
- [ ] TT-RSS accessible, flux existants présents (Postgres restauré)
- [ ] lescoursdesophie.com : base VOOSO accessible (MariaDB restauré)
- [ ] rat (plcoder.net/placedusport2.com) : données présentes dans `/opt/rat/data`
- [ ] Certificats Let's Encrypt présents et valides (ou à renouveler si expirés entre
      temps)

## Voir aussi

- `TODO.md` § Backup des données — plan et détail d'implémentation
- `CLAUDE.md` § Sauvegardes critiques — périmètre exact
- Mémoire Claude `project_glaurung_backup_plan` — historique des décisions
