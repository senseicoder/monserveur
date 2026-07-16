# Phase 2 — Traefik prend les ports 80/443

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
