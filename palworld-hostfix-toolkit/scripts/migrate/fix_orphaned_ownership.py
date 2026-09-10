import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import UUID


def format_guid(g):
    g = g.replace("-", "").lower()
    return "{}-{}-{}-{}-{}".format(g[:8], g[8:12], g[12:16], g[16:20], g[20:])


def main():
    save_path = sys.argv[1]
    old_guid = sys.argv[2]
    new_guid = sys.argv[3]

    old_fmt = format_guid(old_guid)
    new_fmt = format_guid(new_guid)
    # Raw on-disk GUID bytes use a reordered (Microsoft-style mixed-endian) layout,
    # not a plain sequential hex-to-bytes mapping. Use the library's own UUID class
    # to get the correct raw byte pattern for binary search/replace.
    old_bytes = UUID.from_str(old_fmt).raw_bytes
    new_bytes = UUID.from_str(new_fmt).raw_bytes
    print(f"Replacing {old_fmt} -> {new_fmt}")
    print(f"  old raw bytes: {old_bytes.hex()}")
    print(f"  new raw bytes: {new_bytes.hex()}")

    level_sav_path = save_path + "/Level.sav"
    with open(level_sav_path, "rb") as f:
        data = f.read()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
    json_data = gvas_file.dump()

    # 1. CharacterSaveParameterMap: fix any entries (player + owned pals) still on old GUID.
    char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
    char_changed = 0
    for entry in char_map:
        if entry["key"]["PlayerUId"]["value"] == old_fmt:
            entry["key"]["PlayerUId"]["value"] = new_fmt
            char_changed += 1
    print(f"CharacterSaveParameterMap: updated {char_changed} entries")

    # 2. GroupSaveDataMap: fix decoded groups via JSON fields, and raw (undecoded)
    #    groups via direct binary substitution (GUID bytes are stored sequentially,
    #    no reordering, so a straight byte-pattern replace is safe and length-preserving).
    group_map = json_data["properties"]["worldSaveData"]["value"]["GroupSaveDataMap"]["value"]
    decoded_changes = 0
    raw_changes = 0
    for group in group_map:
        group_type = group["value"]["GroupType"]["value"]["value"]
        raw = group["value"]["RawData"]["value"]
        if "values" in raw:
            # Undecoded - patch raw bytes directly.
            b = bytes(raw["values"])
            count = b.count(old_bytes)
            if count:
                b2 = b.replace(old_bytes, new_bytes)
                raw["values"] = list(b2)
                raw_changes += count
            continue
        if group_type != "EPalGroupType::Guild":
            continue
        if raw.get("admin_player_uid") == old_fmt:
            raw["admin_player_uid"] = new_fmt
            decoded_changes += 1
        for p in raw.get("players", []):
            if p["player_uid"] == old_fmt:
                p["player_uid"] = new_fmt
                decoded_changes += 1
        for h in raw.get("individual_character_handle_ids", []):
            if h.get("guid") == old_fmt:
                h["guid"] = new_fmt
                decoded_changes += 1
    print(f"GroupSaveDataMap: {decoded_changes} decoded-field updates, {raw_changes} raw-byte-pattern replacements")

    gvas_file2 = GvasFile.load(json_data)
    sav_file = compress_gvas_to_sav(gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
    with open(level_sav_path, "wb") as f:
        f.write(sav_file)
    print("Done, Level.sav rewritten.")


if __name__ == "__main__":
    main()
