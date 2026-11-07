# happy-server-deploy — relais happy auto-hébergé

Serveur de synchronisation de [happy](https://github.com/slopus/happy) (client mobile
pour Claude Code) hébergé sur glaurung, pour que le CLI du poste (M7) et l'app Android
passent par ce relais plutôt que par le relais public `api.cluster-fluster.com`.

Sources lues le 2026-11-07 (dépôt slopus/happy, commit `490c33a`) :
`packages/happy-server-self-host/README.md`, `packages/happy-server/sources/standalone.ts`,
`docs/plans/happy-serve-self-host.md`, `docs/deployment.md`, `docs/encryption.md`, `docs/api.md`.

## Ce qui est déployé

- Paquet npm **`happy-server-self-host`** (version épinglée dans `defaults/main.yml`,
  1.1.11 au 2026-11-07), binaire `happy-server migrate | serve`, en **mode standalone** :
  base **PGlite embarquée** et fichiers sur disque local — ni Postgres, ni Redis, ni S3
  (README du paquet : « embedded PGlite storage and local filesystem uploads — no
  Postgres, no Redis, no S3 »). Le mode « production » (`Dockerfile.server`,
  `docs/deployment.md`) exige au contraire Postgres + Redis + S3 : écarté.
- Image construite **en local** (`files/image/Dockerfile`, `node:22-bookworm-slim` +
  `openssl`), poussée sur `ghcr.io/senseicoder/happy-server:<compteur>`, jamais construite
  sur glaurung. Le conteneur applique les migrations puis sert l'API et l'app web sur 3005.
- Traefik (`websecure`, 443) → `happy-server:3005`, certificat certbot webroot comme les
  autres services ; le hook de renouvellement et `traefik-tls.yml` sont dans `traefik-deploy`.
- Données : `/opt/mindwtr/data/happy-server/data` (`pglite/`, `files/`), propriété de
  l'utilisateur `node` (1000) de l'image ; sauvegardé par `backup-setup`.
- **Secret maître** `HANDY_MASTER_SECRET` : généré sur glaurung au premier déploiement
  (32 octets aléatoires) dans `/opt/mindwtr/data/happy-server/master-secret.env` (0600),
  jamais dans le dépôt ni dans les journaux Ansible. Il est inclus dans la sauvegarde :
  le perdre rend illisibles les jetons tiers chiffrés côté serveur.

Essai local du 2026-11-07 (image construite depuis ce rôle, conteneur jetable sur M6) :
`happy-server` affiche l'aide attendue ; 37 migrations au premier démarrage, aucune au
second (persistance du volume) ; `GET /health` → `{"status":"ok",…,"service":"happy-server"}` ;
`/` sert l'app web ; Socket.IO `/v1/updates` répond en polling (200) et en websocket (101).

## Déployer

1. Créer l'enregistrement DNS `happy.daneel.net` (CNAME → `glaurung.daneel.net`) — **non
   automatisé**.
2. `cd ansible && ./run list happy.list` (dry-run), lire le diff — en particulier les lignes
   **retirées** de `traefik-tls.yml` et du hook (cf. branches déployées non mergées).
3. `./run list happy.list run`.
4. Vérifier : `curl -s https://happy.daneel.net/health`.

## Client PC (M7)

Le CLI s'appelle désormais **`happy`** sur npm (README du projet : « Migrated from the
`happy-coder` package ») : `happy` 1.2.6 (27/10/2026, = `cli-1.2.6` de GitHub) ;
`happy-coder` est resté en 1.1.9 (14/05/2026). Installation en espace utilisateur avec le
Node 22 déjà présent :

```bash
PATH=$HOME/.local/node22/bin:$PATH npm_config_prefix=$HOME/.local/happy \
  npm install -g happy@1.2.6
```

Pointer le CLI vers le relais **avant** toute authentification (précédence dans
`packages/happy-cli/src/configuration.ts` : variable d'environnement, puis
`~/.happy/settings.json`, puis le relais public) — soit dans `~/.happy/settings.json` :

```json
{ "serverUrl": "https://happy.daneel.net", "webappUrl": "https://happy.daneel.net" }
```

soit par `HAPPY_SERVER_URL=https://happy.daneel.net` et `HAPPY_WEBAPP_URL=https://happy.daneel.net`.
Pas de repli automatique sur le relais public quand l'URL est définie
(`docs/plans/happy-serve-self-host.md` § « No fallback »). Puis `happy auth login`,
`happy daemon start`, `happy claude`.

## App Android

App **Happy** du Play Store (`com.ex3ndr.happy`, client natif de `packages/happy-android`) :
réglages → Serveur → **Custom Server URL** = `https://happy.daneel.net`, puis se
déconnecter et se reconnecter (« For self-hosted servers. Sign out and back in after
changing it. »). Ne jamais l'appairer au relais public.

## Compatibilité client ↔ serveur

- `happy-server-self-host` publié (1.1.11, 10/06/2026) est **plus ancien** que le code du
  dépôt : 37 migrations contre 39 (manquent `add_projects`, 11/06, et
  `add_session_avatars`, 14/09). Aucune version plus récente n'est publiée sur npm.
- Le CLI 1.2.6 découvre ce même paquet pour `happy server` : c'est la combinaison
  officiellement prévue. Comparaison statique des chaînes de route du CLI 1.2.6 publié
  et du serveur 1.1.11 publié : toutes les routes happy appelées par le CLI existent
  côté serveur (`/v1/auth/request`, `/v1/connect`, `/v1/machines`, `/v1/push-tokens`,
  `/v1/sessions`, `/v1/updates`, `/v3/sessions`, `push-event`) ; les deux « absentes »
  sont des URL tierces (OAuth Google et Anthropic). **Non vérifié en conditions réelles.**
- L'app Android récente a une fonction « projets » (`ProjectApi.kt`) que le serveur 1.1.11
  n'a pas : à attendre en échec dans l'app, sans incidence sur les sessions.

## Modèle de sécurité (d'après `docs/encryption.md`, `docs/api.md`)

- **Chiffré de bout en bout par les clients** (le serveur ne stocke que des blobs opaques) :
  messages des sessions, métadonnées et état d'agent des sessions, métadonnées et état du
  daemon/machine, artefacts, valeurs du magasin clé-valeur, clés d'accès.
- **Visible par le serveur** : identifiants, tags et versions, horodatages, tailles et
  rythme des échanges, clés publiques des comptes, adresses IP, jetons push.
- **Notifications push** : le titre, le texte et le titre de session des notifications
  partent **en clair** du CLI vers le serveur (`/v1/sessions/:id/push-event`) puis vers le
  service push (Expo `exp.host` dans le serveur 1.1.11 ; le dépôt passe à
  `push.cluster-fluster.com`), donc aussi vers Google (FCM) — même en auto-hébergé.
- **Jetons tiers** (GitHub, fournisseurs d'IA) éventuellement confiés au serveur : chiffrés
  au repos avec une clé dérivée de `HANDY_MASTER_SECRET`, pas de bout en bout.
- **Inscription ouverte** : `POST /v1/auth` crée un compte pour toute clé publique qui
  signe le défi ; le serveur est multi-comptes, sans restriction au premier client
  (point ouvert n° 5 du plan self-host). Un tiers ne peut pas lire nos données, mais peut
  utiliser le relais. Pistes non mises en place : limite de débit Traefik, liste blanche
  d'IP impossible avec un téléphone en 4G.
