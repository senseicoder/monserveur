# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Objectif

Infrastructure as code pour le VPS personnel `glaurung` (Debian 9 stretch). Déploie des services auto-hébergés via Docker + Ansible.

## État de production sur glaurung (au 2026-06-21)

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

Certbot installé via **snap** (v5.6.0, mode classic), **pas apt**. Certs : `bots.plcoder.net`, `reader.daneel.net`, `mindwtr.daneel.net`.

### Conteneurs Docker actifs
| Conteneur | Image | Notes |
|-----------|-------|-------|
| `traefik` | `traefik:v3` | Port 8787/HTTPS, réseau mindwtr ✅ |
| `mindwtr-cloud` | `ghcr.io/dongdongbh/mindwtr-cloud:latest` | Healthy, réseau mindwtr ✅ |
| `php` | `debian:11` | Shell PHP ponctuel, lancé manuellement hors Compose |
| `ttrss-docker-*` (×4) | `cthulhoo/ttrss-*` + `postgres:12-alpine` | Géré depuis `~/ttrss-docker/` |

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
├── ansible.cfg                   ← inventory Epiconcept, vault via .vault_passw.sh
├── inventory/hosts.yml           ← doc seulement (inventaire réel : ~/Sync/Epiconcept/inventory/)
├── .vault_passw.sh               ← cmdp hebergements/mindwtr/vault | head -1
├── group_vars/all/
│   ├── vars.yml                  ← mindwtr_domain, acme_email
│   ├── vault.yml                 ← mindwtr_token (chiffré, versionné)
│   └── vault.yml.example         ← modèle
├── requirements.yml              ← collection community.docker
├── install.yml                   ← playbook principal
└── roles/
    ├── infra-deploy/             ← rôle Phase 1
    │   ├── defaults/main.yml     ← deploy_dir=/opt/mindwtr
    │   ├── handlers/main.yml     ← restart traefik, restart mindwtr
    │   ├── tasks/main.yml
    │   └── templates/
    │       ├── apache-mindwtr.conf.j2        ← vhost HTTP-01 certbot
    │       ├── docker-compose.traefik.yml.j2
    │       ├── docker-compose.mindwtr.yml.j2
    │       ├── traefik-tls.yml.j2            ← TLS file provider
    │       └── certbot-renewal-hook.sh.j2
    └── ssh-securite/             ← durcissement SSH (stub, Phase 2)
```

## Commandes

### Déployer / redéployer

```bash
cd ansible && ansible-playbook install.yml --limit glaurung
```

Les tâches sont idempotentes (Docker, réseau, certbot, vhost skippés si déjà en place).

### Vérifier les services sur le serveur

```bash
docker-compose -f /opt/mindwtr/docker-compose.traefik.yml ps
docker-compose -f /opt/mindwtr/docker-compose.mindwtr.yml ps
```

## Infra Apache / certbot sur glaurung — points critiques

- Vhosts dans `/etc/apache2/sites-available/*.conf` — **générés automatiquement** par l'outillage Epiconcept. Chaque vhost a un dossier `.d/` pour snippets additionnels.
- Les vhosts existants écoutent sur les IPs **explicites** du serveur (`51.254.212.250:80` et `[2001:41d0:302:2100::4203]:80`). Un vhost `*:80` est dans un groupe de priorité inférieure et ne s'applique **jamais** — le vhost certbot doit déclarer les mêmes IPs explicites.
- Certbot via snap, `--webroot -w /var/www/html`. Le challenge HTTP-01 nécessite un vhost Apache dédié pour le domaine (sans lui, Apache redirige vers `bots.plcoder.net:443` qui timeout).
- Hook de renouvellement : `/etc/letsencrypt/renewal-hooks/deploy/reload-traefik.sh` — copie les certs dans `/opt/mindwtr/certs/` et `docker restart traefik`.
- **Docker Compose** sur glaurung : version 1 (`docker-compose` avec trait d'union). Pas de plugin Compose v2 (`docker compose`) — le serveur tourne sur Debian stretch avec Docker installé manuellement.
- Modules Apache actifs : proxy, proxy_http, proxy_fcgi, rewrite, ssl, headers.

## Todos Phase 1 (restants)

- [ ] **Firewall** : INPUT ACCEPT sans règle + piège Docker/PREROUTING. Utiliser la chaîne `DOCKER-USER` pour filtrer. Ports à ouvrir : 22, 80, 443, 8000-8002, 8787, 22000.
- [ ] **IPv6 full-stack** : Docker a IPv6 activé (daemon.json `"ipv6":true`, réseau mindwtr `fd00:0:0:1::/64`, forwarding kernel). Mais le routage IPv6 externe est bloqué au niveau OVH (port 443 lui-même timeout en IPv6). Contournement actuel : `mindwtr.daneel.net` est un A sans AAAA. Fix requis : activer le bloc IPv6 /64 dans le panel OVH (Network → IP → IPv6), puis configurer la route sur glaurung.

## Dette technique / refactoring

- **Découper le rôle `infra-deploy`** : il fait trop de choses. Candidats à extraire en rôles séparés : `docker-base` (install + daemon + kernel IPv6), `apache-certbot` (vhost + cert), `mindwtr` (réseau + stack Compose). Le playbook `install.yml` appellerait la séquence de rôles.

## Phase 2 (à faire)

- **Traefik sur 80/443** : passer Apache sur port interne, Traefik prend 80/443
- **Traefik ACME DNS-01** : via API OVH — élimine certbot et le hook. HTTP-01 impossible tant qu'Apache tient 80/443.
- **TT-RSS** : intégrer `~/ttrss-docker/` dans ce repo (templates `.j2` + vault), labels Traefik sur `web-nginx`
- **Dashboard Traefik** : activer derrière BasicAuth (`htpasswd -nB admin`, doubler les `$` dans le YAML)
- **ssh-securite** : compléter le rôle (durcissement sshd)
- **Conteneur php** : formaliser le lancement

## Sauvegardes critiques

- `/opt/mindwtr/data/cloud/` — données sync Mindwtr
- `/etc/letsencrypt/` — certificats TLS (renouvellement auto via certbot snap)
