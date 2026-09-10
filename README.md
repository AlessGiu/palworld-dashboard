# Palworld Dashboard

Genere `palworld_dashboard.html` depuis la sauvegarde du serveur Palworld (co-op) et le
deploie sur `palworld.pollice.dev` (CT111 / nginx). Tourne chaque heure via une tache
planifiee Windows (`PalworldDashboardHourly`) qui lance `generate_palworld_dashboard.py`.

## Mise en place sur une nouvelle machine

1. `pip install paramiko palworld_save_tools`
2. Copier `secrets_local.py.example` en `secrets_local.py` et remplir les vraies valeurs
   (identifiants SFTP Hosterfy, webhook Discord, IP Proxmox) -- ce fichier n'est jamais
   commit (voir `.gitignore`).
3. Recuperer `palworld-hostfix-toolkit/ooz/libooz.dll` (non versionne, licence upstream
   floue) : lancer `python palworld-hostfix-toolkit/scripts/fetch_ooz.py`, ou copier le
   fichier depuis une autre machine ou deja configuree.
4. Verifier la clé SSH `~/.ssh/id_ed25519_proxmox` (utilisee pour le `pct push` vers le
   CT111) est bien presente sur la machine.
5. `python generate_palworld_dashboard.py` -- telecharge la sauvegarde, regenere le HTML,
   le deploie et poste le diff sur Discord.

## Backend taches (onglet Organisation / kanban)

L'onglet "Organisation" est un vrai kanban partage (a faire / en cours / fait) qui survit
aux regenerations horaires : contrairement au reste du dashboard (regenere a partir de la
sauvegarde de partie), ses donnees vivent dans un service a part.

- `tasks_backend/` -- petit service Flask + SQLite (meme pattern que `ecurie-app`/`opel-dashboard`),
  deploye en conteneur Docker `palworld-tasks` sur le CT111 (port hote 5010:5000, volume
  nomme `palworld-tasks-data` pour la base SQLite).
- Expose sous `https://palworld.pollice.dev/api/` via une regle `location /api/` ajoutee au
  nginx partage (`/opt/nginx/nginx.conf` dans le CT111, conteneur `opt-static-1`), qui proxy
  vers `http://192.168.0.57:5010/` (IP LAN du CT111, meme pattern que chevaux.pollice.dev).
- Redeploiement (si le conteneur doit etre recree) : copier `tasks_backend/` vers
  `/opt/palworld-tasks/` sur le CT111 puis `docker compose up -d --build` dans ce dossier.
  La regle nginx `/api/` doit deja etre en place (voir ci-dessus) -- sinon la rajouter dans
  les deux blocs `server_name palworld.pollice.dev;` (port 80 et 443) avant `location /`.

## Fichiers non versionnes (voir `.gitignore`)

- `secrets_local.py` -- identifiants reels
- `palworld_dashboard.html`, `palworld_last_snapshot.json` -- sorties regenerees a chaque run
- `*.sav`, `remote_save*/`, `FULL_BACKUP_*/` -- sauvegardes brutes de la partie (gros binaires,
  retelechargeables via le script)
- `pst_site_backup/`, `pst_latest/` -- anciennes copies de reference de `palworld_save_tools`
  (le vrai package utilise au runtime est installe via pip)
