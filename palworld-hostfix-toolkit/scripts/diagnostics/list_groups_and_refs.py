import sys
from collections import Counter
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import UUID

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
wsd = json_data["properties"]["worldSaveData"]["value"]

print("--- groups in GroupSaveDataMap ---")
group_ids = set()
for gi, group in enumerate(wsd["GroupSaveDataMap"]["value"]):
    gtype = group["value"]["GroupType"]["value"]["value"]
    key_id = str(group["key"])
    raw = group["value"]["RawData"]["value"]
    blob_id = ""
    if "values" in raw:
        blob_id = str(UUID(bytes(raw["values"][:16])))
    print(f"group[{gi}] key={key_id} type={gtype} blob_group_id={blob_id}")
    group_ids.add(key_id.lower())

print("\n--- group_id referenced by char entries ---")
refs = Counter()
for e in wsd["CharacterSaveParameterMap"]["value"]:
    raw = e["value"]["RawData"]["value"]
    gid = str(raw.get("group_id", "?"))
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {})
    is_player = sp.get("IsPlayer", {}).get("value", False)
    refs[(gid, is_player)] += 1
for (gid, is_player), n in refs.most_common():
    exists = gid.lower() in group_ids
    print(f"group_id={gid}  is_player={is_player}  count={n}  EXISTS_IN_GROUPMAP={exists}")
