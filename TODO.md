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
- [ ] **Backup des données** : analyser et mettre en place une sauvegarde effective des chemins listés en § Sauvegardes critiques de `CLAUDE.md` — aujourd'hui seulement documentés, aucun mécanisme de backup réel. Inclut désormais `/opt/rat/data/` (données réelles migrées de Gandi, plcoder.net + placedusport2.com — pas de sauvegarde du tout à ce jour). Étendu par l'audit du 2026-07-31 (voir wiki `postes/glaurung.md` § Audit reconstruction totale) : s'applique aussi à ntfy (`/opt/mindwtr/data/ntfy/`, jamais documenté avant cet audit), MariaDB natif (VOOSO/ttrss) et au volume Postgres TT-RSS.
- [ ] **Gaps de reconstruction identifiés par l'audit du 2026-07-31** (détail complet dans wiki `postes/glaurung.md` § Audit reconstruction totale) — rôles Ansible manquants pour que `glaurung.list` couvre tout ce qui tourne réellement sur l'hôte :
  - Installation de Certbot (snap) lui-même — les rôles existants scriptent l'obtention de certs mais supposent Certbot déjà présent
  - `ntfy-deploy` (conteneur actif en prod, absent de `mindwtr.list`/`glaurung.list`/`roles/`)
  - MariaDB natif hôte (installation + dump/restore de `VOOSO` et `ttrss`)
  - Vhosts Apache hors périmètre : `reader.daneel.net`, `bots.plcoder.net`, `ntfy.daneel.net`, `lescoursdesophie.com` + 3 variantes (`ssl.`, `sophie.daneel.net`, `sslsophie.daneel.net`)
  - Rôle `glaurung-healthcheck` référencé dans le wiki (cron `*/10 * * * *`) mais introuvable dans `ansible/roles/` — à vérifier (renommé ? jamais commité ?)
  - Host keys SSH, `sudoers`, inventaire des paquets hors Ansible (Python compilés à la main) — non auditables sans accès `become`, à faire avec Cédric présent

## Dette technique / refactoring

- [ ] **À vérifier** : dans `docker-network-mindwtr-setup`, le loop d'arrêt de la stack avant reconfiguration Docker/réseau ne couvre que `traefik` et `mindwtr`, pas `vaultwarden` — comportement repris tel quel de l'ancien rôle monolithique, jamais confirmé volontaire. Si le réseau `mindwtr` est recréé (IPv6 absent détecté), Vaultwarden pourrait rester connecté à l'ancien réseau jusqu'à son propre redémarrage.
- [ ] **À revoir** : cohérence du nommage réseau Docker `mindwtr` — créé indépendamment du conteneur/service `mindwtr-cloud` (rôle `docker-network-mindwtr-setup`) mais aussi rejoint par `vaultwarden` et `rat-web`. Le nom porte à confusion : ce n'est pas un réseau propre au service mindwtr, c'est le réseau bridge commun de toute la stack. À clarifier — renommage (ex. `stack` ou `glaurung`) ou documentation explicite du partage.
- [ ] **Simplification du rôle `rat-setup`/`rat-migratefromgandi`** (voir détail dans `~/www/c/rat-git/TODO.md`) : symlinks fichier-par-fichier dans `admin/`, chemin racine + nom de domaine codés en dur à plusieurs endroits (Dockerfile, vhosts Apache, docker-compose, symlinks), 3 tâches Ansible distinctes pour construire `admin/` — à fusionner/factoriser.
