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

group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]
print(f"Total groups: {len(group_map)}")
for group in group_map:
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    decoded = "values" not in raw
    print(f"  type={group_type}  decoded_ok={decoded}", end="")
    if decoded and group_type == "EPalGroupType::Guild":
        print(f"  admin={raw.get('admin_player_uid')}  guild_name={raw.get('guild_name')}  num_players={len(raw.get('players', []))}", end="")
        for p in raw.get("players", []):
            print(f"\n    player_uid={p['player_uid']}  name={p.get('player_info',{}).get('player_name')}", end="")
    print()

char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
print(f"\nTotal CharacterSaveParameterMap entries: {len(char_map)}")
from collections import Counter
uids = Counter(e["key"]["PlayerUId"]["value"] for e in char_map)
for uid, count in uids.most_common(20):
    print(f"  PlayerUId={uid}  count={count}")
