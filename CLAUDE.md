# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Notes wiki** : voir le wiki personnel de Cédric, page `postes/glaurung.md` (synthèse opérationnelle), `services/vaultwarden.md`, `services/rustdesk.md`.

## Objectif

Infrastructure as code pour le VPS personnel `glaurung` (Debian 9 stretch). Déploie des services auto-hébergés via Docker + Ansible.

## État de production sur glaurung (au 2026-07-11)

### Réseau hôte
| Port | Bind | Usage |
|------|------|-------|
| 22 | 0.0.0.0 | SSH |
| 80 / 443 | ::: | Apache2 hôte (vhosts, certbot) |
| 3306 | 127.0.0.1 | MySQL (conteneur `php`) |
| 8000–8002 | 0.0.0.0 | Chatbots (publics, hors scope) |
| 8028 | 127.0.0.1 | TT-RSS nginx |
| 8384 | 127.0.0.1 | Syncthing UI |
| 8787 | 0.0.0.0 | Traefik → mindwtr-cloud ✅ Phase 1 déployée |
| 22000 | ::: | Syncthing sync |
| 21115-21116 | 0.0.0.0 | RustDesk hbbs (tcp), 21116 aussi udp — hors Traefik ✅ |
| 21117 | 0.0.0.0 | RustDesk hbbr (tcp) — hors Traefik ✅ |

### Apache2 — vhosts actifs (`/etc/apache2/sites-enabled/`)
| Vhost | Ports | Notes |
|-------|-------|-------|
| `mindwtr.daneel.net` | 80 | Vhost certbot webroot (géré par ce repo) |
| `reader.daneel.net` | 80 + 443 | → proxy ttrss (127.0.0.1:8028) |
| `bots.plcoder.net` | 80 + 443 | → chatbots |
| `lescoursdesophie.com` | 80 | |
| `ssl.lescoursdesophie.com` | 80 | |
| `sophie.daneel.net` | 80 | |
| `sslsophie.daneel.net` | 80 | |

Certbot installé via **snap** (v5.6.0, mode classic), **pas apt**. Certs : `bots.plcoder.net`, `reader.daneel.net`, `mindwtr.daneel.net`, `vault.daneel.net`.

### Conteneurs Docker actifs
| Conteneur | Image | Notes |
|-----------|-------|-------|
| `traefik` | `traefik:v3` | Port 8787/HTTPS, réseau mindwtr ✅ |
| `mindwtr-cloud` | `ghcr.io/dongdongbh/mindwtr-cloud:latest` | Healthy, réseau mindwtr ✅ |
| `vaultwarden` | `vaultwarden/server:latest` | vault.daneel.net:8787, réseau mindwtr |
| `php` | `debian:11` | Shell PHP ponctuel, lancé manuellement hors Compose |
| `ttrss-docker-*` (×4) | `cthulhoo/ttrss-*` + `postgres:12-alpine` | Géré depuis `~/ttrss-docker/` |
| `rustdesk-hbbs` | `rustdesk/rustdesk-server:latest` | Ports directs sur l'hôte, hors réseau Docker mindwtr ✅ |
| `rustdesk-hbbr` | `rustdesk/rustdesk-server:latest` | Ports directs sur l'hôte, hors réseau Docker mindwtr ✅ |

### Réseaux Docker existants
| Réseau | Subnet | Conteneurs |
|--------|--------|------------|
| `bridge` | 172.17.0.0/16 | php |
| `ttrss-docker_default` | 172.23.0.0/16 | stack ttrss |
| `mindwtr` | (auto) | traefik, mindwtr-cloud |

### Firewall
**INPUT ACCEPT sans règle** — pas de pare-feu hôte. Docker injecte ses règles en PREROUTING/DNAT, ce qui contourne INPUT. Filtrage Docker à faire via chaîne `DOCKER-USER`.

## Architecture Phase 1 (déployée le 2026-06-20)

```
client  →  8787/HTTPS  →  Traefik v3 (TLS via certs certbot, dashboard désactivé)
                               │  réseau Docker "mindwtr"
                               └── mindwtr-cloud:8787

certbot (HTTP-01, webroot)  →  /etc/letsencrypt/live/mindwtr.daneel.net/
certs copiés dans            →  /opt/mindwtr/certs/ (isolation Traefik)
hook post-renewal            →  docker restart traefik
```

**URL client Mindwtr :** `https://mindwtr.daneel.net:8787/v1`  
**Test :** `curl -sk https://mindwtr.daneel.net:8787/health` → `{"ok":true}`

## Structure du repo

```
ansible/
├── ansible.cfg                   ← inventory local, vault via .vault_passw.sh
├── inventory/hosts.yml           ← inventaire local (host unique : glaurung)
├── .vault_passw.sh               ← cmdp hebergements/mindwtr/vault | head -1
├── group_vars/all/
│   ├── vars.yml                  ← mindwtr_deploy_dir, mindwtr_domain, acme_email
│   ├── vault.yml                 ← mindwtr_token (chiffré, versionné)
│   └── vault.yml.example         ← modèle
├── requirements.yml              ← collection community.docker
├── run                           ← wrapper, dry-run par défaut, ANSIBLE_ROLES_PATH → infra-deploy si présent
├── run_role.yml                  ← playbook générique "role", handlers Compose centralisés (cf. note ci-dessous)
├── mindwtr.list / rat.list / rustdesk.list / security.list
└── roles/
    ├── docker-engine-setup/      ← install Docker CE + plugin Compose
    ├── network-ipv6-setup/       ← forwarding IPv6 kernel + service systemd ipv6-default-route
    ├── docker-network-mindwtr-setup/  ← daemon.json IPv6 + réseau Docker mindwtr (down/up des 3 stacks si reconfig)
    ├── traefik-deploy/           ← répertoires, docker-compose.traefik.yml, TLS dynamique, hook certbot, start
    │   └── templates/
    │       ├── docker-compose.traefik.yml.j2
    │       ├── traefik-tls.yml.j2                ← TLS file provider (mindwtr + vault)
    │       └── certbot-renewal-hook.sh.j2         ← copie certs + restart traefik
    ├── mindwtr-cloud-deploy/     ← data/cloud, docker-compose.mindwtr.yml, vhost+certbot mindwtr, start
    ├── vaultwarden-deploy/       ← data/vaultwarden, docker-compose.vaultwarden.yml, vhost+certbot vault, start
    ├── rustdesk-setup/           ← hbbs/hbbr RustDesk, hors Traefik (ports directs sur l'hôte), joué via ./run list rustdesk.list
    └── ssh-securite/             ← durcissement sshd (PasswordAuthentication/PermitRootLogin/AllowUsers), joué via ./run list security.list
```

Plus de playbook global : chaque profil (`*.list`) se joue indépendamment via `./run list`, il n'y a plus de séquence unique équivalente à l'ancien `install.yml`.

Découpage issu de l'ancien rôle monolithique `infra-deploy` (cf. `RAPPROCHEMENT_INFRA_DEPLOY.md` à la racine du repo pour l'historique et le détail par rôle). **Handlers `restart traefik`/`restart mindwtr`/`restart vaultwarden` centralisés dans `run_role.yml`** (pas dans les rôles) : `./run list` joue chaque rôle d'une liste dans une invocation `ansible-playbook` séparée, donc un handler défini dans un rôle ne serait pas visible par un autre rôle du même run qui le notifie (ex. `vaultwarden-deploy` notifie `restart traefik`).

## Commandes

### Déployer / redéployer

```bash
cd ansible && ./run list mindwtr.list run   # stack mindwtr complète, exécution réelle
cd ansible && ./run list mindwtr.list       # dry-run (par défaut, sans "run")
cd ansible && ./run role traefik-deploy run # un seul rôle
```

Les tâches sont idempotentes (Docker, réseau, certbot, vhost skippés si déjà en place).

### Vérifier les services sur le serveur

```bash
docker-compose -f /opt/mindwtr/docker-compose.traefik.yml ps
docker-compose -f /opt/mindwtr/docker-compose.mindwtr.yml ps
```

## Pièges Docker sur glaurung

**seccomp Docker 19.03 + apps Rust/Go modernes** : le profil seccomp de Docker 19.03 ne whitelist pas `clone3` (ajouté Linux 5.3+). Les runtimes récents (Tokio 1.x pour Rust) l'utilisent pour spawner des threads → panic `OS can't spawn worker thread: Operation not permitted`. Fix : ajouter `security_opt: ["seccomp:unconfined"]` dans le compose du service concerné. Inutile si Docker est upgradé vers 20.10+.

**URL clients Vaultwarden** : saisir uniquement `https://<domaine>:<port>` dans le champ "URL du serveur". Les autres champs (API, Identity, Icons, Notifications, Events) sont déduits automatiquement par le client.

## Ajouter un nouveau service Docker

### Derrière Traefik (recommandé)

1. Rejoindre le réseau externe `mindwtr`
2. Labels dans le Compose :
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.<nom>.rule=Host(`<domaine>`)"
     - "traefik.http.routers.<nom>.entrypoints=mindwtr"
     - "traefik.http.routers.<nom>.tls=true"
     - "traefik.http.services.<nom>.loadbalancer.server.port=<port interne>"
   ```
3. **TLS file provider** — Traefik n'a pas d'ACME (Apache tient 80/443). Pour chaque nouveau domaine :
   - Obtenir un cert certbot : `certbot certonly --webroot -w /var/www/html -d <domaine>`
   - Copier les certs dans `/opt/mindwtr/certs/` (ou un sous-dossier dédié)
   - Mettre à jour `traefik-tls.yml.j2` pour référencer les nouveaux certs
   - Tout nouveau domaine certbot nécessite un **vhost Apache dédié** (voir section ci-dessous)
4. **Entrypoint unique** : `mindwtr` = port 8787. Tous les services Traefik actuels sont sur 8787 (non standard). Phase 2 = Traefik sur 80/443.
5. **Healthcheck** : utiliser `127.0.0.1` et non `localhost` — avec IPv6 activé, `localhost` résout en `::1` et échoue si le service n'écoute qu'en IPv4.

### Hors Traefik (services non-HTTP)

Certains services ne parlent pas HTTP (protocole TCP/UDP brut avec chiffrement propre) et ne peuvent pas passer par le routeur HTTP de Traefik. Exemple : `rustdesk` (rôle `roles/rustdesk-setup/`), qui expose `hbbs`/`hbbr` directement sur l'hôte via `ports:` dans le Compose, sans certbot ni Traefik.

1. Nouveau rôle Ansible dédié plutôt que d'ajouter à un rôle existant (`traefik-deploy`, `mindwtr-cloud-deploy`, `vaultwarden-deploy` sont volontairement étroits, cf. `RAPPROCHEMENT_INFRA_DEPLOY.md`)
2. `ports:` mappés directement sur l'hôte dans le template Compose (pas de réseau `mindwtr`, pas de labels Traefik)
3. Si le service persiste un secret généré au premier démarrage (ex. clé RustDesk `id_ed25519`), monter un volume dédié — sinon chaque redéploiement/recréation régénère le secret et casse les clients déjà configurés
4. Ajouter le rôle à un `*.list` existant, ou en créer un nouveau (cf. `RAPPROCHEMENT_INFRA_DEPLOY.md` § Profils de rôles)

### DNS pour un nouveau domaine

`glaurung.daneel.net` a un A (`51.254.212.250`) + AAAA (`2001:41d0:302:2100::4203`). Un CNAME vers `glaurung.daneel.net` hérite des deux enregistrements et fonctionnera en IPv4 et IPv6. Utiliser un A direct si on veut exclure l'IPv6.

### Subnets à ne pas chevaucher

| Réseau | Subnet IPv4 | Subnet IPv6 |
|--------|-------------|-------------|
| bridge | 172.17.0.0/16 | — |
| ttrss-docker_default | 172.23.0.0/16 | — |
| mindwtr | auto | fd00:0:0:1::/64 |

Nouveau réseau : choisir un subnet `172.x.0.0/16` libre, et `fd00:0:0:N::/64` différent si IPv6 nécessaire.

## Infra Apache / certbot sur glaurung — points critiques

- Vhosts dans `/etc/apache2/sites-available/*.conf` — **générés automatiquement** par les templates Ansible de ce repo. Chaque vhost a un dossier `.d/` pour snippets additionnels.
- Les vhosts existants écoutent sur les IPs **explicites** du serveur (`51.254.212.250:80` et `[2001:41d0:302:2100::4203]:80`). Un vhost `*:80` est dans un groupe de priorité inférieure et ne s'applique **jamais** — le vhost certbot doit déclarer les mêmes IPs explicites.
- Certbot via snap, `--webroot -w /var/www/html`. Le challenge HTTP-01 nécessite un vhost Apache dédié pour le domaine (sans lui, Apache redirige vers `bots.plcoder.net:443` qui timeout).
- Hook de renouvellement : `/etc/letsencrypt/renewal-hooks/deploy/reload-traefik.sh` — copie les certs dans `/opt/mindwtr/certs/` et `docker restart traefik`.
- **Docker Compose** sur glaurung : version 1 (`docker-compose` avec trait d'union). Pas de plugin Compose v2 (`docker compose`) — le serveur tourne sur Debian stretch avec Docker installé manuellement.
- Modules Apache actifs : proxy, proxy_http, proxy_fcgi, rewrite, ssl, headers.
- **Filtre IPv6 dans les templates Apache** : `ansible_all_ipv6_addresses` inclut les IPs Docker internes (`fd00::/8`). Filtrer `^fe80` seul ne suffit pas — filtrer aussi `^fd` et `^fc`. Sans ça, le VirtualHost est déclaré sur `fd00:0:0:1::1` au lieu de l'IP publique OVH, Let's Encrypt ne trouve pas le challenge et échoue.

## Todos Phase 1 (restants)

- [ ] **Firewall** : INPUT ACCEPT sans règle + piège Docker/PREROUTING. Utiliser la chaîne `DOCKER-USER` pour filtrer. Ports à ouvrir : 22, 80, 443, 8000-8002, 8787, 22000, 21115-21117 (rustdesk, tcp), 21116 (rustdesk, udp).
- [x] **IPv6 full-stack** : activé — daemon.json, réseau mindwtr `fd00:0:0:1::/64`, forwarding kernel, route par défaut OVH via service systemd `ipv6-default-route`. `mindwtr.daneel.net` est un CNAME → `glaurung.daneel.net` (A + AAAA). Android vérifié en WiFi et mobile.

## Dette technique / refactoring

- ~~Découper le rôle `infra-deploy`~~ **Fait** — 6 rôles (`docker-engine-setup`, `network-ipv6-setup`, `docker-network-mindwtr-setup`, `traefik-deploy`, `mindwtr-cloud-deploy`, `vaultwarden-deploy`), joués en séquence via `./run list mindwtr.list`. Détail dans `RAPPROCHEMENT_INFRA_DEPLOY.md`.
- **À vérifier** : dans `docker-network-mindwtr-setup`, le loop d'arrêt de la stack avant reconfiguration Docker/réseau ne couvre que `traefik` et `mindwtr`, pas `vaultwarden` — comportement repris tel quel de l'ancien rôle monolithique, jamais confirmé volontaire. Si le réseau `mindwtr` est recréé (IPv6 absent détecté), Vaultwarden pourrait rester connecté à l'ancien réseau jusqu'à son propre redémarrage.
- **À revoir** : cohérence du nommage réseau Docker `mindwtr` — créé indépendamment du conteneur/service `mindwtr-cloud` (rôle `docker-network-mindwtr-setup`) mais aussi rejoint par `vaultwarden` (et `traefik`). Le nom porte à confusion : ce n'est pas un réseau propre au service mindwtr, c'est le réseau bridge commun de toute la stack. À clarifier — renommage (ex. `stack` ou `glaurung`) ou documentation explicite du partage.

## Phase 2 (à faire)

- **Traefik sur 80/443** : plan détaillé en étapes dans [PHASE2.md](PHASE2.md) (établi le 2026-07-16 — inclut la bascule ACME HTTP-01 natif Traefik, qui remplace l'ancienne piste DNS-01/OVH, erronée : le DNS est chez Gandi et HTTP-01 suffit une fois Traefik sur le port 80)
- **TT-RSS** : intégrer `~/ttrss-docker/` dans ce repo (templates `.j2` + vault), labels Traefik sur `web-nginx`
- **Dashboard Traefik** : activer derrière BasicAuth (`htpasswd -nB admin`, doubler les `$` dans le YAML)
- **Conteneur php** : formaliser le lancement
- **Backup des données** : analyser et mettre en place une sauvegarde effective des chemins listés en § Sauvegardes critiques (`data/cloud`, `data/vaultwarden`, `/etc/letsencrypt`) — aujourd'hui seulement documentés, aucun mécanisme de backup réel

## Vaultwarden — setup initial

**URL :** `https://vault.daneel.net:8787`

`SIGNUPS_ALLOWED=false` par défaut (sécurité). Deux options pour créer le premier compte :

**Option A — ADMIN_TOKEN (recommandé)** : ajouter `vaultwarden_admin_token: "..."` dans `vault.yml` (`ansible-vault edit ansible/group_vars/all/vault.yml`), redéployer, puis créer l'utilisateur via `https://vault.daneel.net:8787/admin`.

**Option B — signup temporaire** : passer `SIGNUPS_ALLOWED: "true"` dans le template, déployer, créer le compte, remettre `false`.

Données persistées dans `/opt/mindwtr/data/vaultwarden/` (uid 1000).

## Sauvegardes critiques

- `/opt/mindwtr/data/cloud/` — données sync Mindwtr
- `/opt/mindwtr/data/vaultwarden/` — données Vaultwarden (mots de passe)
- `/etc/letsencrypt/` — certificats TLS (renouvellement auto via certbot snap)
