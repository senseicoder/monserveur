# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Objectif

Infrastructure as code pour le VPS personnel `glaurung` (Debian bookworm). Déploie des services auto-hébergés via Docker + Ansible.

## État de production sur glaurung (au 2026-06-20)

### Réseau hôte
| Port | Bind | Usage |
|------|------|-------|
| 22 | 0.0.0.0 | SSH |
| 80 / 443 | ::: | Apache2 hôte (6 vhosts, certbot) |
| 3306 | 127.0.0.1 | MySQL (conteneur `php`) |
| 8000–8002 | 0.0.0.0 | Chatbots (publics, hors scope) |
| 8028 | 127.0.0.1 | TT-RSS nginx |
| 8384 | 127.0.0.1 | Syncthing UI |
| 8787 | 0.0.0.0 | Traefik → mindwtr-cloud (Phase 1) |
| 22000 | ::: | Syncthing sync |

### Apache2 — vhosts actifs (`/etc/apache2/sites-enabled/`)
| Vhost | Ports |
|-------|-------|
| `reader.daneel.net` | 80 + 443 → proxy ttrss (127.0.0.1:8028) |
| `bots.plcoder.net` | 80 + 443 → chatbots |
| `lescoursdesophie.com` | 80 |
| `ssl.lescoursdesophie.com` | 80 |
| `sophie.daneel.net` | 80 |
| `sslsophie.daneel.net` | 80 |

Certbot renouvelle via Apache (authenticator = apache, HTTP-01). Certs existants : `bots.plcoder.net`, `reader.daneel.net`.

### Conteneurs Docker actifs
| Conteneur | Image | Notes |
|-----------|-------|-------|
| `php` | `debian:11` | Shell PHP ponctuel, lancé manuellement hors Compose |
| `ttrss-docker-*` (×4) | `cthulhoo/ttrss-*` + `postgres:12-alpine` | Géré depuis `~/ttrss-docker/` (clone officiel, branche `static-dockerhub`) |

### Réseaux Docker existants
| Réseau | Subnet | Conteneurs |
|--------|--------|------------|
| `bridge` | 172.17.0.0/16 | php |
| `ttrss-docker_default` | 172.23.0.0/16 | stack ttrss |
| `mindwtr` | (auto) | traefik, mindwtr-cloud |

### Firewall
**INPUT ACCEPT sans règle** — pas de pare-feu hôte. Docker injecte ses règles en PREROUTING/DNAT, ce qui contourne INPUT. Filtrage Docker à faire via chaîne `DOCKER-USER`.

## Architecture Phase 1 (implémentée)

```
client  →  8787/HTTPS  →  Traefik v3 (TLS via certs certbot, dashboard désactivé)
                               │  réseau Docker "mindwtr"
                               └── mindwtr-cloud:8787

certbot (Apache HTTP-01)  →  /etc/letsencrypt/live/mindwtr.daneel.net/
hook post-renewal  →  docker restart traefik
```

**URL client Mindwtr :** `https://mindwtr.daneel.net:8787/v1`

## Structure du repo

```
ansible/
├── ansible.cfg                   ← ssh via ssh-config local (non versionné), vault via .vault_passw.py
├── inventory/hosts.yml           ← hôte : glaurung
├── group_vars/all/
│   ├── vars.yml                  ← variables non-secrètes (deploy_dir, domaine, email)
│   └── vault.yml.example         ← modèle pour le vault (mindwtr_token)
├── requirements.yml              ← collection community.docker
├── install.yml                   ← playbook principal
└── roles/
    ├── infra-deploy/             ← rôle principal Phase 1
    │   ├── defaults/main.yml
    │   ├── handlers/main.yml
    │   ├── tasks/main.yml
    │   └── templates/
    │       ├── docker-compose.traefik.yml.j2
    │       ├── docker-compose.mindwtr.yml.j2
    │       ├── traefik-tls.yml.j2        ← config TLS file provider Traefik
    │       └── certbot-renewal-hook.sh.j2
    └── ssh-securite/             ← durcissement SSH (stub, Phase 2)

compose/
├── .env.example                  ← référence variables secrets
└── logs/                         ← logs debug locaux
```

## Commandes

### Premier déploiement

```bash
cd ansible
# 1. Créer le vault avec le token mindwtr
cp group_vars/all/vault.yml.example group_vars/all/vault.yml
ansible-vault encrypt group_vars/all/vault.yml   # saisir le mdp
# Puis éditer : ansible-vault edit group_vars/all/vault.yml

# 2. Installer la collection Ansible
ansible-galaxy collection install -r requirements.yml

# 3. Déployer
ansible-playbook install.yml
```

### Redéployer après modif

```bash
cd ansible && ansible-playbook install.yml
```

Les tâches Docker et certbot sont idempotentes (skippées si déjà en place).

### Vérifier les services sur le serveur

```bash
docker compose -f /opt/mindwtr/docker-compose.traefik.yml ps
docker compose -f /opt/mindwtr/docker-compose.mindwtr.yml ps
```

## Todos fin de Phase 1

- [ ] Revoir le firewall : INPUT sans règle + piège Docker/PREROUTING. Utiliser `DOCKER-USER` pour filtrer les ports Docker. Ports à autoriser : 22, 80, 443, 8000-8002, 8787, 22000.

## Phase 2 (à faire)

- **Traefik sur 80/443** : passer Apache sur port interne, Traefik prend 80/443
- **TT-RSS** : intégrer `~/ttrss-docker/` dans ce repo (`.j2` + vault), labels Traefik sur `web-nginx`
- **Dashboard Traefik** : activer derrière BasicAuth (`htpasswd -nB admin`, doubler les `$`)
- **ssh-securite** : compléter le rôle (durcissement sshd)
- **Conteneur php** : formaliser le lancement

## Sauvegardes critiques

- `/opt/mindwtr/data/cloud/` — données sync Mindwtr
- `/etc/letsencrypt/` — certificats TLS (renouvellement auto via certbot)
