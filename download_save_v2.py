import paramiko
import os
import stat

from secrets_local import SFTP_HOST as HOST, SFTP_PORT as PORT, SFTP_USER as USER, SFTP_PASS as PASS

REMOTE_DIR = "/Pal/Saved/SaveGames/0/D5C16DC3464E7CC492225ABB991F1FA2"
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "remote_save_v2")

os.makedirs(LOCAL_DIR, exist_ok=True)

transport = paramiko.Transport((HOST, PORT))
transport.connect(username=USER, password=PASS)
sftp = paramiko.SFTPClient.from_transport(transport)


def download_recursive(remote_path, local_path, skip_backup=True):
    os.makedirs(local_path, exist_ok=True)
    for entry in sftp.listdir_attr(remote_path):
        if skip_backup and entry.filename == "backup":
            continue
        r = remote_path + "/" + entry.filename
        l = os.path.join(local_path, entry.filename)
        if stat.S_ISDIR(entry.st_mode):
            download_recursive(r, l, skip_backup=False)
        else:
            sftp.get(r, l)
            print("downloaded", r, "->", l, entry.st_size)


download_recursive(REMOTE_DIR, LOCAL_DIR)

sftp.close()
transport.close()
print("DONE")
