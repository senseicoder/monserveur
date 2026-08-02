# RESTORE.md

Procédure de restauration du backup glaurung (cf. `TODO.md` § Backup des données et
mémoire `project_glaurung_backup_plan`). **Statut : rédigé le 2026-08-02, pas encore
testé** — le test complet sur une VM locale (VirtualBox, ramoth2) reste à faire (cf.
TODO.md, différé volontairement par Cédric à après la mise en place du backup
lui-même). Ne pas considérer cette procédure fiable tant qu'elle n'a pas été exécutée
de bout en bout au moins une fois.

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
