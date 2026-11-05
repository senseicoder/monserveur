# Cartographie privée sur glaurung — collecteur + oocarto

Rôles `collecteur-deploy` et `oocarto-deploy`, liste `ansible/carto.list`.
**Rien n'a été lancé** : ni check, ni run. Procédure à suivre par Cédric.

## Architecture

| Élément | Où | Remarque |
|---|---|---|
| Collecteur (`collecteur.php`) | conteneur `php:8.2-apache-buster` officiel, `https://{{ collecteur_domain }}/collecteur.php` | Aucun build. Classe `CCollecteurWebServeur` lue dans la lib partagée **installée sur l'hôte** (`/space/www/libs/LIB_PARTAGEE`, en lecture seule). Dépôts JSON dans `/space/applisdata/collecteurweb`, purgés après 2 jours (`/etc/cron.d/collecteur-purge`). |
| oocarto | image `ghcr.io/senseicoder/oocarto-web` (PHP 8.2 + mysqli/pdo_mysql, **sans code applicatif**), construite et publiée **en local** comme rat | Code oocarto et lib partagée **synchronisés depuis les clones locaux** (`oocarto_src_local`, `oocarto_lib_src_local`), donc aucun jeton d'accès aux dépôts sur glaurung. Le `code/config.inc.php` du dépôt est **exclu** et remplacé par un template. `prepend_central` et Zend Framework : ceux de l'hôte, en lecture seule. |
| Base | MariaDB native de glaurung, base et compte `oocarto` restreints à `172.18.%.%` | Même schéma que rat-setup (bind et pare-feu INPUT déjà posés par rat-setup). |
| Traitements | `/etc/cron.d/oocarto` → `/opt/oocarto/oocarto-cron.sh hourly|daily` → `code/crontab.d/<période>/*.php` dans le conteneur | Intégrations de l'infra d'origine exclues (`oocarto_cron_exclure` : vSphere, Proxmox, inventaire déclaratif, mails, push des gravités). |
| TLS | vhost Apache ACME + certbot + `certs/collecteur|oocarto`, entrées ajoutées dans `traefik-deploy` (`traefik-tls.yml`, hook de renouvellement) | Même schéma que puttini-deploy. |

Pourquoi pas l'image du banc `infra-oocarto/docker_dev` : elle part de
`epi_deb12_frontal` (Debian 12). Apache des images bullseye et plus récentes
plante sur le noyau 3.16 de glaurung (AH00141, constaté dans rat-setup). Elle est
aussi construite en clonant le dépôt avec un PAT, alors que l'ADR interdit tout
build sur glaurung. Pourquoi pas l'Apache de l'hôte : PHP 5.6.40 seulement, alors
que le code cible PHP 8.

## Prérequis

1. **DNS** : `collecteur.daneel.net` et `carto.daneel.net` (variables
   `collecteur_domain` / `oocarto_domain`, `group_vars/all/vars.yml`) vers glaurung.
2. **Secrets** (`ansible-vault edit group_vars/all/vault.yml`) — valeurs **neuves**,
   alphanumériques, car elles sont injectées dans du PHP entre apostrophes ; les
   rôles refusent sinon :
   ```bash
   openssl rand -hex 24   # une fois par clé
   ```
   `collecteur_pwd`, `oocarto_db_password`, `oocarto_http_password`. Ne jamais
   reprendre le mot de passe codé en dur dans le code du collecteur d'origine.
3. **Clones locaux à jour** sur le poste qui lance Ansible : `~/www/e/infra-oocarto`
   et `~/www/o/infra-lib-partagee`. C'est leur état qui est déployé.
4. PAT ghcr.io (`cmdp show services/github.com/docker_registry`), comme pour rat.

## Mise en service

```bash
cd ~/www/c/monserveur/ansible
./run list carto.list            # mode check par défaut
./run list carto.list run        # réel
./run list glaurung.list         # (ou le seul traefik-deploy) APRÈS carto.list :
                                 # traefik-tls.yml référence certs/collecteur|oocarto,
                                 # qui doivent déjà exister
```

## Vérifications après le run

- `curl -s -o /dev/null -w '%{http_code}' -d 'pwd=x&serveur=x&canal=x&cmd=get&donnees=x' https://collecteur.daneel.net/collecteur.php` → 200
  (le corps compressé contient `auth error`).
- `https://carto.daneel.net/` : page oocarto, identifiant `oocarto_http_login`.
- `docker exec oocarto-web php crontab.d/daily/01_get_ecfacts.php` (dans
  `/space/www/apps/infra-oocarto/code`) : lit le collecteur sans erreur.
- `/var/log/oocarto-cron.log` après le premier passage horaire.

## Hors périmètre (tâches séparées)

- Clients ecfacts (M6, M7, ramoth2, glaurung…) : fichiers de conf `collecteur_url`
  et `collecteur_pwd` pour pousser vers cette instance.
- Bascule vers l'ACME natif de Traefik (une autre tâche est en cours sur ce
  sujet) : les deux rôles suivent le schéma certbot actuel et devront suivre
  la bascule.

## Points à vérifier au premier run

- `prepend_central.inc.php` de l'hôte (paquet arborescence de juillet 2026) sous
  PHP 8.2 dans le conteneur. Repli possible : définir les constantes
  (`CHEMIN_LIB_PARTAGEE`, `CHEMIN_ZF`) dans `php-oocarto.ini` plutôt qu'un prepend.
- Chemin `CHEMIN_ZF . '1.13.0/'` présent dans `/space/www/libs/ZendFramework` de
  l'hôte (paquet `epi-zendframework` 1.13.0 vu installé le 24/09).
- Extensions PHP : seules mysqli et pdo_mysql sont ajoutées à l'image officielle.
  En cas d'erreur « call to undefined function », ajouter l'extension dans le Dockerfile.
