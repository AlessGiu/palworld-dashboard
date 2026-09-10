import os
import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

ANCHOR_PLAYER_NAME = os.environ.get("ANCHOR_PLAYER_NAME", "PLAYER_NAME")

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

for gi, group in enumerate(group_map):
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw or group_type != "EPalGroupType::Guild":
        continue
    b = bytes(raw["values"])
    print(f"\n=== group[{gi}] len={len(b)} ===")

    admin_guid_pattern = b"\x00" * 15 + b"\x01"
    idx = b.find(admin_guid_pattern)
    print(f"  admin-guid-like pattern (15x00+01) found at offsets: {[i for i in range(len(b)) if b[i:i+16] == admin_guid_pattern]}")

    for name in [ANCHOR_PLAYER_NAME.encode(), b"Unnamed Guild", b"AA018782000000000000000000000000".lower(), b"00000000000000000000000000000001"]:
        idx = b.find(name)
        print(f"  {name!r} found at offset: {idx}")

    # dump hex around each admin-guid-like match for manual cross-check
    for i in range(len(b) - 15):
        if b[i:i+16] == admin_guid_pattern:
            lo = max(0, i - 8)
            hi = min(len(b), i + 60)
            print(f"    context around offset {i}: {b[lo:hi]}")
