import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import UUID
from collections import Counter

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
wsd = json_data["properties"]["worldSaveData"]["value"]
char_map = wsd["CharacterSaveParameterMap"]["value"]

# Build instance_id -> (is_player, key_guid) from char map
inst_info = {}
for e in char_map:
    inst = str(e["key"]["InstanceId"]["value"])
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {})
    is_player = sp.get("IsPlayer", {}).get("value", False)
    inst_info[inst] = is_player

group_map = wsd["GroupSaveDataMap"]["value"]
for gi, group in enumerate(group_map):
    group_type = group["value"]["GroupType"]["value"]["value"]
    if group_type != "EPalGroupType::Guild":
        continue
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw:
        print(f"group[{gi}]: decoded OK — handles: {len(raw.get('individual_character_handle_ids', []))}")
        continue
    b = bytes(raw["values"])
    print(f"group[{gi}] Guild raw blob len={len(b)}")
    # For each known instance id, locate its raw bytes and read the 16 bytes immediately before (the handle guid)
    guid_counter = Counter()
    found = 0
    for inst, is_player in inst_info.items():
        inst_bytes = UUID.from_str(inst).raw_bytes
        idx = b.find(inst_bytes)
        if idx >= 16:
            handle_guid = UUID(b[idx-16:idx])
            guid_counter[(str(handle_guid), is_player)] += 1
            found += 1
    print(f"  handles matched to known instances: {found}")
    for (guid, is_player), n in guid_counter.most_common(10):
        print(f"    handle_guid={guid}  is_player={is_player}  count={n}")
