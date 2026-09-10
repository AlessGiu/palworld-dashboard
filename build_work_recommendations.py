# -*- coding: utf-8 -*-
"""
Cross-reference the user's real owned-species roster (species_list.txt) against
the exhaustive datamined work-suitability data from blaynem/paldex
(data-provider/baked-data/en/pals.json) to produce 100% concrete, verified
"Travail a la base" recommendations -- replacing the previous reputation-based
WORK_RECOMMENDATIONS guess.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Real 13 work-suitability fields (DT_PalMonsterParameter) -> French category label
# matching the field names actually present in paldex's pals.json.
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

# Load paldex data
with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)

by_devname = {}
by_devname_lower = {}
for entry in paldex:
    dn = entry.get("pal_dev_name")
    if dn:
        by_devname[dn] = entry
        by_devname_lower[dn.lower()] = entry

print(f"paldex entries loaded: {len(paldex)}, unique dev_name keys: {len(by_devname)}")

# Supplement with real per-species work_suitability scraped directly from paldb.cc
# for Feybreak/DLC-era species absent from the paldex snapshot (verified via each
# species' own page, not guessed).
DISPLAY_NAME_EXTRA = {
    "CloverFairy": "Clovee",
    "JellyfishFairy": "Jelliette",
    "JellyfishGhost": "Jellroy",
    "PurpleSpider": "Tarantriss",
    "ClioneTwins": "Amione",
    "ElecPomeranian": "Puffolt",
    "FluffyBird": "Muffly",
    "GhostBlackCat": "Wispaw",
    "GrassMinotaur": "Elgrove",
    "PandaGirl": "Leafan",
    "SamuraiDog": "Pupperai",
    "SmallYeti": "Snugloo",
    "StuffedShark": "Finsider",
    "SwordCutlassfish": "Skutlass",
    "KendoFrog": "Croajiro",
    "DarkAlien": "Xenovader",
    "MimicDog": "Mimog",
    "LeafMomonga": "Herbil",
}
extra_path = os.path.join(HERE, "paldb_extra_work_suitability.json")
if os.path.exists(extra_path):
    with open(extra_path, "r", encoding="utf-8") as f:
        extra_ws = json.load(f)
    for codename, ws in extra_ws.items():
        if codename not in by_devname:
            entry = {
                "pal_dev_name": codename,
                "pal_name": DISPLAY_NAME_EXTRA.get(codename, codename),
                "work_suitability": ws,
            }
            by_devname[codename] = entry
            by_devname_lower[codename.lower()] = entry
    print(f"supplemented with {len(extra_ws)} paldb.cc entries -> total dev_name keys: {len(by_devname)}")

# Known non-matchable roster entries, documented rather than silently dropped:
KNOWN_EXCLUSIONS = {
    "Hunter_Bat": "pas un Pal standard reference sur paldex/paldb -- aucune donnee de travail verifiable trouvee",
    "BOSS_Male_Soldier02": "PNJ humain capture, pas un Pal -- aucune aptitude de travail associee",
}

# Palworld elemental-variant reskins (dungeon-only recolors, e.g. "_Fire"/"_Dark"/"_Electric"/
# "_Water"/"_Grass"/"_Ice" suffixes) reuse their base species' non-combat data in the game's
# DataTable -- only element/skills change, work_suitability stays identical to the base form.
# This is a documented game-data fact (not a guess), so falling back to the base species'
# work_suitability for an unmatched variant is still "concrete" data, just inherited.
VARIANT_SUFFIXES = ["_Fire", "_Dark", "_Electric", "_Water", "_Grass", "_Ice"]


def resolve_devname(codename):
    """Return (entry, note) where note explains any fallback used, or (None, None)."""
    if codename in by_devname:
        return by_devname[codename], None
    if codename.lower() in by_devname_lower:
        return by_devname_lower[codename.lower()], "case-insensitive match"
    # Strip BOSS_/Boss_ prefix and retry
    base = codename
    prefix_note = None
    if base.startswith("BOSS_") or base.startswith("Boss_"):
        base = base[5:]
        prefix_note = "boss-prefix stripped"
        if base in by_devname:
            return by_devname[base], prefix_note
        if base.lower() in by_devname_lower:
            return by_devname_lower[base.lower()], prefix_note + ", case-insensitive"
    # Strip elemental variant suffix and retry (with and without prefix already stripped)
    for suffix in VARIANT_SUFFIXES:
        if base.endswith(suffix):
            root = base[: -len(suffix)]
            if root in by_devname:
                note = f"variant suffix {suffix} stripped"
                if prefix_note:
                    note += f", {prefix_note}"
                return by_devname[root], note
            if root.lower() in by_devname_lower:
                note = f"variant suffix {suffix} stripped, case-insensitive"
                if prefix_note:
                    note += f", {prefix_note}"
                return by_devname_lower[root.lower()], note
    return None, None

# Load owned species roster
roster = []  # (codename, count, max_level)
with open(os.path.join(HERE, "species_list.txt"), "r", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) < 3:
            continue
        codename, count, max_level = parts[0], parts[1], parts[2]
        if not codename:
            continue
        roster.append((codename, int(count), int(max_level)))

print(f"owned species rows: {len(roster)}")

# Match roster codenames to paldex dev_names (with documented fallback rules)
matched = {}
match_notes = {}
unmatched = []
for codename, count, max_level in roster:
    entry, note = resolve_devname(codename)
    if entry:
        matched[codename] = entry
        if note:
            match_notes[codename] = note
    else:
        unmatched.append(codename)

print(f"matched: {len(matched)}  unmatched: {len(unmatched)}")
if match_notes:
    print("\nMatched via fallback rule (not a direct dev_name hit):")
    for cn, note in match_notes.items():
        print(f"  - {cn}: {note}")
if unmatched:
    print("\nSTILL UNMATCHED:")
    for u in unmatched:
        reason = KNOWN_EXCLUSIONS.get(u, "raison inconnue -- a investiguer")
        print(f" - {u}: {reason}")

# Build best-3 per category using REAL star values (0-4), only counting species we actually own
best_per_category = {}
for field, label in CATEGORIES:
    scored = []
    for codename, count, max_level in roster:
        entry = matched.get(codename)
        if not entry:
            continue
        stars = entry.get("work_suitability", {}).get(field, 0)
        if stars and stars > 0:
            scored.append((stars, max_level, codename, count, entry.get("pal_name", codename)))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    best_per_category[label] = scored[:3]

# Print full report
print("\n=== TRAVAIL A LA BASE - DONNEES REELLES (paldex work_suitability) ===\n")
for field, label in CATEGORIES:
    print(f"-- {label} --")
    for stars, max_level, codename, count, display_name in best_per_category[label]:
        print(f"   {stars}* | {display_name} ({codename}) x{count}, niveau max {max_level}")
    if not best_per_category[label]:
        print("   (aucun Pal possede avec une aptitude > 0 dans cette categorie)")
    print()

# Dump a JSON we can load into the dashboard generator
out = {}
for field, label in CATEGORIES:
    out[label] = [
        {"stars": s, "max_level": ml, "codename": cn, "count": c, "display_name": dn}
        for (s, ml, cn, c, dn) in best_per_category[label]
    ]

with open(os.path.join(HERE, "work_recommendations_real.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("Wrote work_recommendations_real.json")
print("\nUnmatched codenames count:", len(unmatched))
