import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.rawdata.group import instance_id_reader, uuid_reader

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
raw_gvas, save_type = decompress_sav_to_gvas(data)
gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
json_data = gvas_file.dump()

group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]

# find raw undecoded groups
for gi, group in enumerate(group_map):
    group_type = group["value"]["GroupType"]["value"]["value"]
    raw = group["value"]["RawData"]["value"]
    if "values" not in raw:
        continue
    group_bytes = raw["values"]
    print(f"\n=== group[{gi}] type={group_type} len={len(group_bytes)} ===")

    # Need a reader; reuse the top-level gvas_file's internal reader isn't accessible here,
    # so build one fresh via FArchiveReader directly.
    from palworld_save_tools.archive import FArchiveReader
    reader = FArchiveReader(bytes(group_bytes), PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, debug=False)

    try:
        group_id = reader.guid()
        print(f"  group_id={group_id}  pos={reader.data.tell()}/{reader.size}")
        group_name = reader.fstring()
        print(f"  group_name={group_name!r}  pos={reader.data.tell()}/{reader.size}")
        handle_ids = reader.tarray(instance_id_reader)
        print(f"  individual_character_handle_ids count={len(handle_ids)}  pos={reader.data.tell()}/{reader.size}")

        if group_type in ["EPalGroupType::Guild", "EPalGroupType::IndependentGuild", "EPalGroupType::Organization"]:
            org_type = reader.byte()
            print(f"  org_type={org_type}  pos={reader.data.tell()}/{reader.size}")
            remaining_now = reader.size - reader.data.tell()
            peek = reader.data.read(min(remaining_now, 64))
            reader.data.seek(reader.data.tell() - len(peek))
            print(f"  [peek {len(peek)} bytes before base_ids]: {peek}")
            base_ids = reader.tarray(uuid_reader)
            print(f"  base_ids count={len(base_ids)}  pos={reader.data.tell()}/{reader.size}")

        if group_type in ["EPalGroupType::Guild", "EPalGroupType::IndependentGuild"]:
            base_camp_level = reader.i32()
            print(f"  base_camp_level={base_camp_level}  pos={reader.data.tell()}/{reader.size}")
            map_obj_ids = reader.tarray(uuid_reader)
            print(f"  map_object_instance_ids_base_camp_points count={len(map_obj_ids)}  pos={reader.data.tell()}/{reader.size}")
            guild_name = reader.fstring()
            print(f"  guild_name={guild_name!r}  pos={reader.data.tell()}/{reader.size}")

        if group_type == "EPalGroupType::Guild":
            admin_player_uid = reader.guid()
            print(f"  admin_player_uid={admin_player_uid}  pos={reader.data.tell()}/{reader.size}")
            player_count = reader.i32()
            print(f"  player_count={player_count}  pos={reader.data.tell()}/{reader.size}")
            for i in range(player_count):
                player_uid = reader.guid()
                last_online = reader.i64()
                player_name = reader.fstring()
                print(f"    player[{i}] uid={player_uid} last_online={last_online} name={player_name!r} pos={reader.data.tell()}/{reader.size}")

        print(f"  EOF reached: {reader.eof()}  final pos={reader.data.tell()}/{reader.size}")
        if not reader.eof():
            remaining = reader.read_to_end()
            print(f"  remaining bytes ({len(remaining)}): {remaining}")
    except Exception as e:
        print(f"  FAILED at pos={reader.data.tell()}/{reader.size}: {e}")
