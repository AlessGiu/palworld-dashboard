import paramiko
import os
import time

from secrets_local import SFTP_HOST as HOST, SFTP_PORT as PORT, SFTP_USER as USER, SFTP_PASS as PASS

REMOTE_BASE = "/Pal/Saved/SaveGames/0"
REMOTE_DIR = REMOTE_BASE + "/D5C16DC3464E7CC492225ABB991F1FA2"
REMOTE_OLD_DIR = REMOTE_BASE + "/D5C16DC3464E7CC492225ABB991F1FA2_BEFORE_GUILDFIX_" + str(int(time.time()))

LOCAL_DIR = os.path.join(os.path.dirname(__file__), "remote_save_v2")

transport = paramiko.Transport((HOST, PORT))
transport.connect(username=USER, password=PASS)
sftp = paramiko.SFTPClient.from_transport(transport)

# 1. rename remote current folder aside (safety net)
sftp.rename(REMOTE_DIR, REMOTE_OLD_DIR)
print("Renamed remote dir to", REMOTE_OLD_DIR)

# 2. recreate the target dir and Players subdir
sftp.mkdir(REMOTE_DIR)
sftp.mkdir(REMOTE_DIR + "/Players")

# 3. upload top-level files (skip backup/ dir, skip Players dir itself)
top_level_files = ["Level.sav", "LevelMeta.sav", "LocalData.sav", "WorldOption.sav"]
for fname in top_level_files:
    local_path = os.path.join(LOCAL_DIR, fname)
    remote_path = REMOTE_DIR + "/" + fname
    sftp.put(local_path, remote_path)
    print("uploaded", fname, os.path.getsize(local_path), "bytes")

# 4. upload Players/*.sav
players_dir = os.path.join(LOCAL_DIR, "Players")
for fname in os.listdir(players_dir):
    local_path = os.path.join(players_dir, fname)
    remote_path = REMOTE_DIR + "/Players/" + fname
    sftp.put(local_path, remote_path)
    print("uploaded Players/" + fname, os.path.getsize(local_path), "bytes")

sftp.close()
transport.close()
print("UPLOAD DONE")
