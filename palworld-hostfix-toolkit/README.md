# Palworld Host-Save Fix Toolkit (Post-"Tides of Terraria" / Oodle Update)

Complete toolkit for migrating a Palworld **co-op save to a dedicated server** (and back) on game versions after the 2026 Summer Update ("Tides of Terraria"), which broke all existing community tools in two ways:

1. **New save compression**: `.sav` files are now Oodle-compressed (magic bytes `PlM1` instead of `PlZ`). `palworld-save-tools` (up to at least v0.24.0) cannot read them.
2. **Changed binary struct layouts** inside `Level.sav` (guild data, work data, map objects, etc.) that make the old decoders crash even after decompression.

On top of that, the classic **host-GUID migration bug** turned out to have FOUR distinct layers on the new version — fixing only the ones the old `xNul/palworld-host-save-fix` tool knew about leaves your character working but **all pals silently deleted by the dedicated server on load**.

Built & battle-tested 2026-07-13 by walking a real 4-player co-op world onto a Windows dedicated server, with every failure mode encountered and solved along the way.

> **Disclaimer**: Not affiliated with or endorsed by Pocketpair. These scripts edit save files by directly parsing/patching their binary structure — always back up your world folder before running anything here. Use at your own risk.

---

## Folder contents

| Folder | What it is |
|---|---|
| `ooz/` | Not committed to this repo. Run `python scripts/fetch_ooz.py` to download `libooz.dll` straight from the [zao/ooz](https://github.com/zao/ooz) v0.2.4 release into `ooz/`. It's a reimplementation of Oodle Kraken decompression, fetched on demand rather than redistributed here since upstream has no explicit license. |
| `patched_palworld_save_tools/` | Patched copies of [cheahjs/palworld-save-tools](https://github.com/cheahjs/palworld-save-tools) (MIT licensed, base: v0.24.0) files. Drop these over your installed package (`pip install -r requirements.txt` first, then overwrite). |
| `scripts/migrate/` | The scripts you actually run to do the migration. |
| `scripts/diagnostics/` | Tools for when things still go wrong after migrating (see table below). |
| `scripts/dev/` | Exploration/debugging one-offs from the original investigation. Not needed for normal use — kept for reference. |

## Setup

1. Python ≥ 3.10
2. `pip install -r requirements.txt`
3. Overwrite the installed package files with the ones in `patched_palworld_save_tools/` (find the install dir with `pip show palworld-save-tools`). Back up the originals first.
4. `python scripts/fetch_ooz.py` — downloads `libooz.dll` from the upstream zao/ooz release into `ooz/`.
5. Set the env var so the patched loader can find the Oodle decompressor:
   `set PALWORLD_OOZ_DLL_PATH=<full path to ooz\libooz.dll>`
   (or copy `.env.example` to `.env` and fill it in)

### What the patches do

- `palsav.py`: detects `PlM` magic and decompresses via `libooz.dll` (ctypes). **Write-back always uses plain zlib (`PlZ`)** — the game still accepts zlib-compressed saves, so Oodle *compression* is never needed.
- `rawdata/*.py`: two generic hardening patterns for the new struct layouts:
  - *trailing-bytes preservation*: unknown appended fields are captured opaquely (`trailing_bytes`) and written back byte-for-byte;
  - *raw fallback*: if a decoder fails mid-struct, the data is kept as raw bytes instead of crashing, and encoders skip re-encoding anything still raw (`if "values" not in ...` guards).
- Also fixes a pre-existing crash in `work.py` (`writer.write(list)` → needs `bytes(...)`).

### GUID byte-order gotcha (important if you write your own scripts)

On-disk GUIDs use **Microsoft-style mixed-endian byte order**, NOT sequential hex. Always build binary search patterns with the library's own class:
```python
from palworld_save_tools.archive import UUID
raw = UUID.from_str("aa018782-0000-0000-0000-000000000000").raw_bytes
```
`bytes.fromhex(...)` will silently find zero matches.

---

## The migration procedure (co-op → dedicated server)

Old host GUID in co-op saves is always `00000000-0000-0000-0000-000000000001`.
The "new GUID" is generated when the host first joins the dedicated server.

1. Copy the co-op world folder from `%LOCALAPPDATA%\Pal\Saved\SaveGames\<steamid>\<worldid>` to `PalServer\Pal\Saved\SaveGames\0\`.
2. Set `DedicatedServerName=<worldid>` in `PalServer\Pal\Saved\Config\WindowsServer\GameUserSettings.ini`. Delete the world's `WorldOption.sav` (back it up; only resets respawn points).
3. Start the server, have the **host** join once (creates a new empty character). The new file that appears in `Players\` is the host's new GUID. Stop the server.
4. Run the classic fix (character merge — layer 0):
   `python scripts/migrate/fix_host_save.py <world_path> <NEW_GUID> 00000000000000000000000000000001 False`
5. Run the three additional layers (all operate on `<world_path>/Level.sav`):
   - **Layer 1+2 — pal map keys & internal owners**:
     `python scripts/migrate/fix_pal_keys.py <world_path>/Level.sav <new-guid-formatted> 00000000-0000-0000-0000-000000000001`
     Re-keys every `IsPlayer=False` entry in `CharacterSaveParameterMap` to the zero GUID (the dedicated server **deletes** any pal keyed to a nonzero PlayerUId) and retargets `OwnerPlayerUId`/`OldOwnerPlayerUIds` to the new GUID.
   - **Layer 3 — guild member handles**:
     `python scripts/migrate/fix_guild_handles.py <world_path>/Level.sav`
     In `GroupSaveDataMap` guild blobs, each pal's membership handle must carry the **zero GUID** (players keep their real GUIDs). Wrong handles ⇒ guild dissolves on load + pals purged.
   - **Layer 4 — character container slots** (the one nobody knew about):
     `python scripts/migrate/fix_container_slots.py <world_path>/Level.sav`
     Every slot in `CharacterContainerSaveData` (party / palbox / base containers) carries its own `player_uid` field. If it points at the old host GUID (a player that doesn't exist on the server), the server empties the slot and garbage-collects the pal. Must be zeroed.
6. Start the server and verify pals in-game **within the first minutes**. If anything is still wrong, STOP THE SERVER IMMEDIATELY — it autosaves (~30s interval) and will overwrite your fixed file with the broken in-memory state.

### Reverse direction (dedicated → co-op)

Same idea with GUIDs swapped: `fix_host_save.py <path> 00000000000000000000000000000001 <DEDICATED_GUID> False`, and the guild raw-blob references can be fixed with `scripts/migrate/fix_orphaned_ownership.py` (raw byte-pattern GUID replacement inside undecoded guild blobs — handles the new guild struct that can't be parsed yet).

---

## Diagnostic scripts (for when things still go wrong)

All under `scripts/diagnostics/`.

| Script | Purpose |
|---|---|
| `recount_char_map.py` | Count `CharacterSaveParameterMap` entries per PlayerUId key — the fastest "did the server purge my pals" check |
| `count_owners.py` | Pal counts per internal `OwnerPlayerUId` |
| `analyze_guild_handles.py` | Dump guild membership handle GUIDs matched to known character instances |
| `inspect_containers.py` | Dump container slots incl. the per-slot `player_uid` field |
| `list_groups_and_refs.py` | Cross-reference char-entry `group_id`s against existing groups |
| `compare_pal_entry.py` | Field-by-field dump of pal entries for diffing against a healthy world |
| `trace_test.py` / `roundtrip_test.py` | Verify a `.sav` parses and survives a lossless round trip |

`scripts/dev/` holds the rest of the one-off exploration scripts from the original investigation (byte-pattern searches, struct brute-forcing, etc.) — not needed for normal use, kept for reference if you're debugging a new struct layout change yourself.

## Verification methodology that cracked it

Run the dedicated server **headlessly yourself** (no player needed) — the purge happens at world load, and the server autosaves every ~30s. Deploy candidate file → start `PalServer.exe` → wait ~90s → stop → recount entries. This turns a slow "ask a friend to join and look" loop into a 2-minute automated test. Also: the server keeps timestamped world backups in `<world>\backup\world\` on every load — great forensics.
