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

## Fichiers non versionnes (voir `.gitignore`)

- `secrets_local.py` -- identifiants reels
- `palworld_dashboard.html`, `palworld_last_snapshot.json` -- sorties regenerees a chaque run
- `*.sav`, `remote_save*/`, `FULL_BACKUP_*/` -- sauvegardes brutes de la partie (gros binaires,
  retelechargeables via le script)
- `pst_site_backup/`, `pst_latest/` -- anciennes copies de reference de `palworld_save_tools`
  (le vrai package utilise au runtime est installe via pip)
