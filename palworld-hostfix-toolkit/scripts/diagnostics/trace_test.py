import sys, traceback
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
try:
    gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
    print("PARSE OK")
except Exception:
    traceback.print_exc()
