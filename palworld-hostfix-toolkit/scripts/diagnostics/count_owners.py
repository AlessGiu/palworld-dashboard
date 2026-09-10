import sys
from collections import Counter
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]

owners = Counter()
for e in char_map:
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {})
    if sp.get("IsPlayer", {}).get("value", False):
        continue
    owner = str(sp.get("OwnerPlayerUId", {}).get("value", "NO-OWNER-FIELD"))
    owners[owner] += 1

for uid, n in owners.most_common():
    print(f"owner={uid}: {n} pals")
