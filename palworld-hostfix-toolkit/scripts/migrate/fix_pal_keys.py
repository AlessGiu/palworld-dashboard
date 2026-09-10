import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

ZERO = "00000000-0000-0000-0000-000000000000"


def main():
    level_sav_path = sys.argv[1]
    host_guid = sys.argv[2]        # e.g. aa018782-0000-0000-0000-000000000000
    old_host_guid = sys.argv[3]    # e.g. 00000000-0000-0000-0000-000000000001

    with open(level_sav_path, "rb") as f:
        data = f.read()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
    json_data = gvas_file.dump()
    char_map = json_data["properties"]["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]

    rekeyed = 0
    owner_fixed = 0
    old_owner_fixed = 0
    players_kept = 0

    for e in char_map:
        raw = e["value"]["RawData"]["value"]
        obj = raw.get("object", {}) if isinstance(raw, dict) else {}
        sp = obj.get("SaveParameter", {}).get("value", {})
        is_player = sp.get("IsPlayer", {}).get("value", False)

        if is_player:
            players_kept += 1
            continue

        # Pal entry: key must be the zero GUID or the dedicated server purges it.
        if e["key"]["PlayerUId"]["value"] != ZERO:
            e["key"]["PlayerUId"]["value"] = ZERO
            rekeyed += 1

        # Internal ownership: retarget the old host GUID to the real one.
        owner = sp.get("OwnerPlayerUId", {})
        if owner.get("value") == old_host_guid:
            owner["value"] = host_guid
            owner_fixed += 1
        old_owners = sp.get("OldOwnerPlayerUIds", {}).get("value", {})
        vals = old_owners.get("values") if isinstance(old_owners, dict) else None
        if isinstance(vals, list):
            for i, v in enumerate(vals):
                if str(v) == old_host_guid:
                    vals[i] = host_guid
                    old_owner_fixed += 1

    print(f"players kept keyed as-is: {players_kept}")
    print(f"pals re-keyed to zero GUID: {rekeyed}")
    print(f"OwnerPlayerUId retargeted: {owner_fixed}")
    print(f"OldOwnerPlayerUIds entries retargeted: {old_owner_fixed}")

    gvas_file2 = GvasFile.load(json_data)
    sav_file = compress_gvas_to_sav(gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
    with open(level_sav_path, "wb") as f:
        f.write(sav_file)
    print("Done, Level.sav rewritten.")


if __name__ == "__main__":
    main()
