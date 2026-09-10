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
wsd = json_data["properties"]["worldSaveData"]["value"]

print("worldSaveData keys:", sorted(wsd.keys()))
bc = wsd.get("BaseCampSaveData", {}).get("value", [])
print(f"BaseCampSaveData count: {len(bc)}")
mo = wsd.get("MapObjectSaveData", {}).get("value", {}).get("values", [])
print(f"MapObjectSaveData count: {len(mo)}")
ccsd = wsd.get("CharacterContainerSaveData", {}).get("value", [])
print(f"CharacterContainerSaveData count: {len(ccsd)}")
icsd = wsd.get("ItemContainerSaveData", {}).get("value", [])
print(f"ItemContainerSaveData count: {len(icsd)}")
gsm = wsd.get("GroupSaveDataMap", {}).get("value", [])
print(f"GroupSaveDataMap count: {len(gsm)}")
