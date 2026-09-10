import sys, json
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
wsd = json_data["properties"]["worldSaveData"]["value"]

ccsd = wsd["CharacterContainerSaveData"]["value"]
print(f"[{label}] containers: {len(ccsd)}")
for i, c in enumerate(ccsd):
    key = c["key"]
    # key structure may include ID and belong-info
    key_keys = list(key.keys()) if isinstance(key, dict) else key
    cid = key.get("ID", {}).get("value") if isinstance(key, dict) else "?"
    slots = c["value"].get("Slots", {}).get("value", {})
    slot_values = slots.get("values", []) if isinstance(slots, dict) else []
    # count non-empty slots (those with a non-zero instance id)
    filled = 0
    for s in slot_values:
        rd = s.get("RawData", {}).get("value", {})
        inst = rd.get("instance_id") if isinstance(rd, dict) else None
        if inst and str(inst) != "00000000-0000-0000-0000-000000000000":
            filled += 1
    print(f"  container[{i}] key_fields={key_keys if isinstance(key_keys, list) else '?'} id={cid} slots={len(slot_values)} filled={filled}")
    if i == 0:
        print(f"    full key dump: {json.dumps(key, default=str)[:400]}")
        if slot_values:
            print(f"    slot[0] dump: {json.dumps(slot_values[0], default=str)[:400]}")
