# -*- coding: utf-8 -*-
"""Construit pals_fr.json : noms FR officiels des especes et des passifs (paldb.cc/fr).

- pals      : identifiant interne (ex. IceHorse_Dark) -> nom FR
- passives  : identifiant interne (ex. ElementBoost_Dark_2_PAL) -> {nom, rang, desc}
              rang : -3..-1 = defaut (rouge), 1 = commun, 2-3 = rare (or), 4 = legendaire (arc-en-ciel)

A relancer apres une mise a jour du jeu. Le dashboard horaire lit seulement le JSON (aucun reseau).
"""
import html as htmllib
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


# --- especes ---
bf = fetch("https://paldb.cc/fr/Breeding_Farm")
start = bf.index('id="BreedCombi"')
end = bf.index('id="BreedUnique"')
pals = {}
for m in re.finditer(r'<tr><td><a data-pal-id="([^"]+)"[^>]*>.*?/>([^<]+)</a></td><td>(\d+)</td>', bf[start:end]):
    pals[m.group(1)] = htmllib.unescape(m.group(2)).strip()

# --- passifs : identifiant interne -> nom FR (table), puis rang + description FR (page detaillee) ---
table = fetch("https://paldb.cc/fr/PassiveSkills_Table")
id_to_name = {}
for name, pid in re.findall(r'flex-grow-1 mx-2">([^<]+)<div>([A-Za-z0-9_]+)</div>', table):
    id_to_name[pid] = htmllib.unescape(name).strip()

page = fetch("https://paldb.cc/fr/Passive_Skills")
by_name = {}
for block in page.split('<div class="col"><div class="border bg-dark">')[1:]:
    m = re.search(r'passive-rank(-?\d+) ps-2 py-1">([^<]+)</div>', block)
    if not m:
        continue
    rang, nom = int(m.group(1)), htmllib.unescape(m.group(2)).strip()
    d = re.search(r'<div class="p-2"[^>]*>\s*<div>(.*?)</div>', block, flags=re.S)
    desc = ""
    if d:
        desc = d.group(1).replace("<br />", " ; ")
        desc = re.sub(r"</?[A-Za-z_0-9]*[^>]*>", "", desc)
        desc = re.sub(r"\s+", " ", htmllib.unescape(desc)).strip(" ;")
    by_name.setdefault(nom, {"rang": rang, "desc": desc})

passives = {}
for pid, nom in id_to_name.items():
    info = by_name.get(nom, {})
    passives[pid] = {"nom": nom, "rang": info.get("rang", 0), "desc": info.get("desc", "")}

with open(os.path.join(HERE, "pals_fr.json"), "w", encoding="utf-8") as f:
    json.dump({"pals": pals, "passives": passives}, f, ensure_ascii=False, indent=0)

sans_rang = sum(1 for v in passives.values() if not v["rang"])
print(f"pals: {len(pals)} | passifs: {len(passives)} (sans rang: {sans_rang})")
