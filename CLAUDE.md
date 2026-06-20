# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Objectif

Infrastructure as code pour le VPS personnel `glaurung` (Debian). Gère le déploiement de services auto-hébergés via Docker + Ansible.

## État de production sur glaurung (au 2026-06-20)

### Réseau hôte
| Port | Bind | Usage |
|------|------|-------|
| 22 | 0.0.0.0 | SSH |
| 80 / 443 | ::: | **Frontal existant** (nginx/apache hôte — à identifier avant de déployer Traefik) |
| 3306 | 127.0.0.1 | MySQL (conteneur `php`) |
| 8000–8002 | 0.0.0.0 | Chatbots (publics, hors scope) |
| 8028 | 127.0.0.1 | TT-RSS nginx |
| 8384 | 127.0.0.1 | Syncthing UI |
| 22000 | ::: | Syncthing sync |

### Conteneurs Docker actifs
| Conteneur | Image | Notes |
|-----------|-------|-------|
| `php` | `debian:11` | Shell de confort PHP, lancé manuellement, hors Compose |
| `ttrss-docker-*` (×4) | `cthulhoo/ttrss-*` + `postgres:12-alpine` | Stack TT-RSS officielle, gérée depuis `~/ttrss-docker/` sur le serveur (clone de `https://git.tt-rss.org/fox/ttrss-docker-compose.git`, branche `static-dockerhub`) |

## Architecture cible (ce repo)

Deux stacks Compose séparées, orchestrées par Ansible, partageant un réseau Docker externe `proxy` :

```
Internet :80/:443
    │
  Traefik v3  (Let's Encrypt HTTP-01, dashboard sur traefik.daneel.net)
    │  réseau Docker "proxy"
    ├── mindwtr-cloud  (sync Mindwtr, gtd.daneel.net, port interne 8787)
    │
    └── [Phase 2] ttrss-web-nginx  (ttrss.daneel.net, port interne 80)
```

Fichiers Compose générés par Ansible (templates Jinja2) et déposés dans `/opt/mindwtr/` sur le serveur.

## Structure du repo

```
ansible/
├── ansible.cfg            ← connexion SSH via ssh-config local (non versionné)
├── inventory              ← hôte : glaurung
├── install.yml            ← playbook principal
└── roles/
    ├── infra-deploy/      ← installe Docker, crée réseau proxy, déploie les Compose
    │   ├── defaults/main.yml
    │   ├── handlers/main.yml
    │   └── tasks/main.yml
    └── ssh-securite/      ← durcissement SSH (stub à compléter)

compose/
├── docker-compose.traefik.yml.j2   ← Traefik v3, TLS Let's Encrypt
├── docker-compose.mindwtr.yml.j2   ← mindwtr-cloud (ghcr.io/dongdongbh/mindwtr-cloud)
└── logs/                           ← logs locaux (debug)

images/                    ← OBSOLÈTE — builds custom debian:jessie, non utilisés en prod
```

## Commandes

### Déployer sur glaurung

```bash
cd ansible
ansible-playbook install.yml
```

Le rôle `infra-deploy` :
1. Installe Docker + plugin Compose
2. Crée le réseau Docker externe `proxy`
3. Dépose les Compose (depuis les templates `.j2`) dans `/opt/mindwtr/`
4. Démarre Traefik puis mindwtr

### Variables à renseigner dans `ansible/inventory`

| Variable | Usage |
|----------|-------|
| `mindwtr_token` | Token auth mindwtr (générer : `cat /dev/urandom \| LC_ALL=C tr -dc 'a-zA-Z0-9' \| fold -w 50 \| head -n 1`) |
| `acme_email` | Email Let's Encrypt |
| `traefik_dashboard_auth` | Hash htpasswd (`htpasswd -nB admin`, doubler les `$`) |
| `deploy_dir` | Dossier de déploiement sur le VPS (défaut : `/opt/mindwtr`) |

## Plan de déploiement

### Contrainte : Apache2 hôte occupe 80/443

Apache2 tourne sur l'hôte avec 6 vhosts actifs — **on ne peut pas l'arrêter** :

| Vhost | Ports |
|-------|-------|
| `reader.daneel.net` | 80 + 443 → proxy vers ttrss (127.0.0.1:8028) |
| `bots.plcoder.net` | 80 + 443 → chatbots |
| `lescoursdesophie.com` | 80 |
| `ssl.lescoursdesophie.com` | 80 |
| `sophie.daneel.net` | 80 |
| `sslsophie.daneel.net` | 80 |

Configs dans `/etc/apache2/sites-enabled/` sur glaurung.

**Deux stratégies possibles pour Traefik :**

- **Option A (retenue pour Phase 1)** : Apache reste sur 80/443. On ajoute un vhost Apache `gtd.daneel.net` qui proxyfie vers le conteneur mindwtr (port interne). TLS via certbot comme les autres vhosts. Traefik n'est pas déployé dans cette phase.
- **Option B (Phase 2+)** : Apache passe sur un port interne (ex. 127.0.0.1:8080). Traefik prend 80/443 et proxyfie Apache pour les anciens vhosts + gère mindwtr et ttrss directement. Migration plus lourde mais cohérente long terme.

### Phase 1 — Traefik + mindwtr (scope actuel)

**Domaine :** `mindwtr.daneel.net` → IP de glaurung (51.254.212.250)
**URL client Mindwtr :** `https://mindwtr.daneel.net:8787/v1`

Architecture :
```
client  →  8787/HTTPS  →  Traefik (TLS via certs certbot)  →  mindwtr:8787 (réseau Docker "mindwtr")
certbot  →  Apache (port 80)  →  renouvelle /etc/letsencrypt/live/mindwtr.daneel.net/
hook post-renewal certbot  →  docker kill --signal=SIGUSR1 traefik  (rechargement cert)
```

Étapes Ansible :
1. Installer Docker si absent
2. Créer le réseau Docker `mindwtr`
3. Déposer `docker-compose.mindwtr.yml` + `.env` prod dans `/opt/mindwtr/`
4. Obtenir le cert : `certbot --apache -d mindwtr.daneel.net`
5. Installer le hook post-renewal certbot pour recharger Traefik
6. Démarrer Traefik puis mindwtr-cloud

**Dashboard Traefik :** désactivé en Phase 1 (`--api.dashboard=false`). Activé en Phase 2 derrière BasicAuth.

**Configurer l'app Mindwtr :** URL `https://mindwtr.daneel.net:8787/v1`, token = `mindwtr_token`

### Todos fin de Phase 1

- [ ] Revoir le firewall (vérifier que 8787 est bien ouvert / règles iptables cohérentes avec les ports exposés)

### Phase 2 — Migration vers Traefik (à faire)

- Passer Apache sur port interne
- Déployer Traefik sur 80/443
- Migrer les vhosts Apache en labels Traefik (ou ProxyPass Traefik → Apache)
- Intégrer ttrss dans Traefik

### Phase 2 — TT-RSS derrière Traefik (à faire)

- La stack TT-RSS tourne depuis `~/ttrss-docker/` sur le serveur (non géré par ce repo)
- Pour l'intégrer : ajouter labels Traefik + réseau `proxy` à `web-nginx`, supprimer l'exposition `${HTTP_PORT}:80`
- Option A : gérer via un `docker-compose.override.yml` dans `~/ttrss-docker/`
- Option B : rapatrier le Compose dans ce repo en `.j2` avec secrets via Ansible vault

### Phase 2 — Conteneur php (à faire)

- Documenter l'usage exact et formaliser le lancement (Compose ou script)

## Sauvegardes critiques sur le serveur

- `/opt/mindwtr/data/letsencrypt/acme.json` — certificats TLS (Traefik)
- `/opt/mindwtr/data/cloud/` — données sync Mindwtr
