import os
import sys
import itertools
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.rawdata.group import instance_id_reader, uuid_reader
from palworld_save_tools.archive import FArchiveReader

ANCHOR_PLAYER_NAME = os.environ.get("ANCHOR_PLAYER_NAME", "PLAYER_NAME")

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()
group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

raw_groups = []
for group in group_map:
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" in raw and group_type in ("EPalGroupType::Guild", "EPalGroupType::IndependentGuild"):
        raw_groups.append((group_type, bytes(raw["values"])))

print(f"Testing against {len(raw_groups)} raw guild groups")


def try_parse(group_type, group_bytes, skip_after_org, skip_after_baseids, skip_after_bclevel, skip_after_mapobj):
    reader = FArchiveReader(group_bytes, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, debug=False)
    reader.guid()
    reader.fstring()
    reader.tarray(instance_id_reader)
    reader.byte()  # org_type
    reader.read(skip_after_org)
    base_ids = reader.tarray(uuid_reader)
    if len(base_ids) > 100:
        raise Exception("base_ids too large, bad alignment")
    reader.read(skip_after_baseids)
    base_camp_level = reader.i32()
    if not (0 <= base_camp_level <= 200):
        raise Exception(f"base_camp_level implausible: {base_camp_level}")
    reader.read(skip_after_bclevel)
    map_obj_ids = reader.tarray(uuid_reader)
    if len(map_obj_ids) > 100:
        raise Exception("map_obj_ids too large, bad alignment")
    reader.read(skip_after_mapobj)
    guild_name = reader.fstring()
    if not guild_name.isprintable() or len(guild_name) > 200:
        raise Exception(f"guild_name not printable/sane: {guild_name!r}")

    result = {"base_camp_level": base_camp_level, "guild_name": guild_name, "base_ids_count": len(base_ids), "map_obj_count": len(map_obj_ids)}

    if group_type == "EPalGroupType::Guild":
        admin_player_uid = reader.guid()
        player_count = reader.i32()
        if not (0 <= player_count <= 50):
            raise Exception(f"player_count implausible: {player_count}")
        players = []
        for _ in range(player_count):
            player_uid = reader.guid()
            last_online = reader.i64()
            player_name = reader.fstring()
            if not player_name.isprintable() or len(player_name) > 100:
                raise Exception(f"player_name not sane: {player_name!r}")
            players.append((player_uid, player_name))
        result["admin_player_uid"] = admin_player_uid
        result["players"] = players

    if not reader.eof():
        raise Exception(f"not EOF, {reader.size - reader.data.tell()} bytes remain")
    return result


candidates = list(range(0, 65, 4))
for idx, (group_type, group_bytes) in enumerate(raw_groups):
    print(f"\n=== group[{idx}] type={group_type} len={len(group_bytes)} — searching per-group ===")
    matches = []
    for s1, s2, s3, s4 in itertools.product(candidates, repeat=4):
        try:
            r = try_parse(group_type, group_bytes, s1, s2, s3, s4)
            # Strong ground-truth filter for the small known guild (len=246):
            # admin must be the real player GUID and the sole player must match ANCHOR_PLAYER_NAME.
            if len(group_bytes) == 246:
                if str(r.get("admin_player_uid")) != "00000000-0000-0000-0000-000000000001":
                    continue
                if len(r.get("players", [])) != 1 or r["players"][0][1] != ANCHOR_PLAYER_NAME:
                    continue
            matches.append(((s1, s2, s3, s4), r))
        except Exception:
            continue
    print(f"  {len(matches)} matching combos found")
    for combo, r in matches[:10]:
        print(f"  skips={combo}  {r}")
