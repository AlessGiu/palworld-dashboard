import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

path = sys.argv[1]
gi_target = int(sys.argv[2])
lo = int(sys.argv[3])
hi = int(sys.argv[4])

with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

count = -1
for group in group_map:
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw or group_type != "EPalGroupType::Guild":
        continue
    count += 1
    if count != gi_target:
        continue
    b = bytes(raw["values"])
    for i in range(lo, min(hi, len(b)), 16):
        chunk = b[i:i+16]
        hexstr = " ".join(f"{x:02x}" for x in chunk)
        ascii_str = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        print(f"{i:5d}: {hexstr:<48} {ascii_str}")
