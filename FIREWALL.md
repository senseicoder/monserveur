# Firewall glaurung — rôle `firewall-setup`

Étude du 2026-07-16 (validée), implémentée dans `ansible/roles/firewall-setup/` (liste `security.list`).
Déclencheur : le 3306 de MariaDB s'est retrouvé exposé sur internet par une règle posée dans la mauvaise chaîne (voir « Leçon 3306 » ci-dessous). État antérieur : **aucun firewall** (policy INPUT ACCEPT, zéro règle).

## Pourquoi deux chaînes

Le trafic entrant suit deux chemins distincts dans Netfilter :

- **Service de l'hôte** (SSH, Apache, MariaDB, Syncthing, chatbots) : le paquet est destiné à une IP locale → livraison locale → chaîne **INPUT**.
- **Port publié par Docker** (`-p 8787:8787`) : le paquet est DNATé en **PREROUTING** (sa destination devient l'IP du conteneur), il n'est plus « pour l'hôte » → il est routé → chaîne **FORWARD**, dont **DOCKER-USER** est le point d'accrochage utilisateur (évaluée avant les règles propres de Docker, jamais modifiée par lui).

Corollaires :
- Une règle DOCKER-USER **ne protège pas un service hôte** (son trafic ne passe jamais par FORWARD).
- Une règle INPUT **ne protège pas un port publié Docker** en IPv4 (le DNAT l'a déjà dérouté avant INPUT).
- Le trafic **conteneur → service hôte** (ex. rat-web → MariaDB via la gateway 172.18.0.1) arrive par **INPUT** (interface `br-*`), pas par DOCKER-USER.
- **IPv6** : Docker 19.03 n'a pas de NAT v6 — les ports publiés v6 sont servis par `docker-proxy`, un processus de l'hôte → chaîne **INPUT v6** (d'où l'union hôte+Docker dans les règles v6 du rôle).

## Liste des ports (état réel vérifié le 2026-07-16, `ss -tlnu` + `sudo ss -ulnp`)

### INPUT (services hôte) — policy DROP

| Port | Proto | Service | Ouverture |
|---|---|---|---|
| 22 | tcp | SSH | monde |
| 80, 443 | tcp | Apache (jusqu'à la bascule Phase 2) | monde |
| 8000-8002 | tcp | chatbots (webhooks GChat/Discord) | monde |
| 22000 | tcp+udp | Syncthing (sync + QUIC) | monde |
| 3306 | tcp | MariaDB natif | lo + 172.18.0.0/16 uniquement, DROP explicite sinon |
| — | icmp / icmpv6 | ping, PMTUD ; NDP en v6 (**jamais bloquer ICMPv6**) | monde |
| — | — | `lo` + `ESTABLISHED,RELATED` | — |

### DOCKER-USER v4 (ports publiés) — DROP final sur `eth0`

| Port | Proto | Service |
|---|---|---|
| 8787 | tcp | Traefik (transitoire, jusqu'à Phase 2 étape 5.1) |
| 80, 443 | tcp | Traefik après la bascule Phase 2 (inoffensif avant : rien de publié) |
| 21115-21117 | tcp | RustDesk hbbs/hbbr |
| 21116 | udp | RustDesk hbbs |

### Sans règle / à ne pas ouvrir

- **8028** (TT-RSS), **8384** (UI Syncthing), **3306 v6** : bind loopback ou v4-only — protégés par le bind + policy DROP.
- **21027/udp** (découverte locale Syncthing) : inutile sur un VPS, pas ouvert.
- **UDP éphémères 39223/47019** : sockets syncthing (STUN/NAT traversal, identifiés par `sudo ss -ulnp`), initiés en sortie — couverts par `ESTABLISHED,RELATED`.

## Décisions de conception

1. **Module `ansible.builtin.iptables` règle par règle** (idempotent, ne touche que INPUT et DOCKER-USER) — jamais de `netfilter-persistent reload`/`restore` en routine : un restore flushe les chaînes `DOCKER-*` peuplées par dockerd et casse le NAT des conteneurs.
2. **Persistance** : paquet `iptables-persistent`, sauvegarde via handler `save iptables` (`netfilter-persistent save`, centralisé dans `run_role.yml`). Au boot, netfilter-persistent charge avant Docker, qui recrée/complète ensuite ses chaînes — ordre naturel correct.
3. **Anti-lockout** : job `at now +15 min` qui remet les policies en ACCEPT, désarmé en fin de rôle **après** un `wait_for` TCP/22 depuis le poste de contrôle (teste une NOUVELLE connexion à travers le firewall, pas la session SSH existante qui survit via ESTABLISHED).
4. **DOCKER-USER : insertion en tête obligatoire** — Docker crée la chaîne avec un `RETURN` final, tout append serait mort.
5. **Piège `--dport` dans DOCKER-USER** : le DNAT est déjà appliqué, `--dport` désigne le port interne du conteneur. OK ici (mappings 1:1) ; si un mapping change de numéro un jour → `-m conntrack --ctorigdstport`.
6. **Règles 3306 partagées avec `rat-setup`** : spécifications identiques dans les deux rôles (déduplication automatique par le module). À terme (une fois firewall-setup en prod), les retirer de rat-setup — une seule source de vérité.
7. **DROP explicite 3306 conservé malgré la policy DROP** : protège aussi quand la policy est temporairement remise en ACCEPT (garde anti-lockout, debug manuel).
8. **FORWARD et OUTPUT non touchés** (FORWARD géré par Docker, OUTPUT ACCEPT).

## Exécution

```bash
cd ansible
./run role firewall-setup          # check mode (dry run)
./run role firewall-setup run      # application réelle
```

Après application : vérifier une **nouvelle** session SSH, `curl` des domaines web, clients Vaultwarden/MindWTR (:8787), RustDesk, Syncthing. La garde `at` couvre les 15 premières minutes.

## Rollback

```bash
sudo iptables -P INPUT ACCEPT && sudo ip6tables -P INPUT ACCEPT   # désactive le filtrage
sudo iptables -F INPUT && sudo ip6tables -F INPUT                 # purge les règles INPUT (3306 redevient exposé !)
sudo netfilter-persistent save                                    # persiste le retour arrière
```

## Séquencement avec la Phase 2 (PHASE2.md)

Le firewall se joue **avant** la bascule Traefik 80/443 : il protège 3306 immédiatement, et 80/443 figurent déjà dans les deux chaînes — la bascule ne demandera aucune retouche. Après l'étape 5.1 de la Phase 2 (décommissionnement du 8787), retirer 8787 de `firewall_docker_tcp_ports`.

## Leçon 3306 (2026-07-16)

La première version du verrou MySQL (rôle rat-setup) posait ACCEPT/DROP dans DOCKER-USER : sans effet pour un service hôte — 3306 est resté ouvert sur internet (testé et confirmé depuis l'extérieur, MariaDB 10.1 avec comptes `@%`). Corrigé le soir même : hotfix manuel INPUT + règles du rôle déplacées en INPUT (commit `54f4079`). Pattern documenté aussi dans le wiki perso (`contexte/docker-avance.md` § 9).
