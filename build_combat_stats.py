# -*- coding: utf-8 -*-
"""Bake per-species combat stats (attack/hp/defense/elements/mount speed) from paldex,
analogous to work_suitability_full.json, so the dashboard never needs network calls."""
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
    stats = e.get("stats", {})
    profiles[dn] = {
        "display_name": (e.get("pal_name") or dn).strip(),
        "elements": e.get("elements", []),
        "melee_attack": stats.get("melee_attack", 0),
        "shot_attack": stats.get("shot_attack", 0),
        "hp": stats.get("hp", 0),
        "defense": stats.get("defense", 0),
        "ride_sprint_speed": stats.get("ride_sprint_speed", -1),
        "partner_skill_description": e.get("partner_skill_description", ""),
    }

print(f"baked {len(profiles)} combat profiles")
out_path = os.path.join(HERE, "combat_stats_full.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=1)
print("Wrote", out_path)
