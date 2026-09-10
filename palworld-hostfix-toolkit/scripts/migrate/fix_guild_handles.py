import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import UUID

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
wsd = json_data["properties"]["worldSaveData"]["value"]
char_map = wsd["CharacterSaveParameterMap"]["value"]

# collect pal instance ids (IsPlayer=False)
pal_instances = []
for e in char_map:
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {})
    if not sp.get("IsPlayer", {}).get("value", False):
        pal_instances.append(str(e["key"]["InstanceId"]["value"]))
print(f"pal instances: {len(pal_instances)}")

ZERO16 = b"\x00" * 16
group_map = wsd["GroupSaveDataMap"]["value"]
total_fixed = 0
for gi, group in enumerate(group_map):
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw or group_type != "EPalGroupType::Guild":
        continue
    b = bytearray(bytes(raw["values"]))
    fixed = 0
    for inst in pal_instances:
        inst_bytes = UUID.from_str(inst).raw_bytes
        idx = bytes(b).find(inst_bytes)
        if idx >= 16:
            if bytes(b[idx-16:idx]) != ZERO16:
                b[idx-16:idx] = ZERO16
                fixed += 1
    if fixed:
        raw["values"] = list(bytes(b))
        total_fixed += fixed
    print(f"group[{gi}] Guild: {fixed} pal handles zeroed")

print(f"total handles fixed: {total_fixed}")

gvas_file2 = GvasFile.load(json_data)
sav_file = compress_gvas_to_sav(gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
with open(path, "wb") as f:
    f.write(sav_file)
print("Done, Level.sav rewritten.")
