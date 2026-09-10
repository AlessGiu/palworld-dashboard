# -*- coding: utf-8 -*-
"""Fetch official French dish names + ingredient names from paldb.cc French locale
pages, one fetch per dish (also yields ingredient translations as a side effect)."""
import re
import time
import urllib.request
import urllib.parse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

import sys
sys.path.insert(0, HERE)
from recipes_data import RECIPES

DISH_NAMES = sorted(set(nom for nom, *_ in RECIPES))

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


dish_fr = {}
ingredient_fr = {}
item_pattern = re.compile(r'itemname"[^>]*href="([A-Za-z0-9_]+)"[^>]*>(?:<img[^>]*>)?([^<]+)</a>')

SLUG_OVERRIDES = {
    "Chikipi Saute": "Chikipi_Sauté",
    "Jam-filled Bun": "Jam-Filled_Bun",
}

for nom in DISH_NAMES:
    slug = SLUG_OVERRIDES.get(nom, nom.replace(" ", "_"))
    url = f"https://paldb.cc/fr/{urllib.parse.quote(slug)}"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"FAIL {nom}: {e}")
        continue
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m:
        dish_fr[nom] = m.group(1)
    else:
        print(f"  ! no og:title for {nom}")
    for eng_slug, fr_name in item_pattern.findall(html):
        eng_name = eng_slug.replace("_", " ")
        ingredient_fr.setdefault(eng_name, fr_name)
    time.sleep(0.3)

print(f"dish_fr: {len(dish_fr)}/{len(DISH_NAMES)}")
print(f"ingredient_fr: {len(ingredient_fr)}")
missing = [n for n in DISH_NAMES if n not in dish_fr]
if missing:
    with open(os.path.join(HERE, "fr_debug_ascii.txt"), "w", encoding="ascii", errors="backslashreplace") as f:
        f.write("MISSING DISHES:\n" + "\n".join(missing) + "\n")

with open(os.path.join(HERE, "fr_debug_ascii.txt"), "a", encoding="ascii", errors="backslashreplace") as f:
    f.write("\nDISHES:\n")
    for nom in DISH_NAMES:
        f.write(f"{nom} -> {dish_fr.get(nom, 'MISSING')}\n")
    f.write("\nINGREDIENTS:\n")
    for k, v in sorted(ingredient_fr.items()):
        f.write(f"{k} -> {v}\n")

with open(os.path.join(HERE, "recipes_fr.json"), "w", encoding="utf-8") as f:
    json.dump({"dishes": dish_fr, "ingredients": ingredient_fr}, f, ensure_ascii=False, indent=1)
print("\nWrote recipes_fr.json")
