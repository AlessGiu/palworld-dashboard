# -*- coding: utf-8 -*-
"""
Analyse le roster reel pour recommander une equipe de terrain (party de combat/exploration),
distincte des recommandations "travail a la base" -- basee sur les vraies stats de combat
(attaque, defense, vitesse) et elements du DataTable paldex, croisees avec le roster possede.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_palworld_dashboard as gpd

with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)
by_dn = {e["pal_dev_name"]: e for e in paldex if e.get("pal_dev_name")}

extra = json.load(open(os.path.join(HERE, "paldb_extra_work_suitability.json"), encoding="utf-8"))

wsd = gpd.load_world_save_data()
char_map = wsd["CharacterSaveParameterMap"]["value"]

species_best = {}  # codename -> best instance info (level, iv sum, passifs)
for e in char_map:
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {}) if isinstance(obj, dict) else {}
    if sp.get("IsPlayer", {}).get("value", False):
        continue
    codename = gpd.unwrap(sp.get("CharacterID"), None)
    if not codename:
        continue
    level = gpd.unwrap(sp.get("Level"), 1)
    iv = (
        gpd.safe_float(gpd.unwrap(sp.get("Talent_HP"), 0))
        + gpd.safe_float(gpd.unwrap(sp.get("Talent_Shot"), 0))
        + gpd.safe_float(gpd.unwrap(sp.get("Talent_Defense"), 0))
    )
    cur = species_best.get(codename)
    score = level * 10 + iv  # privilegie le niveau, IV en departage
    if cur is None or score > cur["score"]:
        species_best[codename] = {"level": level, "iv": iv, "score": score}

print(f"especes possedees (avec au moins 1 exemplaire): {len(species_best)}")

def get_combat_profile(codename):
    base_cn, _ = gpd.resolve_species_profile(codename)
    e = by_dn.get(base_cn) or by_dn.get(codename)
    if not e:
        return None
    stats = e.get("stats", {})
    return {
        "display_name": e.get("pal_name", codename).strip(),
        "elements": e.get("elements", []),
        "melee": stats.get("melee_attack", 0),
        "shot": stats.get("shot_attack", 0),
        "hp": stats.get("hp", 0),
        "defense": stats.get("defense", 0),
        "ride_sprint_speed": stats.get("ride_sprint_speed", -1),
        "run_speed": stats.get("run_speed", -1),
        "partner_skill": e.get("partner_skill_description", ""),
        "is_boss": e.get("is_boss", False),
    }

combat_candidates = []
for codename, inst in species_best.items():
    profile = get_combat_profile(codename)
    if not profile:
        continue
    combat_power = profile["melee"] + profile["shot"]
    combat_candidates.append({
        "codename": codename,
        "nom": profile["display_name"],
        "elements": profile["elements"],
        "power": combat_power,
        "hp": profile["hp"],
        "defense": profile["defense"],
        "level": inst["level"],
        "iv": inst["iv"],
        "ride_sprint_speed": profile["ride_sprint_speed"],
        "partner_skill": profile["partner_skill"],
    })

combat_candidates.sort(key=lambda c: -c["power"])
print("\n=== TOP 15 COMBAT (attaque melee+distance, especes possedees) ===")
for c in combat_candidates[:15]:
    print(f"  {c['power']:4d} pwr | {c['nom']:20s} ({c['codename']:20s}) elements={c['elements']} lvl={c['level']} iv={c['iv']:.0f}% hp={c['hp']} def={c['defense']}")

mounts = [c for c in combat_candidates if c["ride_sprint_speed"] and c["ride_sprint_speed"] > 0]
mounts.sort(key=lambda c: -c["ride_sprint_speed"])
print("\n=== TOP 10 MONTURES (ride_sprint_speed, especes possedees) ===")
for c in mounts[:10]:
    print(f"  speed={c['ride_sprint_speed']:5.0f} | {c['nom']:20s} ({c['codename']}) -- {c['partner_skill'][:80]}")

print("\n=== COUVERTURE ELEMENTAIRE (meilleur combattant possede par element) ===")
by_element = {}
for c in combat_candidates:
    for el in c["elements"]:
        if el not in by_element or c["power"] > by_element[el]["power"]:
            by_element[el] = c
for el, c in sorted(by_element.items()):
    print(f"  {el:10s} -> {c['nom']} (pwr {c['power']}, lvl {c['level']})")

ALL_ELEMENTS = ["Neutral", "Fire", "Water", "Grass", "Electric", "Ice", "Dark", "Dragon", "Ground"]
missing = [el for el in ALL_ELEMENTS if el not in by_element]
print("\nElements NON couverts par le roster possede:", missing if missing else "aucun -- tout est couvert")
