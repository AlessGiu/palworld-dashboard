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
print(f"Total entries: {len(char_map)}")
c = Counter(e["key"]["PlayerUId"]["value"] for e in char_map)
for uid, n in c.most_common(10):
    print(f"  {uid}: {n}")
