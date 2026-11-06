# Phase 2 — Traefik prend les ports 80/443

> **Statut (2026-08-02)** : Étapes 0-3 ci-dessous **faites et mergées** (branche `phase2-apache-backend`, PR #2). Deux incidents rencontrés en exécution (snippet SSL vestige `bots.plcoder.net.d/ssl` faisant planter mod_ssl ; règle firewall manquante pour le nouveau port interne 8081) — corrigés, détail dans l'historique git et le wiki (`ansible-avance.md`, `docker-avance.md`). Étapes 4 et 5 restent à faire, hors périmètre de cette bascule.

Plan établi le 2026-07-16, après vérification de l'état réel sur glaurung.
Objectif : Traefik devient le frontal unique sur 80/443 (en plus de 8787 pendant la transition), Apache passe en backend interne.

## État vérifié (2026-07-16)

- Apache tient 80/443 : 8 vhosts actifs (`sites-enabled/`), IPs explicites, certbot snap actif (timer quotidien).
- Traefik v3 : entrypoint unique `mindwtr` (:8787), pas d'ACME, TLS file provider sur certs certbot copiés dans `/opt/mindwtr/certs/` + hook `docker restart traefik`.
- Réseau `mindwtr` : `172.18.0.0/16` (gateway **172.18.0.1**) + `fd00:0:0:1::/64`.
- Nouveau conteneur `rat-rat-web-1` sur le réseau `mindwtr` (migration rat en cours) — bénéficiaire direct de cette phase (URLs propres sans `:8787`).
- **Correction de l'ancienne note Phase 2** : « ACME DNS-01 via API OVH » était doublement erroné — (a) une fois Traefik sur le port 80, le HTTP-01 natif suffit ; (b) le DNS de `daneel.net`/`plcoder.net` est chez Gandi, pas OVH.

## Architecture cible

```
client → 80/443 → Traefik v3 (frontal unique, ACME HTTP-01 natif)
                      ├── mindwtr.daneel.net  → mindwtr-cloud:8787   (réseau mindwtr)
                      ├── vault.daneel.net    → vaultwarden:80       (réseau mindwtr)
                      ├── sites rat           → rat-rat-web-1:80     (réseau mindwtr)
                      └── vhosts legacy       → Apache 172.18.0.1:8081 (hôte)
                            reader.daneel.net, bots.plcoder.net,
                            lescoursdesophie.com, ssl.lescoursdesophie.com,
                            sophie.daneel.net, sslsophie.daneel.net
```

## Étape 0 — Préliminaires (aucun impact prod)

- [ ] 0.1 `git pull` + branche de travail validée
- [ ] 0.2 Backup `/etc/apache2/` + snapshot de référence (ss, docker ps, curl HTTP/HTTPS des 8 domaines) pour la non-régression
- [ ] 0.3 Architecture figée : Apache = backend interne (reader/bots/sophie/lescoursdesophie), Traefik = frontal unique

## Étape 1 — Nouvelle config Traefik (préparée, non basculée)

- [ ] 1.1 Template compose : entrypoints `web` (:80) et `websecure` (:443), en **gardant `mindwtr` (:8787)** pour ne pas casser les clients Vaultwarden/MindWTR
- [ ] 1.2 Redirection globale HTTP→HTTPS sur l'entrypoint `web`
- [ ] 1.3 Resolver ACME HTTP-01 natif (`acme.json` en volume) — remplacera certbot
- [ ] 1.4 Routers file provider pour les 6 vhosts legacy → `http://172.18.0.1:8081`
- [ ] 1.5 Services Docker existants (mindwtr, vaultwarden, rat) : ajouter `web`/`websecure` à leurs entrypoints
- [ ] 1.6 Conserver le file provider TLS (certs certbot) pendant la transition

## Étape 2 — Apache en backend interne

- [ ] 2.1 `ports.conf` : `Listen 127.0.0.1:8081` + `Listen 172.18.0.1:8081` — plus de 80/443, plus de TLS côté Apache
- [ ] 2.2 Vhosts réécrits en `*:8081` : suppression SSL et redirections 301 (reprises par Traefik), suppression des vhosts webroot certbot (mindwtr, vault) ; conservation proxy ttrss et PHP-FPM ; ajout `mod_remoteip` (X-Forwarded-For) pour les vraies IP clients dans les logs
- [ ] 2.3 Drop-in systemd `apache2` : `After=docker.service` — le bind sur 172.18.0.1 exige le bridge Docker au boot (**risque principal**, test reboot à prévoir)
- [ ] 2.4 Tout en Ansible — extraire un rôle `apache-backend` (dette technique notée dans CLAUDE.md)

## Étape 3 — Bascule (coupure ~1-2 min, rollback prêt)

- [ ] 3.1 Ordre : apply Apache (libère 80/443) → `docker-compose up -d` Traefik (nouveau compose)
- [ ] 3.2 Vérifications : curl HTTP+HTTPS des 8 domaines en IPv4 **et IPv6**, clients `:8787` OK, rat OK
- [ ] 3.3 Rollback documenté : restore backup 0.2 + ancien compose Traefik

## Étape 4 — ACME Traefik, retrait de certbot

- [ ] 4.1 Tester le resolver sur un domaine sans cert (ex. `sophie.daneel.net`)
- [ ] 4.2 Migrer domaine par domaine (retirer du file provider quand ACME OK) — passer `lescoursdesophie.com` en HTTPS à cette occasion
- [ ] 4.3 Fin : désactiver le timer certbot snap, supprimer le hook `reload-traefik.sh`, archiver `/etc/letsencrypt`
- [ ] 4.4 Nouveau workflow « ajouter un domaine » = labels Traefik uniquement (plus de vhost, plus de certbot)

## Étape 5 — Consolidation

- [ ] 5.1 Décommissionner `:8787` après migration des URLs clientes (apps Vaultwarden, clients MindWTR + MCP M6/M7) — garder quelques semaines en double écoute
- [ ] 5.2 Optionnel : router `reader.daneel.net` directement vers le conteneur ttrss-nginx (Traefik rejoint `ttrss-docker_default`) — retire l'intermédiaire Apache
- [ ] 5.3 Firewall à deux volets : étude et rôle `firewall-setup` créés le 2026-07-16 — voir **FIREWALL.md**. À jouer **avant** la bascule (80/443 déjà prévus dans les deux chaînes, aucune retouche à la bascule) ; après 5.1, retirer 8787 de `firewall_docker_tcp_ports`
- [ ] 5.4 Doc : `wiki/postes/glaurung.md`, ce CLAUDE.md, `wiki/log.md`, `wiki/projets/migration-rat-docker.md`, `sujets/machines-postes.md`

## Points de vigilance

- **Bind 172.18.0.1 au boot** : Apache doit démarrer après Docker (2.3) — sinon échec de bind au reboot
- **URLs `:8787` en dur** chez les clients Vaultwarden/MindWTR — couvert par la double écoute (1.1, 5.1)
- **IPv6** : les vhosts actuels écoutent sur IPs v6 explicites — vérifier après bascule que docker-proxy publie bien 80/443 en v6 (comme il le fait pour 8787)
- **docker-compose v1 / Docker 19.03 / Debian stretch** : pas de plugin Compose v2, piège seccomp `clone3` connu (cf. CLAUDE.md)

## Bascule ACME natif + fermeture :8787 (étapes 4-5) — plan

Code : branche `traefik-acme-natif`. Tout est piloté par des variables de `group_vars/all/vars.yml`, **désactivées par défaut** : avec les valeurs par défaut, les templates rendent exactement comme master (vérifié par rendu Jinja2 comparé, pas par un run Ansible). Doc Traefik de référence : https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/

| Variable | Défaut | Rôle |
|---|---|---|
| `traefik_acme_enabled` | `false` | déclare le resolver `le` (TLS-ALPN-01, `tlschallenge`) + volume `/opt/mindwtr/acme` |
| `traefik_acme_ca_server` | staging LE | passer à `https://acme-v02.api.letsencrypt.org/directory` pour la prod (fichier de stockage distinct : `acme-staging.json` / `acme.json`) |
| `traefik_acme_test_domain` | `""` | router jetable → Apache pour valider le resolver sans toucher un domaine en service |
| `traefik_acme_domains` | `[]` | domaines basculés : label `tls.certresolver`, sortie de `tls.yml`, tâches certbot sautées |
| `traefik_legacy_8787_enabled` | `true` | `false` = entrypoint/port `:8787`, labels, URLs `:8787` et port firewall retirés |

Pourquoi TLS-ALPN-01 et pas HTTP-01 : le router `acme-challenge` (priorité 1000, port 80) envoie encore `/.well-known/acme-challenge/` vers Apache pour les renouvellements certbot webroot des domaines non basculés. Avec TLS-ALPN-01, Traefik valide sur :443 et ne touche pas à ce router : les deux mécanismes coexistent pendant toute la bascule.

### Prérequis
1. Dry-run systématique avant chaque run réel (`./run role X` sans `run`), lire les lignes **retirées** (cf. branches déployées sans merge, incident m3gan du 23/10).
2. Le domaine doit pointer vers glaurung en IPv4 **et** IPv6 (TLS-ALPN-01 sur :443). **Exclure** les domaines dont le DNS n'est pas sur glaurung (aujourd'hui `www.plcoder.net`, `www.placedusport2.com` et les alias rat tant que la bascule DNS rat n'est pas faite — à vérifier).
3. Quotas Let's Encrypt : valider en staging d'abord, puis basculer en prod domaine par domaine.

### Étapes
0. **Test resolver en staging** : créer un CNAME jetable (ex. `acme-test.daneel.net` → `glaurung.daneel.net`), puis `traefik_acme_enabled: true`, `traefik_acme_test_domain: acme-test.daneel.net` → `./run role traefik-deploy` (dry-run) puis `run`. Vérifier `docker logs traefik` (pas d'erreur ACME), `/opt/mindwtr/acme/acme-staging.json` rempli et en 0600, `curl -vk https://acme-test.daneel.net` → émetteur « (STAGING) ». Aucun domaine en service touché.
1. **Test resolver en prod** : `traefik_acme_ca_server` = prod, rejouer `traefik-deploy` → cert reconnu sur `acme-test` (`curl -v` sans `-k`).
2. **Bascule domaine par domaine** (ordre du moins au plus critique) : `pub.daneel.net` → `migration.integralsport.com` → `m3gan.daneel.net` → `puttini.daneel.net` → `ntfy.daneel.net` → `reader.daneel.net` / `bots.plcoder.net` → `mindwtr.daneel.net` → `vault.daneel.net`. Pour chaque domaine : l'ajouter à `traefik_acme_domains`, rejouer `traefik-deploy` (tls.yml) **et** le rôle du service (labels ; rien pour reader/bots, routers file-provider), puis vérifier :
   - `echo | openssl s_client -connect <domaine>:443 -servername <domaine> 2>/dev/null | openssl x509 -noout -issuer -dates` → émetteur Let's Encrypt, date d'émission du jour ;
   - idem en IPv6 (`-connect '[2001:41d0:302:2100::4203]:443'`) ;
   - client applicatif OK (app Vaultwarden, MindWTR, ntfy…).
   Laisser tourner quelques jours entre les domaines critiques.
3. **Fermeture :8787** (après migration des clients) : passer les URLs clientes en `https://<domaine>` sans port — apps Vaultwarden/MindWTR, et côté poste : `claude/script/{mcp-local-all.json,mcp-check.sh,claude-install.sh,mindwtr-liste-coach.py,backup-pull-pcloud.sh,glaurung-backup-freshness-check.sh}`, `skills/mindwtr-quality/*`. Puis `traefik_legacy_8787_enabled: false` et rejouer : `traefik-deploy`, `mindwtr-cloud-deploy`, `vaultwarden-deploy`, `ntfy-deploy`, `puttini-deploy`, `m3gan-deploy`, `rat-setup`, `glaurung-healthcheck`, `backup-setup`, `firewall-setup`. Vérifier `ss -ltn | grep 8787` vide, ntfy reçoit bien les alertes healthcheck/backup.
4. **Retrait certbot** (quelques semaines après validation complète) : `certbot delete --cert-name <domaine>` pour les domaines basculés, retrait du hook `reload-traefik.sh` et des vhosts webroot Apache, suppression du code certbot devenu mort (tâches sautées, `traefik_file_certs`, copies reader/bots dans `traefik-deploy`), puis du router `acme-challenge`. Commit séparé.

### Rollback
- Un domaine : le retirer de `traefik_acme_domains`, rejouer `traefik-deploy` + rôle du service → le cert certbot (resté sur l'hôte, toujours renouvelé) revient dans `tls.yml`, le label `certresolver` disparaît.
- Tout ACME : `traefik_acme_enabled: false` + `traefik_acme_domains: []`, rejouer les mêmes rôles.
- :8787 : `traefik_legacy_8787_enabled: true` et rejouer la liste de l'étape 3.
Tant que l'étape 4 n'est pas faite, le rollback ne demande aucune nouvelle émission de certificat.

### Points à valider
- Comportement de Traefik quand un cert du TLS store (file provider) couvre déjà un domaine qui a aussi un `certresolver` : la doc ne le précise pas. Le code évite la question en retirant le domaine de `tls.yml` au moment de la bascule.
- `glaurung-healthcheck` surveille `/etc/letsencrypt/live/` et les copies dans `certs/` : il ne voit pas les certs ACME. À adapter (contrôle du cert réellement servi via `openssl s_client`) avant l'étape 4.
- `firewall-setup` n'ajoute que des règles (`state: present`) : la règle multiport existante qui contient 8787 restera tant qu'elle n'est pas supprimée à la main ; une nouvelle règle sans 8787 sera insérée. Sans conséquence de sécurité une fois le port non publié, mais à nettoyer.
- `acme.json` contient des clés privées : il est sous `/opt/mindwtr/acme`, hors du périmètre `backup_fs_paths` actuel. À ajouter si on veut éviter une réémission après restauration (pas indispensable).
- Docker 19.03 / compose v1 sur glaurung : la syntaxe CLI `--certificatesresolvers...` ne dépend que de l'image `traefik:v3`, mais aucun run n'a été fait.
