# -*- coding: utf-8 -*-
"""
Bake a single local JSON file mapping every known base-form codename to its
full real 13-category work_suitability profile + display name, so the
dashboard generator never needs live network calls to paldex/paldb.cc at
runtime -- it just loads this file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)

profiles = {}
for e in paldex:
    dn = e.get("pal_dev_name")
    if not dn or dn.startswith("BOSS_") or dn.startswith("Boss_"):
        continue
    profiles[dn] = {
        "display_name": (e.get("pal_name") or dn).strip(),
        "work_suitability": e.get("work_suitability", {}),
        "food_amount": e.get("stats", {}).get("food_amount"),
    }

DISPLAY_NAME_EXTRA = {
    "CloverFairy": "Clovee", "JellyfishFairy": "Jelliette", "JellyfishGhost": "Jellroy",
    "PurpleSpider": "Tarantriss", "ClioneTwins": "Amione", "ElecPomeranian": "Puffolt",
    "FluffyBird": "Muffly", "GhostBlackCat": "Wispaw", "GrassMinotaur": "Elgrove",
    "PandaGirl": "Leafan", "SamuraiDog": "Pupperai", "SmallYeti": "Snugloo",
    "StuffedShark": "Finsider", "SwordCutlassfish": "Skutlass", "KendoFrog": "Croajiro",
    "DarkAlien": "Xenovader", "MimicDog": "Mimog", "LeafMomonga": "Herbil",
}
extra_path = os.path.join(HERE, "paldb_extra_work_suitability.json")
with open(extra_path, "r", encoding="utf-8") as f:
    extra = json.load(f)
for cn, ws in extra.items():
    if cn not in profiles:
        # food_amount non disponible pour ces especes (paldb.cc scrape ne l'a pas capture) --
        # None plutot qu'une valeur inventee, gere explicitement comme "inconnu" au runtime.
        profiles[cn] = {"display_name": DISPLAY_NAME_EXTRA.get(cn, cn), "work_suitability": ws, "food_amount": None}

print(f"baked {len(profiles)} base-form species profiles")

out_path = os.path.join(HERE, "work_suitability_full.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=1)
print("Wrote", out_path)
