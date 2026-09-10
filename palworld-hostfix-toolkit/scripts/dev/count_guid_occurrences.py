import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
old_guid_hex = sys.argv[2]
new_guid_hex = sys.argv[3]

old_bytes = bytes.fromhex(old_guid_hex)
new_bytes = bytes.fromhex(new_guid_hex)

with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

for gi, group in enumerate(group_map):
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw:
        continue
    b = bytes(raw["values"])
    old_count = b.count(old_bytes)
    new_count = b.count(new_bytes)
    if old_count or new_count:
        print(f"group[{gi}] type={group_type} len={len(b)}  old_guid_occurrences={old_count}  new_guid_occurrences={new_count}")
