import sys, json
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
    print(f"  key.PlayerUId={uid}: {n}")

# inspect the internal SaveParameter of a pal-like entry (one keyed to the host GUID)
shown = 0
for e in char_map:
    puid = e["key"]["PlayerUId"]["value"]
    if puid == "aa018782-0000-0000-0000-000000000000" and shown < 3:
        raw = e["value"]["RawData"]["value"]
        obj = raw.get("object", {})
        sp = obj.get("SaveParameter", {}).get("value", {})
        keys = list(sp.keys())
        is_player = sp.get("IsPlayer", {}).get("value", False)
        char_id = sp.get("CharacterID", {}).get("value", "?")
        owner = sp.get("OwnerPlayerUId", {}).get("value", "-")
        old_owners = sp.get("OldOwnerPlayerUIds", {}).get("value", "-")
        nick = sp.get("NickName", {}).get("value", "-")
        print(f"\nentry InstanceId={e['key']['InstanceId']['value']}")
        print(f"  IsPlayer={is_player}  CharacterID={char_id}  NickName={nick}")
        print(f"  OwnerPlayerUId={owner}")
        print(f"  OldOwnerPlayerUIds={json.dumps(old_owners, default=str)[:200]}")
        shown += 1
