import sys, json
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
target_uid = sys.argv[2]  # formatted like 00000000-0000-0000-0000-000000000001

with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()

char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
count = 0
for entry in char_map:
    if entry["key"]["PlayerUId"]["value"] == target_uid:
        count += 1
        if count <= 3:
            raw = entry["value"]["RawData"]["value"]
            obj = raw.get("object", {}) if isinstance(raw, dict) else {}
            # Print top-level keys inside object to find owner-related fields
            keys = list(obj.keys()) if isinstance(obj, dict) else []
            print(f"entry {count}: instance_id={entry['key']['InstanceId']['value']}")
            print(f"  RawData top-level keys: {list(raw.keys()) if isinstance(raw, dict) else raw}")
            for k in keys:
                kl = k.lower()
                if "owner" in kl or "player" in kl:
                    print(f"    object.{k} = {obj[k]}")
            char_id = obj.get("CharacterID", {}).get("value") if "CharacterID" in obj else None
            print(f"  CharacterID={char_id}")
print(f"\nTotal entries with PlayerUId={target_uid}: {count}")
