# Installation — Phase 1 : Traefik + mindwtr-cloud

## Prérequis

Sur la machine locale :
- Ansible ≥ 2.14
- Fichier `ansible/ssh-config` configuré pour joindre `glaurung`
- Fichier `ansible/.vault_passw.sh` présent (fournit le mot de passe vault via `cmdp`)
- DNS : `mindwtr.daneel.net` → 51.254.212.250 (IP de glaurung)

## Séquence

### 1. Installer la collection Ansible

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
```

### 2. Créer le vault avec le token Mindwtr

```bash
cp group_vars/all/vault.yml.example group_vars/all/vault.yml
```

Éditer `vault.yml` et remplacer `CHANGEME` par un token généré :

```bash
cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1
```

Puis chiffrer :

```bash
ansible-vault encrypt group_vars/all/vault.yml
```

### 3. Vérifier la connectivité

```bash
ansible all -m ping
```

### 4. Dry-run (check mode)

```bash
cd ansible && ./run list mindwtr.list
```

Dry-run par défaut (pas besoin de `--check --diff`, c'est le comportement du wrapper `run`). Vérifie ce qui serait modifié sans toucher au serveur. Les tâches `command` (réseau Docker, certbot, compose up) ne sont pas simulables et s'affichent comme `skipped` — c'est normal.

### 5. Lancer les rôles

```bash
cd ansible && ./run list mindwtr.list run
```

La liste `mindwtr.list` joue dans l'ordre les 6 rôles suivants (idempotents) :
1. `docker-engine-setup` — installation Docker CE + plugin Compose
2. `network-ipv6-setup` — forwarding IPv6 kernel + route par défaut OVH
3. `docker-network-mindwtr-setup` — daemon.json IPv6 + réseau Docker `mindwtr`
4. `traefik-deploy` — répertoires, fichiers Compose et config TLS Traefik, démarrage
5. `mindwtr-cloud-deploy` — vhost Apache + certbot pour `mindwtr.daneel.net`, Compose, démarrage
6. `vaultwarden-deploy` — vhost Apache + certbot pour `vault.daneel.net`, Compose, démarrage

### 6. Vérifier le déploiement

```bash
# Depuis glaurung
docker-compose -f /opt/mindwtr/docker-compose.traefik.yml ps
docker-compose -f /opt/mindwtr/docker-compose.mindwtr.yml ps

# Test HTTPS
curl -I https://mindwtr.daneel.net:8787/health
```

### 7. Configurer l'app Mindwtr

| Champ | Valeur |
|-------|--------|
| URL | `https://mindwtr.daneel.net:8787/v1` |
| Token | (valeur de `mindwtr_token` dans le vault) |

## Redéploiement

```bash
cd ansible && ./run list mindwtr.list run
```

Les tâches sont idempotentes : Docker, le réseau et le certificat sont skippés s'ils existent déjà.
Pour forcer la mise à jour des conteneurs : `docker-compose pull` sur le serveur.

## Modifier le token

1. Éditer le vault : `ansible-vault edit group_vars/all/vault.yml`
2. Relancer : `cd ansible && ./run list mindwtr.list run`
