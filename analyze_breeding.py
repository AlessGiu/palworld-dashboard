# -*- coding: utf-8 -*-
"""
Calcule, pour toutes les paires d'especes possedees, l'oeuf resultant via la vraie formule
du jeu (Combi Rank) : child_rank = floor((rankA + rankB + 1) / 2), puis l'espece dont le
combi_rank est le plus proche de cette valeur devient le resultat. Filtre sur les especes
PAS ENCORE possedees (objectif : nouvelle espece).
Note : ~28 paires speciales dans le jeu outrepassent cette formule generale (resultats
uniques) -- non modelisees ici, donc a verifier en jeu avant de lancer un elevage long.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_palworld_dashboard as gpd

with open(os.path.join(HERE, "paldex_pals.json"), "r", encoding="utf-8") as f:
    paldex = json.load(f)

# Toutes les especes du jeu (non-boss) avec leur combi_rank reel, pour trouver l'espece
# la plus proche du rang calcule (recherche exhaustive, pas seulement les possedees).
all_species = []
for e in paldex:
    dn = e.get("pal_dev_name")
    if not dn or dn.startswith("BOSS_") or dn.startswith("Boss_"):
        continue
    rank = e.get("combi_rank")
    # rank<=0 ou nom "en_text" = donnee manquante/placeholder dans ce dataset (confirme via
    # plusieurs especes reellement possedees, ex. TentacleTurtle, qui ont pourtant rank=0 --
    # 0 n'est jamais un vrai combi_rank, c'est une valeur par defaut de champ non rempli)
    if rank is None or rank >= 9999 or rank <= 0 or e.get("pal_name") == "en_text":
        continue
    all_species.append({"codename": dn, "nom": e.get("pal_name", dn).strip(), "rank": rank})

print(f"especes avec combi_rank exploitable: {len(all_species)}")

# roster possede (via save)
wsd = gpd.load_world_save_data()
char_map = wsd["CharacterSaveParameterMap"]["value"]
owned_codenames = set()
for e in char_map:
    raw = e["value"]["RawData"]["value"]
    obj = raw.get("object", {}) if isinstance(raw, dict) else {}
    sp = obj.get("SaveParameter", {}).get("value", {}) if isinstance(obj, dict) else {}
    if sp.get("IsPlayer", {}).get("value", False):
        continue
    cid = gpd.unwrap(sp.get("CharacterID"), None)
    if cid:
        base_cn, _ = gpd.resolve_species_profile(cid)
        owned_codenames.add(base_cn)

owned_with_rank = [s for s in all_species if s["codename"] in owned_codenames]
print(f"especes possedees avec combi_rank connu: {len(owned_with_rank)}")

owned_set = set(s["codename"] for s in owned_with_rank)

def closest_species(target_rank):
    return min(all_species, key=lambda s: abs(s["rank"] - target_rank))

results = {}  # codename resultat -> (distance, parentA, parentB)
n = len(owned_with_rank)
for i in range(n):
    for j in range(i + 1, n):
        a, b = owned_with_rank[i], owned_with_rank[j]
        child_rank = (a["rank"] + b["rank"] + 1) // 2
        best = closest_species(child_rank)
        if best["codename"] in owned_set:
            continue  # deja possede, pas interessant pour l'objectif "nouvelle espece"
        dist = abs(best["rank"] - child_rank)
        cur = results.get(best["codename"])
        if cur is None or dist < cur[0]:
            results[best["codename"]] = (dist, a, b, best)

# trier par distance (confiance mecanique) puis par rang (rarete -- rank bas = rare/fort)
ranked = sorted(results.values(), key=lambda r: (r[0], r[3]["rank"]))
print(f"\nNouvelles especes potentiellement obtenables: {len(ranked)}")
print("\n=== TOP 20 (par confiance de la formule, puis rarete) ===")
for dist, a, b, res in ranked[:20]:
    print(f"  {res['nom']:20s} (rank {res['rank']:4d}, ecart {dist:2d}) <- {a['nom']} (rank {a['rank']}) + {b['nom']} (rank {b['rank']})")
