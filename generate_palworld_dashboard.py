import io
import os
import re
import json
import contextlib
import datetime
import subprocess

import paramiko

from recipes_data import RECIPES, CROP_TO_INGREDIENT, STATION_BUILDINGS
from secrets_local import SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASS, WEBHOOK_URL, PROXMOX_HOST

REMOTE_SAVE_DIR = "/Pal/Saved/SaveGames/0/D5C16DC3464E7CC492225ABB991F1FA2"
REMOTE_LEVEL_SAV = REMOTE_SAVE_DIR + "/Level.sav"

OOZ_DLL_PATH = os.path.join(
    os.path.dirname(__file__), "palworld-hostfix-toolkit", "ooz", "libooz.dll"
)
os.environ["PALWORLD_OOZ_DLL_PATH"] = OOZ_DLL_PATH

HERE = os.path.dirname(__file__)
LOCAL_TMP = os.path.join(HERE, "status_check_Level.sav")
LOCAL_HTML = os.path.join(HERE, "palworld_dashboard.html")
LOCAL_SNAPSHOT = os.path.join(HERE, "palworld_last_snapshot.json")

IGNORED_PLAYER_NAMES = {"skP", "Ekinox"}

# Recommandations "travail a la base" -- données REELLES d'aptitude au travail
# (les 13 champs WorkSuitability du DataTable DT_PalMonsterParameter du jeu, valeurs 0-4),
# pas une estimation basee sur la reputation. Sources :
#   - blaynem/paldex (GitHub) : extraction des DataTables du jeu, baked-data/en/pals.json
#     -> couvre 157 espèces (+ formes Boss/Alpha), 314 entrées
#   - paldb.cc : les 18 espèces ajoutees après la snapshot paldex (Feybreak/DLC, ex.
#     Wispaw, Tarantriss, Skutlass...) ont ete vérifiées individuellement sur leur fiche
#     paldb.cc (section "Work Suitability" de chaque page), pas devinees
# Chaque catégorie liste jusqu'a 10 espèces candidates classees par etoiles réelles
# (toutes espèces du jeu confondues, pas seulement celles possédées) : collect_data()
# ci-dessous filtre en direct selon le roster réellement possédé a chaque génération,
# donc la liste reste a jour automatiquement si de nouveaux Pals sont captures.
# codename interne -> nom affiche en jeu (vérifié via paldex + paldb.cc + palmods.gg)
WORK_RECOMMENDATIONS = {
    "Allumage": [("Umihebi_Fire", "Jormuntide Ignis"), ("GYM_Horus", "PIDF Officer Marcus & Faleris"), ("Horus", "Faleris"), ("KingBahamut", "Blazamut"), ("Manticore", "Blazehowl"), ("Manticore_Dark", "Blazehowl Noct"), ("RedArmorBird", "Ragnahawk"), ("Suzaku", "Suzaku"), ("VolcanicMonster", "Reptyro"), ("AmaterasuWolf", "Kitsun")],
    "Arrosage": [("SwordCutlassfish", "Skutlass"), ("Umihebi", "Jormuntide"), ("BlueDragon", "Azurobe"), ("FairyDragon_Water", "Elphidran Aqua"), ("SakuraSaurus_Water", "Broncherry Aqua"), ("Suzaku_Water", "Suzaku Aqua"), ("CaptainPenguin", "Penking"), ("JellyfishFairy", "Jelliette"), ("JellyfishGhost", "Jellroy"), ("LazyDragon", "Relaxaurus")],
    "Plantation": [("LilyQueen", "Lyleen"), ("FlowerDoll", "Petallia"), ("GYM_LilyQueen", "Free Pal Alliance Founder Lily & Lyleen"), ("GrassMinotaur", "Elgrove"), ("PandaGirl", "Leafan"), ("SakuraSaurus", "Broncherry"), ("BerryGoat", "Caprity"), ("BlueberryFairy", "Prunelia"), ("CuteButterfly", "Cinnamoth"), ("FlowerDinosaur", "Dinossom")],
    "Électricité": [("ThunderDragonMan", "Orserk"), ("ElecPanda", "Grizzbolt"), ("GYM_ElecPanda", "Rayne Syndicate Officer Zoe & Grizzbolt"), ("GYM_ThunderDragonMan", "Brothers of the Eternal Pyre Soul Reader Axel & Orserk"), ("LazyDragon_Electric", "Relaxaurus Lux"), ("ElecPomeranian", "Puffolt"), ("FlowerDinosaur_Electric", "Dinossom Lux"), ("GrassPanda_Electric", "Mossanda Lux"), ("Kirin", "Univolt"), ("ThunderBird", "Beakon")],
    "Manutention": [("Anubis", "Anubis"), ("DarkMutant", "DarkMutant"), ("FoxMage", "Wixen"), ("GrassRabbitMan", "Verdash"), ("LilyQueen", "Lyleen"), ("LilyQueen_Dark", "Lyleen Noct"), ("Mutant", "Lunaris"), ("PandaGirl", "Leafan"), ("PurpleSpider", "Tarantriss"), ("SifuDog", "Dogen")],
    "Cueillette": [("IceHorse_Dark", "Frostallion Noct"), ("BadCatgirl", "Nyafia"), ("GrassRabbitMan", "Verdash"), ("JetDragon", "Jetragon"), ("PandaGirl", "Leafan"), ("PurpleSpider", "Tarantriss"), ("BlueberryFairy", "Prunelia"), ("BrownRabbit", "Lapiron"), ("CatBat", "Tombat"), ("Eagle", "Galeclaw")],
    "Bûcheronnage": [("SwordCutlassfish", "Skutlass"), ("DarkAlien", "Xenovader"), ("GrassMinotaur", "Elgrove"), ("HerculesBeetle", "Warsect"), ("Ronin", "Bushi"), ("ScorpionMan", "Prixter"), ("Yeti", "Wumpo"), ("Yeti_Grass", "Wumpo Botan"), ("BlackCentaur", "Necromus"), ("DarkScorpion", "Menasting")],
    "Minage": [("BlackMetalDragon", "Astegon"), ("KingBahamut", "Blazamut"), ("Anubis", "Anubis"), ("DarkScorpion", "Menasting"), ("DrillGame", "Digtoise"), ("SmallYeti", "Snugloo"), ("VolcanicMonster", "Reptyro"), ("VolcanicMonster_Ice", "Ice Reptyro"), ("WingGolem", "Knocklem"), ("BlackCentaur", "Necromus")],
    "Extraction de pétrole": [("BlackMetalDragon", "Astegon"), ("GoldenHorse", "Gildane"), ("JetDragon", "Jetragon"), ("ScorpionMan", "Prixter"), ("BrownRabbit", "Lapiron"), ("LazyCatfish", "Dumud")],
    "Médecine": [("BlueberryFairy", "Prunelia"), ("CatVampire", "Felbat"), ("DarkMutant", "DarkMutant"), ("GYM_LilyQueen", "Free Pal Alliance Founder Lily & Lyleen"), ("LilyQueen", "Lyleen"), ("LilyQueen_Dark", "Lyleen Noct"), ("VioletFairy", "Vaelet"), ("CatMage", "Katress"), ("FlowerDoll", "Petallia"), ("LittleBriarRose", "Bristla")],
    "Refroidissement": [("IceHorse", "Frostallion"), ("KingAlpaca_Ice", "Ice Kingpaca"), ("SmallYeti", "Snugloo"), ("VolcanicMonster_Ice", "Ice Reptyro"), ("WhiteTiger", "Cryolinx"), ("BirdDragon_Ice", "Vanwyrm Cryst"), ("CaptainPenguin", "Penking"), ("FluffyBird", "Muffly"), ("GrassMammoth_Ice", "Mammorest Cryst"), ("IceDeer", "Reindrix")],
    "Transport": [("WingGolem", "Knocklem"), ("Yeti", "Wumpo"), ("Yeti_Grass", "Wumpo Botan"), ("BirdDragon", "Vanwyrm"), ("BirdDragon_Ice", "Vanwyrm Cryst"), ("BlackFurDragon", "Dragostrophe"), ("ElecPanda", "Grizzbolt"), ("GYM_ElecPanda", "Rayne Syndicate Officer Zoe & Grizzbolt"), ("GYM_Horus", "PIDF Officer Marcus & Faleris"), ("GYM_ThunderDragonMan", "Brothers of the Eternal Pyre Soul Reader Axel & Orserk")],
    "Élevage/Ferme": [("Alpaca", "Melpaca"), ("Bastet", "Mau"), ("Bastet_Ice", "Mau Cryst"), ("BerryGoat", "Caprity"), ("ChickenPal", "Chikipi"), ("CowPal", "Mozzarina"), ("CuteFox", "Vixy"), ("LavaGirl", "Flambelle"), ("SheepBall", "Lamball"), ("SoldierBee", "Beegarde")],
}

# Catégorie FR -> champ interne WorkSuitability (voir WORK_SUITABILITY_FULL ci-dessous)
CATEGORY_FIELD = {
    "Allumage": "emit_flame",
    "Arrosage": "watering",
    "Plantation": "seeding",
    "Électricité": "generate_electricity",
    "Manutention": "handcraft",
    "Cueillette": "collection",
    "Bûcheronnage": "deforest",
    "Minage": "mining",
    "Extraction de pétrole": "oil_extraction",
    "Médecine": "product_medicine",
    "Refroidissement": "cool",
    "Transport": "transport",
    "Élevage/Ferme": "monster_farm",
}
CATEGORY_FIELD_INV = {v: k for k, v in CATEGORY_FIELD.items()}

# Profil complet (13 etoiles réelles) de chaque espèce connue, baked localement
# (build_full_species_profiles.py) pour ne jamais dependre d'un appel réseau a
# chaque génération horaire du dashboard.
with open(os.path.join(HERE, "work_suitability_full.json"), "r", encoding="utf-8") as _f:
    WORK_SUITABILITY_FULL = json.load(_f)

# Stats de combat (attaque/PV/defense/éléments/vitesse monture) par espèce, baked localement
# (build_combat_stats.py) pour l'equipe de terrain recommandee.
with open(os.path.join(HERE, "combat_stats_full.json"), "r", encoding="utf-8") as _f:
    COMBAT_STATS_FULL = json.load(_f)

# Combi Rank (formule de reproduction) par espèce, baked localement (build_combi_ranks.py),
# entrées rank<=0/"en_text" déjà exclues (données non remplies dans le DataTable source).
with open(os.path.join(HERE, "combi_ranks_full.json"), "r", encoding="utf-8") as _f:
    COMBI_RANKS_FULL = json.load(_f)

# Traductions FR officielles des plats/ingredients (fetch_fr_translations.py, sourcees
# directement des pages paldb.cc/fr/<plat> -- vrai texte du jeu, pas une traduction maison).
with open(os.path.join(HERE, "recipes_fr.json"), "r", encoding="utf-8") as _f:
    _RECIPES_FR = json.load(_f)
DISH_NAME_FR = _RECIPES_FR["dishes"]
INGREDIENT_NAME_FR = _RECIPES_FR["ingredients"]

VARIANT_SUFFIXES = ["_Fire", "_Dark", "_Electric", "_Water", "_Grass", "_Ice"]

# Univers "Palpedia reelle" pour le suivi de complétion : on exclut les PNJ uniques de
# tour (prefixe GYM_, pal_index=-2 dans le DataTable -- pas des Pals capturables) et 4
# espèces confirmees non disponibles en jeu (is_available_ingame=False, aucun nom réel
# trouve via 2 sources independantes -- probablement du contenu coupe/de test).
PALPEDIA_EXCLUDED = {"PinkKangaroo", "BeardedDragon", "WaterLizard", "GrassDragon"}
PALPEDIA_UNIVERSE = sorted(
    cn for cn in WORK_SUITABILITY_FULL if not cn.startswith("GYM_") and cn not in PALPEDIA_EXCLUDED
)

# Icones officielles du jeu, servies par paldb.cc (vérifié -- même codename interne que
# pal_dev_name, HTTP 200 confirme sur un echantillon couvrant espèces de base, variantes
# elementaires (suffixe _Fire/_Ice/...) et les 18 espèces hors paldex/DLC).
def pal_icon_url(codename):
    return f"https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_{codename}_icon_normal.webp"


ELEMENT_EMOJI = {
    "Neutral": "&#9898;", "Fire": "&#128293;", "Water": "&#128167;", "Grass": "&#127807;",
    "Electric": "&#9889;", "Ice": "&#10052;&#65039;", "Dark": "&#127761;", "Dragon": "&#128009;",
    "Ground": "&#129688;",
}


def _build_pal_card_data():
    """Fiche complète par espèce (icone + stats + aptitudes + rang combi) pour la modale
    'carte du Pal' cliquable dans Palpédia/Élevage -- toutes données déjà chargees
    localement (WORK_SUITABILITY_FULL/COMBAT_STATS_FULL/COMBI_RANKS_FULL), aucun appel
    réseau supplementaire au runtime."""
    codenames = set(PALPEDIA_UNIVERSE) | set(COMBI_RANKS_FULL) | set(COMBAT_STATS_FULL)
    out = {}
    for cn in codenames:
        ws_entry = WORK_SUITABILITY_FULL.get(cn, {})
        cp_entry = COMBAT_STATS_FULL.get(cn, {})
        cr_entry = COMBI_RANKS_FULL.get(cn, {})
        nom = ws_entry.get("display_name") or cp_entry.get("display_name") or cr_entry.get("display_name") or cn
        aptitudes = sorted(
            (
                (CATEGORY_FIELD_INV.get(field, field), v)
                for field, v in ws_entry.get("work_suitability", {}).items()
                if v > 0
            ),
            key=lambda x: -x[1],
        )[:3]
        out[cn] = {
            "nom": nom,
            "icon": pal_icon_url(cn),
            "elements": cp_entry.get("elements", []),
            "hp": cp_entry.get("hp"),
            "atk": cp_entry.get("melee_attack"),
            "atk_tir": cp_entry.get("shot_attack"),
            "def": cp_entry.get("defense"),
            "monture": cp_entry.get("ride_sprint_speed") or 0,
            "food": ws_entry.get("food_amount"),
            "aptitudes": aptitudes,
            "rang_combi": cr_entry.get("rank"),
        }
    return out


PAL_CARD_DATA = _build_pal_card_data()


def _resolve_from(lookup, codename):
    """Return (base_codename, entry) for a live CharacterID against `lookup`, handling
    BOSS_ prefixes and elemental-variant suffixes (which share their base species' data
    in the game's own DataTable -- documented fact, not a guess). (codename, None) if unknown."""
    if codename in lookup:
        return codename, lookup[codename]
    base = codename
    if base.startswith("BOSS_") or base.startswith("Boss_"):
        base = base[5:]
        if base in lookup:
            return base, lookup[base]
    for suffix in VARIANT_SUFFIXES:
        if base.endswith(suffix):
            root = base[: -len(suffix)]
            if root in lookup:
                return root, lookup[root]
    lower_map = {k.lower(): k for k in lookup}
    if base.lower() in lower_map:
        real = lower_map[base.lower()]
        return real, lookup[real]
    return codename, None


def resolve_species_profile(codename):
    """Work-suitability profile (13 catégories) for a live CharacterID."""
    return _resolve_from(WORK_SUITABILITY_FULL, codename)


def resolve_combat_profile(codename):
    """Combat stats (attack/hp/defense/éléments/mount speed) for a live CharacterID."""
    return _resolve_from(COMBAT_STATS_FULL, codename)


def resolve_combi_rank(codename):
    """Combi Rank (breeding formula) for a live CharacterID."""
    return _resolve_from(COMBI_RANKS_FULL, codename)


SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519_proxmox")
SSH_EXE = r"C:\Program Files\Git\usr\bin\ssh.exe"
SCP_EXE = r"C:\Program Files\Git\usr\bin\scp.exe"


def unwrap(field, default=0):
    v = field.get("value", default) if isinstance(field, dict) else default
    while isinstance(v, dict) and "value" in v:
        v = v["value"]
    return v


def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def prettify_boss_name(name):
    name = name.replace("BOSS_BATTLE_NAME_", "").replace("_", " ")
    name = re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()
    return name


STAT_NAME_FR = {
    "最大HP": "PV Max",
    "改造最大HP": "PV Max",
    "最大SP": "Endurance",
    "攻撃力": "Attaque",
    "所持重量": "Poids transportable",
    "捕獲率": "Capture",
    "作業速度": "Vitesse de travail",
    "移動速度アップ": "Vitesse de deplacement",
    "空腹率低減": "Reduction de la faim",
    "泳ぎ速度": "Vitesse de nage",
    "滑空速度": "Vitesse de planeur",
    "消化速度": "Vitesse de digestion",
    "パルスフィアホーミング": "Visee auto (Sphere)",
}

PLATFORM_FR = {
    "EPalPlayerPlatform::Steam": "Steam",
    "EPalPlayerPlatform::Xbox": "Xbox",
    "EPalPlayerPlatform::PS": "PlayStation",
}


def dotnet_ticks_to_days_ago(ticks):
    dt = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=ticks / 10)
    delta = datetime.datetime.now() - dt
    return delta.total_seconds() / 86400


def stat_points_list(field):
    if not isinstance(field, dict):
        return []
    values = field.get("value", {})
    if isinstance(values, dict):
        values = values.get("values", [])
    rows = []
    for entry in values:
        raw_name = unwrap(entry.get("StatusName"), "?")
        pts = unwrap(entry.get("StatusPoint"), 0)
        if pts:
            rows.append((STAT_NAME_FR.get(raw_name, raw_name), pts))
    return rows


def download_level_sav():
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.get(REMOTE_LEVEL_SAV, LOCAL_TMP)
    sftp.close()
    transport.close()


def download_player_sav(uid_str):
    filename = uid_str.replace("-", "").upper() + ".sav"
    local_path = os.path.join(HERE, "status_check_" + filename)
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.get(REMOTE_SAVE_DIR + "/Players/" + filename, local_path)
    sftp.close()
    transport.close()
    return local_path


def _parse_sav(local_path, top_key):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from palworld_save_tools.gvas import GvasFile
        from palworld_save_tools.palsav import decompress_sav_to_gvas
        from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

        with open(local_path, "rb") as f:
            data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)
        gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
        json_data = gvas_file.dump()
    return json_data["properties"][top_key]["value"]


def load_world_save_data():
    return _parse_sav(LOCAL_TMP, "worldSaveData")


def load_player_save_data(local_path):
    data = _parse_sav(local_path, "SaveData")
    os.remove(local_path)
    return data


def collect_data():
    download_level_sav()
    wsd = load_world_save_data()

    char_map = wsd["CharacterSaveParameterMap"]["value"]
    players = []
    pals = []
    pal_by_instance = {}
    for e in char_map:
        raw = e["value"]["RawData"]["value"]
        obj = raw.get("object", {}) if isinstance(raw, dict) else {}
        sp = obj.get("SaveParameter", {}).get("value", {}) if isinstance(obj, dict) else {}
        if sp.get("IsPlayer", {}).get("value", False):
            uid = e["key"]["PlayerUId"]["value"]
            if unwrap(sp.get("NickName"), "?") not in IGNORED_PLAYER_NAMES:
                players.append((str(uid), sp))
        else:
            pal_by_instance[str(e["key"]["InstanceId"]["value"])] = sp
            pals.append(sp)

    uid_to_name = {uid: unwrap(sp.get("NickName"), "?") for uid, sp in players}

    data = {}

    # --- MONDE ---
    gt = wsd["GameTimeSaveData"]["value"]
    ticks = gt["GameDateTimeTicks"]["value"]
    days = ticks / (10_000_000 * 60 * 60 * 24)
    invaders = wsd["InvaderSaveData"]["value"]
    active_raids = sum(1 for e in invaders if e["value"].get("bIsInvading", {}).get("value"))
    # bIsClear = etat TRANSITOIRE (ce camp precis est vide d'ennemis LA MAINTENANT) -- les
    # camps repeuplent avec le temps, donc ce chiffre retombe a 0 même si le joueur en a
    # déjà conquis plein. Le vrai compteur cumulatif est CampConqueredCount (par joueur,
    # dans RecordData) -- voir plus bas.
    camps = wsd["EnemyCampSaveData"]["value"]["EnemyCampStatusMap"]["value"]
    camps_cleared = sum(1 for c in camps if c["value"].get("bIsClear", {}).get("value"))
    dungeon_markers = len(wsd["DungeonPointMarkerSaveData"]["value"]["values"])
    num_bases = len(wsd["BaseCampSaveData"]["value"])

    data["monde"] = {
        "jours": round(days, 1),
        "bases": num_bases,
        "raids_actifs": active_raids,
        "raids_total": len(invaders),
        "camps_nettoyes": camps_cleared,
        "camps_total": len(camps),
        "donjons": dungeon_markers,
    }

    # --- JOUEURS ---
    data["joueurs"] = []
    for uid, p in players:
        name = unwrap(p.get("NickName"), "?")
        entry = {
            "nom": name,
            "niveau": unwrap(p.get("Level"), 1),
            "xp": unwrap(p.get("Exp"), 0),
            "faim": safe_float(unwrap(p.get("FullStomach"), 0)),
            "bouclier": safe_float(unwrap(p.get("ShieldHP"), 0)),
            "stats": stat_points_list(p.get("GotStatusPointList")),
        }
        try:
            local_path = download_player_sav(uid)
            psd = load_player_save_data(local_path)

            last_online_ticks = unwrap(psd.get("LastOnlineDateTime"), None)
            entry["derniere_connexion_jours"] = (
                round(dotnet_ticks_to_days_ago(last_online_ticks), 2) if last_online_ticks else None
            )

            platform_raw = unwrap(psd.get("PlayerPlatform"), None)
            entry["plateforme"] = PLATFORM_FR.get(platform_raw, platform_raw or "inconnue")
            entry["points_tech_boss"] = unwrap(psd.get("bossTechnologyPoint"), 0)

            quests = psd.get("CompletedQuestArray_FullRelease")
            qv = quests.get("value", {}) if isinstance(quests, dict) else {}
            entry["quetes_completees"] = len(qv.get("values", [])) if isinstance(qv, dict) else 0

            recipes = psd.get("UnlockedRecipeTechnologyNames")
            rv = recipes.get("value", {}) if isinstance(recipes, dict) else {}
            entry["recettes_debloquees"] = len(rv.get("values", [])) if isinstance(rv, dict) else 0

            rd = psd.get("RecordData")
            rd_val = rd.get("value", {}) if isinstance(rd, dict) else {}
            tower_flags = rd_val.get("TowerBossDefeatFlag", {}).get("value", [])
            entry["boss_tour"] = [prettify_boss_name(e["key"]) for e in tower_flags if e.get("value")]
            world_flags = rd_val.get("NormalBossDefeatFlag", {}).get("value", [])
            entry["boss_monde"] = sum(1 for e in world_flags if e.get("value"))
            entry["camps_conquis"] = unwrap(rd_val.get("CampConqueredCount"), 0)

            oqa = psd.get("OrderedQuestArray_FullRelease")
            oqa_vals = oqa.get("value", {}).get("values", []) if isinstance(oqa, dict) else []
            entry["quete_en_cours"] = (
                prettify_boss_name(unwrap(oqa_vals[0].get("QuestName"), "aucune")) if oqa_vals else "aucune"
            )
        except Exception:
            pass

        data["joueurs"].append(entry)

    # --- PALS ---
    species = set()
    owners = {}
    species_count = {}
    species_best_level = {}
    for p in pals:
        cid = unwrap(p.get("CharacterID"), "?")
        species.add(cid)
        species_count[cid] = species_count.get(cid, 0) + 1
        lvl = unwrap(p.get("Level"), 1)
        if cid not in species_best_level or lvl > species_best_level[cid]:
            species_best_level[cid] = lvl
        owner = unwrap(p.get("OwnerPlayerUId"), None)
        owner_key = str(owner) if owner else None
        display = uid_to_name.get(owner_key, "Sans propriétaire")
        owners[display] = owners.get(display, 0) + 1

    top_level = sorted(pals, key=lambda p: unwrap(p.get("Level"), 1), reverse=True)[:10]
    top_friend = sorted(pals, key=lambda p: safe_float(unwrap(p.get("FriendshipPoint"), 0)), reverse=True)[:5]

    def iv_score(p):
        return safe_float(unwrap(p.get("Talent_HP"), 0)) + safe_float(unwrap(p.get("Talent_Shot"), 0)) + safe_float(unwrap(p.get("Talent_Defense"), 0))

    def passive_names(p):
        pl = p.get("PassiveSkillList")
        vals = pl.get("value", {}) if isinstance(pl, dict) else {}
        return vals.get("values", []) if isinstance(vals, dict) else []

    best_iv = sorted(pals, key=iv_score, reverse=True)[:10]

    data["pals"] = {
        "total": len(pals),
        "especes": len(species),
        "repartition": owners,
        "top_niveaux": [
            {"espece": unwrap(p.get("CharacterID")), "niveau": unwrap(p.get("Level"))} for p in top_level
        ],
        "top_affection": [
            {"espece": unwrap(p.get("CharacterID")), "affection": int(safe_float(unwrap(p.get("FriendshipPoint"))))}
            for p in top_friend
        ],
        "top_iv": [
            {
                "espece": unwrap(p.get("CharacterID")),
                "hp": unwrap(p.get("Talent_HP")),
                "att": unwrap(p.get("Talent_Shot")),
                "def": unwrap(p.get("Talent_Defense")),
                "passifs": passive_names(p),
            }
            for p in best_iv
        ],
    }

    # --- PALPEDIA PAR JOUEUR ---
    # Base sur la propriété ACTUELLE des Pals (OwnerPlayerUId), pas un historique de capture --
    # si un Pal a change de main ou dort dans un coffre partage, ca peut sous-compter le vrai
    # nombre d'espèces qu'un joueur a un jour capturees.
    owned_species_by_player = {}
    for p in pals:
        owner = unwrap(p.get("OwnerPlayerUId"), None)
        owner_key = str(owner) if owner else None
        owner_name = uid_to_name.get(owner_key)
        if not owner_name:
            continue
        cid = unwrap(p.get("CharacterID"), "?")
        base_cn, _ = resolve_species_profile(cid)
        owned_species_by_player.setdefault(owner_name, set()).add(base_cn)

    palpedia_universe_set = set(PALPEDIA_UNIVERSE)
    palpedia_out = []
    for player_name, owned_set in owned_species_by_player.items():
        owned_in_universe = owned_set & palpedia_universe_set
        missing = sorted(
            (
                {"nom": WORK_SUITABILITY_FULL[cn]["display_name"], "codename": cn}
                for cn in palpedia_universe_set - owned_set
            ),
            key=lambda x: x["nom"],
        )
        possedees_liste = sorted(
            (
                {"nom": WORK_SUITABILITY_FULL[cn]["display_name"], "codename": cn}
                for cn in owned_in_universe
            ),
            key=lambda x: x["nom"],
        )
        palpedia_out.append({
            "joueur": player_name,
            "possedees": len(owned_in_universe),
            "total": len(palpedia_universe_set),
            "pct": round(len(owned_in_universe) / len(palpedia_universe_set) * 100, 1),
            "manquantes": missing,
            "possedees_liste": possedees_liste,
        })
    palpedia_out.sort(key=lambda p: -p["pct"])

    data["palpedia"] = {"joueurs": palpedia_out}

    # --- EQUIPE DE TERRAIN (combat/exploration, distincte du travail a la base) ---
    # Meilleure instance possédée par espèce (niveau + IV comme critere de choix),
    # avec ses vrais passifs (specifiques a cet exemplaire, pas a l'espèce).
    def interpret_passive(name):
        if name.startswith("ElementBoost_"):
            parts = name.split("_")
            if len(parts) >= 3:
                return f"boost dégâts {parts[1]} (niv.{parts[2]})"
        if "AutoHPRegeneRate" in name:
            return "régénération PV automatique"
        if "WorkSpeed" in name:
            return "vitesse de travail +"
        if "ReloadSpeedUp" in name:
            return "vitesse de rechargement +"
        if "MiniNushi" in name or "Legend" in name:
            return "passif rare puissant (bonus global)"
        return None

    species_best_instance = {}
    for p in pals:
        cid = unwrap(p.get("CharacterID"), "?")
        lvl = unwrap(p.get("Level"), 1)
        iv = safe_float(unwrap(p.get("Talent_HP"), 0)) + safe_float(unwrap(p.get("Talent_Shot"), 0)) + safe_float(unwrap(p.get("Talent_Defense"), 0))
        score = lvl * 10 + iv
        cur = species_best_instance.get(cid)
        if cur is None or score > cur["score"]:
            species_best_instance[cid] = {"level": lvl, "iv": iv, "passifs": passive_names(p), "score": score}

    combat_candidates = []
    for codename, inst in species_best_instance.items():
        base_cn, cp = resolve_combat_profile(codename)
        if not cp:
            continue
        power = cp["melee_attack"] + cp["shot_attack"]
        combat_candidates.append({
            "codename": codename,
            "nom": cp["display_name"],
            "elements": cp["elements"],
            "power": power,
            "hp": cp["hp"],
            "defense": cp["defense"],
            "level": inst["level"],
            "iv": inst["iv"],
            "passifs": [interpret_passive(x) and f"{x} ({interpret_passive(x)})" or x for x in inst["passifs"]],
            "ride_sprint_speed": cp["ride_sprint_speed"],
            "partner_skill": cp["partner_skill_description"],
        })
    combat_candidates.sort(key=lambda c: -c["power"])

    mounts = sorted(
        [c for c in combat_candidates if c["ride_sprint_speed"] and c["ride_sprint_speed"] > 0],
        key=lambda c: -c["ride_sprint_speed"],
    )

    TEAM_SIZE = 5
    equipe = []
    if mounts:
        equipe.append(dict(mounts[0], role="monture"))
    used_codenames = set(e["codename"] for e in equipe)
    covered_elements = set()

    # 1ere passe : privilegier la couverture elementaire (le plus puissant par élément manquant)
    for c in combat_candidates:
        if len(equipe) >= TEAM_SIZE:
            break
        if c["codename"] in used_codenames:
            continue
        new_elements = set(c["elements"]) - covered_elements
        if new_elements:
            equipe.append(dict(c, role="combat"))
            used_codenames.add(c["codename"])
            covered_elements |= set(c["elements"])
    # 2eme passe : completer par pure puissance
    for c in combat_candidates:
        if len(equipe) >= TEAM_SIZE:
            break
        if c["codename"] in used_codenames:
            continue
        equipe.append(dict(c, role="combat"))
        used_codenames.add(c["codename"])

    all_elements_owned = set(el for c in combat_candidates for el in c["elements"])
    KNOWN_ELEMENTS = ["Neutral", "Fire", "Water", "Grass", "Electric", "Ice", "Dark", "Dragon", "Ground"]
    elements_non_couverts = [el for el in KNOWN_ELEMENTS if el not in all_elements_owned]

    data["equipe_terrain"] = {
        "membres": equipe,
        "elements_non_couverts": elements_non_couverts,
    }

    # --- ELEVAGE / REPRODUCTION (formule Combi Rank reelle du jeu) ---
    # child_rank = floor((rankA + rankB + 1) / 2), puis l'espèce dont le combi_rank réel
    # est le plus proche de cette valeur est le résultat (mecanique officielle, sourcee
    # palbreeding.com / xgamingserver.com) -- ~28 paires speciales outrepassent la regle
    # generale et ne sont pas modelisees ici (a vérifier en jeu avant un élevage long).
    owned_ranked = []
    seen_rank_cn = set()
    for cn in species_count:
        base_cn, entry = resolve_combi_rank(cn)
        if entry and base_cn not in seen_rank_cn:
            seen_rank_cn.add(base_cn)
            owned_ranked.append({"codename": base_cn, "nom": entry["display_name"], "rank": entry["rank"]})
    owned_rank_set = set(o["codename"] for o in owned_ranked)

    all_species_ranked = [
        {"codename": cn, "nom": e["display_name"], "rank": e["rank"]}
        for cn, e in COMBI_RANKS_FULL.items()
    ]

    def closest_species(target_rank):
        return min(all_species_ranked, key=lambda s: abs(s["rank"] - target_rank))

    breeding_results = {}
    n = len(owned_ranked)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = owned_ranked[i], owned_ranked[j]
            child_rank = (a["rank"] + b["rank"] + 1) // 2
            best = closest_species(child_rank)
            if best["codename"] in owned_rank_set:
                continue
            dist = abs(best["rank"] - child_rank)
            cur = breeding_results.get(best["codename"])
            if cur is None or dist < cur["dist"] or (dist == cur["dist"] and best["rank"] < cur["target_rank"]):
                breeding_results[best["codename"]] = {
                    "nom": best["nom"], "target_rank": best["rank"], "dist": dist,
                    "parentA": a["nom"], "parentB": b["nom"],
                }

    breeding_list = sorted(breeding_results.values(), key=lambda r: (r["dist"], r["target_rank"]))[:16]

    data["elevage"] = {
        "combinaisons": breeding_list,
        "nb_especes_possedees_avec_rang": len(owned_ranked),
    }

    # --- TRAVAIL A LA BASE (recommandations, croisees avec le roster réel) ---
    # Les formes Boss/Alpha (prefixe BOSS_) partagent les mêmes aptitudes de travail
    # que leur forme normale (vérifié sur les données paldex) -- on agrege donc les
    # deux variantes pour ne pas rater un exemplaire possédé uniquement sous forme boss.
    data["travail_base"] = []
    for catégorie, candidats in WORK_RECOMMENDATIONS.items():
        trouvés = []
        for codename, nom_affiche in candidats:
            variants = [codename, "BOSS_" + codename] if not codename.startswith("BOSS_") else [codename]
            nombre = sum(species_count.get(v, 0) for v in variants)
            if nombre:
                niveau_max = max(species_best_level.get(v, 0) for v in variants)
                trouvés.append({
                    "nom": nom_affiche,
                    "nombre": nombre,
                    "niveau_max": niveau_max,
                })
        if trouvés:
            data["travail_base"].append({"categorie": catégorie, "pals": trouvés})

    # --- ETAT ACTUEL DE LA BASE (pals réellement assignes au travail) + SWAPS ---
    # On retrouve le/les conteneurs "WorkerDirector" de chaque base (BaseCampSaveData),
    # on lit les Pals places dedans (CharacterContainerSaveData), et on compare leur
    # vrai profil d'aptitudes (WORK_SUITABILITY_FULL) a ce qui dort dans le roster.
    ccsd = wsd["CharacterContainerSaveData"]["value"]
    containers_by_id = {str(c["key"]["ID"]["value"]): c["value"] for c in ccsd}

    # --- INFOS PAR BASE (id, position, conteneur de travail) ---
    bases_info = []
    for b in wsd["BaseCampSaveData"]["value"]:
        base_id = str(b["key"])
        raw = b["value"]["RawData"]["value"]
        translation = raw.get("transform", {}).get("translation", {}) if isinstance(raw.get("transform"), dict) else {}
        try:
            wd_raw = b["value"]["WorkerDirector"]["value"]["RawData"]["value"]
            container_id = str(wd_raw["container_id"])
        except (KeyError, TypeError):
            container_id = None
        bases_info.append({
            "base_id": base_id,
            "container_id": container_id,
            "x": round(translation.get("x", 0)),
            "y": round(translation.get("y", 0)),
            "deployed_count": 0,
        })

    deployed = []
    for binfo in bases_info:
        cont = containers_by_id.get(binfo["container_id"]) if binfo["container_id"] else None
        if not cont:
            continue
        slots = cont["Slots"]["value"]["values"]
        for slot in slots:
            raw = slot["RawData"]["value"]
            instance_id = str(raw["instance_id"])
            if instance_id == "00000000-0000-0000-0000-000000000000":
                continue
            sp = pal_by_instance.get(instance_id)
            if not sp:
                continue
            codename = unwrap(sp.get("CharacterID"), "?")
            niveau = unwrap(sp.get("Level"), 1)
            base_cn, profil = resolve_species_profile(codename)
            deployed.append({
                "idx": len(deployed),
                "base_id": binfo["base_id"],
                "codename": codename,
                "base_codename": base_cn,
                "niveau": niveau,
                "profil": profil.get("work_suitability", {}) if profil else {},
            })
            binfo["deployed_count"] += 1

    # --- CONSTRUCTIONS DE LA BASE (pour savoir si une catégorie a déjà son bâtiment) ---
    # Chaque objet construit porte un "base_camp_id_belong_to" (Model.RawData) qui le relie
    # a une base, et un nom de type exact via MapObjectId (ex. "ElectricGenerator", "CampFire").
    base_ids = set(b["base_id"] for b in bases_info)
    building_counts = {}
    building_counts_per_base = {bid: {} for bid in base_ids}
    eggs_per_base = {bid: [] for bid in base_ids}
    for e in wsd["MapObjectSaveData"]["value"]["values"]:
        model_raw = e["Model"]["value"]["RawData"]["value"]
        belong = str(model_raw.get("base_camp_id_belong_to", ""))
        if belong in base_ids:
            name = e["MapObjectId"]["value"]
            building_counts_per_base[belong][name] = building_counts_per_base[belong].get(name, 0) + 1
            if name == "HatchingPalEgg":
                try:
                    cm_raw = e["ConcreteModel"]["value"]["RawData"]["value"]
                    hatched = cm_raw.get("hatched_character_save_parameter", {})
                    species = unwrap(hatched.get("CharacterID"), None) if isinstance(hatched, dict) else None
                except Exception:
                    species = None
                eggs_per_base[belong].append(species)
            building_counts[name] = building_counts.get(name, 0) + 1

    # Correspondance bâtiment -> catégorie, basee sur le nom exact du bâtiment trouve dans la
    # sauvegarde (pas une supposition) : ce sont des types de structures sans ambiguite dans le
    # jeu (four/cuisiniere = Allumage, parcelle de culture = Plantation+Arrosage, etc.)
    BUILDINGS_BY_CATEGORY = {
        "Allumage": ["CampFire", "BlastFurnace2", "ElectricKitchen", "Heater"],
        "Arrosage": [k for k in building_counts if k.startswith("FarmBlockV2")],
        "Plantation": [k for k in building_counts if k.startswith("FarmBlockV2")],
        "Électricité": ["ElectricGenerator"],
        "Médecine": ["MedicineFacility_01", "Clinic"],
        "Élevage/Ferme": ["MonsterFarm", "BreedFarm"],
        "Manutention": ["WeaponFactory_Dirty_02", "RepairBench", "Crusher", "FlourMill"],
    }
    # Catégories ou le jeu exige un bâtiment placable specifique qui n'apparait pas du tout
    # dans le recensement ci-dessus -- absence constatee, pas une supposition sur le nom exact
    # (Cooler Box / Extracteur de pétrole n'ont pas d'equivalent parmi les objets trouvés).
    CATEGORIES_SANS_BATIMENT_DEDIE = {"Refroidissement", "Extraction de pétrole"}
    # Catégories qui exploitent des ressources naturelles du terrain (arbres, veines de
    # minerai) plutot qu'un bâtiment pose par le joueur -- la presence/absence ne peut pas
    # être confirmee depuis les objets construits.
    CATEGORIES_RESSOURCE_NATURELLE = {"Minage", "Bûcheronnage", "Cueillette", "Transport"}

    def batiment_dispo(catégorie, counts=None):
        noms = BUILDINGS_BY_CATEGORY.get(catégorie)
        if noms is None:
            return None  # pas verifiable depuis les constructions (ressource naturelle)
        source = counts if counts is not None else building_counts
        return any(source.get(n, 0) > 0 for n in noms)

    # meilleure espèce possédée par catégorie (deployee ou non) -- 1er candidat de
    # WORK_RECOMMENDATIONS (déjà trie par etoiles desc) que le roster possédé réellement
    deployed_base_codenames = set(d["base_codename"] for d in deployed)
    écarts = []
    for catégorie, candidats in WORK_RECOMMENDATIONS.items():
        for codename, nom_affiche in candidats:
            variants = [codename, "BOSS_" + codename]
            nombre = sum(species_count.get(v, 0) for v in variants)
            if nombre:
                stars = WORK_SUITABILITY_FULL.get(codename, {}).get("work_suitability", {}).get(
                    CATEGORY_FIELD[catégorie], 0
                )
                écarts.append({
                    "categorie": catégorie,
                    "nom": nom_affiche,
                    "codename": codename,
                    "etoiles": stars,
                    "nombre_possede": nombre,
                    "deja_deploye": codename in deployed_base_codenames,
                })
                break

    # swaps : associer chaque manque (meilleure espèce possédée mais pas deployee) au
    # poste actuel le plus faible, avec garde-fous :
    #  - jamais sortir un pal si ca fait tomber une catégorie qu'il couvre a 0 fournisseur
    #    (sauf si le remplaçant couvre lui-même cette catégorie)
    #  - jamais sortir un pal pour un remplaçant qui n'est pas strictement meilleur (etoiles)
    #  - jamais recommander plus d'exemplaires d'une espèce que ce qui est réellement possédé
    #  - une catégorie confirmee sans bâtiment dédié (Refroidissement, Pétrole) n'est pas
    #    proposee en swap immediat -- le gain serait inutilisable tant que rien n'est construit
    manques = sorted(
        [e for e in écarts if not e["deja_deploye"] and e["categorie"] not in CATEGORIES_SANS_BATIMENT_DEDIE],
        key=lambda e: -e["etoiles"],
    )
    manques_sans_batiment = [e for e in écarts if not e["deja_deploye"] and e["categorie"] in CATEGORIES_SANS_BATIMENT_DEDIE]

    # etat simule de la base (copie mutable) pour vérifier la couverture au fil des swaps.
    # "protected" = vient d'être ajoute pendant cette simulation -> jamais re-sorti dans
    # le même lot (sinon un pal fraichement swap-in pour un poste peut se faire recycler
    # par erreur comme "doublon" pour un autre poste juste après).
    sim = [dict(d, protected=False) for d in deployed]

    best_level_per_species = {}
    for d in sim:
        cur = best_level_per_species.get(d["base_codename"])
        if cur is None or d["niveau"] > cur["niveau"]:
            best_level_per_species[d["base_codename"]] = d
    pool_remaining = {}  # combien d'exemplaires d'une espèce "manque" restent disponibles a proposer
    swap_out_info = {}  # idx (poste d'origine) -> justification de sortie/entrée

    def coverage_count(pals, field):
        return sum(1 for p in pals if p["profil"].get(field, 0) > 0)

    swaps = []
    for manque in manques:
        codename = manque["codename"]
        remaining = pool_remaining.get(codename, manque["nombre_possede"])
        if remaining <= 0:
            continue  # espèce déjà entierement utilisee sur un autre swap

        # candidats a la sortie (jamais un pal protege), tries : doublons (espèce déjà en
        # poste ailleurs) d'abord, puis par etoile max croissante (le plus faible en premier)
        ranked = []
        for d in sim:
            if d["protected"]:
                continue
            is_duplicate = best_level_per_species.get(d["base_codename"]) is not d
            best_star = max(d["profil"].values()) if d["profil"] else 0
            ranked.append((0 if is_duplicate else 1, best_star, is_duplicate, best_star, d))
        ranked.sort(key=lambda r: (r[0], r[1]))

        chosen = None
        for _, _, is_duplicate, best_star, d in ranked:
            if d["base_codename"] == codename:
                continue  # ne pas sortir la même espèce qu'on veut faire entrer
            if best_star >= manque["etoiles"] and not is_duplicate:
                continue  # pas un vrai gain -- on ne sacrifie pas un poste au moins aussi bon
            if not is_duplicate:
                # vérifier qu'aucune catégorie couverte par d ne tombe a 0 fournisseur
                would_break_coverage = False
                for field, stars in d["profil"].items():
                    if stars > 0 and field != CATEGORY_FIELD[manque["categorie"]] and coverage_count(sim, field) <= 1:
                        would_break_coverage = True
                        break
                if would_break_coverage:
                    continue
            chosen = d
            break

        if chosen is None:
            continue  # aucun swap sur -- on ne force rien, ce manque reste non couvert

        nom_sortant = WORK_SUITABILITY_FULL.get(chosen["base_codename"], {}).get("display_name", chosen["codename"])
        is_dup = best_level_per_species.get(chosen["base_codename"]) is not chosen
        best_star_sortant = max(chosen["profil"].values()) if chosen["profil"] else 0
        swaps.append({
            "sortir": nom_sortant,
            "sortir_raison": "doublon (même espèce déjà en poste)" if is_dup else f"{best_star_sortant}★ max, aucune specialite forte",
            "entrer": manque["nom"],
            "entrer_etoiles": manque["etoiles"],
            "entrer_categorie": manque["categorie"],
            "entrer_nombre_possede": manque["nombre_possede"],
            "gain": manque["etoiles"] - best_star_sortant,
            "food_sortant": WORK_SUITABILITY_FULL.get(chosen["base_codename"], {}).get("food_amount"),
            "food_entrant": WORK_SUITABILITY_FULL.get(codename, {}).get("food_amount"),
        })
        if chosen.get("idx") is not None:
            swap_out_info[chosen["idx"]] = {
                "is_dup": is_dup,
                "best_star_sortant": best_star_sortant,
                "entrer": manque["nom"],
                "entrer_codename": codename,
                "entrer_etoiles": manque["etoiles"],
                "entrer_categorie": manque["categorie"],
                "entrer_nombre_possede": manque["nombre_possede"],
            }
        sim.remove(chosen)
        sim.append({
            "idx": None,
            "codename": codename,
            "base_codename": codename,
            "niveau": 0,
            "profil": WORK_SUITABILITY_FULL.get(codename, {}).get("work_suitability", {}),
            "protected": True,
        })
        pool_remaining[codename] = remaining - 1

    # meilleur(s) pick(s) possédé(s) attribues a un pal DEJA déployé (pour justifier "garder")
    best_pick_by_codename = {}
    for e in écarts:
        if e["deja_deploye"]:
            best_pick_by_codename.setdefault(e["codename"], []).append((e["categorie"], e["etoiles"]))

    def food_of(codename):
        return WORK_SUITABILITY_FULL.get(codename, {}).get("food_amount")

    postes = []
    for d in deployed:
        nom = WORK_SUITABILITY_FULL.get(d["base_codename"], {}).get("display_name", d["codename"])
        aptitudes = sorted(
            [(CATEGORY_FIELD_INV.get(k, k), v) for k, v in d["profil"].items() if v],
            key=lambda x: -x[1],
        )
        food_sortant = food_of(d["base_codename"])
        info = swap_out_info.get(d["idx"])
        if info:
            gain = info["entrer_etoiles"] - info["best_star_sortant"]
            if info["is_dup"]:
                raison = (
                    f"{nom} fait doublon : un autre exemplaire identique occupe déjà un poste "
                    f"avec le même profil ({info['best_star_sortant']}★ max) -- inutile d'en garder deux."
                )
            else:
                raison = (
                    f"{nom} plafonne a {info['best_star_sortant']}★ (aucune specialite marquante dans son profil)."
                )
            food_entrant = food_of(info["entrer_codename"])
            if food_sortant is not None and food_entrant is not None:
                delta = food_entrant - food_sortant
                if delta > 0:
                    food_txt = f" Cote nourriture : mange {delta} de plus par ration que {nom}."
                elif delta < 0:
                    food_txt = f" Cote nourriture : mange {-delta} de moins par ration que {nom}, en prime."
                else:
                    food_txt = " Consommation de nourriture identique."
            else:
                food_txt = ""
            justification = (
                f"{raison} {info['entrer']} apporte {info['entrer_etoiles']}★ en {info['entrer_categorie']} "
                f"(+{gain}★ sur ce poste par rapport a {nom}), et {info['entrer_nombre_possede']} exemplaire(s) "
                f"dorment dans le roster sans être déployés.{food_txt}"
            )
            postes.append({
                "nom": nom, "niveau": d["niveau"], "aptitudes": aptitudes, "food": food_sortant,
                "decision": "remplacer", "remplacant": info["entrer"], "justification": justification,
            })
        else:
            picks = best_pick_by_codename.get(d["base_codename"])
            if picks:
                cats_txt = ", ".join(f"{c} ({s}★)" for c, s in picks)
                justification = (
                    f"{nom} est déjà le meilleur choix possédé pour {cats_txt} -- aucune autre espèce "
                    f"du roster ne fait mieux sur ce(s) poste(s), donc aucun swap ne l'améliore."
                )
            else:
                best_star = max(d["profil"].values()) if d["profil"] else 0
                top_cat = CATEGORY_FIELD_INV.get(
                    max(d["profil"], key=d["profil"].get) if d["profil"] else "", "?"
                )
                justification = (
                    f"Profil generaliste ({best_star}★ max en {top_cat}) -- aucune espèce disponible en "
                    f"réserve ne depasse ce niveau sur ses points forts, il reste donc utile en poste."
                )
            postes.append({
                "nom": nom, "niveau": d["niveau"], "aptitudes": aptitudes, "food": food_sortant,
                "decision": "garder", "remplacant": None, "justification": justification,
            })

    batiments_out = []
    for catégorie in CATEGORY_FIELD:
        dispo = batiment_dispo(catégorie)
        if dispo is None:
            continue
        batiments_out.append({
            "categorie": catégorie,
            "dispo": dispo,
            "batiments": [f"{n} (x{building_counts[n]})" for n in BUILDINGS_BY_CATEGORY.get(catégorie, []) if building_counts.get(n, 0) > 0],
        })

    # meilleur(s) pal(s) par métier : TOUTES les espèces possédées a egalite du palier
    # d'etoiles maximum pour chaque catégorie (pas juste la première), avec statut déployé/non.
    meilleur_par_metier = []
    for catégorie, candidats in WORK_RECOMMENDATIONS.items():
        owned = []
        for codename, nom_affiche in candidats:
            variants = [codename, "BOSS_" + codename]
            nombre = sum(species_count.get(v, 0) for v in variants)
            if nombre:
                stars = WORK_SUITABILITY_FULL.get(codename, {}).get("work_suitability", {}).get(
                    CATEGORY_FIELD[catégorie], 0
                )
                owned.append((stars, nom_affiche, codename in deployed_base_codenames))
        if not owned:
            continue
        max_star = max(o[0] for o in owned)
        tied = [o for o in owned if o[0] == max_star]
        meilleur_par_metier.append({
            "categorie": catégorie,
            "etoiles": max_star,
            "noms": [(nom, dep) for _, nom, dep in tied[:2]],
            "extra": max(0, len(tied) - 2),
        })

    # Zoom Minage : TOUTES les espèces possédées avec une aptitude Minage > 0 (pas juste le
    # top), avec etoiles/nombre possédé/déployé/consommation de nourriture -- pour choisir
    # librement combien de mineurs dedier, pas juste le meilleur candidat unique.
    zoom_minage = []
    for codename, nom_affiche in WORK_RECOMMENDATIONS.get("Minage", []):
        variants = [codename, "BOSS_" + codename]
        nombre = sum(species_count.get(v, 0) for v in variants)
        if not nombre:
            continue
        stars = WORK_SUITABILITY_FULL.get(codename, {}).get("work_suitability", {}).get("mining", 0)
        if not stars:
            continue
        food = WORK_SUITABILITY_FULL.get(codename, {}).get("food_amount")
        nb_deployes = sum(1 for d in deployed if d["base_codename"] == codename)
        zoom_minage.append({
            "nom": nom_affiche, "etoiles": stars, "nombre_possede": nombre,
            "nb_deployes": nb_deployes, "food": food,
        })
    zoom_minage.sort(key=lambda z: (-z["etoiles"], z["food"] if z["food"] is not None else 999))

    # espèces possédées sans aucune donnée d'aptitude connue (variantes/DLC absents du DataTable)
    especes_non_couvertes = sum(
        1 for cn in species_count if resolve_species_profile(cn)[1] is None
    )

    nb_optimaux = sum(1 for p in postes if p["decision"] == "garder")
    nb_a_ameliorer = sum(1 for p in postes if p["decision"] == "remplacer")
    categories_batiment_manquant = sorted(set(bt["categorie"] for bt in batiments_out if not bt["dispo"]))

    # --- DETAIL PAR BASE (plusieurs bases possibles) ---
    STORAGE_OBJECTS = ["ItemChest", "ItemChest_02", "ItemChest_03", "GlobalPalStorage", "DimensionPalStorage"]
    bases_detail = []
    for i, binfo in enumerate(bases_info, 1):
        counts = building_counts_per_base.get(binfo["base_id"], {})
        cats_ok = [c for c in BUILDINGS_BY_CATEGORY if batiment_dispo(c, counts)]
        cats_manque = [c for c in BUILDINGS_BY_CATEGORY if not batiment_dispo(c, counts)]
        eggs = eggs_per_base.get(binfo["base_id"], [])
        eggs_named = []
        for sp in eggs:
            if not sp:
                eggs_named.append("espèce indeterminee")
                continue
            base_cn, profil = resolve_species_profile(sp)
            eggs_named.append(profil.get("display_name", sp) if profil else sp)
        stockage = {n: counts[n] for n in STORAGE_OBJECTS if counts.get(n, 0) > 0}
        bases_detail.append({
            "nom": f"Base {i}",
            "x": binfo["x"], "y": binfo["y"],
            "postes": binfo["deployed_count"],
            "batiments_ok": cats_ok,
            "batiments_manque": cats_manque,
            "oeufs": eggs_named,
            "stockage": stockage,
        })

    data["base_travail_actuel"] = {
        "nb_emplacements": len(deployed),
        "postes": postes,
        "swaps": swaps,
        "manques_sans_batiment": [
            {"categorie": e["categorie"], "nom": e["nom"], "etoiles": e["etoiles"], "nombre_possede": e["nombre_possede"]}
            for e in manques_sans_batiment
        ],
        "batiments": batiments_out,
        "meilleur_par_metier": meilleur_par_metier,
        "especes_non_couvertes": especes_non_couvertes,
        "nb_optimaux": nb_optimaux,
        "nb_a_ameliorer": nb_a_ameliorer,
        "categories_batiment_manquant": categories_batiment_manquant,
        "bases_detail": bases_detail,
        "zoom_minage": zoom_minage,
    }

    # --- CUISINE (recettes cuisinables avec les cultures + stations réellement possédées) ---
    # Recettes/ingredients/effets : source communautaire (switchbladegaming.com), pas le
    # DataTable brut du jeu -- moins rigoureux que le reste du dashboard, note dans l'UI.
    cultures_dispo = set()
    for crop_building, ingredient in CROP_TO_INGREDIENT.items():
        if building_counts.get(crop_building, 0) > 0:
            cultures_dispo.add(ingredient)
    # La Farine nécessite en plus un Moulin (FlourMill) pour transformer le ble
    if "Flour" in cultures_dispo and building_counts.get("FlourMill", 0) == 0:
        cultures_dispo.discard("Flour")

    stations_dispo = set(
        station for station, noms in STATION_BUILDINGS.items() if any(building_counts.get(n, 0) > 0 for n in noms)
    )

    recettes_out = []
    for nom, station, ingredients, san, effet in RECIPES:
        if station not in STATION_BUILDINGS:
            station_status = "inconnue"  # station non trackee (Cooking Pot/Grand Four) -- jamais "prete"
        elif station in stations_dispo:
            station_status = "ok"
        else:
            station_status = "manquante"
        ingredients_manquants_culture = [
            ing for ing in ingredients if ing in CROP_TO_INGREDIENT.values() and ing not in cultures_dispo
        ]
        ingredients_a_verifier = [ing for ing in ingredients if ing not in CROP_TO_INGREDIENT.values()]
        recettes_out.append({
            "nom": nom, "station": station, "ingredients": ingredients, "san": san, "effet": effet,
            "station_status": station_status,
            "ingredients_manquants_culture": ingredients_manquants_culture,
            "ingredients_a_verifier": ingredients_a_verifier,
            "prete": station_status == "ok" and not ingredients_manquants_culture,
        })

    recettes_out.sort(key=lambda r: (not r["prete"], r["station_status"] != "ok", r["effet"] is None, -r["san"]))

    # Meilleur cuisinier possédé : le niveau d'aptitude Allumage (Kindling) du Pal assigne
    # accelere réellement la cuisson (mecanique confirmee : palworld.wiki.gg/wiki/Kindling,
    # thepalprofessor.com) -- combine avec le palier de la station (Electric Kitchen la
    # plus rapide des stations confirmees ici).
    meilleur_cuisinier = None
    for codename, nom_affiche in WORK_RECOMMENDATIONS.get("Allumage", []):
        variants = [codename, "BOSS_" + codename]
        nombre = sum(species_count.get(v, 0) for v in variants)
        if nombre:
            stars = WORK_SUITABILITY_FULL.get(codename, {}).get("work_suitability", {}).get("emit_flame", 0)
            meilleur_cuisinier = {
                "nom": nom_affiche, "etoiles": stars, "nombre_possede": nombre,
                "deploye": codename in deployed_base_codenames,
            }
            break

    data["cuisine"] = {
        "cultures_dispo": sorted(cultures_dispo),
        "stations_dispo": sorted(stations_dispo),
        "recettes": recettes_out,
        "meilleur_cuisinier": meilleur_cuisinier,
    }

    # --- BASE / GUILDE ---
    bc = wsd["BaseCampSaveData"]["value"]
    module_types = []
    if bc:
        mm = bc[0]["value"].get("ModuleMap", {}).get("value", [])
        module_types = [m["key"].replace("EPalBaseCampModuleType::", "") for m in mm]
    groups = wsd["GroupSaveDataMap"]["value"]
    num_guilds = sum(1 for g in groups if g["value"]["GroupType"]["value"]["value"] == "EPalGroupType::Guild")
    guild_extra = wsd.get("GuildExtraSaveDataMap", {}).get("value", [])
    sup = wsd["SupplySaveData"]["value"]
    last_supply_guid = str(unwrap(sup.get("LastSupplyGuid"), "aucun"))

    data["base"] = {
        "nb_bases": len(bc),
        "modules": module_types,
        "guildes": num_guilds,
        "coffres_guilde": len(guild_extra),
        "dernier_largage": last_supply_guid[:8],
    }

    # --- QUICKNAV + PISTES D'AMELIORATION (vue d'ensemble) ---
    bta = data["base_travail_actuel"]
    connexions = [j["derniere_connexion_jours"] for j in data["joueurs"] if j.get("derniere_connexion_jours") is not None]
    if connexions:
        da = min(connexions)
        dernier_vu_txt = "en ce moment" if da < 0.04 else (f"il y a {da*24:.0f}h" if da < 1 else f"il y a {da:.0f}j")
    else:
        dernier_vu_txt = "inconnu"

    data["quicknav"] = {
        "joueurs_actifs": len(data["joueurs"]),
        "dernier_vu": dernier_vu_txt,
        "pals_total": data["pals"]["total"],
        "pals_especes": data["pals"]["especes"],
        "postes_a_optimiser": bta["nb_a_ameliorer"],
        "postes_total": bta["nb_emplacements"],
    }

    tips = []
    if bta["nb_a_ameliorer"]:
        tips.append(
            f"&#128295; <b>{bta['nb_a_ameliorer']}</b> poste(s) de travail sur {bta['nb_emplacements']} peuvent "
            f"être améliorés avec de meilleurs pals déjà dans la réserve. "
            f"<a class='tip-link' onclick=\"goToTab('tab-work')\">Voir &#8594;</a>"
        )
    if bta["categories_batiment_manquant"]:
        tips.append(
            f"&#127959;&#65039; Bâtiment(s) manquant(s) a la base : <b>{', '.join(bta['categories_batiment_manquant'])}</b> "
            f"-- des pals adaptes attendent sans poste. <a class='tip-link' onclick=\"goToTab('tab-work')\">Voir &#8594;</a>"
        )
    monde = data["monde"]
    sans_proprio = data["pals"]["repartition"].get("Sans propriétaire", 0)
    if sans_proprio:
        tips.append(
            f"&#128062; <b>{sans_proprio}</b> pals sans propriétaire trainent dans la réserve. "
            f"<a class='tip-link' onclick=\"goToTab('tab-pals')\">Voir &#8594;</a>"
        )
    if bta["especes_non_couvertes"]:
        tips.append(
            f"&#128202; <b>{bta['especes_non_couvertes']}</b> espèces possédées ne sont pas encore couvertes "
            f"par les recommandations de travail (variantes/DLC récentes absentes du DataTable). "
            f"<a class='tip-link' onclick=\"goToTab('tab-work')\">Voir &#8594;</a>"
        )
    combinaisons = data["elevage"]["combinaisons"]
    if combinaisons:
        top = combinaisons[0]
        tips.append(
            f"&#129370; Élevage : combinez <b>{top['parentA']}</b> + <b>{top['parentB']}</b> pour obtenir "
            f"<b>{top['nom']}</b>, une espèce qui vous manque. <a class='tip-link' onclick=\"goToTab('tab-breeding')\">Voir &#8594;</a>"
        )
    recettes_pretes = [r for r in data["cuisine"]["recettes"] if r["prete"]]
    if recettes_pretes:
        meilleure = max(recettes_pretes, key=lambda r: r["san"])
        tips.append(
            f"&#127859; Cuisine : <b>{len(recettes_pretes)}</b> plat(s) prets a cuisiner avec vos cultures et "
            f"stations actuelles, dont <b>{esc(DISH_NAME_FR.get(meilleure['nom'], meilleure['nom']))}</b> ({meilleure['san']} SAN"
            f"{' -- ' + esc(meilleure['effet']) if meilleure['effet'] else ''}). "
            f"<a class='tip-link' onclick=\"goToTab('tab-cuisine')\">Voir &#8594;</a>"
        )
    for p in data["palpedia"]["joueurs"]:
        if p["pct"] < 95:
            manquantes = len(p["manquantes"])
            tips.append(
                f"&#128220; Palpédia de <b>{esc(p['joueur'])}</b> : {p['pct']}% ({p['possedees']}/{p['total']}) -- "
                f"{manquantes} espèce(s) encore a capturer. <a class='tip-link' onclick=\"goToTab('tab-palpedia')\">Voir &#8594;</a>"
            )
    data["tips"] = tips

    data["genere_le"] = datetime.datetime.now().strftime("%d/%m/%Y a %H:%M")

    return data


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


BOOST_TAGS = [
    ("vitesse", "vitesse de travail"),
    ("attaque", "attaque"),
    ("defense", "défense"),
    ("faim", "faim ralentie"),
    ("sanite", "san ralentie"),
    ("epique", "qualité épique"),
    ("elevage", "élevage uniquement"),
]


def categorize_effect(effet):
    """Return the list of boost-type tags (slugs) présent in a recipe's effect text."""
    if not effet:
        return ["aucun"]
    low = effet.lower()
    tags = [slug for slug, needle in BOOST_TAGS if needle in low]
    return tags or ["aucun"]


def svg_line_chart(series_list, width=700, height=160, colors=None):
    """series_list: [(label, [(x_index, value), ...]), ...]. x_index shared across series."""
    colors = colors or ["#3498db", "#9b59b6", "#f1c40f", "#2ecc71", "#e67e22", "#e74c3c"]
    all_values = [v for _, pts in series_list for _, v in pts]
    if len(all_values) < 2:
        return "<p class='muted'>Pas encore assez de données pour un graphique (revenez dans quelques heures).</p>"
    vmin, vmax = min(all_values), max(all_values)
    if vmin == vmax:
        vmin, vmax = vmin - 1, vmax + 1
    max_x = max((x for _, pts in series_list for x, _ in pts), default=1)
    pad = 12

    def x_of(i):
        return pad + (width - 2 * pad) * (i / max(1, max_x))

    def y_of(v):
        return height - pad - (height - 2 * pad) * (v - vmin) / (vmax - vmin)

    paths = []
    for idx, (label, pts) in enumerate(series_list):
        color = colors[idx % len(colors)]
        if not pts:
            continue
        points = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in pts)
        paths.append(f"<polyline points='{points}' fill='none' stroke='{color}' stroke-width='2' />")
        lx, lv = pts[-1]
        paths.append(f"<circle cx='{x_of(lx):.1f}' cy='{y_of(lv):.1f}' r='3' fill='{color}' />")

    legend = "".join(
        f"<span style='color:{colors[i % len(colors)]}'>&#9679;</span> {esc(label)} &nbsp; "
        for i, (label, _) in enumerate(series_list)
    )
    svg = f"<svg viewBox='0 0 {width} {height}' style='width:100%; height:{height}px'>{''.join(paths)}</svg>"
    return f"<div>{svg}<div class='muted' style='font-size:0.78rem; margin-top:4px'>{legend}</div></div>"


def render_html(data):
    m = data["monde"]
    b = data["base"]

    player_cards = ""
    for j in data["joueurs"]:
        stats_rows = "".join(
            f"<tr><td>{esc(n)}</td><td>+{p}</td></tr>" for n, p in j.get("stats", [])
        ) or "<tr><td colspan='2' class='muted'>aucun point dépense</td></tr>"

        if j.get("derniere_connexion_jours") is not None:
            da = j["derniere_connexion_jours"]
            conn_txt = "en ce moment" if da < 0.04 else (f"il y a {da*24:.0f}h" if da < 1 else f"il y a {da:.0f}j")
        else:
            conn_txt = "inconnue"

        boss_tour = ", ".join(j.get("boss_tour", [])) or "aucun"

        player_cards += f"""
        <div class="card player-card">
          <h3>&#128100; {esc(j['nom'])}</h3>
          <div class="stat-row">
            <div><span class="label">Niveau</span><span class="value">{j['niveau']}</span><span class="sub">{j['xp']:,} XP</span></div>
            <div><span class="label">Faim</span><span class="value">{j['faim']:.0f}<span class="unit">/100</span></span></div>
            <div><span class="label">Bouclier</span><span class="value">{j['bouclier']:.0f}</span></div>
          </div>
          <div class="meta-row">
            <span>&#128337; {conn_txt}</span>
            <span>&#127918; {esc(j.get('plateforme','?'))}</span>
            <span>&#127775; {j.get('points_tech_boss','?')} pts boss</span>
            <span>&#9989; {j.get('quetes_completees','?')} quêtes</span>
            <span>&#128736; {j.get('recettes_debloquees','?')} recettes</span>
            <span>&#9876;&#65039; {j.get('camps_conquis','?')} camps conquis (total)</span>
          </div>
          <div class="boss-row">
            <span>&#128081; Boss de tour : <b>{len(j.get('boss_tour', []))}</b> -- {esc(boss_tour)}</span>
            <span>&#128128; Boss du monde : <b>{j.get('boss_monde','?')}</b></span>
            <span>&#128204; Quete en cours : {esc(j.get('quete_en_cours','?'))}</span>
          </div>
          <table class="stat-table"><tbody>{stats_rows}</tbody></table>
        </div>"""

    pals = data["pals"]
    owner_rows = "".join(f"<li>{esc(k)} : <b>{v}</b></li>" for k, v in pals["repartition"].items())
    top_niveaux = "".join(
        f"<li>{i+1}. {esc(p['espece'])} <span class='muted'>(lvl {p['niveau']})</span></li>"
        for i, p in enumerate(pals["top_niveaux"])
    )
    top_affection = "".join(
        f"<li>{i+1}. {esc(p['espece'])} <span class='muted'>({p['affection']:,})</span></li>"
        for i, p in enumerate(pals["top_affection"])
    )
    top_iv = ""
    for i, p in enumerate(pals["top_iv"]):
        passifs = (
            f"<div class='passifs'>{esc(', '.join(p['passifs']))}</div>" if p["passifs"] else ""
        )
        top_iv += f"""<li><b>{esc(p['espece'])}</b> -- &#10084;&#65039; {p['hp']}% / &#9876;&#65039; {p['att']}% / &#128737;&#65039; {p['def']}%{passifs}</li>"""

    equipe_terrain = data.get("equipe_terrain", {})
    equipe_rows = ""
    for membre in equipe_terrain.get("membres", []):
        if membre["role"] == "monture":
            raison = (
                f"Monture la plus rapide possédée (vitesse {membre['ride_sprint_speed']:.0f}) -- "
                f"{esc(membre['partner_skill'])}" if membre.get("partner_skill") else "Monture la plus rapide possédée."
            )
            badge = "&#127943; MONTURE"
        else:
            raison = (
                f"Puissance brute {membre['power']} (mêlée+distance) parmi les plus fortes possédées, "
                f"élément {esc('/'.join(membre['elements']))}."
            )
            badge = "&#9876;&#65039; COMBAT"
        passifs_txt = (
            f"<div class='muted' style='font-size:0.8rem; margin-top:2px'>Passifs : {esc(', '.join(membre['passifs']))}</div>"
            if membre.get("passifs") else ""
        )
        equipe_rows += f"""<div style='padding:10px 0; border-bottom:1px solid var(--border)'>
          <div><b>{esc(membre['nom'])}</b> <span class='muted'>(lvl {membre['level']}, IV {membre['iv']:.0f}%)</span> &nbsp; <span style='font-size:0.75rem; color:var(--muted)'>{badge}</span></div>
          <div class='muted' style='font-size:0.85rem; margin-top:3px'>{raison}</div>
          {passifs_txt}
        </div>"""

    elements_non_couverts = equipe_terrain.get("elements_non_couverts", [])
    elements_txt = (
        f"<p class='muted' style='font-size:0.82rem'>&#9888;&#65039; Éléments non couverts par le roster possédé : {esc(', '.join(elements_non_couverts))}</p>"
        if elements_non_couverts else
        "<p class='muted' style='font-size:0.82rem'>&#9989; Tous les éléments du jeu sont couverts par le roster possédé.</p>"
    )

    travail_base = ""
    for cat in data.get("travail_base", []):
        pals_txt = ", ".join(
            f"<b>{esc(p['nom'])}</b> (x{p['nombre']}, lvl max {p['niveau_max']})" for p in cat["pals"]
        )
        travail_base += f"<li><b>{esc(cat['categorie'])}</b> : {pals_txt}</li>"

    bta = data.get("base_travail_actuel", {})
    postes_rows = ""
    for p in bta.get("postes", []):
        apt_txt = ", ".join(f"{esc(c)} {v}&#9733;" for c, v in p["aptitudes"]) or "aucune aptitude notable"
        food_txt = f" &nbsp; <span class='muted'>&#127831; {p['food']}/ration</span>" if p.get("food") is not None else ""
        if p["decision"] == "remplacer":
            badge = f"<span style='color:#e74c3c'>&#128260; remplacer par {esc(p['remplacant'])}</span>"
        else:
            badge = "<span style='color:#2ecc71'>&#9989; garder</span>"
        postes_rows += f"""<div style='padding:10px 0; border-bottom:1px solid var(--border)'>
          <div><b>{esc(p['nom'])}</b> <span class='muted'>(lvl {p['niveau']})</span> -- {apt_txt}{food_txt} &nbsp; {badge}</div>
          <div class='muted' style='font-size:0.85rem; margin-top:3px'>{esc(p['justification'])}</div>
        </div>"""

    swaps_rows = ""
    for s in bta.get("swaps", []):
        food_s, food_e = s.get("food_sortant"), s.get("food_entrant")
        if food_s is not None and food_e is not None:
            delta = food_e - food_s
            food_swap_txt = f", {'+' if delta>0 else ''}{delta} nourriture/ration" if delta else ", même conso. nourriture"
        else:
            food_swap_txt = ""
        swaps_rows += f"""<tr>
          <td>&#10060; {esc(s['sortir'])}<div class='muted' style='font-size:0.75rem'>{esc(s['sortir_raison'])}</div></td>
          <td>&#8594;</td>
          <td>&#9989; {esc(s['entrer'])}<div class='muted' style='font-size:0.75rem'>{esc(s['entrer_categorie'])} {s['entrer_etoiles']}&#9733; -- x{s['entrer_nombre_possede']} possédé(s), non déployé{food_swap_txt}</div></td>
        </tr>"""

    batiments_rows = ""
    for bt in bta.get("batiments", []):
        icone = "&#9989;" if bt["dispo"] else "&#10060;"
        detail = ", ".join(bt["batiments"]) if bt["batiments"] else "aucune structure correspondante trouvee a la base"
        batiments_rows += f"<li>{icone} <b>{esc(bt['categorie'])}</b> -- {esc(detail)}</li>"

    manques_sans_batiment_txt = ""
    for e in bta.get("manques_sans_batiment", []):
        manques_sans_batiment_txt += (
            f"<li><b>{esc(e['categorie'])}</b> : {esc(e['nom'])} ({e['etoiles']}&#9733;, "
            f"x{e['nombre_possede']} possédé(s)) -- inutile de le deployer tant qu'aucune structure "
            f"correspondante n'est construite</li>"
        )

    # "A faire" : swaps consolides (N x même sortant -> même entrant regroupes)
    swap_groups = {}
    swap_order = []
    for s in bta.get("swaps", []):
        key = (
            s["sortir"], s["entrer"], s["entrer_categorie"], s["entrer_etoiles"], s["entrer_nombre_possede"],
            s["gain"], s.get("food_sortant"), s.get("food_entrant"),
        )
        if key not in swap_groups:
            swap_groups[key] = 0
            swap_order.append(key)
        swap_groups[key] += 1

    advice_swaps = ""
    for key in swap_order:
        sortir, entrer, cat, etoiles, dispo, gain, food_s, food_e = key
        count = swap_groups[key]
        prefix = f"{count}&times; " if count > 1 else ""
        if food_s is not None and food_e is not None:
            delta = food_e - food_s
            food_txt = f", {'+' if delta>0 else ''}{delta} nourriture/ration" if delta else ", même conso. nourriture"
        else:
            food_txt = ""
        advice_swaps += (
            f"<li><span class='swap-x'>&#10060;</span> {prefix}<b>{esc(sortir)}</b> &nbsp;&#8594;&nbsp; "
            f"<span class='swap-ok'>&#9989; {esc(entrer)}</span>"
            f"<span class='muted'> -- {esc(cat)} {etoiles}&#9733; (+{gain}&#9733;), {dispo} dispo sans emploi{food_txt}</span></li>"
        )

    deja_optimaux_noms = sorted(set(p["nom"] for p in bta.get("postes", []) if p["decision"] == "garder"))
    deja_optimaux_txt = ", ".join(f"<b>{esc(n)}</b>" for n in deja_optimaux_noms)

    # Recap compact "ce qu'on a" : un poste regroupe par (espèce, aptitudes, decision) au lieu
    # d'une carte + un paragraphe par exemplaire individuel -- vue courte, pas de doublons verbeux.
    recap_groupes = {}
    recap_order = []
    for p in bta.get("postes", []):
        apt_txt = ", ".join(f"{c} {v}&#9733;" for c, v in p["aptitudes"][:2])
        if len(p["aptitudes"]) > 2:
            apt_txt += f" +{len(p['aptitudes']) - 2}"
        key = (p["nom"], apt_txt or "aucune aptitude notable", p["decision"], p.get("remplacant"))
        if key not in recap_groupes:
            recap_groupes[key] = 0
            recap_order.append(key)
        recap_groupes[key] += 1

    recap_rows = ""
    for key in recap_order:
        nom, apt_txt, decision, remplaçant = key
        count = recap_groupes[key]
        prefix = f"{count}&times; " if count > 1 else ""
        badge = "<span style='color:#2ecc71'>&#9989;</span>" if decision == "garder" else f"<span style='color:#e74c3c'>&#128260; &#8594; {esc(remplaçant)}</span>"
        recap_rows += f"<li>{prefix}<b>{esc(nom)}</b> -- {apt_txt} &nbsp; {badge}</li>"

    bases_recap_txt = " &middot; ".join(
        f"{esc(bd['nom'])} ({bd['postes']} poste(s))" for bd in bta.get("bases_detail", [])
    ) or "aucune base detectee"

    apt_grid_rows = ""
    for e in bta.get("meilleur_par_metier", []):
        stars = e["etoiles"]
        color = "var(--gold)" if stars >= 4 else ("var(--orange)" if stars == 3 else ("var(--blue)" if stars == 2 else "var(--muted)"))
        star_txt = "&#9733;" * stars if stars > 0 else "&#9733;"
        noms_txt = ", ".join(
            f"<b>{esc(n)}</b>" + (" <span class='pick-idle'>&#9679;</span>" if not dep else "")
            for n, dep in e["noms"]
        )
        if e["extra"]:
            noms_txt += f" <span class='muted'>+{e['extra']}</span>"
        apt_grid_rows += (
            f"<div class='apt-row'><span class='apt-label'>{esc(e['categorie'])}</span>"
            f"<span class='star-badge' style='color:{color}'>{star_txt}</span>"
            f"<span class='apt-names'>{noms_txt}</span></div>"
        )

    batiments_ok = [bt["categorie"] for bt in bta.get("batiments", []) if bt["dispo"]]
    batiments_manque = [bt["categorie"] for bt in bta.get("batiments", []) if not bt["dispo"]]
    batiments_inline = ""
    if batiments_ok:
        batiments_inline += f"<span class='ok-inline'>&#9989; {esc(', '.join(batiments_ok))}</span>"
    if batiments_manque:
        batiments_inline += f" &nbsp; <span class='bad-inline'>&#10060; manque : {esc(', '.join(batiments_manque))}</span>"

    manques_inline = ""
    if bta.get("manques_sans_batiment"):
        parts = [f"{e['categorie']} ({e['nom']} {e['etoiles']}★, x{e['nombre_possede']})" for e in bta["manques_sans_batiment"]]
        manques_inline = f"<p style='margin:6px 0'><span class='muted'>En réserve mais inutiles sans structure : {esc(', '.join(parts))}</span></p>"

    tips_rows = "".join(f"<li>{t}</li>" for t in data.get("tips", []))
    qn = data.get("quicknav", {})

    bases_detail_rows = ""
    for bd in bta.get("bases_detail", []):
        ok_txt = f"<span class='ok-inline'>&#9989; {esc(', '.join(bd['batiments_ok']))}</span>" if bd["batiments_ok"] else ""
        manque_txt = f"<span class='bad-inline'>&#10060; manque : {esc(', '.join(bd['batiments_manque']))}</span>" if bd["batiments_manque"] else ""
        oeufs_txt = (
            f"<div class='muted' style='font-size:0.82rem; margin-top:4px'>&#129370; {len(bd['oeufs'])} oeuf(s) en incubation : {esc(', '.join(bd['oeufs']))}</div>"
            if bd["oeufs"] else ""
        )
        stockage_txt = (
            ", ".join(f"{esc(n)} (x{c})" for n, c in bd["stockage"].items())
            if bd["stockage"] else "aucun coffre recense"
        )
        bases_detail_rows += f"""<div style='padding:10px 0; border-bottom:1px solid var(--border)'>
          <div><b>{esc(bd['nom'])}</b> <span class='muted'>(x={bd['x']}, y={bd['y']}) -- {bd['postes']} poste(s) de travail assignes</span></div>
          <div style='margin-top:4px'>{ok_txt} {manque_txt}</div>
          <div class='muted' style='font-size:0.82rem; margin-top:4px'>&#128230; Stockage : {stockage_txt}</div>
          {oeufs_txt}
        </div>"""

    zoom_minage_rows = ""
    for z in bta.get("zoom_minage", []):
        statut = f"<span style='color:#2ecc71'>&#9989; {z['nb_deployes']} déployé(s)</span>" if z["nb_deployes"] else "<span class='muted'>en réserve, pas déployé</span>"
        food_txt = f"&#127831; {z['food']}/ration" if z["food"] is not None else "conso. inconnue"
        td_style = "padding:7px 10px; border-bottom:1px solid var(--border)"
        zoom_minage_rows += f"""<tr>
          <td style="{td_style}"><b>{esc(z['nom'])}</b></td>
          <td style="{td_style}">{z['etoiles']}&#9733;</td>
          <td style="{td_style}">x{z['nombre_possede']} possédé(s)</td>
          <td style="{td_style}">{food_txt}</td>
          <td style="{td_style}">{statut}</td>
        </tr>"""

    history = data.get("history", [])
    pals_series = [(i, e["pals_total"]) for i, e in enumerate(history) if "pals_total" in e]
    joueur_series = {}
    for i, e in enumerate(history):
        for j in e.get("joueurs", []):
            joueur_series.setdefault(j["nom"], []).append((i, j["niveau"]))
    niveau_series = [(nom, pts) for nom, pts in joueur_series.items()]
    chart_pals = svg_line_chart([("Pals total", pals_series)])
    chart_niveaux = svg_line_chart(niveau_series)
    history_range_txt = (
        f"{esc(history[0]['t'])} &#8594; {esc(history[-1]['t'])} ({len(history)} points)"
        if len(history) >= 2 else "historique en cours de constitution"
    )

    élevage = data.get("elevage", {})
    breed_cards = ""
    for combo in élevage.get("combinaisons", []):
        breed_cards += f"""<div class="breed-card" data-nom="{esc(combo['nom'])}" data-rang="{combo['target_rank']}" data-ecart="{combo['dist']}">
          <div class="breed-egg">&#129370;</div>
          <div class="breed-result">{esc(combo['nom'])}</div>
          <div class="breed-parents">
            <span class="breed-parent">{esc(combo['parentA'])}</span>
            <span class="breed-plus">+</span>
            <span class="breed-parent">{esc(combo['parentB'])}</span>
          </div>
          <div class="breed-rank">Rang combi cible {combo['target_rank']} (ecart {combo['dist']})</div>
        </div>"""

    cuisine = data.get("cuisine", {})
    BOOST_LABELS = {
        "vitesse": "&#9889; Vitesse de travail", "attaque": "&#9876;&#65039; Attaque",
        "defense": "&#128737;&#65039; Défense", "faim": "&#127831; Faim ralentie",
        "sanite": "&#128516; SAN ralentie", "epique": "&#127775; Épique",
        "elevage": "&#129370; Élevage", "aucun": "&#10062; Aucun effet",
    }
    recipe_cards = ""
    boosts_present = set()
    for r in cuisine.get("recettes", []):
        tags = categorize_effect(r["effet"])
        boosts_present.update(tags)
        ing_spans = ""
        for ing, qty in r["ingredients"].items():
            css_cls = ""
            if ing in r["ingredients_manquants_culture"]:
                css_cls = " missing"
            elif ing in r["ingredients_a_verifier"]:
                css_cls = " unverified"
            ing_fr = INGREDIENT_NAME_FR.get(ing, ing)
            ing_spans += f"<span class='{css_cls.strip()}' title='{esc(ing)}'>{qty}&times; {esc(ing_fr)}</span>"
        effet_txt = esc(r["effet"]) if r["effet"] else "aucun effet special"
        card_cls = "recipe-card" if r["prete"] else "recipe-card blocked"
        blocage = ""
        if r["station_status"] == "inconnue":
            blocage = f"<div style='font-size:0.78rem; margin-top:8px; color:var(--orange)'>&#10067; station {esc(r['station'])} non trackee -- a vérifier en jeu</div>"
        elif r["station_status"] == "manquante":
            blocage = f"<div class='muted' style='font-size:0.78rem; margin-top:8px'>&#10060; station {esc(r['station'])} non construite</div>"
        elif r["ingredients_manquants_culture"]:
            blocage = f"<div class='muted' style='font-size:0.78rem; margin-top:8px'>&#10060; culture manquante : {esc(', '.join(r['ingredients_manquants_culture']))}</div>"
        nom_fr = DISH_NAME_FR.get(r["nom"], r["nom"])
        recipe_cards += f"""<div class="{card_cls}" data-boosts="{' '.join(tags)}">
          <div class="recipe-name" title="{esc(r['nom'])}">{esc(nom_fr)}</div>
          <div class="recipe-station">{esc(r['station'])}</div>
          <div class="recipe-ing">{ing_spans}</div>
          <div class="recipe-effect"><span class="san">+{r['san']} SAN</span> -- {effet_txt}</div>
          {blocage}
        </div>"""

    boost_filter_order = [slug for slug, _ in BOOST_TAGS] + ["aucun"]
    boost_filters = "<button class='filter-btn active' data-filter='tous' onclick='filterRecipes(this)'>Tous</button>"
    for slug in boost_filter_order:
        if slug in boosts_present:
            boost_filters += f"<button class='filter-btn' data-filter='{slug}' onclick='filterRecipes(this)'>{BOOST_LABELS[slug]}</button>"

    cultures_txt = ", ".join(cuisine.get("cultures_dispo", [])) or "aucune"
    stations_txt = ", ".join(cuisine.get("stations_dispo", [])) or "aucune"
    nb_prete = sum(1 for r in cuisine.get("recettes", []) if r["prete"])

    mc = cuisine.get("meilleur_cuisinier")
    if mc:
        statut_mc = "<span style='color:#2ecc71'>&#9989; déjà dans l'equipe de la base</span>" if mc["deploye"] else "<span class='muted'>en réserve, pas encore affecte</span>"
        meilleur_cuisinier_txt = (
            f"<p class='muted' style='font-size:0.85rem'>&#128293; Meilleur cuisinier possédé : "
            f"<b>{esc(mc['nom'])}</b> ({mc['etoiles']}&#9733; Allumage, x{mc['nombre_possede']} possédé(s)) -- "
            f"un fort Allumage accelere réellement la cuisson. {statut_mc}</p>"
        )
    else:
        meilleur_cuisinier_txt = ""

    palpedia_players = data.get("palpedia", {}).get("joueurs", [])
    palpedia_tabs_html = ""
    palpedia_panels_html = ""
    for idx, p in enumerate(palpedia_players):
        slug = f"pp{idx}"
        active = " active" if idx == 0 else ""
        palpedia_tabs_html += (
            f'<button class="filter-btn{active}" data-player="{slug}" onclick="palpediaShowPlayer(this)">'
            f"&#128100; {esc(p['joueur'])} ({p['pct']}%)</button>"
        )
        def _pal_card(m, status):
            return f"""<div class="palpedia-pal-card" data-status="{status}" onclick="showPalCard('{esc(m['codename'])}')">
              <img class="palpedia-pal-icon" src="{esc(pal_icon_url(m['codename']))}" loading="lazy" alt="{esc(m['nom'])}" onerror="palIconError(this)">
              <span class="palpedia-pal-name">{esc(m['nom'])}</span>
            </div>"""

        pal_cards_html = "".join(_pal_card(m, "missing") for m in p["manquantes"])
        pal_cards_html += "".join(_pal_card(m, "owned") for m in p["possedees_liste"])
        panel_style = "" if idx == 0 else "display:none"
        status_buttons = (
            '<button class="filter-btn active" data-status="missing" onclick="palpediaSetStatus(this, \'' + slug + '\')">Non capturé</button>'
            '<button class="filter-btn" data-status="owned" onclick="palpediaSetStatus(this, \'' + slug + '\')">Capturé</button>'
        )
        page_size_buttons = "".join(
            f'<button class="filter-btn{" active" if size == 20 else ""}" data-size="{size}" onclick="palpediaSetPageSize(this, \'{slug}\')">{label}</button>'
            for size, label in [(20, "20"), (50, "50"), (100, "100"), (9999, "Tout")]
        )
        palpedia_panels_html += f"""<div class="palpedia-player-panel" data-player="{slug}" style="{panel_style}">
          <div class="palpedia-bar-track"><div class="palpedia-bar-fill" style="width:{p['pct']}%"></div></div>
          <div class="palpedia-count">{p['possedees']} / {p['total']} espèces possédées -- {len(p['manquantes'])} a capturer (clique sur une carte pour voir ses stats)</div>
          <div class="filter-row" style="margin-top:14px">
            {status_buttons}
          </div>
          <div class="filter-row" style="margin-top:8px">
            <input type="text" class="kanban-input" style="max-width:260px" placeholder="&#128269; Rechercher un pal..." oninput="palpediaSetQuery(this, '{slug}')">
          </div>
          <div class="filter-row" style="margin-top:8px">
            <span class="muted" style="font-size:0.8rem; align-self:center">Cartes par page :</span>
            {page_size_buttons}
          </div>
          <div class="palpedia-card-grid" id="palpedia-grid-{slug}">{pal_cards_html}</div>
          <p class="muted" id="palpedia-empty-{slug}" style="display:none">Aucune espèce dans cette categorie.</p>
          <div class="pagination-row">
            <button class="filter-btn" onclick="palpediaPage('{slug}', -1)">&#8592; Précédent</button>
            <span id="palpedia-pageinfo-{slug}" class="muted" style="font-size:0.82rem"></span>
            <button class="filter-btn" onclick="palpediaPage('{slug}', 1)">Suivant &#8594;</button>
          </div>
        </div>"""

    pal_data_json = json.dumps(PAL_CARD_DATA, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Palworld -- Tableau de bord</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0c11; --bg-soft: #10131a; --card: #141822; --card-soft: #10131b;
    --border: #242a38; --border-soft: #1b2029;
    --text: #eef0f5; --text-dim: #c7cdda; --muted: #8b93a8;
    --blue: #5b9cf0; --purple: #b487ea; --gold: #f0b93d; --green: #4ed195; --orange: #f0904f;
    --red: #ef5f6b; --brand: #f0a838;
    --radius: 14px; --radius-sm: 10px;
    --shadow: 0 1px 2px rgba(0,0,0,.5), 0 12px 28px -14px rgba(0,0,0,.65);
    --font-display: "Sora", "Segoe UI", system-ui, sans-serif;
    --font-body: "Manrope", "Segoe UI", system-ui, sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--font-body); line-height: 1.55; font-size: 15px;
  }}
  .layout {{ max-width: 1300px; margin: 0 auto; padding: 24px 24px 48px; display: flex; align-items: flex-start; gap: 24px; }}
  .page {{ flex: 1; min-width: 0; }}
  h1, h2, h3, h4 {{ font-family: var(--font-display); margin-top: 0; text-wrap: balance; letter-spacing: -0.01em; }}
  .value, .kpi .value, .stat-row .value, .breed-result, .palpedia-pct, .recipe-effect .san {{
    font-family: var(--font-display); font-variant-numeric: tabular-nums;
  }}
  a {{ color: var(--blue); }}

  /* ---- header ---- */
  .site-header {{
    background: linear-gradient(180deg, var(--bg-soft), var(--bg) 85%);
    border-bottom: 1px solid var(--border-soft); padding: 28px 24px 20px;
  }}
  .site-header-inner {{ max-width: 1240px; margin: 0 auto; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; flex-wrap: wrap; }}
  .brand {{ display: flex; align-items: center; gap: 16px; }}
  .brand-mark {{
    font-size: 1.7rem; width: 52px; height: 52px; border-radius: 14px; flex-shrink: 0;
    background: linear-gradient(145deg, var(--brand), #c9791f);
    display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow);
  }}
  .brand h1 {{ font-size: 1.5rem; font-weight: 800; margin: 0; }}
  .brand .tagline {{ color: var(--muted); font-size: 0.88rem; margin: 4px 0 0; max-width: 46ch; }}
  .updated-pill {{
    background: var(--card); border: 1px solid var(--border); color: var(--text-dim);
    padding: 8px 16px; border-radius: 999px; font-size: 0.82rem; white-space: nowrap;
    display: flex; align-items: center; gap: 8px;
  }}
  .updated-pill .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 3px rgba(78,209,149,.18); }}

  /* ---- tab nav (sidebar verticale a gauche) ---- */
  .tabs {{
    position: sticky; top: 24px; z-index: 10; display: flex; flex-direction: column; gap: 4px;
    flex-shrink: 0; width: 210px;
    background: var(--card); border: 1px solid var(--border-soft); border-radius: var(--radius);
    padding: 10px; box-shadow: var(--shadow);
  }}
  .tab-btn {{
    flex-shrink: 0; display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
    background: transparent; border: 1px solid transparent; color: var(--muted);
    padding: 10px 14px; border-radius: 10px; font-size: 0.88rem; font-weight: 600;
    font-family: var(--font-body); cursor: pointer; transition: color .15s, border-color .15s, background .15s;
  }}
  .tab-btn:hover {{ color: var(--text); background: var(--card-soft); }}
  .tab-btn.active {{ color: var(--bg); background: var(--tab-accent, var(--blue)); border-color: var(--tab-accent, var(--blue)); }}
  .tab-section-label {{
    font-size: 0.66rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 700;
    color: var(--muted); margin: 10px 10px 0; padding-top: 8px; border-top: 1px solid var(--border-soft);
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; animation: fadeIn .2s ease; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @media (prefers-reduced-motion: reduce) {{ .tab-panel.active {{ animation: none; }} html {{ scroll-behavior: auto; }} }}

  /* ---- mobile ---- */
  @media (max-width: 640px) {{
    .layout {{ padding: 0 14px 32px; flex-direction: column; gap: 14px; }}
    .site-header {{ padding: 20px 14px 16px; }}
    .brand-mark {{ width: 42px; height: 42px; font-size: 1.4rem; border-radius: 12px; }}
    .brand h1 {{ font-size: 1.15rem; }}
    .brand .tagline {{ font-size: 0.8rem; }}
    .tabs {{
      position: sticky; top: 0; flex-direction: row; width: auto; flex-wrap: nowrap;
      overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none;
      margin: 0 -14px; padding: 10px 14px; border-radius: 0; border-left: none; border-right: none;
      background: rgba(10,12,17,.92); backdrop-filter: blur(8px);
    }}
    .tabs::-webkit-scrollbar {{ display: none; }}
    .tab-btn {{ width: auto; padding: 8px 13px; font-size: 0.82rem; }}
    .tab-section-label {{ display: none; }}
  }}

  /* ---- kanban ---- */
  .kanban-add-row {{ display: flex; gap: 8px; margin: 16px 0; }}
  .kanban-input {{
    flex: 1; background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: 8px;
    padding: 9px 12px; color: var(--text); font-family: var(--font-body); font-size: 0.9rem;
  }}
  .kanban-input:focus {{ outline: none; border-color: var(--orange); }}
  .kanban-board {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
  .kanban-column {{
    background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: var(--radius);
    padding: 12px; min-height: 120px;
  }}
  .kanban-column.drag-over {{ border-color: var(--orange); }}
  .kanban-col-title {{ display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; margin: 0 0 10px 0; }}
  .kanban-count {{ background: var(--bg); border-radius: 999px; padding: 2px 9px; font-size: 0.75rem; color: var(--muted); }}
  .kanban-col-body {{ display: flex; flex-direction: column; gap: 8px; min-height: 60px; }}
  .kanban-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; cursor: grab; }}
  .kanban-card:active {{ cursor: grabbing; }}
  .kanban-card.dragging {{ opacity: 0.4; }}
  .kanban-card-title {{ font-size: 0.88rem; font-weight: 600; overflow-wrap: break-word; }}
  .kanban-card-desc {{ font-size: 0.78rem; color: var(--muted); margin-top: 4px; overflow-wrap: break-word; }}
  .kanban-card-actions {{ display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }}
  .kanban-card-move {{ display: flex; gap: 4px; }}
  .kanban-card-move button, .kanban-card-del {{
    background: none; border: 1px solid var(--border-soft); color: var(--muted); border-radius: 6px;
    padding: 2px 7px; font-size: 0.75rem; cursor: pointer; font-family: var(--font-body);
  }}
  .kanban-card-move button:hover, .kanban-card-del:hover {{ color: var(--text); border-color: var(--orange); }}
  @media (max-width: 640px) {{ .kanban-board {{ grid-template-columns: 1fr; }} }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
  .grid-2col {{ grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--blue);
    border-radius: var(--radius); padding: 20px 22px; box-shadow: var(--shadow);
  }}
  .card.monde {{ border-left-color: var(--blue); }}
  .card.player-card {{ border-left-color: var(--purple); grid-column: span 1; }}
  .card.pals {{ border-left-color: var(--gold); }}
  .card.work {{ border-left-color: var(--orange); grid-column: 1 / -1; }}
  .card.basecard {{ border-left-color: var(--green); grid-column: 1 / -1; }}
  h2 {{ font-size: 1.15rem; font-weight: 700; }}
  h3 {{ font-size: 1rem; font-weight: 700; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-top: 12px; }}
  .kpi {{ background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: var(--radius-sm); padding: 12px 14px; }}
  .kpi .label {{ display: block; color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }}
  .kpi .value {{ font-size: 1.5rem; font-weight: 700; }}
  .stat-row {{ display: flex; gap: 20px; margin: 10px 0; flex-wrap: wrap; }}
  .stat-row .label {{ display: block; color: var(--muted); font-size: 0.72rem; text-transform: uppercase; font-weight: 600; }}
  .stat-row .value {{ font-size: 1.3rem; font-weight: 700; }}
  .stat-row .unit {{ font-size: 0.9rem; color: var(--muted); }}
  .stat-row .sub {{ display: block; font-size: 0.75rem; color: var(--muted); }}
  .meta-row, .boss-row {{ display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.85rem; color: var(--muted); margin: 8px 0; }}
  .boss-row {{ color: var(--text-dim); }}
  .stat-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.85rem; }}
  .stat-table td {{ padding: 5px 6px; border-bottom: 1px solid var(--border-soft); }}
  .stat-table td:last-child {{ text-align: right; color: var(--gold); font-weight: 700; font-variant-numeric: tabular-nums; }}
  .muted {{ color: var(--muted); }}
  .cols3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-top: 12px; }}
  ul {{ margin: 6px 0; padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  .passifs {{ font-style: italic; color: var(--muted); font-size: 0.8rem; margin-left: 14px; }}
  .modules {{ color: var(--muted); font-size: 0.88rem; }}
  .swap-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  .swap-table td {{ padding: 10px; border-bottom: 1px solid var(--border-soft); vertical-align: top; font-size: 0.9rem; }}
  .swap-table td:nth-child(2) {{ text-align: center; color: var(--muted); width: 30px; }}
  .subhead {{ margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--border-soft); }}
  .advice-list {{ list-style: none; margin: 10px 0; padding: 0; }}
  .advice-list li {{
    background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
    padding: 10px 14px; margin-bottom: 6px; font-size: 0.88rem;
  }}
  .advice-list .swap-x {{ opacity: 0.7; }}
  .advice-list .swap-ok {{ color: var(--green); font-weight: 700; }}
  .apt-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 4px 20px; margin-top: 10px;
  }}
  .apt-row {{
    display: grid; grid-template-columns: 150px 60px 1fr; align-items: center;
    gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-soft); font-size: 0.85rem;
  }}
  .apt-row .apt-label {{ color: var(--muted); }}
  .apt-row .apt-names {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .pick-idle {{ color: var(--green); font-size: 0.6rem; }}
  .ok-inline {{ color: var(--green); }}
  .bad-inline {{ color: var(--red); }}
  .quicknav-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }}
  .quicknav-card {{
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px 18px; display: flex; align-items: center; gap: 12px; cursor: pointer;
    transition: border-color .15s, transform .12s; box-shadow: var(--shadow);
  }}
  .quicknav-card:hover {{ border-color: var(--blue); transform: translateY(-2px); }}
  .quicknav-card .qn-icon {{ font-size: 1.5rem; }}
  .quicknav-card .qn-body {{ display: flex; flex-direction: column; flex: 1; }}
  .quicknav-card .qn-title {{ font-weight: 700; font-size: 0.95rem; font-family: var(--font-display); }}
  .quicknav-card .qn-stat {{ color: var(--muted); font-size: 0.78rem; margin-top: 2px; }}
  .quicknav-card .qn-arrow {{ color: var(--muted); font-size: 1.1rem; }}
  .card.tips {{ border-left-color: var(--gold); grid-column: 1 / -1; margin-top: 16px; }}
  .tip-link {{ color: var(--blue); cursor: pointer; font-size: 0.82rem; white-space: nowrap; font-weight: 600; }}
  .tip-link:hover {{ text-decoration: underline; }}
  .breed-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 16px; margin-top: 16px; }}
  .breed-card {{
    background: linear-gradient(160deg, #191d29, var(--card));
    border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 16px;
    position: relative; overflow: hidden; transition: transform .15s, border-color .15s; box-shadow: var(--shadow);
  }}
  .breed-card:hover {{ transform: translateY(-2px); border-color: var(--gold); }}
  .breed-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--gold), var(--orange));
  }}
  .breed-egg {{ font-size: 1.4rem; }}
  .breed-result {{ font-size: 1.15rem; font-weight: 700; color: var(--gold); margin: 6px 0 12px 0; }}
  .breed-parents {{ display: flex; align-items: center; gap: 8px; font-size: 0.82rem; flex-wrap: wrap; }}
  .breed-parent {{
    background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: 999px;
    padding: 5px 12px; color: var(--text);
  }}
  .breed-plus {{ color: var(--muted); font-weight: 700; font-size: 0.9rem; }}
  .breed-rank {{ color: var(--muted); font-size: 0.72rem; margin-top: 10px; }}
  .recipe-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 16px; }}
  .recipe-card {{
    background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--green);
    border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow);
  }}
  .recipe-card.blocked {{ border-left-color: var(--muted); opacity: 0.75; box-shadow: none; }}
  .recipe-name {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; font-family: var(--font-display); }}
  .recipe-station {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; margin-bottom: 10px; }}
  .recipe-ing {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .recipe-ing span {{
    background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: 999px;
    padding: 3px 9px; font-size: 0.76rem;
  }}
  .recipe-ing span.missing {{ border-color: var(--red); color: var(--red); }}
  .recipe-ing span.unverified {{ border-color: var(--orange); color: var(--orange); }}
  .recipe-effect {{ font-size: 0.85rem; }}
  .recipe-effect .san {{ color: var(--gold); font-weight: 700; }}
  .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }}
  .filter-btn {{
    background: var(--card-soft); border: 1px solid var(--border); color: var(--muted);
    padding: 6px 14px; border-radius: 999px; font-size: 0.82rem; font-weight: 600; cursor: pointer;
    transition: color .15s, border-color .15s, background .15s;
  }}
  .filter-btn:hover {{ color: var(--text); border-color: var(--green); }}
  .filter-btn.active {{ color: var(--bg); background: var(--green); border-color: var(--green); }}
  .palpedia-bar-track {{ background: var(--card-soft); border-radius: 999px; height: 10px; overflow: hidden; margin: 16px 0 6px 0; }}
  .palpedia-bar-fill {{ background: linear-gradient(90deg, var(--blue), var(--purple)); height: 100%; border-radius: 999px; }}
  .palpedia-count {{ color: var(--muted); font-size: 0.82rem; }}
  .palpedia-card-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px;
    margin-top: 16px;
  }}
  .palpedia-pal-card {{
    display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 16px 10px;
    background: var(--card-soft); border: 1px solid var(--border-soft); border-top: 3px solid var(--purple);
    border-radius: 12px; cursor: pointer; transition: border-color .15s, transform .15s, box-shadow .15s;
  }}
  .palpedia-pal-card:hover {{ border-color: var(--purple); transform: translateY(-3px); box-shadow: var(--shadow); }}
  .palpedia-pal-card[data-status="owned"] {{ border-top-color: var(--green); }}
  .palpedia-pal-card[data-status="owned"]:hover {{ border-color: var(--green); }}
  .palpedia-pal-icon {{ width: 76px; height: 76px; object-fit: contain; border-radius: 10px; background: var(--bg); flex-shrink: 0; }}
  .palpedia-pal-name {{
    font-size: 0.85rem; font-weight: 600; color: var(--text); text-align: center; line-height: 1.2;
    overflow-wrap: break-word; word-break: break-word; max-width: 100%;
  }}
  .pagination-row {{ display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 20px; }}
  .pal-modal-overlay {{
    display: none; position: fixed; inset: 0; background: rgba(5,6,10,0.72); z-index: 999;
    align-items: center; justify-content: center; padding: 20px;
  }}
  .pal-modal-overlay.open {{ display: flex; }}
  .pal-modal {{
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    box-shadow: var(--shadow); max-width: 420px; width: 100%; padding: 24px; position: relative;
  }}
  .pal-modal-close {{
    position: absolute; top: 14px; right: 16px; background: none; border: none; color: var(--muted);
    font-size: 1.3rem; cursor: pointer; line-height: 1;
  }}
  .pal-modal-close:hover {{ color: var(--text); }}
  .pal-modal-head {{ display: flex; align-items: center; gap: 16px; }}
  .pal-modal-icon {{ width: 72px; height: 72px; object-fit: contain; border-radius: 12px; background: var(--card-soft); flex-shrink: 0; }}
  .pal-modal-name {{ font-size: 1.3rem; font-weight: 800; }}
  .pal-modal-elements {{ margin-top: 4px; font-size: 0.9rem; color: var(--muted); }}
  .pal-modal-stats {{
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px; margin-top: 18px;
    font-size: 0.85rem;
  }}
  .pal-modal-stats .stat-label {{ color: var(--muted); }}
  .pal-modal-stats .stat-value {{ font-weight: 700; }}
  .pal-modal-section {{ margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-soft); }}
  .pal-modal-section h4 {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 0 0 8px 0; }}
  .pal-modal-apt {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .pal-modal-apt span {{
    background: var(--card-soft); border: 1px solid var(--border-soft); border-radius: 999px;
    padding: 4px 10px; font-size: 0.78rem;
  }}
  .pal-modal-empty {{ color: var(--muted); font-size: 0.82rem; }}
  footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border-soft); color: var(--muted); font-size: 0.78rem; text-align: center; }}
</style>
</head>
<body>
  <header class="site-header">
    <div class="site-header-inner">
      <div class="brand">
        <span class="brand-mark">&#127991;&#65039;</span>
        <div>
          <h1>Palworld -- Tableau de bord</h1>
          <p class="tagline">Suivi communautaire en direct de notre monde : bases, Pals, élevage, cuisine et progression des joueurs.</p>
        </div>
      </div>
      <div class="updated-pill"><span class="dot"></span> Mis a jour {esc(data['genere_le'])}</div>
    </div>
  </header>

  <div class="layout">
  <nav class="tabs">
    <button class="tab-btn active" data-tab="tab-overview" style="--tab-accent: var(--blue)" onclick="showTab(this)">&#127757; Vue d'ensemble</button>
    <div class="tab-section-label">Pals</div>
    <button class="tab-btn" data-tab="tab-pals" style="--tab-accent: var(--gold)" onclick="showTab(this)">&#128062; Pals</button>
    <button class="tab-btn" data-tab="tab-palpedia" style="--tab-accent: var(--purple)" onclick="showTab(this)">&#128220; Palpédia</button>
    <button class="tab-btn" data-tab="tab-breeding" style="--tab-accent: var(--gold)" onclick="showTab(this)">&#129370; Élevage</button>
    <div class="tab-section-label">Base</div>
    <button class="tab-btn" data-tab="tab-work" style="--tab-accent: var(--orange)" onclick="showTab(this)">&#128736; Travail a la base</button>
    <button class="tab-btn" data-tab="tab-cuisine" style="--tab-accent: var(--green)" onclick="showTab(this)">&#127859; Cuisine</button>
    <div class="tab-section-label">Suivi</div>
    <button class="tab-btn" data-tab="tab-players" style="--tab-accent: var(--purple)" onclick="showTab(this)">&#128100; Joueurs</button>
    <button class="tab-btn" data-tab="tab-history" style="--tab-accent: var(--green)" onclick="showTab(this)">&#128200; Historique</button>
    <div class="tab-section-label">Perso</div>
    <button class="tab-btn" data-tab="tab-kanban" style="--tab-accent: var(--orange)" onclick="showTab(this)">&#128203; Organisation</button>
    <button class="tab-btn" data-tab="tab-guides" style="--tab-accent: var(--gold)" onclick="showTab(this)">&#128214; Guides</button>
  </nav>
  <div class="page">

  <div id="tab-overview" class="tab-panel active">
    <div class="grid grid-2col">
      <div class="card monde">
        <h2>&#127757; Monde</h2>
        <div class="kpi-grid">
          <div class="kpi"><span class="label">Jours ecoules</span><span class="value">{m['jours']}</span></div>
          <div class="kpi"><span class="label">Bases</span><span class="value">{m['bases']}</span></div>
          <div class="kpi"><span class="label">Raids en cours</span><span class="value">{m['raids_actifs']}/{m['raids_total']}</span></div>
          <div class="kpi"><span class="label">Camps repeuplés (transitoire)</span><span class="value">{m['camps_total'] - m['camps_nettoyes']}/{m['camps_total']}</span></div>
          <div class="kpi"><span class="label">Repères donjon</span><span class="value">{m['donjons']}</span></div>
        </div>
      </div>

      <div class="card basecard" style="grid-column: span 1">
        <h2>&#127968; Base &amp; Guilde</h2>
        <div class="kpi-grid">
          <div class="kpi"><span class="label">Bases</span><span class="value">{b['nb_bases']}</span></div>
          <div class="kpi"><span class="label">Guildes actives</span><span class="value">{b['guildes']}</span></div>
          <div class="kpi"><span class="label">Coffres guilde</span><span class="value">{b['coffres_guilde']}</span></div>
          <div class="kpi"><span class="label">Dernier largage</span><span class="value" style="font-size:0.9rem">{esc(b['dernier_largage'])}...</span></div>
        </div>
        <p class="modules">Modules actifs : {esc(', '.join(b['modules']))}</p>
      </div>
    </div>

    <div class="quicknav-grid">
      <div class="quicknav-card" onclick="goToTab('tab-players')">
        <span class="qn-icon">&#128100;</span>
        <span class="qn-body"><span class="qn-title">Joueurs</span>
        <span class="qn-stat">{qn.get('joueurs_actifs', 0)} actifs &middot; dernier vu {esc(qn.get('dernier_vu', '?'))}</span></span>
        <span class="qn-arrow">&#8594;</span>
      </div>
      <div class="quicknav-card" onclick="goToTab('tab-pals')">
        <span class="qn-icon">&#128062;</span>
        <span class="qn-body"><span class="qn-title">Pals</span>
        <span class="qn-stat">{qn.get('pals_total', 0)} pals &middot; {qn.get('pals_especes', 0)} espèces</span></span>
        <span class="qn-arrow">&#8594;</span>
      </div>
      <div class="quicknav-card" onclick="goToTab('tab-work')">
        <span class="qn-icon">&#128736;</span>
        <span class="qn-body"><span class="qn-title">Travail a la base</span>
        <span class="qn-stat">{qn.get('postes_a_optimiser', 0)}/{qn.get('postes_total', 0)} postes a optimiser</span></span>
        <span class="qn-arrow">&#8594;</span>
      </div>
    </div>

    <div class="card tips">
      <h2>&#128161; Pistes d'amélioration</h2>
      <ul class="advice-list">{tips_rows or "<li class='muted'>Rien a signaler pour le moment.</li>"}</ul>
    </div>
  </div>

  <div id="tab-players" class="tab-panel">
    <div class="grid">
      {player_cards}
    </div>
  </div>

  <div id="tab-pals" class="tab-panel">
    <div class="grid grid-2col">
      <div class="card pals">
        <h2>&#128062; Vue d'ensemble</h2>
        <div class="kpi-grid">
          <div class="kpi"><span class="label">Total</span><span class="value">{pals['total']}</span></div>
          <div class="kpi"><span class="label">Espèces</span><span class="value">{pals['especes']}</span></div>
        </div>
        <h3 style="margin-top:18px">Répartition par propriétaire</h3>
        <ul>{owner_rows}</ul>
      </div>

      <div class="card" style="border-left-color: var(--purple)">
        <h2>&#127942; Classements</h2>
        <div class="cols3">
          <div><h3>&#127942; Top Niveaux</h3><ul>{top_niveaux}</ul></div>
          <div><h3>&#10084;&#65039; Top Affection</h3><ul>{top_affection}</ul></div>
        </div>
      </div>

      <div class="card" style="border-left-color: var(--gold); grid-column: 1 / -1">
        <h2>&#128142; Top IV &amp; Passifs</h2>
        <p class="muted" style="margin-top:-6px">Les 10 Pals possédés avec les meilleures IV (PV/Attaque/Defense), et leurs passifs reels.</p>
        <ul>{top_iv}</ul>
      </div>

      <div class="card" style="border-left-color: var(--red); grid-column: 1 / -1">
        <h2>&#9876;&#65039; Equipe de terrain recommandee</h2>
        <p class="muted" style="margin-top:-6px">
          A emmener en exploration/combat (distinct du travail a la base) : stats de combat réelles
          (attaque, PV, defense) du DataTable, croisees avec le meilleur exemplaire possédé de chaque
          espèce (niveau + IV), plus une monture rapide. Recalcule a chaque génération.
        </p>
        {equipe_rows or "<p class='muted'>Aucune donnée de combat exploitable pour l'instant.</p>"}
        {elements_txt}
      </div>
    </div>
  </div>

  <div id="tab-work" class="tab-panel">
    <div class="grid">
      <div class="card work">
        <h2>&#128736; Travail a la base</h2>

        <div class="kpi-grid" style="margin-bottom:16px">
          <div class="kpi"><span class="label">Postes</span><span class="value">{bta.get('nb_emplacements', 0)}</span></div>
          <div class="kpi"><span class="label">Optimaux</span><span class="value" style="color:var(--green)">{bta.get('nb_optimaux', 0)}</span></div>
          <div class="kpi"><span class="label">A améliorer</span><span class="value" style="color:#e74c3c">{bta.get('nb_a_ameliorer', 0)}</span></div>
          <div class="kpi"><span class="label">Bâtiments manquants</span><span class="value">{len(bta.get('categories_batiment_manquant', []))}</span></div>
        </div>

        <h3>&#128203; Ce qu'on a</h3>
        <ul>{recap_rows or "<li class='muted'>Aucun poste actif.</li>"}</ul>
        <div class="muted" style="font-size:0.82rem">{esc(bases_recap_txt)} &nbsp;|&nbsp; {batiments_inline}</div>
        {manques_inline}

        <div class="subhead">
          <h3>&#128161; Comment améliorer</h3>
          <ul class="advice-list">{advice_swaps or "<li class='muted'>Rien a changer -- les postes actuels couvrent déjà les meilleures espèces possédées.</li>"}</ul>
        </div>

        <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
          Etoiles 0-4 du DataTable du jeu (<code>blaynem/paldex</code> + paldb.cc). {bta.get('especes_non_couvertes', 0)}
          espèces possédées non couvertes (variantes/DLC récentes), exclues plutot que devinees.
        </p>
      </div>
    </div>
  </div>

  <div id="tab-history" class="tab-panel">
    <div class="grid">
      <div class="card basecard">
        <h2>&#128200; Evolution dans le temps</h2>
        <p class="muted" style="margin-top:-6px">
          Un point ajoute a chaque génération (toutes les heures) -- {history_range_txt}.
        </p>
        <h3>Pals total</h3>
        {chart_pals}
        <h3 style="margin-top:20px">Niveau des joueurs</h3>
        {chart_niveaux}
      </div>
    </div>
  </div>

  <div id="tab-breeding" class="tab-panel">
    <div class="grid">
      <div class="card" style="border-left-color: var(--gold); grid-column: 1 / -1;">
        <h2>&#129370; Élevage -- nouvelles espèces possibles</h2>
        <p class="muted" style="margin-top:-6px">
          Calcule via la vraie formule de reproduction du jeu (Combi Rank : le rang de l'oeuf =
          (rang parent A + rang parent B + 1) &#247; 2, arrondi a l'espèce dont le rang réel est
          le plus proche) -- {élevage.get('nb_especes_possedees_avec_rang', 0)} espèces possédées
          avec un rang combi connu, combinees deux a deux pour trouver ce qui manque a la collection.
          Recalcule a chaque génération.
        </p>
        <div class="filter-row">
          <button class="filter-btn active" data-sort="ecart" onclick="sortBreeding(this)">Confiance (par defaut)</button>
          <button class="filter-btn" data-sort="rang" onclick="sortBreeding(this)">Rareté (rang combi)</button>
          <button class="filter-btn" data-sort="nom" onclick="sortBreeding(this)">Alphabetique</button>
        </div>
        <div class="breed-grid" id="breed-grid">{breed_cards or "<p class='muted'>Aucune nouvelle combinaison trouvee pour l'instant.</p>"}</div>
        <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
          Deux réserves : (1) le jeu compte ~28 paires speciales qui outrepassent cette formule
          generale avec un résultat unique -- non modelisees ici, a vérifier en jeu avant un élevage
          long ; (2) il faut un male et une femelle parmi les deux parents indiques (peu importe lequel).
        </p>
      </div>
    </div>
  </div>

  <div id="tab-cuisine" class="tab-panel">
    <div class="grid">
      <div class="card" style="border-left-color: var(--green); grid-column: 1 / -1;">
        <h2>&#127859; Cuisine -- meilleurs plats a preparer</h2>
        <p class="muted" style="margin-top:-6px">
          Croise les cultures et stations de cuisine réellement construites a la base avec une
          liste de recettes (ingredients/effets sources d'un guide communautaire, pas du DataTable
          brut du jeu comme le reste du dashboard -- a prendre avec un peu plus de recul).
          Recalcule a chaque génération.
        </p>
        <div class="kpi-grid" style="margin-bottom:6px">
          <div class="kpi"><span class="label">Prêtes a cuisiner</span><span class="value" style="color:var(--green)">{nb_prete}</span></div>
          <div class="kpi"><span class="label">Cultures dispo</span><span class="value" style="font-size:0.95rem">{esc(cultures_txt)}</span></div>
          <div class="kpi"><span class="label">Stations dispo</span><span class="value" style="font-size:0.95rem">{esc(stations_txt)}</span></div>
        </div>
        {meilleur_cuisinier_txt}
        <div class="filter-row">{boost_filters}</div>
        <div class="recipe-grid" id="recipe-grid">{recipe_cards or "<p class='muted'>Aucune recette a evaluer.</p>"}</div>
        <p class="muted" id="recipe-empty-msg" style="display:none">Aucun plat ne correspond a ce filtre.</p>
        <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
          Les ingredients en <span style="color:var(--orange)">orange</span> (viande, oeuf, lait...) ne sont
          pas vérifiés automatiquement (contenu des coffres illisible depuis la sauvegarde) -- a confirmer
          en jeu. Ceux en <span style="color:#e74c3c">rouge</span> manquent carrement (culture pas plantee).
        </p>
      </div>
    </div>
  </div>

  <div id="tab-palpedia" class="tab-panel">
    <div class="grid">
      <div class="card" style="border-left-color: var(--purple); grid-column: 1 / -1;">
        <h2>&#128220; Palpédia -- complétion par joueur</h2>
        <p class="muted" style="margin-top:-6px">
          Base sur la propriété ACTUELLE des Pals (pas un historique de capture) contre
          {len(PALPEDIA_UNIVERSE)} espèces réelles reconnues (PNJ uniques de tour et contenu
          non disponible exclus). Si un Pal a change de main ou dort dans un coffre partage,
          ca peut sous-compter. Recalcule a chaque génération.
        </p>
        <div class="filter-row" id="palpedia-player-tabs">{palpedia_tabs_html or "<p class='muted'>Aucun joueur avec des Pals identifies.</p>"}</div>
        {palpedia_panels_html}
      </div>
    </div>
  </div>

  <div id="tab-kanban" class="tab-panel">
    <div class="card" style="border-left-color: var(--orange)">
      <h2>&#128203; Organisation -- a faire pour le serveur</h2>
      <p class="muted" style="margin-top:-6px">
        Liste de taches partagee entre vous deux (stockee a part, elle survit aux regenerations
        horaires du dashboard). Glissez une carte vers une autre colonne, ou utilisez les fleches.
      </p>
      <div class="kanban-add-row">
        <input type="text" id="kanban-new-title" class="kanban-input" placeholder="Nouvelle tache...">
        <button class="filter-btn active" onclick="kanbanAddTask()">+ Ajouter</button>
      </div>
      <div class="kanban-board" id="kanban-board">
        <div class="kanban-column" data-column="todo">
          <h3 class="kanban-col-title">A faire <span class="kanban-count" id="kanban-count-todo">0</span></h3>
          <div class="kanban-col-body" id="kanban-col-todo" ondragover="kanbanDragOver(event)" ondrop="kanbanDrop(event, 'todo')"></div>
        </div>
        <div class="kanban-column" data-column="doing">
          <h3 class="kanban-col-title">En cours <span class="kanban-count" id="kanban-count-doing">0</span></h3>
          <div class="kanban-col-body" id="kanban-col-doing" ondragover="kanbanDragOver(event)" ondrop="kanbanDrop(event, 'doing')"></div>
        </div>
        <div class="kanban-column" data-column="done">
          <h3 class="kanban-col-title">Fait <span class="kanban-count" id="kanban-count-done">0</span></h3>
          <div class="kanban-col-body" id="kanban-col-done" ondragover="kanbanDragOver(event)" ondrop="kanbanDrop(event, 'done')"></div>
        </div>
      </div>
      <p class="muted" id="kanban-status" style="font-size:0.78rem; margin-top:12px"></p>
    </div>
  </div>

  <div id="tab-guides" class="tab-panel">
    <div class="filter-row" id="guide-selector">
      <button class="filter-btn active" data-guide="g0" onclick="showGuide(this)">&#128214; Farm XP mid-game</button>
      <button class="filter-btn" data-guide="g1" onclick="showGuide(this)">&#127968; Base mid-game</button>
      <button class="filter-btn" data-guide="g2" onclick="showGuide(this)">&#127907; La peche</button>
      <button class="filter-btn" data-guide="g3" onclick="showGuide(this)">&#128165; Build Tocotoco -- Megaton Implode</button>
      <button class="filter-btn" data-guide="g4" onclick="showGuide(this)">&#128163; Puffsplode -- la chaine complete</button>
    </div>

    <div class="guide-panel" data-guide="g0">
    <div class="card" style="border-left-color: var(--gold)">
      <h2>&#128214; Farm XP mid-game -- le camp qu'on ne finit jamais</h2>
      <p class="muted" style="margin-top:-6px">
        Resume de la video <a href="https://www.youtube.com/watch?v=1ipOrXhpZuw" target="_blank" rel="noopener">« NOUVELLE TECHNIQUE D'XP POUR VOS PALS sur PALWORLD 1.0 »</a>
        (Cheatah, 21 aout 2026) -- comment monter une equipe de Pals jusqu'au niveau ~70-75 sans materiel de fin de jeu.
      </p>

      <div class="subhead">
      <h3 style="font-size:1rem">&#127890; Materiel necessaire</h3>
      <ul class="advice-list">
        <li><b>Un Pal avec une grosse attaque de zone (AOE)</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Herbil ou Omascul avec Rafale de Vent dans la video. D'autres attaques de zone (tourbillon de sable, tenebres...) devraient marcher aussi, non testees de facon exhaustive par le createur.</div>
        </li>
        <li><b>Omascul si accessible</b> <span class="muted" style="font-weight:400">(optionnel)</span>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Passif +80% XP a 4 etoiles plein. Pal tardif a capturer, la technique marche quand meme sans lui.</div>
        </li>
        <li><b>Nourriture boost XP</b> pour les Pals a monter
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Une salade a base de poisson/fruits de mer citee dans la video, recette pas claire dans la transcription, a verifier en jeu.</div>
        </li>
        <li><b>La Clochette de Croissance</b> (objet posable, boost XP)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Emplacement exact non retrouve par le createur ; un commentaire de la video mentionne un plan vers -26, -92, <span style="color:var(--red)">non verifie</span>.</div>
        </li>
        <li><b>Vos Pals niveau 1 a monter</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">4 a 15 selon le besoin.</div>
        </li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#127800; Le lieu</h3>
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Ile de Sakura</b> -- camp de PNJ colle a un teleporteur, condition clee pour boucler vite.
        L'ile du Fin a ete testee et ecartee : aucun camp assez proche d'un TP.
      </p>
      <div class="kpi-grid">
        <div class="kpi"><span class="label">Niveau de zone</span><span class="value" style="font-size:1.1rem">~50-60</span></div>
        <div class="kpi"><span class="label">Teleporteur</span><span class="value" style="font-size:1.1rem">-600, 214</span></div>
      </div>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128260; La boucle</h3>
      <p class="muted" style="margin-top:0">Principe : ne jamais tuer 100% du camp, pour eviter le respawn PNJ classique (~30 min).</p>
      <ol style="padding-left:20px; color:var(--muted); font-size:0.9rem; line-height:1.9">
        <li>Emmenez vos Pals niveau 1 + leur nourriture XP au camp (donnez la bouffe avant de commencer).</li>
        <li>Envoyez le Pal a attaque de zone au milieu du camp -- il nettoie la majorite des ennemis en un coup.</li>
        <li>Repartez sans tout achever, puis dechargez la zone (fuite rapide/vol, ou aller-retour au teleporteur).</li>
        <li>Revenez : le camp s'est regenere sans avoir attendu le timer complet.</li>
        <li>Repetez 5 a 10 fois -- selon les parametres serveur, comptez une equipe autour du niveau 70-75, avec de l'or/tissu/loot a chaque passage.</li>
      </ol>
      <p class="muted" style="font-size:0.85rem">
        &#9201;&#65039; Le vrai goulot d'etranglement n'est pas le combat mais l'ecran de chargement du teleporteur --
        beaucoup plus rapide en solo/serveur local qu'en multi.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129517; Alternatives evoquees</h3>
      <ul class="advice-list">
        <li><b>Boucler une tour de donjon</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Fonctionne (~30 sec/boucle sur la plus rapide), mais ratio XP/temps juge moins bon par le createur.</div>
        </li>
        <li><b>Monture + attaque feu sur la Tour du Paradis</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Piste evoquee, pas encore testee en video au moment de l'enregistrement.</div>
        </li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#9888;&#65039; A savoir avant de vous lancer</h3>
      <ul class="advice-list">
        <li>Ce n'est pas un niveau 70 en 10 secondes -- il faut repeter la boucle plusieurs fois.</li>
        <li>Pour le end-game pur (niveau 80), l'autre technique du createur (Omascul full stuff + boss unique) a ete nerfee recemment : comptez plutot 75-77 que 80.</li>
        <li>Choisissez un camp adapte a votre niveau actuel -- trop bas level si vous etes deja loin en progression, l'efficacite XP en patit.</li>
        <li>Details non verifies par le createur lui-meme : emplacement exact de la Clochette de Croissance, recette precise de la nourriture XP.</li>
      </ul>
      </div>
      <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
        Contenu resume d'une video tierce (chaine Cheatah), pas un guide officiel Palworld.
      </p>
    </div>
    </div>

    <div class="guide-panel" data-guide="g1" style="display:none">
    <div class="card" style="border-left-color: var(--purple)">
      <h2>&#127968; Une base mid-game qui tient la route</h2>
      <p class="muted" style="margin-top:-6px">
        Resume de la video <a href="https://www.youtube.com/watch?v=6b-u0D7_vp8" target="_blank" rel="noopener">« UNE BASE PARFAITE MID GAME? sur PALWORLD 1.0 »</a>
        (Cheatah, 14 aout 2026) -- agencement, astuces et exemples de Pals pour la transition niveau ~30/40 vers 80.
      </p>
      <p class="muted" style="font-size:0.82rem; background:var(--card-soft); border:1px dashed var(--border); border-radius:10px; padding:10px 14px; margin-top:12px">
        &#9888;&#65039; Le createur joue avec une contrainte perso (deblocage des Pals a l'ordre du Palpedia) : ses choix de Pals sont adaptes a cette regle, pas forcement le pick optimal standard. Les principes d'agencement restent valables pour tous.
      </p>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128205; Choix d'emplacement</h3>
      <ul class="advice-list">
        <li><b>Regroupez vos futures bases</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Une zone avec la place pour 4 bases cote a cote evite les allers-retours en teleporteur en late-game.</div>
        </li>
        <li><b>Construire sur l'eau est debloque bien plus tot</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Environ niveau 20-23 desormais (contre ~66 avant), terrain plat garanti.</div>
        </li>
        <li><b>L'emplacement compte surtout en early-game</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">En late-game vous produirez tout sur place, l'impact du spot devient minime.</div>
        </li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128193; Organisation par secteurs</h3>
      <ul class="advice-list">
        <li>Agriculture + transformation de nourriture regroupees, forge pas loin.</li>
        <li>Un coin elevage/ferme distinct plutot qu'eparpille.</li>
        <li>Coffre "cherche-tout" + Coffre de Guilde (sans peremption) pose direct sur les postes d'extraction pour un depot automatique.</li>
        <li>Prioriser la recherche arrosage/fontaine : +20% d'arrosage sur toute la base.</li>
        <li>Un seul bon generateur electrique (~5 points de recherche investis) peut couvrir toute l'energie de la base.</li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128142; Farm rapide de cubes</h3>
      <p class="muted" style="margin-top:0">
        Pour fermer des noyaux de civilisation antique, des <b style="color:var(--text)">petites expeditions repetees</b>
        (~30 min, ciblant les fragments de bete noire) sont bien plus rentables qu'une grosse expedition longue (~1h) :
        3-4 cubes minimum par cycle plus des livres de competence, contre 1-2 noyaux pour une grosse expedition a pleine charge.
      </p>
      <p class="muted" style="font-size:0.82rem">
        &#128161; Astuce bonus : dans l'ecran d'expedition, une exception permet d'empecher un Pal precis de partir
        (utile pour ne jamais perdre l'acces a votre ramasseur d'oeufs par exemple).
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129521; Astuce empilement (lits / cultures)</h3>
      <p class="muted" style="margin-top:0">Gain de place et d'ergonomie, aucun gain de performance associe.</p>
      <ol style="padding-left:20px; color:var(--muted); font-size:0.9rem; line-height:1.9">
        <li>Placez un mur de reference.</li>
        <li>Alignez votre objet (lit, parcelle) contre le mur avec la touche d'alignement (Ctrl).</li>
        <li>Ajoutez un coussin de sol (ou banc/chaise) a l'endroit du prochain objet.</li>
        <li>Reconstruisez l'objet aligne sur le mur, par-dessus le coussin -- repetez pour empiler.</li>
      </ol>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128062; Exemples de roles de Pals (mid-game)</h3>
      <ul class="advice-list">
        <li><b>Lumoun</b> -- Artisanat
          <div class="muted" style="font-size:0.85rem; margin-top:4px">3&#9733; + Serieux/Applique/Soumis/Nocturne (travaille 24/7), top early-mid game.</div>
        </li>
        <li><b>Oeil de Kouloulou</b> -- Transport
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Build 100% vitesse, cite comme top 1-2 des meilleurs transporteurs meme en late-game.</div>
        </li>
        <li><b>Cinnamoth</b> -- Agriculture
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Semence + collecte full etoile pour gerer seule les parcelles.</div>
        </li>
        <li><b>Ruchoir</b> -- Minage
          <div class="muted" style="font-size:0.85rem; margin-top:4px">5&#9733;, epaule par un second mineur car un seul ne suit plus en mid-game.</div>
        </li>
        <li><b>Tifan</b> -- Eau / polyvalent
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Arrose tout sans trou, plus transport, farine, pierre-&gt;brique et recherche eau.</div>
        </li>
        <li><b>Ruby / Melpaca / Chikipi</b> -- Production long-terme
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Laine, lait, oeufs -- montes a fond car utiles jusqu'a la fin.</div>
        </li>
      </ul>
      </div>

      <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
        Contenu resume d'une video tierce (chaine Cheatah), pas un guide officiel Palworld.
      </p>
    </div>
    </div>

    <div class="guide-panel" data-guide="g2" style="display:none">
    <div class="card" style="border-left-color: var(--blue)">
      <h2>&#127907; La peche -- comment ca marche</h2>
      <p class="muted" style="margin-top:-6px">
        Resume de la video <a href="https://www.youtube.com/watch?v=NBMXHd5Tqeg" target="_blank" rel="noopener">« LA PECHE COMMENT CA MARCHE? sur PALWORLD 1.0 »</a>
        (Cheatah, 15 aout 2026) -- cannes, appats, equipe de Pals, spots et peche a l'aimant.
      </p>

      <div class="subhead">
      <h3 style="font-size:1rem">&#127907; Materiel</h3>
      <ul class="advice-list">
        <li><b>3 cannes a peche</b> -- Normale et Epique se debloquent par recherche technologique. La Legendaire demande de dropper son plan (notamment via les campements ennemis aquatiques, gros taux selon le createur).
          <div class="muted" style="font-size:0.85rem; margin-top:4px">La canne influence la taille/facilite de la jauge du mini-jeu de capture, pas la qualite du loot.</div>
        </li>
        <li><b>Les appats n'accelerent pas la touche</b> (teste par le createur)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Ce qu'ils changent vraiment : un bonus de depart direct sur la jauge de capture -- meilleur appat = pourcentage de depart plus eleve.</div>
        </li>
        <li><b>L'aimant de peche</b> -- debloque par la recherche, mecanique cle a partir du niveau ~62.</li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128062; Equipe pour la peche standard</h3>
      <ul class="advice-list">
        <li><b>Gloupy</b> (full etoilee)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Reduit de 35% la penalite en cas d'erreur au mini-jeu. Inutile si vous ne ratez jamais -- mais "ca arrive toujours" selon le createur.</div>
        </li>
        <li><b>Jelliette</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Double les items droppes en peche standard (ne fonctionne pas pour la peche a l'aimant, c'est le role de Jellroy).</div>
        </li>
        <li><b>Walaska + Walaska Ignis</b> (cumulables)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">+17% et +14% de jauge de capture des le debut (soit +30% cumule). Necessitent une selle craftee pour que le passif s'active -- juste presents dans le stock de Pals, pas besoin de les sortir.</div>
        </li>
        <li><b>Salmora / Salmora Ignis</b> <span class="muted" style="font-weight:400">(optionnel)</span>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Augmente l'IV des Pals captures en pechant -- utile seulement si vous pechez pour chopper des Pals (moins pertinent depuis l'Arbre Monde selon le createur).</div>
        </li>
        <li>Aucune competence passive du Pal lui-meme n'influence la peche -- passifs libres.</li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128204; Reperer les spots</h3>
      <p class="muted" style="margin-top:0">
        Les loots suivent les biomes (zone d'herbe &#8594; foret &#8594; volcan &#8594; desert &#8594; neige &#8594; Sakura &#8594; Feybreak &#8594; iles volantes &#8594; Arbre Monde), avec un loot proportionnellement meilleur dans les biomes avances. L'Arbre Monde est le meilleur spot en late-game (plans epiques/legendaires).
      </p>
      <p class="muted" style="font-size:0.82rem; background:var(--card-soft); border:1px dashed var(--border); border-radius:10px; padding:10px 14px">
        &#9888;&#65039; La distinction "5 poissons visibles = spot standard / 3 poissons = spot legendaire" est une deduction personnelle du createur et sa communaute (aucune source officielle trouvee) -- il a lui-meme eu un contre-exemple pendant le tournage. A prendre avec prudence, ou verifier via le site paldb.cc (lien description video) qui donne spots et temps de respawn exacts.
      </p>
      <ul class="advice-list">
        <li><b>Aura verte</b> sur un poisson
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Pal capture avec passifs quasi assures rainbow/legendaires -- la aura a viser si vous pechez pour chopper des Pals.</div>
        </li>
        <li><b>Aura violette simple</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Marqueur "alpha" seulement, peu d'interet en soi.</div>
        </li>
        <li><b>Aura violette + eclat (GZR)</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Trophee des Flots garanti a 100% -- specialiste aquatique.</div>
        </li>
      </ul>
      <p class="muted" style="font-size:0.82rem">
        Les appats et auras n'influencent QUE le Pal obtenu en capture -- jamais les ressources/items droppes.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129442; Peche a l'aimant</h3>
      <p class="muted" style="margin-top:0">
        Mecanique separee, debloquee vers le niveau 62 : recuperer les detritus en mer, surtout pour le <b style="color:var(--text)">Korallium</b>
        (essentiel en late-game, avant de pouvoir le synthetiser bien plus tard).
      </p>
      <ul class="advice-list">
        <li><b>Jellroy</b> (le plus etoile possible)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Double ce que vous recuperez -- indispensable, contrairement a Jelliette qui ne marche que pour la peche standard.</div>
        </li>
        <li><b>Un Pal de deplacement rapide dans l'eau</b> (Neptilus dans la video)
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Pour enchainer les points de detritus vite -- le reste de l'equipe de peche standard est inutile ici.</div>
        </li>
        <li>La qualite/niveau de la canne a peche n'influence pas la peche a l'aimant (teste par le createur).</li>
        <li><b>2 types de spots aussi</b> -- standard (tonneau gris) vs legendaire (tonneau a bordure doree, loot bien meilleur) : dans la zone Feybreak c'est garanti a 100% legendaire, pas aleatoire.</li>
      </ul>
      <p class="muted" style="font-size:0.82rem; background:var(--card-soft); border:1px dashed var(--border); border-radius:10px; padding:10px 14px">
        &#128161; Astuce d'un commentateur de la video (non verifiee par le createur) : le combo <b style="color:var(--text)">Reptyro / Reptyro Cryst</b> annule le poids du Korallium recupere -- pratique pour les longues sessions de farm intensif.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#9888;&#65039; A savoir</h3>
      <ul class="advice-list">
        <li>Alternative mineure pour du Korallium en tout debut de jeu : looter les Walaska tues directement (4 a 6 par kill max, pas une grosse quantite).</li>
        <li>D'apres un commentaire de la video, viser les poissons "de base" plutot que "brillants" donnerait plus de composants (fluides, ingredients cuisine) -- les brillants dropperaient plutot des objets a vendre. Non confirme par le createur lui-meme.</li>
      </ul>
      </div>

      <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
        Contenu resume d'une video tierce (chaine Cheatah), pas un guide officiel Palworld.
      </p>
    </div>
    </div>

    <div class="guide-panel" data-guide="g3" style="display:none">
    <div class="card" style="border-left-color: var(--red)">
      <h2>&#128165; Build Tocotoco -- Megaton Implode</h2>
      <p class="muted" style="margin-top:-6px">
        Inspire d'un build <a href="https://www.reddit.com/r/Palworld/comments/1wb313h/he_has_become_death_destroyer_of_worlds/" target="_blank" rel="noopener">partage sur r/Palworld</a> (691 upvotes) : un Tocotoco niveau 66 qui spamme Megaton Implode (1200 de puissance affichee) sans jamais mourir de sa propre explosion.
      </p>

      <div class="subhead">
      <h3 style="font-size:1rem">&#9888;&#65039; Le principe</h3>
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Megaton Implode</b> est la competence exclusive de Tocotoco (aucun fruit de competence n'existe pour l'apprendre a un autre Pal) -- Neutre, 500 de puissance de base (55s de cooldown, Brulure 100%), apprise naturellement au <b style="color:var(--text)">niveau 22</b>. Sa description est claire : le Pal "risque sa vie" pour l'explosion -- elle inflige des degats au Pal lui-meme. Tout le build sert a survivre a sa propre attaque pour la spammer en boucle.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129514; Les 4 passifs du build</h3>
      <ul class="advice-list">
        <li><b>Heavily Armored</b> <span class="muted" style="font-weight:400">(la piece maitresse)</span>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Immunite aux degats d'explosion -- sans lui, Megaton Implode se retourne contre le Pal. Passif de mutation, implant "Disposable Implant: Heavily Armored" (rarete 4).</div>
        </li>
        <li><b>God of Destruction</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Attaque +40% / Defense +20% / PV -50%. Implant obtenu via Officiers de Prime, Marchand de l'Arene, ou en recyclant des Reliques Anciennes a l'Ancient Relic Recycler (rarete de relique plus elevee = meilleure chance) -- ou trouve directement sur un Pal capture dans l'Arbre Monde.</div>
        </li>
        <li><b>Diamond Body</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Bonus de Defense (ajoute avec Feybreak), compense la perte de PV de God of Destruction. Memes sources d'implant que God of Destruction.</div>
        </li>
        <li><b>Lucky</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Vitesse de travail +15% / Attaque +15%. Ne se trouve <b style="color:var(--text)">jamais</b> sur un Pal sauvage aleatoire -- uniquement via reproduction depuis une lignee qui l'a deja, ou sur certains boss.</div>
        </li>
      </ul>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128221; Etapes</h3>
      <ol style="padding-left:20px; color:var(--muted); font-size:0.9rem; line-height:1.9">
        <li>Capturer/posseder un Tocotoco et le monter au moins au niveau 22 pour debloquer Megaton Implode (le monter plus haut ensuite pour les stats/rangs).</li>
        <li>Debloquer la Table de Chirurgie Pal (Technology, niveau 38) -- indispensable pour implanter les 3 passifs qui ne se trouvent jamais naturellement sur un Tocotoco sauvage.</li>
        <li>Farmer/acheter les implants Heavily Armored, God of Destruction et Diamond Body (Officiers de Prime, Marchand de l'Arene, Ancient Relic Recycler).</li>
        <li>Reproduire pour faire remonter Lucky sur la lignee de Tocotoco (breeding, pas d'implant possible).</li>
        <li>Implanter les 4 passifs sur le Tocotoco via la Table de Chirurgie.</li>
        <li>Reproduire plusieurs Tocotoco entre eux pour monter les IV (Talents PV/Attaque/Defense proches de 100%), et sacrifier les doublons au Pal Box pour monter le rang (etoiles).</li>
      </ol>
      </div>

      <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
        Compile depuis un post r/Palworld et plusieurs pages wiki (palworld.wiki.gg, Game8, PalMods, Fextralife) -- pas un guide officiel Palworld, a verifier patch par patch (les valeurs de puissance/passifs evoluent avec les mises a jour du jeu).
      </p>
    </div>
    </div>

    <div class="guide-panel" data-guide="g4" style="display:none">
    <div class="card" style="border-left-color: var(--orange)">
      <h2>&#128163; Puffsplode -- la chaine complete</h2>
      <p class="muted" style="margin-top:-6px">
        Inspire d'un build <a href="https://www.reddit.com/r/Palworld/comments/1wc1s52/i_made_the_cutest_little_nuke_youve_ever_seen/" target="_blank" rel="noopener">partage sur r/Palworld</a> (1.4K upvotes) -- la suite logique du build Tocotoco : une espece finale minuscule qui garde Megaton Implode.
      </p>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128300; Le principe</h3>
      <p class="muted" style="margin-top:0">
        Deux Puffolt (orthographie "Puffbolt" par l'auteur) differents sont necessaires, obtenus par <b style="color:var(--text)">deux chemins de reproduction separes</b>, puis combines ensemble pour obtenir Puffsplode.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#128260; Chemin 1 -- le Puffolt qui porte Megaton Implode</h3>
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Tocotoco + Pyrin &#8594; Puffolt</b> (avec Megaton Implode herite, a condition que le Tocotoco parent le connaisse deja -- voir le guide Tocotoco ci-dessus).
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129516; Chemin 2 -- un second Puffolt "propre" (chaine a 3 etapes)</h3>
      <ol style="padding-left:20px; color:var(--muted); font-size:0.9rem; line-height:1.9">
        <li><b style="color:var(--text)">Hartail + Moldron &#8594; Azurmane</b></li>
        <li><b style="color:var(--text)">Azurmane + Green Slime &#8594; Smokie</b></li>
        <li><b style="color:var(--text)">Smokie + Gumoss &#8594; Puffolt</b></li>
      </ol>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#127919; Etape finale</h3>
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Puffolt (chemin 1) + Puffolt (chemin 2) &#8594; Puffsplode</b>, qui herite de Megaton Implode.
      </p>
      </div>

      <div class="subhead">
      <h3 style="font-size:1rem">&#129514; Passifs et astuces annexes du thread</h3>
      <ul class="advice-list">
        <li><b>Immortality + Demon God</b> <span class="muted" style="font-weight:400">(build initial de l'auteur)</span>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Envisage de remplacer Immortality par <b style="color:var(--text)">God of Destruction</b> (meme passif que le build Tocotoco) -- alternative citee aussi : <b style="color:var(--text)">Twin-Edged Holy Blade</b>.</div>
        </li>
        <li><b>Explosive Resistant Undershirt</b> <span class="muted" style="font-weight:400">(alternative a Heavily Armored)</span>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Cet accessoire protege le joueur ET les pals actifs de l'equipe des degats d'explosion (confirme par deux commentateurs) -- pas besoin forcement d'implanter Heavily Armored si tu l'equipes.</div>
        </li>
        <li><b>Optimisation IV en reproduction</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Gateaux legume (vegetable cake, puis extravagant vegetable cake = meilleure transmission d'IV) + un pal comme <b style="color:var(--text)">Grintale</b> (50-75% de chance de doubler le nombre d'oeufs par ponte) pour accelerer le tri des meilleurs IV.</div>
        </li>
        <li><b>Ca marche aussi avec d'autres pals de base</b>
          <div class="muted" style="font-size:0.85rem; margin-top:4px">Un commentateur dit avoir fait la meme chose en partant de <b style="color:var(--text)">Kingpaca</b> au lieu de Tocotoco.</div>
        </li>
      </ul>
      </div>

      <p class="muted" style="font-size:0.82rem; background:var(--card-soft); border:1px dashed var(--border); border-radius:10px; padding:10px 14px; margin-top:12px">
        &#9888;&#65039; Puffsplode n'apparait pas encore dans les bases de breeding tierces verifiees (ex. palbreed.com) -- probablement un ajout de contenu tres recent. Les etapes ci-dessus viennent uniquement du temoignage de l'auteur du post en commentaire, pas d'une source wiki confirmee independamment.
      </p>

      <p class="muted" style="font-size:0.72rem; margin-top:18px; border-top:1px solid var(--border); padding-top:10px">
        Compile depuis un post r/Palworld -- pas un guide officiel Palworld.
      </p>
    </div>
    </div>
  </div>

  <footer>Généré automatiquement depuis la sauvegarde du serveur Palworld -- refresh periodique</footer>
  </div>
  </div>

  <div class="pal-modal-overlay" id="pal-modal-overlay" onclick="if (event.target === this) closePalModal()">
    <div class="pal-modal">
      <button class="pal-modal-close" onclick="closePalModal()">&times;</button>
      <div class="pal-modal-head">
        <img class="pal-modal-icon" id="pal-modal-icon" src="" alt="">
        <div>
          <div class="pal-modal-name" id="pal-modal-name"></div>
          <div class="pal-modal-elements" id="pal-modal-elements"></div>
        </div>
      </div>
      <div class="pal-modal-stats" id="pal-modal-stats"></div>
      <div class="pal-modal-section" id="pal-modal-apt-section">
        <h4>Meilleures aptitudes de travail</h4>
        <div class="pal-modal-apt" id="pal-modal-apt"></div>
      </div>
    </div>
  </div>

  <script>
    var PAL_DATA = {pal_data_json};
    function showTab(btn) {{
      var tabId = btn.getAttribute('data-tab');
      document.querySelectorAll('.tab-panel').forEach(function(p) {{ p.classList.remove('active'); }});
      document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      document.getElementById(tabId).classList.add('active');
      btn.classList.add('active');
      try {{ localStorage.setItem('palworld_dash_tab', tabId); }} catch (e) {{}}
    }}
    function goToTab(tabId) {{
      var btn = document.querySelector('.tab-btn[data-tab="' + tabId + '"]');
      if (btn) {{ showTab(btn); window.scrollTo({{top: 0, behavior: 'smooth'}}); }}
    }}
    function filterRecipes(btn) {{
      var filter = btn.getAttribute('data-filter');
      document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var cards = document.querySelectorAll('#recipe-grid > div[data-boosts]');
      var shown = 0;
      cards.forEach(function(card) {{
        var boosts = (card.getAttribute('data-boosts') || '').split(' ');
        var match = filter === 'tous' || boosts.indexOf(filter) !== -1;
        card.style.display = match ? '' : 'none';
        if (match) shown++;
      }});
      var emptyMsg = document.getElementById('recipe-empty-msg');
      if (emptyMsg) emptyMsg.style.display = shown === 0 ? '' : 'none';
    }}
    function sortBreeding(btn) {{
      var sortKey = btn.getAttribute('data-sort');
      var row = btn.parentElement;
      row.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var grid = document.getElementById('breed-grid');
      if (!grid) return;
      var cards = Array.prototype.slice.call(grid.querySelectorAll('div[data-nom]'));
      cards.sort(function(a, b) {{
        if (sortKey === 'nom') {{
          return a.getAttribute('data-nom').localeCompare(b.getAttribute('data-nom'));
        }}
        var av = parseInt(a.getAttribute('data-' + sortKey), 10);
        var bv = parseInt(b.getAttribute('data-' + sortKey), 10);
        return av - bv;
      }});
      cards.forEach(function(card) {{ grid.appendChild(card); }});
    }}
    var ELEMENT_LABEL = {{
      Neutral: '&#9898; Neutre', Fire: '&#128293; Feu', Water: '&#128167; Eau', Grass: '&#127807; Plante',
      Electric: '&#9889; Electrique', Ice: '&#10052;&#65039; Glace', Dark: '&#127761; Tenebres',
      Dragon: '&#128009; Dragon', Ground: '&#129688; Sol'
    }};
    function showPalCard(codename) {{
      var d = PAL_DATA[codename];
      if (!d) return;
      document.getElementById('pal-modal-icon').src = d.icon;
      document.getElementById('pal-modal-icon').alt = d.nom;
      document.getElementById('pal-modal-name').textContent = d.nom;
      document.getElementById('pal-modal-elements').innerHTML = (d.elements || []).map(function(e) {{
        return ELEMENT_LABEL[e] || e;
      }}).join(' &middot; ');
      var stats = '';
      if (d.hp != null) stats += '<div><span class="stat-label">PV</span> <span class="stat-value">' + d.hp + '</span></div>';
      if (d.atk != null) stats += '<div><span class="stat-label">Attaque (mêlée)</span> <span class="stat-value">' + d.atk + '</span></div>';
      if (d.atk_tir != null) stats += '<div><span class="stat-label">Attaque (tir)</span> <span class="stat-value">' + d.atk_tir + '</span></div>';
      if (d['def'] != null) stats += '<div><span class="stat-label">Defense</span> <span class="stat-value">' + d['def'] + '</span></div>';
      if (d.food != null) stats += '<div><span class="stat-label">Nourriture/repas</span> <span class="stat-value">' + d.food + '</span></div>';
      if (d.monture) stats += '<div><span class="stat-label">Vitesse monture</span> <span class="stat-value">' + d.monture + '</span></div>';
      if (d.rang_combi != null) stats += '<div><span class="stat-label">Rang combi (élevage)</span> <span class="stat-value">' + d.rang_combi + '</span></div>';
      document.getElementById('pal-modal-stats').innerHTML = stats || '<div class="pal-modal-empty">Stats non disponibles</div>';
      var aptSection = document.getElementById('pal-modal-apt-section');
      if (d.aptitudes && d.aptitudes.length) {{
        aptSection.style.display = '';
        document.getElementById('pal-modal-apt').innerHTML = d.aptitudes.map(function(a) {{
          return '<span>' + a[0] + ' ' + a[1] + '&#9733;</span>';
        }}).join('');
      }} else {{
        aptSection.style.display = 'none';
      }}
      document.getElementById('pal-modal-overlay').classList.add('open');
    }}
    function closePalModal() {{
      document.getElementById('pal-modal-overlay').classList.remove('open');
    }}
    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape') closePalModal();
    }});
    var PAL_ICON_FALLBACK = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64'%3E%3Crect width='64' height='64' rx='10' fill='%23232838'/%3E%3Ctext x='32' y='42' font-size='28' text-anchor='middle' fill='%23888'%3E%3F%3C/text%3E%3C/svg%3E";
    function palIconError(img) {{ img.onerror = null; img.src = PAL_ICON_FALLBACK; }}
    function showGuide(btn) {{
      var slug = btn.getAttribute('data-guide');
      document.querySelectorAll('#guide-selector .filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      document.querySelectorAll('.guide-panel').forEach(function(p) {{ p.style.display = 'none'; }});
      var panel = document.querySelector('.guide-panel[data-guide="' + slug + '"]');
      if (panel) panel.style.display = '';
    }}
    function palpediaShowPlayer(btn) {{
      var slug = btn.getAttribute('data-player');
      document.querySelectorAll('#palpedia-player-tabs .filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      document.querySelectorAll('.palpedia-player-panel').forEach(function(p) {{ p.style.display = 'none'; }});
      var panel = document.querySelector('.palpedia-player-panel[data-player="' + slug + '"]');
      if (panel) panel.style.display = '';
    }}
    var palpediaState = {{}};
    function palpediaGetState(slug) {{
      var st = palpediaState[slug];
      if (!st) {{
        st = {{page: 1, size: 20, status: 'missing', query: ''}};
        palpediaState[slug] = st;
      }}
      return st;
    }}
    function palpediaSetQuery(input, slug) {{
      var st = palpediaGetState(slug);
      st.query = (input.value || '').trim().toLowerCase();
      st.page = 1;
      palpediaRender(slug);
    }}
    function palpediaRender(slug) {{
      var st = palpediaGetState(slug);
      var grid = document.getElementById('palpedia-grid-' + slug);
      if (!grid) return;
      var allCards = Array.prototype.slice.call(grid.querySelectorAll('.palpedia-pal-card'));
      var matchesQuery = function(c) {{
        if (!st.query) return true;
        var name = c.querySelector('.palpedia-pal-name');
        return name && name.textContent.toLowerCase().indexOf(st.query) !== -1;
      }};
      var cards = allCards.filter(function(c) {{ return c.getAttribute('data-status') === st.status && matchesQuery(c); }});
      allCards.forEach(function(c) {{
        if (c.getAttribute('data-status') !== st.status || !matchesQuery(c)) c.style.display = 'none';
      }});
      var totalPages = Math.max(1, Math.ceil(cards.length / st.size));
      if (st.page > totalPages) st.page = totalPages;
      var start = (st.page - 1) * st.size, end = start + st.size;
      cards.forEach(function(c, i) {{ c.style.display = (i >= start && i < end) ? '' : 'none'; }});
      var info = document.getElementById('palpedia-pageinfo-' + slug);
      if (info) info.textContent = cards.length ? ('Page ' + st.page + ' / ' + totalPages + ' (' + cards.length + ' espèces)') : '';
      var empty = document.getElementById('palpedia-empty-' + slug);
      if (empty) empty.style.display = cards.length ? 'none' : '';
    }}
    function palpediaSetStatus(btn, slug) {{
      var status = btn.getAttribute('data-status');
      var row = btn.parentElement;
      row.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var st = palpediaGetState(slug);
      st.status = status;
      st.page = 1;
      palpediaRender(slug);
    }}
    function palpediaSetPageSize(btn, slug) {{
      var size = parseInt(btn.getAttribute('data-size'), 10);
      var row = btn.parentElement;
      row.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var st = palpediaGetState(slug);
      st.size = size;
      st.page = 1;
      palpediaRender(slug);
    }}
    function palpediaPage(slug, delta) {{
      var st = palpediaGetState(slug);
      st.page = Math.max(1, st.page + delta);
      palpediaRender(slug);
    }}
    document.querySelectorAll('.palpedia-player-panel').forEach(function(p) {{
      palpediaRender(p.getAttribute('data-player'));
    }});
    var KANBAN_API = '/api/tasks';
    var KANBAN_COLUMNS = ['todo', 'doing', 'done'];
    var kanbanTasks = [];
    function kanbanStatus(msg) {{
      var el = document.getElementById('kanban-status');
      if (el) el.textContent = msg || '';
    }}
    function kanbanLoad() {{
      fetch(KANBAN_API).then(function(r) {{
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }}).then(function(data) {{
        kanbanTasks = data;
        kanbanStatus('');
        kanbanRender();
      }}).catch(function() {{
        kanbanStatus('Impossible de charger les taches (service indisponible pour le moment).');
      }});
    }}
    function kanbanCardEl(t, colIdx) {{
      var card = document.createElement('div');
      card.className = 'kanban-card';
      card.draggable = true;
      card.dataset.id = t.id;
      card.addEventListener('dragstart', function(e) {{
        e.dataTransfer.setData('text/plain', String(t.id));
        card.classList.add('dragging');
      }});
      card.addEventListener('dragend', function() {{ card.classList.remove('dragging'); }});
      var title = document.createElement('div');
      title.className = 'kanban-card-title';
      title.textContent = t.title;
      card.appendChild(title);
      if (t.description) {{
        var desc = document.createElement('div');
        desc.className = 'kanban-card-desc';
        desc.textContent = t.description;
        card.appendChild(desc);
      }}
      var actions = document.createElement('div');
      actions.className = 'kanban-card-actions';
      var move = document.createElement('div');
      move.className = 'kanban-card-move';
      if (colIdx > 0) {{
        var left = document.createElement('button');
        left.type = 'button';
        left.textContent = '←';
        left.onclick = function() {{ kanbanMove(t.id, KANBAN_COLUMNS[colIdx - 1]); }};
        move.appendChild(left);
      }}
      if (colIdx < KANBAN_COLUMNS.length - 1) {{
        var right = document.createElement('button');
        right.type = 'button';
        right.textContent = '→';
        right.onclick = function() {{ kanbanMove(t.id, KANBAN_COLUMNS[colIdx + 1]); }};
        move.appendChild(right);
      }}
      actions.appendChild(move);
      var del = document.createElement('button');
      del.type = 'button';
      del.className = 'kanban-card-del';
      del.textContent = '×';
      del.onclick = function() {{ kanbanDelete(t.id); }};
      actions.appendChild(del);
      card.appendChild(actions);
      return card;
    }}
    function kanbanRender() {{
      KANBAN_COLUMNS.forEach(function(col, colIdx) {{
        var body = document.getElementById('kanban-col-' + col);
        if (!body) return;
        body.innerHTML = '';
        var items = kanbanTasks.filter(function(t) {{ return t.column === col; }})
          .sort(function(a, b) {{ return a.position - b.position; }});
        var countEl = document.getElementById('kanban-count-' + col);
        if (countEl) countEl.textContent = items.length;
        items.forEach(function(t) {{ body.appendChild(kanbanCardEl(t, colIdx)); }});
      }});
    }}
    function kanbanAddTask() {{
      var input = document.getElementById('kanban-new-title');
      var title = (input.value || '').trim();
      if (!title) return;
      fetch(KANBAN_API, {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{title: title, column: 'todo'}})
      }}).then(function(r) {{ return r.json(); }}).then(function(task) {{
        kanbanTasks.push(task);
        kanbanRender();
        input.value = '';
        kanbanStatus('');
      }}).catch(function() {{ kanbanStatus("Erreur lors de l'ajout."); }});
    }}
    function kanbanMove(id, newColumn) {{
      fetch(KANBAN_API + '/' + id, {{
        method: 'PATCH', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{column: newColumn}})
      }}).then(function(r) {{ return r.json(); }}).then(function(updated) {{
        kanbanTasks = kanbanTasks.map(function(t) {{ return t.id === updated.id ? updated : t; }});
        kanbanRender();
      }}).catch(function() {{ kanbanStatus('Erreur lors du deplacement.'); }});
    }}
    function kanbanDelete(id) {{
      fetch(KANBAN_API + '/' + id, {{method: 'DELETE'}}).then(function() {{
        kanbanTasks = kanbanTasks.filter(function(t) {{ return t.id !== id; }});
        kanbanRender();
      }}).catch(function() {{ kanbanStatus('Erreur lors de la suppression.'); }});
    }}
    function kanbanDragOver(e) {{
      e.preventDefault();
      var col = e.currentTarget.closest('.kanban-column');
      if (col) col.classList.add('drag-over');
    }}
    function kanbanDrop(e, column) {{
      e.preventDefault();
      var col = e.currentTarget.closest('.kanban-column');
      if (col) col.classList.remove('drag-over');
      var id = parseInt(e.dataTransfer.getData('text/plain'), 10);
      if (id) kanbanMove(id, column);
    }}
    document.querySelectorAll('.kanban-col-body').forEach(function(body) {{
      body.addEventListener('dragleave', function() {{
        var col = body.closest('.kanban-column');
        if (col) col.classList.remove('drag-over');
      }});
    }});
    var kanbanNewInput = document.getElementById('kanban-new-title');
    if (kanbanNewInput) {{
      kanbanNewInput.addEventListener('keydown', function(e) {{ if (e.key === 'Enter') kanbanAddTask(); }});
    }}
    kanbanLoad();
    (function() {{
      try {{
        var saved = localStorage.getItem('palworld_dash_tab');
        if (saved) {{
          var btn = document.querySelector('.tab-btn[data-tab="' + saved + '"]');
          if (btn) showTab(btn);
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>
"""
    return html


def load_previous_snapshot():
    if os.path.exists(LOCAL_SNAPSHOT):
        with open(LOCAL_SNAPSHOT, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_snapshot(data):
    with open(LOCAL_SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


HISTORY_FILE = os.path.join(HERE, "palworld_history.jsonl")
MAX_HISTORY_ENTRIES = 500


def append_history(data):
    entry = {
        "t": datetime.datetime.now().strftime("%d/%m %Hh%M"),
        "jours": data["monde"]["jours"],
        "pals_total": data["pals"]["total"],
        "pals_especes": data["pals"]["especes"],
        "joueurs": [{"nom": j["nom"], "niveau": j["niveau"], "xp": j["xp"]} for j in data["joueurs"]],
    }
    lines = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    lines.append(json.dumps(entry, ensure_ascii=False) + "\n")
    lines = lines[-MAX_HISTORY_ENTRIES:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return [json.loads(l) for l in lines]


def compute_diff_lines(old, new):
    if old is None:
        return ["Première exécution -- pas de comparaison possible."]

    lines = []

    old_pals = old.get("pals", {})
    new_pals = new.get("pals", {})
    d_total = new_pals.get("total", 0) - old_pals.get("total", 0)
    d_esp = new_pals.get("especes", 0) - old_pals.get("especes", 0)
    if d_total:
        lines.append(f"Pals total : {old_pals.get('total')} -> {new_pals.get('total')} ({'+' if d_total>0 else ''}{d_total})")
    if d_esp:
        lines.append(f"Espèces différentes : {old_pals.get('especes')} -> {new_pals.get('especes')} ({'+' if d_esp>0 else ''}{d_esp})")

    old_players = {p["nom"]: p for p in old.get("joueurs", [])}
    for p in new.get("joueurs", []):
        name = p["nom"]
        op = old_players.get(name)
        if op is None:
            lines.append(f"{name} : nouveau joueur detecte (niveau {p['niveau']})")
            continue

        d_lvl = p["niveau"] - op["niveau"]
        d_xp = p["xp"] - op["xp"]
        d_quests = p.get("quetes_completees", 0) - op.get("quetes_completees", 0)
        d_recipes = p.get("recettes_debloquees", 0) - op.get("recettes_debloquees", 0)
        d_boss_tour = len(p.get("boss_tour", [])) - len(op.get("boss_tour", []))
        d_boss_monde = p.get("boss_monde", 0) - op.get("boss_monde", 0)

        parts = []
        if d_lvl:
            parts.append(f"niveau {'+' if d_lvl>0 else ''}{d_lvl}")
        if d_xp:
            parts.append(f"XP {'+' if d_xp>0 else ''}{d_xp:,}")
        if d_quests:
            parts.append(f"quêtes {'+' if d_quests>0 else ''}{d_quests}")
        if d_recipes:
            parts.append(f"recettes {'+' if d_recipes>0 else ''}{d_recipes}")
        if d_boss_tour:
            parts.append(f"boss de tour {'+' if d_boss_tour>0 else ''}{d_boss_tour}")
        if d_boss_monde:
            parts.append(f"boss du monde {'+' if d_boss_monde>0 else ''}{d_boss_monde}")

        if parts:
            lines.append(f"{name} : " + ", ".join(parts))

    return lines


def post_diff_notification(diff_lines):
    if not diff_lines:
        return  # rien de nouveau, pas de notif
    content = "**Mise a jour Palworld (dernière heure)**\n\n" + "\n".join(f"- {l}" for l in diff_lines)
    payload = json.dumps({"content": content}).encode("utf-8")
    import urllib.request
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; PalworldStatusBot/1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print("Discord diff notification code:", resp.status)


def deploy(local_html_path):
    remote_tmp = "/tmp/palworld_dashboard.html"
    subprocess.run(
        [SCP_EXE, "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", local_html_path,
         f"root@{PROXMOX_HOST}:{remote_tmp}"],
        check=True,
    )
    subprocess.run(
        [SSH_EXE, "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"root@{PROXMOX_HOST}",
         f"pct push 111 {remote_tmp} /opt/palworld/results/dashboard.html && rm {remote_tmp}"],
        check=True,
    )


def main():
    previous = load_previous_snapshot()
    data = collect_data()

    diff_lines = compute_diff_lines(previous, data)
    for l in diff_lines:
        print("DIFF:", l.encode("ascii", "replace").decode())
    post_diff_notification(diff_lines)

    data["history"] = append_history(data)

    html = render_html(data)
    with open(LOCAL_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("Local HTML written:", LOCAL_HTML)
    deploy(LOCAL_HTML)
    print("Deployed to palworld.pollice.dev")

    save_snapshot(data)


if __name__ == "__main__":
    main()
