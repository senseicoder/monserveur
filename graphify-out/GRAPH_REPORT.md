# Graph Report - .  (2026-08-01)

## Corpus Check
- Corpus is ~12,321 words - fits in a single context window. You may not need a graph.

## Summary
- 128 nodes · 154 edges · 26 communities (12 shown, 14 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.78)
- Token cost: 251,055 input · 0 output

## Community Hubs (Navigation)
- Traefik & Reverse-Proxy Pitfalls
- Global Ansible Vars — Overview
- Docker Engine & Rustdesk Setup
- Deployment Roles — Tasks
- Secrets & Inventory
- Firewall Rules & Lessons
- Install Sequence & Infra-Deploy Rapprochement
- Ntfy Healthcheck Config
- run_role.yml Wrapper Script
- Network IPv6 & SSH Hardening
- RAT Migration & Setup
- Firewall Safety — Anti-Lockout
- Vault Password Script
- Docker Engine Defaults
- IPv6 Defaults
- Ntfy Defaults
- RAT Migration Defaults
- Traefik Defaults
- Vaultwarden Defaults
- New Domain DNS Note
- Docker Subnets Note
- Firewall Persistence Note
- Install Prerequisites
- Phase 2 — Step 0
- Phase 2 — Step 4
- README Overview

## God Nodes (most connected - your core abstractions)
1. `CLAUDE.md — guide monserveur` - 17 edges
2. `TODO.md — backlog monserveur` - 10 edges
3. `FIREWALL.md — étude firewall glaurung` - 9 edges
4. `Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)` - 7 edges
5. `Séquence des 6 rôles joués par mindwtr.list` - 7 edges
6. `docker-network-mindwtr-setup/tasks/main.yml — daemon.json IPv6 + réseau mindwtr` - 7 edges
7. `Traefik v3 (reverse proxy)` - 6 edges
8. `mindwtr_deploy_dir` - 6 edges
9. `mindwtr-cloud-deploy/defaults/main.yml (consomme mindwtr_deploy_dir/domain/acme_email)` - 6 edges
10. `mindwtr-cloud (conteneur)` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Piège seccomp Docker 19.03 + clone3 (Rust/Go)` --semantically_similar_to--> `Découpage du rôle infra-deploy monolithique en 6 rôles`  [INFERRED] [semantically similar]
  CLAUDE.md → RAPPROCHEMENT_INFRA_DEPLOY.md
- `collection community.mysql (>=3.0.0)` --shares_data_with--> `Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)`  [INFERRED]
  ansible/requirements.yml → CLAUDE.md
- `Étape 3 — Bascule (coupure 1-2 min, rollback prêt)` --semantically_similar_to--> `Rollback firewall (policies ACCEPT, purge INPUT)`  [INFERRED] [semantically similar]
  PHASE2.md → FIREWALL.md
- `docker-network-mindwtr-setup/tasks/main.yml — daemon.json IPv6 + réseau mindwtr` --references--> `mindwtr-cloud (conteneur)`  [INFERRED]
  ansible/roles/docker-network-mindwtr-setup/tasks/main.yml → CLAUDE.md
- `Leçon 3306 — MariaDB exposé sur internet (2026-07-16)` --references--> `Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)`  [INFERRED]
  FIREWALL.md → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Rôles composant mindwtr.list (stack applicative Phase 1)** — ansible_roles_docker_network_mindwtr_setup_tasks_main, ansible_roles_mindwtr_cloud_deploy_defaults_main, claude_vaultwarden, claude_traefik, install_sequence_roles [EXTRACTED 1.00]
- **Pattern firewall à deux chaînes (INPUT/DOCKER-USER) et sa mise en oeuvre** — firewall_deux_chaines, firewall_ports_input, firewall_ports_dockeruser, firewall_lecon_3306, ansible_roles_firewall_setup_tasks_main [EXTRACTED 0.95]
- **Mécanisme d'exploitation repris de maconfiguration (run/run_role/*.list/ANSIBLE_ROLES_PATH)** — rapprochement_infra_deploy_run_wrapper, rapprochement_infra_deploy_run_role_yml, rapprochement_infra_deploy_lists, rapprochement_infra_deploy_ansible_roles_path [EXTRACTED 0.90]
- **Services derrière Traefik : pattern certbot + vhost Apache + notify restart traefik** — ansible_roles_traefik_deploy_tasks_main_tasks, ansible_roles_mindwtr_cloud_deploy_tasks_main_tasks, ansible_roles_vaultwarden_deploy_tasks_main_tasks, ansible_roles_ntfy_deploy_tasks_main_tasks, ansible_run_role_restart_traefik [INFERRED 0.85]
- **Pipeline build/déploiement/migration rat-web** — ansible_roles_rat_setup_tasks_main_tasks, ansible_roles_rat_setup_defaults_main_defaults, ansible_roles_rat_setup_handlers_main_restart_mariadb, ansible_roles_rat_migratefromgandi_tasks_main_tasks [INFERRED 0.85]
- **Convention partagée mindwtr_deploy_dir entre stacks Docker** — ansible_roles_mindwtr_cloud_deploy_tasks_main_tasks, ansible_roles_ntfy_deploy_tasks_main_tasks, ansible_roles_traefik_deploy_tasks_main_tasks, ansible_roles_vaultwarden_deploy_tasks_main_tasks, ansible_run_role_playbook [INFERRED 0.85]

## Communities (26 total, 14 thin omitted)

### Community 0 - "Traefik & Reverse-Proxy Pitfalls"
Cohesion: 0.12
Nodes (23): docker-network-mindwtr-setup/tasks/main.yml — daemon.json IPv6 + réseau mindwtr, Procédure : ajouter un service derrière Traefik, Apache2 hôte glaurung (vhosts), Points critiques Apache/certbot sur glaurung, certbot via snap (v5.6.0, mode classic), réseau Docker "mindwtr", CLAUDE.md — guide monserveur, Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com) (+15 more)

### Community 1 - "Global Ansible Vars — Overview"
Cohesion: 0.17
Nodes (14): acme_email, ipv6_gateway, mindwtr_deploy_dir, mindwtr_domain, rat_deploy_dir, rat_gandi_mount, rat_repo_url, vaultwarden_domain (+6 more)

### Community 2 - "Docker Engine & Rustdesk Setup"
Cohesion: 0.15
Nodes (12): rustdesk_domain, docker-engine-setup/tasks/main.yml — install Docker CE + plugin Compose, Procédure : ajouter un service hors Traefik (non-HTTP), RustDesk hbbs/hbbr, Piège seccomp Docker 19.03 + clone3 (Rust/Go), Séquencement firewall-setup avec la Phase 2, PHASE2.md — plan Traefik sur 80/443, Points de vigilance Phase 2 (bind boot, URLs :8787, IPv6) (+4 more)

### Community 3 - "Deployment Roles — Tasks"
Cohesion: 0.20
Nodes (12): mindwtr-cloud-deploy tasks, ntfy-deploy tasks, rustdesk-setup defaults, rustdesk-setup tasks, traefik-deploy tasks, vaultwarden-deploy tasks, run_role.yml generic playbook, restart mindwtr handler (run_role.yml) (+4 more)

### Community 4 - "Secrets & Inventory"
Cohesion: 0.18
Nodes (10): rat_sites (liste sites www.plcoder.net / www.placedusport2.com), group_vars/all/vault.yml — magasin de secrets chiffré (ansible-vault), inventory/hosts.yml — host glaurung, ansible_sudo_pass (lookup pass sudo/nodes), collection ansible.posix (>=1.5.0), collection community.docker (>=3.0.0), collection community.general (>=8.0.0), collection community.mysql (>=3.0.0) (+2 more)

### Community 5 - "Firewall Rules & Lessons"
Cohesion: 0.29
Nodes (11): firewall-setup/defaults/main.yml — ports/ifaces/guard, firewall-setup/tasks/main.yml — règles iptables INPUT/DOCKER-USER, wiki perso — postes/glaurung.md, Pourquoi deux chaînes (INPUT vs DOCKER-USER), Leçon 3306 — MariaDB exposé sur internet (2026-07-16), FIREWALL.md — étude firewall glaurung, Liste des ports DOCKER-USER (ports publiés), Liste des ports INPUT (état réel vérifié 2026-07-16) (+3 more)

### Community 6 - "Install Sequence & Infra-Deploy Rapprochement"
Cohesion: 0.29
Nodes (7): Vaultwarden (gestionnaire de mots de passe), Setup initial Vaultwarden (ADMIN_TOKEN vs signup temporaire), Séquence des 6 rôles joués par mindwtr.list, ANSIBLE_ROLES_PATH (résolution de rôles externes), fichiers *.list (profils de rôles composables), run_role.yml (playbook générique "role"), wrapper `run` (dry-run par défaut)

### Community 7 - "Ntfy Healthcheck Config"
Cohesion: 0.50
Nodes (5): ntfy_domain, ntfy_health_topic, glaurung-healthcheck/defaults/main.yml — seuils disque/cert/cron, glaurung-healthcheck/tasks/main.yml — déploiement script + cron, ntfy (notifications, rôle ntfy-deploy)

### Community 8 - "run_role.yml Wrapper Script"
Cohesion: 0.60
Nodes (3): run script, role_exists(), usage()

### Community 9 - "Network IPv6 & SSH Hardening"
Cohesion: 0.50
Nodes (4): network-ipv6-setup tasks, ssh-securite defaults, restart sshd handler (ssh-securite), ssh-securite tasks

### Community 10 - "RAT Migration & Setup"
Cohesion: 0.50
Nodes (4): rat-migratefromgandi tasks, rat-setup defaults, restart mariadb handler (rat-setup), rat-setup tasks

### Community 11 - "Firewall Safety — Anti-Lockout"
Cohesion: 0.67
Nodes (3): Anti-lockout : job `at` de secours, Rollback firewall (policies ACCEPT, purge INPUT), Étape 3 — Bascule (coupure 1-2 min, rollback prêt)

## Knowledge Gaps
- **47 isolated node(s):** `.vault_passw.sh script`, `certbot via snap (v5.6.0, mode classic)`, `TT-RSS (ttrss-docker)`, `DNS glaurung.daneel.net (A+AAAA) pour nouveau domaine`, `Subnets Docker à ne pas chevaucher` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CLAUDE.md — guide monserveur` connect `Traefik & Reverse-Proxy Pitfalls` to `Global Ansible Vars — Overview`, `Docker Engine & Rustdesk Setup`, `Secrets & Inventory`, `Firewall Rules & Lessons`, `Install Sequence & Infra-Deploy Rapprochement`, `Ntfy Healthcheck Config`?**
  _High betweenness centrality (0.210) - this node is a cross-community bridge._
- **Why does `Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)` connect `Traefik & Reverse-Proxy Pitfalls` to `Global Ansible Vars — Overview`, `Secrets & Inventory`, `Firewall Rules & Lessons`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `TODO.md — backlog monserveur` connect `Traefik & Reverse-Proxy Pitfalls` to `Docker Engine & Rustdesk Setup`, `Firewall Rules & Lessons`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)` (e.g. with `collection community.mysql (>=3.0.0)` and `Leçon 3306 — MariaDB exposé sur internet (2026-07-16)`) actually correct?**
  _`Migration rat (Gandi → glaurung, plcoder.net/placedusport2.com)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Séquence des 6 rôles joués par mindwtr.list` (e.g. with `fichiers *.list (profils de rôles composables)` and `wrapper `run` (dry-run par défaut)`) actually correct?**
  _`Séquence des 6 rôles joués par mindwtr.list` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.vault_passw.sh script`, `certbot via snap (v5.6.0, mode classic)`, `TT-RSS (ttrss-docker)` to the rest of the system?**
  _47 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Traefik & Reverse-Proxy Pitfalls` be split into smaller, more focused modules?**
  _Cohesion score 0.1225296442687747 - nodes in this community are weakly interconnected._