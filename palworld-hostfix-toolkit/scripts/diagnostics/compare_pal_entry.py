import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
label = sys.argv[2]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]

shown = 0
for e in char_map:
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {})
    if sp.get("IsPlayer", {}).get("value", False):
        continue
    if shown >= 2:
        break
    shown += 1
    tb = raw.get("trailing_bytes", [])
    ub = raw.get("unknown_bytes", [])
    print(f"[{label}] pal #{shown}  CharacterID={sp.get('CharacterID', {}).get('value')}")
    print(f"  key.PlayerUId={e['key']['PlayerUId']['value']}")
    print(f"  raw.group_id={raw.get('group_id')}")
    print(f"  unknown_bytes={bytes(ub).hex() if ub else '(none)'}")
    print(f"  trailing_bytes len={len(tb)} hex={bytes(tb).hex() if tb else '(none)'}")
    print(f"  SaveParameter keys: {sorted(sp.keys())}")
    print()
