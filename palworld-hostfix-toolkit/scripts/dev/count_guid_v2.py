import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import UUID

def format_guid(g):
    g = g.replace("-", "").lower()
    return "{}-{}-{}-{}-{}".format(g[:8], g[8:12], g[12:16], g[16:20], g[20:])

path = sys.argv[1]
old_fmt = format_guid(sys.argv[2])
new_fmt = format_guid(sys.argv[3])
old_bytes = UUID.from_str(old_fmt).raw_bytes
new_bytes = UUID.from_str(new_fmt).raw_bytes

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
    oc = b.count(old_bytes)
    nc = b.count(new_bytes)
    if oc or nc:
        print(f"group[{gi}] type={group_type} len={len(b)}  old_occurrences={oc}  new_occurrences={nc}")
