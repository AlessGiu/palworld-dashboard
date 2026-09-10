import sys
import json
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()

raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()

gvas_file2 = GvasFile.load(json_data)
rewritten = gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES)

# Re-parse the rewritten bytes to compare JSON structures (not raw bytes)
gvas_file3 = GvasFile.read(rewritten, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data2 = gvas_file3.dump()

s1 = json.dumps(json_data, sort_keys=True, default=str)
s2 = json.dumps(json_data2, sort_keys=True, default=str)

print(f"json_data length: {len(s1)}, json_data2 (from rewritten) length: {len(s2)}")
print(f"JSON representations identical: {s1 == s2}")

if s1 != s2:
    # find first differing character for a clue
    minlen = min(len(s1), len(s2))
    for i in range(minlen):
        if s1[i] != s2[i]:
            print(f"first char diff at {i}")
            print("json_data :", s1[max(0,i-150):i+150])
            print("json_data2:", s2[max(0,i-150):i+150])
            break
