#!/usr/bin/env python3
"""Chapter 4, The Lower Stvor. Static only: letters, mail ahead, map join, assets."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def letter_blocks(text, n):
    match = re.search(r"^## Письмо %d\..*?$(.*?)(?=^## )" % n, text, re.S | re.M)
    assert match, n
    blocks, cur = [], []
    for ln in match.group(1).split("\n"):
        if ln.startswith(">"):
            cur.append(ln[2:] if ln.startswith("> ") else ln[1:])
        elif cur:
            blocks.append("\n".join(cur).strip())
            cur = []
    if cur:
        blocks.append("\n".join(cur).strip())
    return blocks


canon = (ROOT / "docs/canon/letters-ch4.md").read_text(encoding="utf-8")
timeline = (ROOT / "docs/canon/chapter4-timeline.md").read_text(encoding="utf-8")
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter4_story.json").read_text(encoding="utf-8"))
world = json.loads((ROOT / "Postman/GameAssets/Data/world.json").read_text(encoding="utf-8"))
stvor = json.loads((ROOT / "Postman/GameAssets/UI/map/stvor.json").read_text(encoding="utf-8"))
items = {item["id"]: item for item in story["items"]}
events = {event["id"]: event for event in story["events"]}

blocks = {n: letter_blocks(canon, n) for n in range(1, 11)}
for n in (1, 2, 3, 4, 5, 6, 7, 8, 10):
    if not blocks[n]:
        fail(f"canon letter {n} has no quoted body")
    elif items[f"l{n}"]["text"] != blocks[n][0]:
        fail(f"l{n} is not the edited letter")
if blocks[9]:
    fail("letter 9 grew a quoted body; texts must stay unopened")
if "не вскрывать" not in items["l9"]["text"]:
    fail("l9 does not say the texts are not to be opened")

for banned in ("Тишина", "сорок один", "41 имён", "Город молчания"):
    blob = "\n".join(item["text"] for item in story["items"])
    if banned in blob:
        fail(f"a letter contains {banned}")

# K-2 must not be named out loud in player-facing chapter 4 copy.
spoken = json.dumps({"items": story["items"], "events": story["events"],
                     "fates": story.get("fates"), "arrivals": story.get("arrivals"),
                     "quests": story.get("quests"), "finaleTitle": story.get("finaleTitle"),
                     "nextChapter": story.get("nextChapter")}, ensure_ascii=False)
if "К-2" in spoken or "K-2" in spoken:
    fail("chapter 4 names K-2 out loud")

VALID_STATUS = {"atPost", "onRoad", "inBag", "inPocket", "delivered", "sent", "lostWind", "leftBehind", "read"}
for item in story["items"]:
    if item.get("initial") not in VALID_STATUS:
        fail(f"{item['id']} initial is not a valid ItemStatus: {item.get('initial')}")

chapter = next(c for c in world["chapters"] if c["id"] == 4)
if chapter["startStep"] != 75000 or chapter["lengthSteps"] != 45000:
    fail(f"chapter 4 is not world steps 75000–120000: {chapter['startStep']} + {chapter['lengthSteps']}")
if chapter["title"] != "Нижний Створ":
    fail("chapter 4 title is not Нижний Створ")
if chapter.get("assetsFolder") not in ("Chapter4", None) and chapter.get("folder") not in ("Chapter4", None):
    # accept either key used by world.json
    pass
folder = chapter.get("assetsFolder") or chapter.get("folder")
if folder != "Chapter4":
    fail(f"chapter 4 assets folder is {folder}")

ch3 = next(c for c in world["chapters"] if c["id"] == 3)
if ch3["startStep"] + ch3["lengthSteps"] != 75000:
    fail("chapter 3 does not end where chapter 4 starts")
ch3_story = json.loads((ROOT / "Postman/GameAssets/Data/chapter3_story.json").read_text(encoding="utf-8"))
if ch3_story["nextChapter"] != "Глава 4 «Нижний Створ»":
    fail(f"chapter 3 nextChapter is {ch3_story['nextChapter']!r}")
if "скоро" in ch3_story["nextChapter"]:
    fail("chapter 3 still says chapter 4 is only coming")
if "Город молчания" in ch3_story["nextChapter"]:
    fail("chapter 3 still uses the working title")
if story["nextChapter"] != "Глава 5 «Край карты» — скоро":
    fail("chapter 4 hook is not «Край карты» — скоро")
if "Город молчания" in story.get("finaleTitle", "") or "Город молчания" in story.get("nextChapter", ""):
    fail("chapter 4 finale uses the working title")

# t431: pickup and the drop are both still ahead; read-in-place letters have no delivery.
drops = {
    "l1": "d_otstoyniki",
    "l2": "d_kotelnaya",
    "l3": "d_sarai",
    "l4": "d_sarai",
    "l5": "d_otdelenie",  # Nyura gets it only through the e_address answer (effects)
    "l7": "d_otdelenie",
}
read_here = {"l6", "l8", "l10"}
pickup = {
    "l1": "p_l1", "l2": "p_l2", "l3": "p_l3", "l4": "p_l4", "l5": "p_l5",
    "l6": "p_l6", "l7": "p_l7", "l8": "p_l8", "l9": "p_l9", "l10": "p_l10",
}
behind_ids = set()
for c in world["chapters"]:
    if c["id"] < 4:
        behind_ids.update(s["id"] for s in c["settlements"])

bag = (ROOT / "Postman/App/BagPolicy.swift").read_text(encoding="utf-8")
for item_id, ev_id in drops.items():
    if ev_id not in events:
        fail(f"missing drop event {ev_id} for {item_id}")
        continue
    drop = events[ev_id]
    pick = events[pickup[item_id]]
    if pick["step"] >= drop["step"] and item_id != "l5":
        # l5 is picked at the sheds (28000) and the address choice is at 36500
        fail(f"{item_id} drop is not ahead of pickup: {pick['step']} -> {drop['step']}")
    if drop["type"] != "scene" and ev_id != "e_address":
        fail(f"{ev_id} must be a scene like chapter 3 deliveries, not {drop['type']}")
    if items[item_id]["settlement"] in behind_ids or drop.get("settlement") in behind_ids:
        fail(f"{item_id} is routed behind the chapter")
    if f'case (4, "{item_id}")' not in bag:
        fail(f"BagPolicy has no chapter 4 drop for {item_id}")
for item_id in read_here:
    if item_id in drops:
        fail(f"{item_id} is read in place but has a delivery")
    # no bag drop case should send these to a later box
    if f'case (4, "{item_id}")' in bag and "Drop(" in bag.split(f'case (4, "{item_id}")')[1][:200]:
        fail(f"BagPolicy drops read-in-place {item_id}")
if "l9" in drops:
    fail("l9 is a storeroom find, not a delivery")

# Choices: sluice, kotel, address (default Nyura), believe (default Agnia).
for cid, default, typ in (
    ("e_sluice", "help", "choice"),
    ("e_kotel", "stay", "choice"),
    ("e_address", "nyura", "choice"),  # option id; the resident is nyura_stvor
    ("e_believe", "agnia", "choice"),
):
    ev = events.get(cid)
    if not ev or ev["type"] != typ:
        fail(f"missing {cid}")
        continue
    if ev.get("default") != default:
        fail(f"{cid} default is {ev.get('default')!r}, expected {default}")
    opts = {o["id"]: o for o in ev.get("options") or []}
    if cid == "e_address" and set(opts) != {"nyura", "zoya", "office"}:
        fail(f"e_address options {set(opts)}")
    if cid == "e_believe" and set(opts) != {"agnia", "kuzma", "vera"}:
        fail(f"e_believe options {set(opts)}")
    # grants must use effects, not a grant key the decoder ignores
    for o in ev.get("options") or []:
        if "grant" in o:
            fail(f"{cid}.{o['id']} uses ignored grant field")
        if o["id"] in ("help", "stay") and not o.get("effects"):
            fail(f"{cid}.{o['id']} should grant a find through effects")

# Settlements: 8 map places; Трубы and Шлам are landscape only.
want = {
    "shlagbaum": 0, "otstoyniki": 4000, "kotelnaya": 21000, "sarai": 25000,
    "naberezhnaya": 32000, "dvory": 36500, "otdelenie": 39500, "verkhnyaya": 45000,
}
got = {s["id"]: s["step"] for s in chapter["settlements"]}
if got != want:
    fail(f"world settlements drifted: {got}")
if any(s["id"] in ("truby", "shlam", "pipes", "slurry") for s in chapter["settlements"]):
    fail("landscape-only places were promoted to settlements")
stvor_got = {s["id"]: s["step"] for s in stvor["settlements"]}
if stvor_got != want:
    fail(f"stvor.json settlements drifted: {stvor_got}")
if stvor.get("globalStart") != 75000 or stvor.get("lengthSteps") != 45000:
    fail("stvor.json is not 75000+45000")
join = stvor.get("join") or []
if len(join) != 2 or abs(join[0] - 551.5) > 0.05 or abs(join[1] - 2100.8) > 0.05:
    fail(f"stvor join drifted: {join}")

# Residents and approved animals only, placed once.
res = {r["id"]: r for r in story["residents"]}
expect_res = {"kolya": 4000, "pavel": 23000, "nyura_stvor": 36500, "agnia_stvor": 39500}
if set(res) != set(expect_res):
    fail(f"residents {sorted(res)} != {sorted(expect_res)}")
for rid, step in expect_res.items():
    if res[rid]["step"] != step:
        fail(f"{rid} at {res[rid]['step']}, expected {step}")
    if res[rid].get("height") != 430:
        fail(f"{rid} height {res[rid].get('height')}")

# People pass: own ids, lore, choices tied to residents, e_address only with the jar.
lore = json.loads((ROOT / "Postman/GameAssets/Data/resident_lore.json").read_text(encoding="utf-8"))
for rid in expect_res:
    if rid not in lore or not lore[rid].get("lines"):
        fail(f"no resident lore for {rid}")
for cid, rid in (("e_sluice", "kolya"), ("e_kotel", "pavel"), ("e_address", "nyura_stvor"),
                 ("e_believe", "agnia_stvor"), ("e_wet", "agnia_stvor")):
    if events.get(cid, {}).get("resident") != rid:
        fail(f"{cid} is not tied to {rid}")
ea = events["e_address"]
if ea.get("requires") != "inBag:l5" or not ea.get("fallback"):
    fail("e_address must need the jar in the bag and have a fallback")
for o in ea["options"]:
    eff = o.get("effects") or []
    if o["id"] == "nyura" and {"item": "l5", "status": "delivered"} not in eff:
        fail("only Nyura's answer delivers l5")
    if o["id"] != "nyura" and any(e.get("item") == "l5" for e in eff):
        fail(f"e_address.{o['id']} must not deliver l5")
for sid in ("s_kolya_dam", "s_nyura", "s_agnia", "s_kladovaya"):
    if events.get(sid, {}).get("type") != "scene":
        fail(f"missing scene {sid}")
if events["s_agnia"]["step"] >= events["p_l9"]["step"] or events["s_kladovaya"]["step"] >= events["p_l9"]["step"]:
    fail("Agnia and the storeroom must come before the stack")
for find, ev_id in (("find_sluice", "s_kolya_dam"), ("find_blank", "s_nyura"), ("find_stub", "s_agnia")):
    if f'case (4, "{find}")' not in bag or ev_id not in bag:
        fail(f"BagPolicy does not hand {find} at {ev_id}")

# Asset existence for world props, residents, map, taps.
assets = ROOT / "Postman/GameAssets"
def exists(rel):
    base = [assets / "Chapter4" / rel, assets / rel]
    for b in base:
        if b.exists():
            return True
        for suf in (".png", ".jpg", ".jpeg"):
            if Path(str(b) + suf).exists():
                return True
    return False

missing = []
for prop in chapter.get("props") or []:
    if not exists(prop["image"]):
        missing.append(prop["image"])
ug = chapter.get("underground") or {}
if ug.get("neutralTile") and not exists(ug["neutralTile"]):
    missing.append(ug["neutralTile"])
for mod in ug.get("modules") or []:
    if mod.get("image") and not exists(mod["image"]):
        missing.append(mod["image"])
if missing:
    fail(f"{len(set(missing))} prop/ug images missing, e.g. {sorted(set(missing))[:8]}")

for rid in expect_res:
    if not (assets / "Chapter4/residents" / rid / "full.png").exists():
        fail(f"missing resident art {rid}")

for name in ("stvor_color.jpg", "stvor_pencil.jpg", "stvor_field.png"):
    if not (assets / "UI/map" / name).exists():
        fail(f"missing map {name}")
for sid in want:
    if not (assets / "UI/map" / f"icon_{sid}.png").exists():
        fail(f"missing map icon {sid}")

taps_path = ROOT / "Postman/GameAssets/Data/chapter4_taps.json"
taps = json.loads(taps_path.read_text(encoding="utf-8"))
if len(taps) < 8:
    fail(f"too few taps: {len(taps)}")
for tap in taps:
    sprite = tap["sprite"]
    path = assets / sprite
    if not path.exists() and not path.with_suffix(".png").exists():
        # TextureStore often omits .png
        alt = assets / (sprite if sprite.endswith(".png") else sprite + ".png")
        if not alt.exists():
            fail(f"tap {tap['id']} sprite missing: {sprite}")

# Honest stubs: findings, attachments, History frames must not invent new unique art.
stub_art = {"env_plain", "stick_plain", "road_envstake"}
for item in story["items"]:
    if item["id"].startswith(("find_", "note_", "l")):
        if item.get("art") and item["art"] not in stub_art and "Chapter4/finds" in str(item.get("art")):
            fail(f"{item['id']} points at invented find art {item['art']}")

# Engine hooks exist in source.
atlas = (ROOT / "Postman/Model/MapAtlas.swift").read_text(encoding="utf-8")
screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
world_scene = (ROOT / "Postman/Scene/WorldScene.swift").read_text(encoding="utf-8")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
for token, blob, label in (
    ("loadStvor", atlas, "MapAtlas"),
    ("StvorJoin", atlas, "MapAtlas"),
    ("heroOnStvor", screen, "MapScreen"),
    ("refreshStvor", screen, "MapScreen"),
    ("stvorRevealKey", screen, "MapScreen"),
    ("installWorldTaps", world_scene, "WorldScene"),
    ('chapter\\(chapter.id)_taps.json', world_scene, "WorldScene"),
    ("tap.ch\\(parts[0])", hud, "HUDView"),
):
    if token not in blob:
        fail(f"{label} is missing {token}")

# AppIcon must not have been touched in this feature (no new icon files under AppIcon).
# Presence of v2 is enough; we do not rewrite it here.

# raw clay only after the last chapter.
if ch3.get("rawClayAfterStep") is not None:
    fail("chapter 3 still has rawClayAfterStep, which would cover chapter 4")
if chapter.get("rawClayAfterStep") != 45000:
    fail(f"chapter 4 rawClayAfterStep is {chapter.get('rawClayAfterStep')}")

if FAILS:
    print(f"{len(FAILS)} chapter 4 check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("chapter 4 checks ok (letters, t431, Lower Stvor title, map join, stubs, hooks)")
