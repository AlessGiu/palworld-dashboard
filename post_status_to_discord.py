import io
import os
import sys
import json
import contextlib
import datetime
import urllib.request

import paramiko

from secrets_local import SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASS, WEBHOOK_URL

REMOTE_SAVE_DIR = "/Pal/Saved/SaveGames/0/D5C16DC3464E7CC492225ABB991F1FA2"
REMOTE_LEVEL_SAV = REMOTE_SAVE_DIR + "/Level.sav"

OOZ_DLL_PATH = os.path.join(
    os.path.dirname(__file__), "palworld-hostfix-toolkit", "ooz", "libooz.dll"
)
os.environ["PALWORLD_OOZ_DLL_PATH"] = OOZ_DLL_PATH

LOCAL_TMP = os.path.join(os.path.dirname(__file__), "status_check_Level.sav")

IGNORED_PLAYER_NAMES = {"skP"}


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


def stat_points_table(field):
    if not isinstance(field, dict):
        return "```\naucun point depense\n```"
    values = field.get("value", {})
    if isinstance(values, dict):
        values = values.get("values", [])
    rows = []
    for entry in values:
        raw_name = unwrap(entry.get("StatusName"), "?")
        pts = unwrap(entry.get("StatusPoint"), 0)
        if pts:
            rows.append((STAT_NAME_FR.get(raw_name, raw_name), pts))
    if not rows:
        return "```\naucun point depense\n```"
    width = max(len(n) for n, _ in rows)
    lines = [f"{n.ljust(width)}  +{p}" for n, p in rows]
    return "```\n" + "\n".join(lines) + "\n```"


import re


def prettify_boss_name(name):
    name = name.replace("BOSS_BATTLE_NAME_", "").replace("_", " ")
    name = re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()
    return name


PLATFORM_FR = {
    "EPalPlayerPlatform::Steam": "Steam",
    "EPalPlayerPlatform::Xbox": "Xbox",
    "EPalPlayerPlatform::PS": "PlayStation",
}


def dotnet_ticks_to_days_ago(ticks):
    dt = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=ticks / 10)
    delta = datetime.datetime.now() - dt
    return delta.total_seconds() / 86400


def download_level_sav():
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.get(REMOTE_LEVEL_SAV, LOCAL_TMP)
    sftp.close()
    transport.close()


def download_player_sav(uid_str):
    filename = uid_str.replace("-", "").upper() + ".sav"
    local_path = os.path.join(os.path.dirname(__file__), "status_check_" + filename)
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.get(REMOTE_SAVE_DIR + "/Players/" + filename, local_path)
    sftp.close()
    transport.close()
    return local_path


def load_player_save_data(local_path):
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
    os.remove(local_path)
    return json_data["properties"]["SaveData"]["value"]


def load_world_save_data():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from palworld_save_tools.gvas import GvasFile
        from palworld_save_tools.palsav import decompress_sav_to_gvas
        from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

        with open(LOCAL_TMP, "rb") as f:
            data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)
        gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True)
        json_data = gvas_file.dump()
    return json_data["properties"]["worldSaveData"]["value"]


def build_embeds(wsd):
    char_map = wsd["CharacterSaveParameterMap"]["value"]

    players = []
    pals = []
    for e in char_map:
        raw = e["value"]["RawData"]["value"]
        obj = raw.get("object", {}) if isinstance(raw, dict) else {}
        sp = obj.get("SaveParameter", {}).get("value", {}) if isinstance(obj, dict) else {}
        if sp.get("IsPlayer", {}).get("value", False):
            uid = e["key"]["PlayerUId"]["value"]
            if unwrap(sp.get("NickName"), "?") not in IGNORED_PLAYER_NAMES:
                players.append((str(uid), sp))
        else:
            pals.append(sp)

    uid_to_name = {uid: unwrap(sp.get("NickName"), "?") for uid, sp in players}

    embeds = []

    # --- EMBED 1 : MONDE ---
    gt = wsd["GameTimeSaveData"]["value"]
    ticks = gt["GameDateTimeTicks"]["value"]
    days = ticks / (10_000_000 * 60 * 60 * 24)

    invaders = wsd["InvaderSaveData"]["value"]
    active_raids = sum(1 for e in invaders if e["value"].get("bIsInvading", {}).get("value"))

    camps = wsd["EnemyCampSaveData"]["value"]["EnemyCampStatusMap"]["value"]
    camps_cleared = sum(1 for c in camps if c["value"].get("bIsClear", {}).get("value"))

    dungeon_markers = len(wsd["DungeonPointMarkerSaveData"]["value"]["values"])
    num_bases = len(wsd["BaseCampSaveData"]["value"])

    embeds.append({
        "title": "\U0001F30D Monde",
        "color": 0x3498DB,
        "fields": [
            {"name": "Jours ecoules", "value": f"**{days:.0f}**", "inline": True},
            {"name": "Bases", "value": f"**{num_bases}**", "inline": True},
            {"name": "Raids en cours", "value": f"**{active_raids}/{len(invaders)}**", "inline": True},
            {"name": "Camps ennemis nettoyes", "value": f"**{camps_cleared}/{len(camps)}**", "inline": True},
            {"name": "Reperes de donjon", "value": f"**{dungeon_markers}**", "inline": True},
        ],
    })

    # --- EMBED 2 : JOUEURS (un embed par joueur) ---
    for uid, p in players:
        name = unwrap(p.get("NickName"), "?")
        level = unwrap(p.get("Level"), 1)
        exp = unwrap(p.get("Exp"), 0)
        stomach = safe_float(unwrap(p.get("FullStomach"), 0))
        shield = safe_float(unwrap(p.get("ShieldHP"), 0))
        stat_table = stat_points_table(p.get("GotStatusPointList"))

        fields = [
            {"name": "Niveau", "value": f"**{level}**  ({exp:,} XP)", "inline": True},
            {"name": "Faim", "value": f"**{stomach:.0f}**/100", "inline": True},
            {"name": "Bouclier", "value": f"**{shield:.0f}**", "inline": True},
        ]

        try:
            local_path = download_player_sav(uid)
            psd = load_player_save_data(local_path)

            last_online_ticks = unwrap(psd.get("LastOnlineDateTime"), None)
            if last_online_ticks:
                days_ago = dotnet_ticks_to_days_ago(last_online_ticks)
                if days_ago < 0.04:
                    last_online_txt = "en ce moment"
                elif days_ago < 1:
                    last_online_txt = f"il y a {days_ago*24:.0f}h"
                else:
                    last_online_txt = f"il y a {days_ago:.0f}j"
            else:
                last_online_txt = "inconnu"

            platform_raw = unwrap(psd.get("PlayerPlatform"), None)
            platform_txt = PLATFORM_FR.get(platform_raw, platform_raw or "inconnue")

            boss_pts = unwrap(psd.get("bossTechnologyPoint"), 0)

            quests = psd.get("CompletedQuestArray_FullRelease")
            num_quests = 0
            if isinstance(quests, dict):
                qv = quests.get("value", {})
                num_quests = len(qv.get("values", [])) if isinstance(qv, dict) else 0

            recipes = psd.get("UnlockedRecipeTechnologyNames")
            num_recipes = 0
            if isinstance(recipes, dict):
                rv = recipes.get("value", {})
                num_recipes = len(rv.get("values", [])) if isinstance(rv, dict) else 0

            fields.append({"name": "Derniere connexion", "value": f"**{last_online_txt}**", "inline": True})
            fields.append({"name": "Plateforme", "value": platform_txt, "inline": True})
            fields.append({"name": "Points tech. boss", "value": f"**{boss_pts}**", "inline": True})
            fields.append({"name": "Quetes completees", "value": f"**{num_quests}**", "inline": True})
            fields.append({"name": "Recettes debloquees", "value": f"**{num_recipes}**", "inline": True})

            rd = psd.get("RecordData")
            rd_val = rd.get("value", {}) if isinstance(rd, dict) else {}

            tower_flags = rd_val.get("TowerBossDefeatFlag", {}).get("value", [])
            tower_names = [prettify_boss_name(e["key"]) for e in tower_flags if e.get("value")]

            world_flags = rd_val.get("NormalBossDefeatFlag", {}).get("value", [])
            num_world_bosses = sum(1 for e in world_flags if e.get("value"))

            fields.append({
                "name": "\U0001F451 Boss de tour vaincus",
                "value": (f"**{len(tower_names)}** -- " + ", ".join(tower_names)) if tower_names else "aucun",
                "inline": False,
            })
            fields.append({"name": "\U0001F480 Boss du monde vaincus", "value": f"**{num_world_bosses}**", "inline": True})

            oqa = psd.get("OrderedQuestArray_FullRelease")
            oqa_vals = oqa.get("value", {}).get("values", []) if isinstance(oqa, dict) else []
            current_quest = prettify_boss_name(unwrap(oqa_vals[0].get("QuestName"), "aucune")) if oqa_vals else "aucune"
            fields.append({"name": "\U0001F4CC Quete en cours", "value": current_quest, "inline": True})
        except Exception as exc:
            fields.append({"name": "Donnees joueur", "value": f"indisponibles ({exc})", "inline": False})

        fields.append({"name": "Points de statut", "value": stat_table, "inline": False})

        embeds.append({
            "title": f"\U0001F464 {name}",
            "color": 0x9B59B6,
            "fields": fields,
        })

    # --- EMBED 3 : PALS ---
    species = set()
    owners = {}
    for p in pals:
        species.add(unwrap(p.get("CharacterID"), "?"))
        owner = unwrap(p.get("OwnerPlayerUId"), None)
        owner_key = str(owner) if owner else None
        display = uid_to_name.get(owner_key, "Sans proprietaire")
        owners[display] = owners.get(display, 0) + 1

    owner_lines = "\n".join(f"• {k} : **{v}**" for k, v in owners.items())

    top_level = sorted(pals, key=lambda p: unwrap(p.get("Level"), 1), reverse=True)[:5]
    top_niveaux = "\n".join(
        f"{i+1}. {unwrap(p.get('CharacterID'))} (lvl {unwrap(p.get('Level'))})"
        for i, p in enumerate(top_level)
    ) or "aucun"

    top_friend = sorted(pals, key=lambda p: safe_float(unwrap(p.get("FriendshipPoint"), 0)), reverse=True)[:3]
    top_affection = "\n".join(
        f"{i+1}. {unwrap(p.get('CharacterID'))} ({int(safe_float(unwrap(p.get('FriendshipPoint')))):,})"
        for i, p in enumerate(top_friend)
    ) or "aucun"

    def iv_score(p):
        return safe_float(unwrap(p.get("Talent_HP"), 0)) + safe_float(unwrap(p.get("Talent_Shot"), 0)) + safe_float(unwrap(p.get("Talent_Defense"), 0))

    def passives_txt(p):
        pl = p.get("PassiveSkillList")
        if not isinstance(pl, dict):
            return ""
        vals = pl.get("value", {})
        names = vals.get("values", []) if isinstance(vals, dict) else []
        return (f"\n> *{', '.join(names)}*") if names else ""

    best_iv = sorted(pals, key=iv_score, reverse=True)[:5]
    iv_txt = "\n".join(
        f"{i+1}. **{unwrap(p.get('CharacterID'))}** -- ❤️ {unwrap(p.get('Talent_HP'))}% / "
        f"⚔️ {unwrap(p.get('Talent_Shot'))}% / \U0001F6E1️ {unwrap(p.get('Talent_Defense'))}%{passives_txt(p)}"
        for i, p in enumerate(best_iv)
    ) or "aucun"

    embeds.append({
        "title": "\U0001F43E Pals",
        "color": 0xF1C40F,
        "fields": [
            {"name": "Total", "value": f"**{len(pals)}** Pals -- **{len(species)}** especes", "inline": False},
            {"name": "Repartition", "value": owner_lines, "inline": False},
            {"name": "\U0001F3C6 Top 5 Niveaux", "value": top_niveaux, "inline": True},
            {"name": "❤️ Top 3 Affection", "value": top_affection, "inline": True},
            {"name": "\U0001F48E Top 5 IV + Passifs", "value": iv_txt, "inline": False},
        ],
    })

    # --- EMBED 4 : BASE / GUILDE ---
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

    embeds.append({
        "title": "\U0001F3E0 Base & Guilde",
        "color": 0x2ECC71,
        "fields": [
            {"name": "Bases", "value": f"**{len(bc)}**", "inline": True},
            {"name": "Guildes actives", "value": f"**{num_guilds}**", "inline": True},
            {"name": "Coffres de guilde", "value": f"**{len(guild_extra)}**", "inline": True},
            {"name": "Modules actifs", "value": ", ".join(module_types) if module_types else "aucun", "inline": False},
            {"name": "\U0001F4E6 Dernier largage", "value": f"`{last_supply_guid[:8]}...`", "inline": False},
        ],
    })

    return embeds


def post_to_discord(embeds):
    # Discord webhook allows max 10 embeds per message
    payload = json.dumps({"embeds": embeds[:10]}).encode("utf-8")
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
        print("Discord response code:", resp.status)


def main():
    download_level_sav()
    wsd = load_world_save_data()
    embeds = build_embeds(wsd)
    for e in embeds:
        print("===", e["title"].encode("ascii", "replace").decode(), "===")
        for f in e["fields"]:
            print(" -", f["name"].encode("ascii", "replace").decode(), ":",
                  f["value"].encode("ascii", "replace").decode())
        print()
    post_to_discord(embeds)
    os.remove(LOCAL_TMP)


if __name__ == "__main__":
    main()
