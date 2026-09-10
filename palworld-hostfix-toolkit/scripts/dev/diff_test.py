import sys
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

print(f"original: {len(raw_gvas)}, rewritten: {len(rewritten)}, diff: {len(rewritten) - len(raw_gvas)}")

minlen = min(len(raw_gvas), len(rewritten))
first_diff = None
for i in range(minlen):
    if raw_gvas[i] != rewritten[i]:
        first_diff = i
        break

if first_diff is None:
    print("No byte difference in common prefix; extra/missing bytes are purely at the end.")
    print("tail of original:", raw_gvas[minlen-40:minlen])
    print("tail of rewritten:", rewritten[minlen-40:minlen])
else:
    print(f"first byte difference at offset {first_diff}")
    lo = max(0, first_diff - 40)
    hi = first_diff + 80
    print("original  :", raw_gvas[lo:hi])
    print("rewritten :", rewritten[lo:hi])
