# -*- coding: utf-8 -*-
import re
import json
import os

TMP = r"C:\Users\apoll\AppData\Local\Temp"

HREF_TO_FIELD = {
    "Kindling": "emit_flame",
    "Watering": "watering",
    "Planting": "seeding",
    "Generating_Electricity": "generate_electricity",
    "Handiwork": "handcraft",
    "Gathering": "collection",
    "Lumbering": "deforest",
    "Mining": "mining",
    "Oil_Extraction": "oil_extraction",
    "Medicine_Production": "product_medicine",
    "Cooling": "cool",
    "Transporting": "transport",
    "Farming": "monster_farm",
}

ROW_RE = re.compile(
    r'<div><a href="([A-Za-z_]+)">.*?</a></div><div><span style="font-size:x-small">Lv</span>(?:<span class="Status_Up">(\d+)</span>|(\d+))</div>'
)

CODENAME_BY_DISPLAY = {
    "Clovee": "CloverFairy",
    "Jelliette": "JellyfishFairy",
    "Jellroy": "JellyfishGhost",
    "Tarantriss": "PurpleSpider",
    "Amione": "ClioneTwins",
    "Puffolt": "ElecPomeranian",
    "Muffly": "FluffyBird",
    "Wispaw": "GhostBlackCat",
    "Elgrove": "GrassMinotaur",
    "Leafan": "PandaGirl",
    "Pupperai": "SamuraiDog",
    "Snugloo": "SmallYeti",
    "Finsider": "StuffedShark",
    "Skutlass": "SwordCutlassfish",
    "Croajiro": "KendoFrog",
    "Xenovader": "DarkAlien",
    "Mimog": "MimicDog",
    "Herbil": "LeafMomonga",
}

results = {}
for display_name, codename in CODENAME_BY_DISPLAY.items():
    path = os.path.join(TMP, f"pal_{display_name}.html")
    if not os.path.exists(path):
        print(f"MISSING FILE for {display_name}")
        continue
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # isolate the work-suitability block: between "Work Suitability" heading and next major section
    start = html.find('href="Work_Suitability"')
    if start == -1:
        print(f"{display_name} ({codename}): NO Work Suitability SECTION FOUND")
        results[codename] = {}
        continue
    end = html.find('BestWorkSuitability', start)
    block = html[start:end if end != -1 else start + 6000]

    ws = {v: 0 for v in HREF_TO_FIELD.values()}
    for m in ROW_RE.finditer(block):
        href, v1, v2 = m.group(1), m.group(2), m.group(3)
        val = int(v1) if v1 is not None else int(v2)
        field = HREF_TO_FIELD.get(href)
        if field:
            ws[field] = val
        else:
            print(f"  ! unknown href '{href}' for {display_name}")
    results[codename] = ws
    print(f"{display_name} ({codename}): {ws}")

out_path = os.path.join(
    r"C:\Users\apoll\AppData\Local\Temp\claude\C--Users-apoll\afde2145-bc39-4447-8bc7-c4383b0e8750\scratchpad\palworld_migration",
    "paldb_extra_work_suitability.json",
)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nWrote", out_path)
