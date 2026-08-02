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
- [ ] **Backup des données** — plan validé le 2026-08-02, reste à implémenter :
  - Architecture : cron **root** sur glaurung fait le dump + chiffrement local (asymétrique GPG, clé publique déjà déployée dans `/home/cedric/glaurung-backup-pub.asc`, fingerprint `FF14418E0EB055017DF0AB72FBB17B44FFFEF469`) ; M6 (poste des crons Juiz) vient chercher (pull SSH) le dump chiffré et le pousse vers pCloud (remote `rclone pcloud` déjà configuré sur M6). Aucun secret pCloud sur le VPS public.
  - Emplacement du rôle Ansible côté glaurung : `ansible/roles/backup-setup/` dans ce repo (nouveau `ansible/backup.list`, joué via `./run list backup.list run`, même convention que les autres rôles étroits).
  - Emplacement du script pull+push côté M6 : hors de ce repo, dans `~/Sync/Central/Dossiers/claude/script/` (convention scripts Claude). **Cédric a signalé que glaurung ne sera pas le seul hôte à couvrir bientôt** — concevoir ce script comme générique (host en paramètre/config, pas de nom d'hôte en dur) plutôt que spécifique à glaurung, pour éviter de le réécrire au premier deuxième hôte.
  - Chiffrement : clé privée de déchiffrement dans le pass perso de Cédric, `hebergement/glaurung/backup_decrypt` (sans passphrase sur la clé elle-même, protégée par le chiffrement du pass store).
  - Fréquence/méthode : quotidien en **différentiel** (`tar --listed-incremental`, snapshot figé recalculé contre le 1er du mois, pas en chaîne).
  - Rétention dégressive sur pCloud : 6 mois pour les sauvegardes du 1er de chaque mois, 2 semaines pour le quotidien.
  - Périmètre : `/opt/mindwtr/data/cloud`, `/opt/mindwtr/data/vaultwarden`, `/opt/mindwtr/data/ntfy`, `/etc/letsencrypt`, `/opt/rat/data`, **+ ajout legacy découvert le 2026-08-02** : dump MariaDB hôte (bases `lescoursdesophie.com`/`sophie.daneel.net`, jamais sauvegardées), dump Postgres du volume `ttrss-docker_db`, et les petits dossiers home (`bot1`, `chatbot`, `chatbots`, `inbox0`, `oneclickpocket`, `mbox`) — en attente de réintégration dans le projet domotique ou un futur projet bot, mais ont de la valeur en l'état.
  - Backup **ponctuel** (une seule fois, pas récurrent) du code de tous les vhosts actifs et archivés (y compris `sites-archive/relaibruno.daneel.net`, legacy conservé pour le moment) — le code ne devrait plus changer.
  - Alerting : notification `ntfy` (déjà déployé sur glaurung) en cas d'échec du dump ou du pull M6.
  - **Process de restauration complète à documenter et tester sur une VM locale au poste de dev** avant de considérer le backup fiable — restaurer depuis un export pCloud vers une VM neuve, valider chaque service (Vaultwarden, mindwtr, ntfy, rat, MariaDB, ttrss).
  - Volumes Docker orphelins `deb` et `c34a0b6f0136...` : vérifiés vides (nov. 2024), hors périmètre, candidats à `docker volume prune`.

## Dette technique / refactoring

- [ ] **À vérifier** : dans `docker-network-mindwtr-setup`, le loop d'arrêt de la stack avant reconfiguration Docker/réseau ne couvre que `traefik` et `mindwtr`, pas `vaultwarden` — comportement repris tel quel de l'ancien rôle monolithique, jamais confirmé volontaire. Si le réseau `mindwtr` est recréé (IPv6 absent détecté), Vaultwarden pourrait rester connecté à l'ancien réseau jusqu'à son propre redémarrage.
- [ ] **À revoir** : cohérence du nommage réseau Docker `mindwtr` — créé indépendamment du conteneur/service `mindwtr-cloud` (rôle `docker-network-mindwtr-setup`) mais aussi rejoint par `vaultwarden` et `rat-web`. Le nom porte à confusion : ce n'est pas un réseau propre au service mindwtr, c'est le réseau bridge commun de toute la stack. À clarifier — renommage (ex. `stack` ou `glaurung`) ou documentation explicite du partage.
- [ ] **Simplification du rôle `rat-setup`/`rat-migratefromgandi`** (voir détail dans `~/www/c/rat-git/TODO.md`) : symlinks fichier-par-fichier dans `admin/`, chemin racine + nom de domaine codés en dur à plusieurs endroits (Dockerfile, vhosts Apache, docker-compose, symlinks), 3 tâches Ansible distinctes pour construire `admin/` — à fusionner/factoriser.
