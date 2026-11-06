# Actions — logs puttini persistants via journald (2026-10-08)

Contexte : l'alerte « session iCloud expirée » de puttini (2026-10-08 16:58 UTC)
n'a pas pu être analysée, les logs Docker (`json-file`) ayant disparu au
redéploiement de 21:22 UTC. Cette branche passe puttini sur le driver `journald`
et rend le journal de glaurung persistant. Supprimer ce fichier une fois tout
coché.

## Préalable sur M6

- [ ] Fermer la connexion SSH maîtresse figée vers GitHub (tous les `git pull`/`push`
      bloquaient ; contournée avec `GIT_SSH_COMMAND="ssh -o ControlMaster=no -o ControlPath=none"`) :
      `ssh -O exit git@github.com`, puis vérifier qu'un `git -C ~/www/c/monserveur fetch` passe.

## Merge

- [ ] Relire et merger la PR `puttini-logs-journald` (monserveur).
- [ ] `git -C ~/www/c/monserveur pull` sur master.

## Déploiement — dans cet ordre

- [ ] 1. Journal persistant : `cd ~/www/c/monserveur/ansible && ./run role journald-persistent-setup`
      (dry-run), relire, puis `./run role journald-persistent-setup run`.
- [ ] 2. puttini : `./run list puttini.list` (dry-run), relire, puis `./run list puttini.list run`
      (`up -d` recrée le conteneur avec le nouveau driver).

## Tests sur glaurung

- [ ] `ls -ld /var/log/journal` existe, `journalctl --disk-usage` indique une taille sur disque.
- [ ] `docker inspect -f '{{.HostConfig.LogConfig}}' puttini` → `{journald map[tag:puttini]}`.
- [ ] `docker logs puttini` affiche les logs (lecture inchangée).
- [ ] `journalctl CONTAINER_NAME=puttini --since today` affiche les logs
      (nécessite le groupe `systemd-journal` ou `adm`, sinon sudo).
- [ ] Recréer le conteneur (redéploiement ou `docker-compose -f docker-compose.puttini.yml up -d --force-recreate`)
      et vérifier que `journalctl CONTAINER_NAME=puttini` montre toujours les lignes d'avant.
- [ ] Après le prochain reboot de glaurung : les logs d'avant le reboot sont toujours là.

## Suite de l'analyse iCloud

- [ ] À la prochaine alerte « session iCloud expirée » : relire les logs puttini autour de
      l'heure de l'alerte (`journalctl CONTAINER_NAME=puttini --since "<heure-10min>" --until "<heure+10min>"`)
      pour savoir quelle étape d'authentification pyicloud a échoué. Si le niveau INFO ne suffit
      pas, passer le logger `pyicloud` en DEBUG.

## Documentation

- [ ] Relire le journal `~/Sync/infra-notes/cgd/rst/20261008_docker_logs_journald.rst`
      (écrit avant déploiement : corriger l'état « pas encore déployé ni testé » une fois les tests faits).
- [ ] Lancer le doc sync infra-notes.
