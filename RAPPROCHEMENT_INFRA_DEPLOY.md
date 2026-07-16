# Rapprochement vers le modèle infra-deploy / maconfiguration

## Référence observée

`maconfiguration` a déjà fait ce travail de rapprochement (voir son `RAPPROCHEMENT_INFRA_DEPLOY.md` et son `CLAUDE.md`) : wrapper `run` avec dry-run par défaut, `run_role.yml` générique, fichiers `*.list` pour composer des séquences de rôles, résolution de rôles externes via `ANSIBLE_ROLES_PATH`. `monserveur` reprend directement ce mécanisme plutôt que de le redériver depuis `infra-deploy` seul.

Contrairement à `maconfiguration` (multi-postes), `monserveur` ne cible qu'un seul host (`glaurung`). Les `*.list` gardent un intérêt malgré tout : composer des sous-ensembles de rôles rejouables isolément (ex. rejouer juste la stack mindwtr sans toucher à rustdesk ou à la migration rat).

Le but n'est pas de copier le périmètre employeur. L'objectif est de reprendre les mécanismes d'exploitation qui rendent les rôles rejouables, auditables et composables — et de garder la capacité (déjà éprouvée par `maconfiguration`) d'importer un rôle `infra-deploy` sans le copier, pour le jour où un rôle générique pertinent existera.

**Note de terminologie** : ce document utilise "Étape" (pas "Phase") pour le plan de migration Ansible, afin de ne pas entrer en collision avec "Phase 1"/"Phase 2" qui désignent déjà, dans le `CLAUDE.md` de ce repo, les étapes du déploiement applicatif (Traefik sur 8787 puis sur 80/443, cf. `PHASE2.md`).

## Écarts structurants

| Sujet | monserveur actuel | Cible (maconfiguration/infra-deploy) | Écart utile |
|-------|--------------------|----------------------------------------|--------------|
| Entrée principale | `install.yml` monolithique, séquence fixe de rôles | `run_role.yml` générique | Jouer un rôle isolé proprement |
| Composition | rôles + tags en dur dans `install.yml` | fichiers `*.list` | Profils lisibles, versionnés, rejouables par sous-ensemble |
| Résolution de rôles externes | `roles_path = roles` fixe dans `ansible.cfg`, aucune résolution externe | `ANSIBLE_ROLES_PATH` (`roles:infra-deploy/ansible/roles`), positionné par le wrapper | Capacité d'importer un rôle `infra-deploy` sans copie ni divergence |
| Rôle `infra-deploy` (local) | nom trompeur (aucun rapport avec le repo pro), monolithique : Docker + IPv6 + réseau mindwtr + Traefik + mindwtr-cloud + vaultwarden + certbot | découpage en rôles kebab-case par domaine + action | Rejouabilité, clarté, rôles plus petits et audités séparément |
| Defaults | partiels : `rat-setup`, `rat-migratefromgandi`, `rustdesk` en ont ; `ssh-securite` n'en a pas ; le rôle `infra-deploy` en a un minimal (`deploy_dir`) | systématiques | Documentation locale des variables de chaque rôle |
| Handlers | présents seulement dans le rôle `infra-deploy` (restart traefik/mindwtr) | centralisés par rôle | Redémarrages cohérents une fois le découpage fait |
| Lancement | `ansible-playbook install.yml --limit glaurung`, exécution directe | dry-run par défaut (`run`) | Exploitation plus prudente sur un serveur de prod perso unique |
| Tests | aucun | pas prioritaire ici (host réel unique, pas de flotte à tester) | — |

## Cible proposée pour monserveur

```
ansible/
  ansible.cfg                 ← conservé (inventory, vault, become) ; roles_path reste "roles" en repli
  inventory/hosts.yml
  group_vars/all/
    vars.yml
    vault.yml
  requirements.yml
  run                         ← nouveau wrapper, dry-run par défaut, ANSIBLE_ROLES_PATH conditionnel
  run_role.yml                ← nouveau, playbook générique "role"
  base.list
  mindwtr.list
  rat.list
  rustdesk.list
  roles/
    docker-engine-setup/
    network-ipv6-setup/
    docker-network-mindwtr-setup/
    traefik-deploy/
    mindwtr-cloud-deploy/
    vaultwarden-deploy/
    rat-setup/
    rat-migratefromgandi/
    rustdesk/
    ssh-securite/
```

`ANSIBLE_ROLES_PATH`, exporté par le wrapper, prend le pas sur `roles_path` d'`ansible.cfg` (comportement standard Ansible : une variable d'environnement équivalente à un réglage de `ansible.cfg` est prioritaire). Pas de conflit à gérer, juste à documenter.

**Piège de nommage rencontré à l'implémentation** : `deploy_dir` (générique) ne peut pas devenir un `group_vars/all` — `rustdesk` et, jusqu'à une modification concurrente pendant ce chantier, `rat-setup`/`rat-migratefromgandi` définissent chacun leur propre `deploy_dir` en *default de rôle*. Un `group_vars/all.deploy_dir` global aurait silencieusement écrasé ces defaults (précédence Ansible : `group_vars` bat les defaults de rôle), redirigeant par exemple `rustdesk` vers `/opt/mindwtr` au lieu de `/opt/rustdesk`. Retenu : `mindwtr_deploy_dir`, sur le même modèle que `rat_deploy_dir` déjà en place — chaque stack a son propre nom de variable qualifié, jamais de générique partagé au niveau `group_vars/all`.

## Profils de rôles proposés

### `base.list`

Socle serveur, prérequis communs :

```
docker-engine-setup
network-ipv6-setup
```

### `mindwtr.list`

Stack mindwtr complète (Phase 1 applicative déjà déployée) :

```
docker-network-mindwtr-setup
traefik-deploy
mindwtr-cloud-deploy
vaultwarden-deploy
```

### `rat.list`

Migration rat en cours (étape 4 validée le 2026-07-16, déploiement à blanc) :

```
rat-setup
rat-migratefromgandi
```

### `rustdesk.list`

```
rustdesk
```

### `legacy.list` ou intégré à `base.list` une fois complété

```
ssh-securite   # stub Phase 2 applicative, durcissement sshd à compléter
```

Cédric a indiqué prévoir d'autres listes à l'avenir — cette liste de profils n'est pas figée.

## Plan de migration recommandé

### Étape 1 — ce document

Documenter l'écart et la cible avant tout changement de code. Fait.

### Étape 2 — rendre l'exploitation lisible (risque faible)

Sans toucher au contenu des rôles existants :

- `run_role.yml` minimal qui applique `role`
- wrapper `run` inspiré de `maconfiguration` : dry-run par défaut (`-C -D`), mot-clé `run` pour exécuter réellement, `ANSIBLE_ROLES_PATH` conditionnel sur l'existence de `~/www/e/infra-deploy/ansible/roles`
- `*.list` initiaux ci-dessus
- `defaults/main.yml` sur `ssh-securite` (seul rôle actif qui n'en a pas)

**Révision (2026-07-16)** : `install.yml` a finalement été supprimé plutôt que conservé comme legacy — les `*.list` couvrent déjà tous les rôles actifs, garder un second point d'entrée (`./run legacy`) n'apportait rien et avait déjà divergé une fois (référence à `infra-deploy` restée après son découpage en Étape 3). `legacy`/`hosts`/`tags` retirés du wrapper `run` en conséquence.

### Étape 3 — découper le rôle `infra-deploy`

Le rôle actuel mélange plusieurs domaines indépendants (visibles dans les sections déjà commentées de `tasks/main.yml`) :

- `docker-engine-setup` — install Docker CE + plugin Compose. **Rôle local dédié**, pas un import `infra-deploy` : analysé et écarté — `epi-docker` n'est pas un obstacle (déployé sur les machines de Cédric), mais `docker_dockerce_setup`/`docker_dockercompose_setup` ne gèrent pas IPv6 dans leur `daemon.json.j2` (glaurung a `"ipv6": true` / `fixed-cidr-v6` en prod) et installent le binaire standalone `docker-compose` (v2.2.3) au lieu du plugin `docker-compose-plugin` (`docker compose`) déjà en place sur glaurung ; `docker_generic_setup`/`docker_dockerce_conf` sont du déploiement métier Epiconcept (semaphore, icanopee…), hors sujet.
- `network-ipv6-setup` — forwarding IPv6 kernel + service systemd `ipv6-default-route`, host-level, indépendant de Docker.
- `docker-network-mindwtr-setup` — `daemon.json` IPv6 + création/recréation du réseau Docker `mindwtr`. **⚠️ Point d'attention** : aujourd'hui couplé à l'arrêt/redémarrage des 3 stacks Compose (traefik/mindwtr/vaultwarden) quand `daemon.json` change ou que le réseau n'a pas IPv6. Préserver explicitement cette séquence (down avant redémarrage Docker/recréation réseau, up après) en la découpant — via handlers ou dépendances de rôles — sans la perdre.
- `traefik-deploy` — répertoires `mindwtr_deploy_dir`, `docker-compose.traefik.yml`, config TLS dynamique, `notify: restart traefik`.
- `mindwtr-cloud-deploy` — répertoire `data/cloud`, `docker-compose.mindwtr.yml`, vhost Apache + certbot du domaine mindwtr, `notify: restart mindwtr`.
- `vaultwarden-deploy` — répertoire `data/vaultwarden`, `docker-compose.vaultwarden.yml`, vhost Apache + certbot du domaine vaultwarden, `notify: restart vaultwarden`.

Risque moyen à élevé : ce rôle pilote des services en production sur l'unique serveur perso. À faire avec dry-run systématique et vérification service par service après chaque extraction, jamais en un seul commit massif.

### Étape 4 — defaults systématiques sur les nouveaux rôles

Fait. Aucune de leurs variables n'est un tunable propre au rôle — toutes viennent de `group_vars/all/vars.yml` (`mindwtr_deploy_dir`, `mindwtr_domain`, `vaultwarden_domain`, `acme_email`). Un default de rôle du même nom serait masqué par le group_var (cf. piège de nommage ci-dessus) sans rien apporter : les 6 `defaults/main.yml` documentent donc en commentaire la dépendance externe plutôt que de dupliquer une valeur ignorée.

## Position directe

Le gain n'est pas dans la syntaxe Ansible. Il est dans la séparation entre :

- le socle serveur (Docker, IPv6 kernel) ;
- la stack mindwtr (réseau, Traefik, mindwtr-cloud, Vaultwarden) ;
- les chantiers en cours (migration rat, durcissement SSH) ;
- les services indépendants (RustDesk).

Une fois cette séparation faite, modifier un service ne demande plus de rejouer (ou de relire) un rôle de 300+ lignes qui touche aussi les deux autres.

## Usage de rôles externes (infra-deploy)

Le mécanisme `ANSIBLE_ROLES_PATH` est mis en place dès l'Étape 2, mais aucun rôle `infra-deploy` n'est importé aujourd'hui : `docker-engine-setup` reste local pour les raisons détaillées à l'Étape 3 (IPv6, plugin Compose, rôles métier hors sujet). La capacité reste disponible pour un futur rôle générique (non-Docker) d'`infra-deploy` qui conviendrait tel quel — à évaluer au cas par cas, sans forcer un import qui n'apporterait rien aujourd'hui.
