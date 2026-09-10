import sys
from collections import Counter
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

ZERO = "00000000-0000-0000-0000-000000000000"
OLD = "00000000-0000-0000-0000-000000000001"

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
wsd = json_data["properties"]["worldSaveData"]["value"]
ccsd = wsd["CharacterContainerSaveData"]["value"]

dist = Counter()
fixed = 0
for c in ccsd:
    slots = c["value"].get("Slots", {}).get("value", {})
    for s in slots.get("values", []):
        rd = s.get("RawData", {}).get("value", {})
        if not isinstance(rd, dict) or "player_uid" not in rd:
            continue
        uid = str(rd["player_uid"])
        dist[uid] += 1
        if uid == OLD:
            rd["player_uid"] = ZERO
            fixed += 1

print("slot player_uid distribution BEFORE fix:")
for uid, n in dist.most_common():
    print(f"  {uid}: {n}")
print(f"slots fixed (old host -> zero): {fixed}")

gvas_file2 = GvasFile.load(json_data)
sav_file = compress_gvas_to_sav(gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
with open(path, "wb") as f:
    f.write(sav_file)
print("Done, Level.sav rewritten.")
