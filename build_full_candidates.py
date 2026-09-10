# -*- coding: utf-8 -*-
"""
Generate the WORK_RECOMMENDATIONS candidate list (codename, display_name) per
category, ranked by REAL work_suitability stars across the full known species
set (paldex + paldb.cc supplement), not just the currently-owned roster.
This keeps the dashboard self-updating: collect_data() already cross-references
this list against the LIVE species_count each run, so if the user later catches
a stronger candidate it will surface automatically without touching this file again.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = [
    ("emit_flame", "Allumage"),
    ("watering", "Arrosage"),
    ("seeding", "Plantation"),
    ("generate_electricity", "Electricite"),
    ("handcraft", "Manutention"),
    ("collection", "Cueillette"),
    ("deforest", "Bucheronnage"),
    ("mining", "Minage"),
    ("oil_extraction", "Extraction de petrole"),
    ("product_medicine", "Medecine"),
    ("cool", "Refroidissement"),
    ("transport", "Transport"),
    ("monster_farm", "Elevage/Ferme"),
]

with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)

all_entries = {}
for e in paldex:
    dn = e.get("pal_dev_name")
    if dn:
        all_entries[dn] = e

extra_path = os.path.join(HERE, "paldb_extra_work_suitability.json")
DISPLAY_NAME_EXTRA = {
    "CloverFairy": "Clovee", "JellyfishFairy": "Jelliette", "JellyfishGhost": "Jellroy",
    "PurpleSpider": "Tarantriss", "ClioneTwins": "Amione", "ElecPomeranian": "Puffolt",
    "FluffyBird": "Muffly", "GhostBlackCat": "Wispaw", "GrassMinotaur": "Elgrove",
    "PandaGirl": "Leafan", "SamuraiDog": "Pupperai", "SmallYeti": "Snugloo",
    "StuffedShark": "Finsider", "SwordCutlassfish": "Skutlass", "KendoFrog": "Croajiro",
    "DarkAlien": "Xenovader", "MimicDog": "Mimog", "LeafMomonga": "Herbil",
}
if os.path.exists(extra_path):
    with open(extra_path, "r", encoding="utf-8") as f:
        extra = json.load(f)
    for codename, ws in extra.items():
        all_entries[codename] = {
            "pal_dev_name": codename,
            "pal_name": DISPLAY_NAME_EXTRA.get(codename, codename),
            "work_suitability": ws,
        }

print(f"total known species (paldex + paldb supplement): {len(all_entries)}")

# Only keep non-boss entries as the "canonical" species per work category (boss/alpha
# forms share identical work_suitability with their base form, confirmed earlier) --
# using base codenames keeps the candidate list matching species_list.txt's normal-form keys,
# while resolve-at-runtime in the dashboard already strips BOSS_ prefix if ever needed.
def is_boss(codename):
    return codename.startswith("BOSS_") or codename.startswith("Boss_")

candidates_out = {}
for field, label in CATEGORIES:
    scored = []
    for codename, e in all_entries.items():
        if is_boss(codename):
            continue
        stars = e.get("work_suitability", {}).get(field, 0)
        if stars and stars > 0:
            scored.append((stars, codename, e.get("pal_name", codename).strip()))
    scored.sort(key=lambda x: (-x[0], x[1]))
    candidates_out[label] = scored[:10]  # keep extras as redundancy for ownership filtering

print("\n=== WORK_RECOMMENDATIONS candidates (top 6 by real stars, all known species) ===\n")
for field, label in CATEGORIES:
    print(f"-- {label} --")
    for stars, codename, name in candidates_out[label]:
        print(f"   {stars}* {name} ({codename})")
    print()

# Emit as Python source ready to paste
lines = ["WORK_RECOMMENDATIONS = {"]
for field, label in CATEGORIES:
    pairs = ", ".join(f'("{cn}", "{nm}")' for _, cn, nm in candidates_out[label])
    lines.append(f'    "{label}": [{pairs}],')
lines.append("}")
py_src = "\n".join(lines)

out_path = os.path.join(HERE, "work_recommendations_dict.py")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(py_src)
print("Wrote", out_path)
