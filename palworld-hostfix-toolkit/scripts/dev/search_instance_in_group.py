import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
instance_id_hex = sys.argv[2].replace("-", "")
target = bytes.fromhex(instance_id_hex)

with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

for gi, group in enumerate(group_map):
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw:
        continue
    b = bytes(raw["values"])
    idx = 0
    while True:
        idx = b.find(target, idx)
        if idx == -1:
            break
        preceding_16 = b[max(0, idx-16):idx]
        print(f"group[{gi}] len={len(b)}  instance_id found at offset {idx}, preceding 16 bytes (owner guid?): {preceding_16.hex()}")
        idx += 1
