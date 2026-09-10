# -*- coding: utf-8 -*-
"""Bake per-species Combi Rank (breeding formula input) from paldex, filtering out
placeholder/unfilled entries (rank<=0 or pal_name=='en_text', confirmed unreliable --
e.g. TentacleTurtle, a real owned species, shows rank=0 which cannot be a genuine value)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)

profiles = {}
skipped = 0
for e in paldex:
    dn = e.get("pal_dev_name")
    if not dn or dn.startswith("BOSS_") or dn.startswith("Boss_"):
        continue
    rank = e.get("combi_rank")
    if rank is None or rank >= 9999 or rank <= 0 or e.get("pal_name") == "en_text":
        skipped += 1
        continue
    profiles[dn] = {"display_name": (e.get("pal_name") or dn).strip(), "rank": rank}

print(f"baked {len(profiles)} combi ranks, skipped {skipped} placeholder/unfilled entries")
out_path = os.path.join(HERE, "combi_ranks_full.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(profiles, f, ensure_ascii=False, indent=1)
print("Wrote", out_path)
