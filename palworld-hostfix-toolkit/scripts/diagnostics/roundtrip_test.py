import sys
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS


def test_file(path):
    print(f"=== Testing {path} ===")
    with open(path, "rb") as f:
        data = f.read()

    raw_gvas, save_type = decompress_sav_to_gvas(data)
    print(f"  decompressed: {len(raw_gvas)} bytes, save_type={hex(save_type)}")

    gvas_file = GvasFile.read(
        raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True
    )
    print(f"  parsed GVAS OK, save_game_class_name={gvas_file.header.save_game_class_name}")

    json_data = gvas_file.dump()
    print(f"  dumped to JSON OK, {len(json_data['properties'])} top-level properties")

    gvas_file2 = GvasFile.load(json_data)
    rewritten_gvas = gvas_file2.write(PALWORLD_CUSTOM_PROPERTIES)
    print(f"  rewritten GVAS: {len(rewritten_gvas)} bytes (original was {len(raw_gvas)})")

    match = rewritten_gvas == raw_gvas
    print(f"  byte-for-byte match with original decompressed GVAS: {match}")

    new_sav = compress_gvas_to_sav(rewritten_gvas, save_type)
    print(f"  recompressed to .sav: {len(new_sav)} bytes, magic={new_sav[8:11]!r}")

    reread_gvas, reread_save_type = decompress_sav_to_gvas(new_sav)
    reread_match = reread_gvas == rewritten_gvas
    print(f"  round-trip decompress matches: {reread_match}")

    if match and reread_match:
        print("  RESULT: SUCCESS - full round trip verified")
    else:
        print("  RESULT: MISMATCH - inspect further before trusting this on real data")
    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            test_file(p)
        except Exception as e:
            print(f"  FAILED: {e}")
            print()
