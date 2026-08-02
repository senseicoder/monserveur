* revue sérieuse de la sécurité
  * suivi des failles et maj sécurité dans les containers
  * mesures actives qui bloquent les connexions en cas de détection d'attaque possible
  * firewall (en cours)
  * monitoring 
* services
  * annuaire SS personnel
  * bots
  * apifreebox/tuya
  * crontab cedric déjà en place à intégrer
  * plus largement, tout ce qui est dessus

## Phase 1 (restants)

- [ ] **Firewall** : `INPUT ACCEPT` sans règle + piège Docker/PREROUTING. Chaîne `DOCKER-USER` pour le trafic forwardé vers les conteneurs (ports publiés), chaîne `INPUT` pour les services de l'hôte (ex. MySQL, cf. rôle `rat-setup`). Ports à ouvrir : 22, 80, 443, 8000-8002, 8787, 22000, 21115-21117 (rustdesk, tcp), 21116 (rustdesk, udp).

## Phase 2

- [ ] **Traefik sur 80/443** : plan détaillé dans [PHASE2.md](PHASE2.md) (ACME HTTP-01 natif Traefik, remplace Apache+certbot)
- [ ] **Prérequis pour la bascule réelle de rat** (voir `~/www/c/rat-git/TODO.md`, backlog) : la bascule DNS/HTTPS réelle de `plcoder.net`/`placedusport2.com` suppose un accès public propre sur le port 443 standard — tant que Traefik reste sur `:8787` (non standard), la bascule réelle de rat est bloquée ou nécessite un pont intermédiaire (proxy Apache existant ?) à définir. À trancher avant de lancer la bascule réelle PLC/PDS2.
- [ ] **TT-RSS** : intégrer `~/ttrss-docker/` dans ce repo (templates `.j2` + vault), labels Traefik sur `web-nginx`
- [ ] **Dashboard Traefik** : activer derrière BasicAuth (`htpasswd -nB admin`, doubler les `$` dans le YAML)
- [ ] **Conteneur php** : formaliser le lancement
- [x] **Backup des données** — plan validé le 2026-08-02, **implémenté et testé de bout en bout le même jour** :
  - Architecture : cron root sur glaurung (`/etc/cron.d/glaurung-backup`, 3h30) fait le dump + chiffrement local (GPG asymétrique, clé publique `/opt/backup/glaurung-backup-pub.asc`, fingerprint `FF14418E0EB055017DF0AB72FBB17B44FFFEF469`) ; M6 (`/etc/cron.d/backup-vps`, 4h30, user **cedric** — pas root, le script n'a besoin d'aucun privilège sur M6, déployé via le rôle `backup-vps` du repo `maconfiguration` — pas posé à la main) tire les fichiers chiffrés via SSH (`~/Sync/Central/Dossiers/claude/script/backup-pull-pcloud.sh`, générique — hôtes listés dans `claude/data/backup-pull/hosts.conf`) et pousse vers pCloud (`rclone`). Aucun secret pCloud sur le VPS public.
  - Rôle Ansible glaurung : `ansible/roles/backup-setup/` + `ansible/backup.list`, dans `glaurung.list`. Correspond à la Phase 0 de [[glaurung-securite-plan]] (wiki).
  - **Premier run réel validé le 2026-08-02** : `fs.tar.gz.gpg` (185M), `mariadb.sql.gz.gpg` (12.6M), `ttrss-postgres.sql.gz.gpg` (24M) — dump + chiffrement OK sur glaurung, pull + push pCloud OK depuis M6 (`pcloud:Glaurung/2026-08-02/`), staging M6 nettoyé après push.
  - Séparation `/opt/backup` (root:root 0700, script + snapshots — contient le token ntfy) vs `/opt/backup-export` (root:cedric 0750, uniquement des fichiers déjà chiffrés) — évite tout accès root SSH depuis M6 vers glaurung, le compte `cedric` existant suffit puisque les payloads sont déjà chiffrés.
  - Marqueur `FULL` déposé par glaurung (reset du snapshot le 1er du mois OU absence de snapshot) — la rétention M6 s'appuie dessus, pas sur le jour du calendrier (sinon un premier run un autre jour que le 1er, comme celui du 2026-08-02, serait purgé après 14j au lieu d'être gardé 6 mois — repéré par Cédric avant que ça pose problème).
  - Chiffrement : clé privée dans le pass perso, `hebergement/glaurung/backup_decrypt`. Credential ntfy pour M6 dans `~/.config/backup-pull-pcloud/ntfy-token` (600, hors Sync/versionné, cf. pattern cron non surveillé).
  - Cron toujours via `/etc/cron.d/`, jamais crontab utilisateur — cf. [[adr-cron-toujours-etc-cron-d]] (wiki), appliqué aussi rétroactivement à `glaurung-healthcheck`.
  - Fréquence/méthode : quotidien en différentiel (`tar --listed-incremental`). Rétention dégressive sur pCloud : 6 mois pour les full, 2 semaines pour le quotidien.
  - Périmètre : `/opt/mindwtr/data/{cloud,vaultwarden,ntfy}`, `/etc/letsencrypt`, `/opt/rat/data`, `/opt/phpbb-integralsport/data` (ajouté 2026-08-02, déploiement de test migration.integralsport.com), MariaDB hôte (`VOOSO`, `ttrss` — legacy MySQL, TT-RSS tourne maintenant sur Postgres, à vérifier si encore utilisée — `phpbb_migration` ajoutée), Postgres `ttrss-docker_db`, dossiers home (`bot1`, `chatbot`, `chatbots`, `inbox0`, `oneclickpocket`, `mbox`).
  - **Reste à faire** : déclencher une fois `./run role backup-setup run --tags vhost-code-once` (backup **ponctuel** du code des vhosts, y compris `/space/www/apps/` — vrais docroots derrière des symlinks — et `sites-archive/relaibruno.daneel.net`, legacy conservé) ; supprimer le résidu vide `/opt/backup/staging` (ancienne version du rôle). Cron M6 posé via le rôle `backup-vps` (repo `maconfiguration`) et fix du marqueur FULL redéployé — **fait le 2026-08-02**.
  - **Process de restauration** : rédigé dans [RESTORE.md](RESTORE.md) (2026-08-02) — **pas encore testé**, le test complet sur une VM locale (VirtualBox, ramoth2) reste à faire, explicitement différé par Cédric à après la mise en place du backup lui-même.
  - Volumes Docker orphelins `deb` et `c34a0b6f0136...` : vérifiés vides (créés nov. 2024, jamais utilisés), hors périmètre, candidats à `docker volume prune`.
- [ ] **Gaps de reconstruction identifiés par l'audit du 2026-07-31** (détail complet dans wiki `postes/glaurung.md` § Audit reconstruction totale) — rôles Ansible manquants pour que `glaurung.list` couvre tout ce qui tourne réellement sur l'hôte (distinct du backup de données ci-dessus : ici il s'agit de pouvoir *redéployer* ces services depuis zéro, pas seulement sauvegarder leurs données). **Deux points de l'audit corrigés le 2026-08-02** après vérification du repo — `ntfy-deploy` et `glaurung-healthcheck` existent en fait depuis le 2026-07-28 (avant l'audit du 31/07, donc déjà faux au moment où l'audit a été écrit) et sont déjà dans `glaurung.list` :
  - Installation de Certbot (snap) lui-même — confirmé réel : les rôles existants (`ntfy-deploy`, `mindwtr-cloud-deploy`, `traefik-deploy`, `vaultwarden-deploy`) appellent tous `certbot certonly` mais aucun n'installe Certbot lui-même
  - MariaDB natif hôte (installation + dump/restore de `VOOSO` et `ttrss`) — confirmé réel : `firewall-setup` protège le port 3306 mais aucun rôle n'installe/configure MariaDB
  - Vhosts Apache hors périmètre : `reader.daneel.net`, `bots.plcoder.net`, `lescoursdesophie.com` + 3 variantes (`ssl.`, `sophie.daneel.net`, `sslsophie.daneel.net`) — **`ntfy.daneel.net` retiré de cette liste**, en fait déjà géré par le rôle `ntfy-deploy` (vhost + certbot, même pattern que mindwtr/vault)
  - ~~`ntfy-deploy` absent~~ / ~~rôle `glaurung-healthcheck` introuvable~~ : **obsolète, les deux rôles existent et sont dans `glaurung.list`** (vérifié 2026-08-02)
  - Host keys SSH, `sudoers`, inventaire des paquets hors Ansible (Python compilés à la main) — non auditables sans accès `become`, à faire avec Cédric présent

## Dette technique / refactoring

- [ ] **À vérifier** : dans `docker-network-mindwtr-setup`, le loop d'arrêt de la stack avant reconfiguration Docker/réseau ne couvre que `traefik` et `mindwtr`, pas `vaultwarden` — comportement repris tel quel de l'ancien rôle monolithique, jamais confirmé volontaire. Si le réseau `mindwtr` est recréé (IPv6 absent détecté), Vaultwarden pourrait rester connecté à l'ancien réseau jusqu'à son propre redémarrage.
- [ ] **À revoir** : cohérence du nommage réseau Docker `mindwtr` — créé indépendamment du conteneur/service `mindwtr-cloud` (rôle `docker-network-mindwtr-setup`) mais aussi rejoint par `vaultwarden` et `rat-web`. Le nom porte à confusion : ce n'est pas un réseau propre au service mindwtr, c'est le réseau bridge commun de toute la stack. À clarifier — renommage (ex. `stack` ou `glaurung`) ou documentation explicite du partage.
- [ ] **Simplification du rôle `rat-setup`/`rat-migratefromgandi`** (voir détail dans `~/www/c/rat-git/TODO.md`) : symlinks fichier-par-fichier dans `admin/`, chemin racine + nom de domaine codés en dur à plusieurs endroits (Dockerfile, vhosts Apache, docker-compose, symlinks), 3 tâches Ansible distinctes pour construire `admin/` — à fusionner/factoriser.
