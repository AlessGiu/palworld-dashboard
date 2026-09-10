# -*- coding: utf-8 -*-
"""
Determine which Pals are CURRENTLY deployed at the base (working) vs sitting
unused in a Palbox/party, then compare against the real work-suitability
recommendations (WORK_RECOMMENDATIONS in generate_palworld_dashboard.py) to
produce concrete "swap this for that" advice.
"""
import sys
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_palworld_dashboard as gpd


def uid_str(u):
    return str(u)


def main():
    gpd.download_level_sav()
    wsd = gpd.load_world_save_data()

    # --- locate the base's worker container id ---
    bc = wsd["BaseCampSaveData"]["value"]
    print(f"num bases: {len(bc)}")
    base_container_ids = []
    for b in bc:
        wd = b["value"]["WorkerDirector"]["value"]["RawData"]["value"]
        cid = wd["container_id"]
        base_container_ids.append(uid_str(cid))
    print("base worker container id(s):", base_container_ids)

    # --- index all CharacterContainerSaveData containers by id ---
    ccsd = wsd["CharacterContainerSaveData"]["value"]
    containers_by_id = {}
    for c in ccsd:
        cid = uid_str(c["key"]["ID"]["value"])
        containers_by_id[cid] = c["value"]

    # --- index all pals/players by instance_id (from CharacterSaveParameterMap) ---
    char_map = wsd["CharacterSaveParameterMap"]["value"]
    by_instance = {}
    for e in char_map:
        instance_id = uid_str(e["key"]["InstanceId"]["value"])
        raw = e["value"]["RawData"]["value"]
        obj = raw.get("object", {}) if isinstance(raw, dict) else {}
        sp = obj.get("SaveParameter", {}).get("value", {}) if isinstance(obj, dict) else {}
        by_instance[instance_id] = sp

    print(f"total characters indexed by instance_id: {len(by_instance)}")

    # --- extract pals sitting in the base worker container ---
    deployed = []
    for cid in base_container_ids:
        cont = containers_by_id.get(cid)
        if not cont:
            print(f"  ! container {cid} not found in CharacterContainerSaveData")
            continue
        slots = cont["Slots"]["value"]["values"]
        for slot in slots:
            raw = slot["RawData"]["value"]
            instance_id = uid_str(raw["instance_id"])
            if instance_id == "00000000-0000-0000-0000-000000000000":
                continue  # empty slot
            sp = by_instance.get(instance_id)
            if not sp:
                print(f"  ! instance {instance_id} in base container but not found in CharacterSaveParameterMap")
                continue
            cid_species = gpd.unwrap(sp.get("CharacterID"), "?")
            level = gpd.unwrap(sp.get("Level"), 1)
            is_player = sp.get("IsPlayer", {}).get("value", False)
            deployed.append({"codename": cid_species, "level": level, "is_player": is_player})

    print(f"\nPals actuellement deployes/assignes a la base : {len(deployed)}")
    for d in deployed:
        print(f"  - {d['codename']} (lvl {d['level']}){' [JOUEUR?]' if d['is_player'] else ''}")

    deployed_codenames = set(d["codename"] for d in deployed if not d["is_player"])

    with open(os.path.join(HERE, "base_deployed_pals.json"), "w", encoding="utf-8") as f:
        json.dump(deployed, f, ensure_ascii=False, indent=2)
    print("\nWrote base_deployed_pals.json")

    # --- compare vs WORK_RECOMMENDATIONS + live roster (species_list.txt-equivalent) ---
    species_count = {}
    species_best_level = {}
    for sp in by_instance.values():
        if sp.get("IsPlayer", {}).get("value", False):
            continue
        cid_species = gpd.unwrap(sp.get("CharacterID"), None)
        if not cid_species:
            continue
        species_count[cid_species] = species_count.get(cid_species, 0) + 1
        lvl = gpd.unwrap(sp.get("Level"), 1)
        if cid_species not in species_best_level or lvl > species_best_level[cid_species]:
            species_best_level[cid_species] = lvl

    print("\n=== ECARTS PAR CATEGORIE (meilleur possede vs actuellement deploye) ===\n")
    gaps = []
    for categorie, candidats in gpd.WORK_RECOMMENDATIONS.items():
        best_owned = None
        for codename, nom_affiche in candidats:
            variants = [codename, "BOSS_" + codename]
            nombre = sum(species_count.get(v, 0) for v in variants)
            if nombre:
                best_owned = (codename, nom_affiche, nombre)
                break  # candidats deja tries par etoiles desc
        if not best_owned:
            continue
        codename, nom_affiche, nombre = best_owned
        deployed_here = codename in deployed_codenames or ("BOSS_" + codename) in deployed_codenames
        status = "DEJA DEPLOYE" if deployed_here else "PAS DEPLOYE (dispo dans le roster mais pas a la base)"
        print(f"{categorie}: meilleur possede = {nom_affiche} (x{nombre}) -> {status}")
        gaps.append({
            "categorie": categorie,
            "meilleur_possede": nom_affiche,
            "codename": codename,
            "nombre_possede": nombre,
            "deja_deploye": deployed_here,
        })

    with open(os.path.join(HERE, "base_work_gaps.json"), "w", encoding="utf-8") as f:
        json.dump(gaps, f, ensure_ascii=False, indent=2)
    print("\nWrote base_work_gaps.json")


if __name__ == "__main__":
    main()
