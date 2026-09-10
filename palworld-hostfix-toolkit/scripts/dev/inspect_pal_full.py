import sys, json
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

def default(o):
    return str(o)

# find a non-player entry (i.e. one whose PlayerUId is all-zero, a wild/base pal) to inspect fully
for entry in char_map:
    puid = entry["key"]["PlayerUId"]["value"]
    if puid == "00000000-0000-0000-0000-000000000000":
        raw = entry["value"]["RawData"]["value"]
        obj = raw.get("object", {})
        print("Sample UNOWNED pal object full dump:")
        print(json.dumps(obj, indent=2, default=default)[:3000])
        break
