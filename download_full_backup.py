import paramiko
import os
import stat

from secrets_local import SFTP_HOST as HOST, SFTP_PORT as PORT, SFTP_USER as USER, SFTP_PASS as PASS

REMOTE_DIR = "/Pal/Saved/SaveGames/0/D5C16DC3464E7CC492225ABB991F1FA2"
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "FULL_BACKUP_20260907")

transport = paramiko.Transport((HOST, PORT))
transport.connect(username=USER, password=PASS)
sftp = paramiko.SFTPClient.from_transport(transport)

total_bytes = [0]
total_files = [0]


def download_recursive(remote_path, local_path):
    os.makedirs(local_path, exist_ok=True)
    for entry in sftp.listdir_attr(remote_path):
        r = remote_path + "/" + entry.filename
        l = os.path.join(local_path, entry.filename)
        if stat.S_ISDIR(entry.st_mode):
            download_recursive(r, l)
        else:
            sftp.get(r, l)
            total_bytes[0] += entry.st_size
            total_files[0] += 1


download_recursive(REMOTE_DIR, LOCAL_DIR)

sftp.close()
transport.close()
print(f"DONE - {total_files[0]} files, {total_bytes[0] / (1024*1024):.1f} MB")
print("Saved to:", LOCAL_DIR)
