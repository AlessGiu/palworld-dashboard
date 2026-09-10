"""
Downloads libooz.dll directly from the upstream zao/ooz GitHub release into ooz/.

We don't bundle the binary in this repo: zao/ooz has no explicit license (GitHub
reports license: null), so redistributing a copy of their build ourselves is a
gray area. Fetching it straight from their release on demand — the same way
`npm install` pulls a package from its own registry — sidesteps that entirely.
"""
import io
import os
import sys
import urllib.request
import zipfile

OOZ_VERSION = "0.2.4"
RELEASE_URL = f"https://github.com/zao/ooz/releases/download/v{OOZ_VERSION}/bun-{OOZ_VERSION}-x64-Release.zip"
DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ooz")


def main():
    dll_path = os.path.join(DEST_DIR, "libooz.dll")
    if os.path.exists(dll_path) and "--force" not in sys.argv:
        print(f"Already present: {dll_path} (use --force to re-download)")
        return

    print(f"Downloading {RELEASE_URL} ...")
    with urllib.request.urlopen(RELEASE_URL) as resp:
        archive_bytes = resp.read()

    os.makedirs(DEST_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        dll_names = [n for n in zf.namelist() if n.lower().endswith("libooz.dll")]
        if not dll_names:
            raise SystemExit(f"libooz.dll not found in archive. Contents: {zf.namelist()}")
        with zf.open(dll_names[0]) as src, open(dll_path, "wb") as dst:
            dst.write(src.read())

    print(f"Extracted {dll_path}")
    print(f"Set PALWORLD_OOZ_DLL_PATH={dll_path}")


if __name__ == "__main__":
    main()
