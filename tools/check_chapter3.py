#!/usr/bin/env python3
"""Chapter 3, the Marshes. Static only: letters, mail ahead of the player, one path length."""
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


canon = (ROOT / "docs/canon/letters-ch3.md").read_text(encoding="utf-8")
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter3_story.json").read_text(encoding="utf-8"))
world = json.loads((ROOT / "Postman/GameAssets/Data/world.json").read_text(encoding="utf-8"))
swamps = json.loads((ROOT / "Postman/GameAssets/UI/map/swamps.json").read_text(encoding="utf-8"))
items = {item["id"]: item for item in story["items"]}
events = {event["id"]: event for event in story["events"]}

blocks = {n: letter_blocks(canon, n) for n in range(1, 11)}
if "Митюша, купила крючки" not in blocks[1][1]:
    fail("the canon letter file is not the edited Galya letter")
expected = {
    "l1": blocks[1][1],
    "l2": blocks[2][0],
    "l3": blocks[3][0],
    "l4": blocks[4][0],
    "l5": blocks[5][0],
    "l6": blocks[6][0],
    "l7": blocks[7][0],
    "l8": blocks[8][0],
    "l9": blocks[9][0],
}
for key, text in expected.items():
    if items[key]["text"] != text:
        fail(f"{key} is not the edited letter")
if items["l1"]["note"] != blocks[1][0]:
    fail("A.L.'s note is not the first block of letter 1")
if "Дед Ф." not in items["note_fedya"]["text"]:
    fail("Fedya's note was rewritten")
if items["l10"]["text"] != "Почтальону.":
    fail("the silent bundle grew a letter")
for banned in ("Тишина", "сорок один", "41 имён"):
    blob = "\n".join(item["text"] for item in story["items"])
    if banned in blob:
        fail(f"a letter contains {banned}")

chapter = next(c for c in world["chapters"] if c["id"] == 3)
if chapter["startStep"] != 45000 or chapter["lengthSteps"] != 30000:
    fail(f"chapter 3 is not world steps 45000–75000: {chapter['startStep']} + {chapter['lengthSteps']}")
if chapter["title"] != "Болота":
    fail("chapter 3 title is not Болота")
if any(c["id"] == 2 and "скоро" in json.dumps(c, ensure_ascii=False) for c in world["chapters"]):
    fail("chapter 2 still says the marshes are only coming")

# t431: pickup and the drop are both still ahead, and never back in chapters 1–2.
behind = {"nii", "sedlo", "kadushki", "svai", "zvonarnya", "pochta"}
drops = {
    "l1": "d_gat", "l4": "d_top", "note_fedya": "e_fedya_help",
    "l2": "d_torf", "l3": "d_barge", "l5": "d_reeds", "l7": "d_reeds", "l9": "d_otstoy",
}
read_here = {"l6", "l8", "l10"}
pickup = {
    "l1": "p_l1", "l2": "p_l2", "l3": "p_l3", "l4": "p_l4", "l5": "p_l5",
    "l6": "p_l6", "l7": "p_l7", "l8": "p_l8", "l9": "p_l9", "l10": "p_l10",
    "note_fedya": "e_fedya_help",
}
for item_id, event_id in pickup.items():
    step = events[event_id]["step"]
    if step <= 0:
        fail(f"{item_id} is picked up at a step the player has already passed ({step})")
    if events[event_id]["settlement"] in behind:
        fail(f"{item_id} is picked up back in the valley or the mountains")
for item_id, event_id in drops.items():
    if item_id == "note_fedya":
        event_id = "d_top"
    drop = events[event_id]
    taken = events[pickup[item_id]]["step"]
    if drop["step"] <= taken:
        fail(f"{item_id} is delivered at {drop['step']}, not ahead of pickup {taken}")
    if drop["settlement"] in behind:
        fail(f"{item_id} is delivered at {drop['settlement']}")
for item_id in read_here:
    if any(item_id in json.dumps(event) and event["type"] == "deliver" for event in story["events"]):
        fail(f"{item_id} is read in place and must not have a delivery event")

policy = (ROOT / "Postman/App/BagPolicy.swift").read_text(encoding="utf-8")
for item_id in ("l6", "l8", "l10"):
    if f'(3, "{item_id}")' in policy.split("func drops", 1)[1].split("func handoff", 1)[0]:
        fail(f"{item_id} was given a drop")

# Variant В: one length. Fog is a veil, not a second road.
scene = (ROOT / "Postman/Scene/WorldScene.swift").read_text(encoding="utf-8")
if "thinner ? 0.28 : 0.72" not in scene:
    fail("the marsh veil is not thinner from 18:00 to 07:00")
if "hour >= 18 || hour < 7" not in scene:
    fail("the evening window is not 18:00–07:00")
veil = scene.split("func updateMarshVeil", 1)[1].split("func ", 1)[0]
if "displayedStep" in veil and ("*=" in veil or "night" in veil.lower()):
    fail("the marsh veil changes the step")
if story["choicePolicy"]["timeoutSteps"] != 400:
    fail("choices do not resolve after 400 steps")
for choice in ("e_gati_fog", "e_fedya_help", "e_bearing", "e_radio", "e_plug"):
    if choice not in events or events[choice]["type"] != "choice" or not events[choice].get("default"):
        fail(f"{choice} is not a choice with a default")

places = {place["id"]: place["step"] for place in swamps["settlements"]}
expected_places = {"gat": 4000, "top": 9000, "torfyanik": 12500, "staraya_protoka": 16500, "gorlo": 22500, "otstoy": 30000}
if places != expected_places:
    fail(f"swamp map places drifted: {places}")
if swamps["globalStart"] != 45000 or swamps["lengthSteps"] != 30000:
    fail("the swamp sheet is not the 45000–75000 road")
if abs(swamps["join"][0] - 619.9) > 0.2 or abs(swamps["join"][1] - 2373.7) > 0.2:
    fail("the swamp join moved")
atlas = (ROOT / "Postman/Model/MapAtlas.swift").read_text(encoding="utf-8")
screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
if "loadSwamps" not in atlas or "MarshSeam.apply" not in screen:
    fail("the swamp sheet is not joined onto the mountains")
if "mountain:" not in atlas.split("enum MarshSeam", 1)[-1][:800]:
    fail("the seam does not blend into the mountain picture")
chapter_dir = ROOT / "Postman/GameAssets/Chapter3"
for folder in ("road", "places", "underground", "foreground", "residents/fedya"):
    path = chapter_dir / folder
    if path.is_symlink():
        fail(f"{folder} is still a link to another chapter")
    if not path.is_dir():
        fail(f"{folder} is not a chapter 3 folder")
if chapter["assetsFolder"] != "Chapter3":
    fail("chapter 3 does not load its own asset folder")
expected_art = {
    "road/road_main_alder.png": (2400, 680),
    "places/bg_far_ridges_tile.png": (2636, 1236),
    "places/bg_mid_fields_tile.png": (2636, 1040),
    "underground/ug_neutral_tile.png": (1148, 415),
}
from PIL import Image
for rel, size in expected_art.items():
    path = chapter_dir / rel
    if not path.exists():
        continue
    with Image.open(path) as im:
        if im.size != size:
            fail(f"{rel} is {im.size}, the strip expects {size}")
taps = json.loads((ROOT / "Postman/GameAssets/Data/chapter3_taps.json").read_text(encoding="utf-8"))
needed = {"frog1", "heron", "bubble1", "boat", "barge", "bell", "radio", "wall", "kettle", "barrier"}
got = {tap["id"] for tap in taps}
if not needed <= got:
    fail(f"missing world taps {sorted(needed - got)}")
scene_body = (ROOT / "Postman/Scene/WorldScene.swift").read_text(encoding="utf-8")
if "marsh:" not in scene_body or "chapter3_taps.json" not in scene_body:
    fail("marsh taps are not hit targets")
fedya = chapter_dir / "residents/fedya/full.png"
if fedya.exists():
    with Image.open(fedya) as im:
        if im.mode != "RGBA":
            fail("Fedya's picture needs a transparent background")
if "destinationIn" in screen:
    fail("the fade must not punch a hole with destinationIn")

history = (ROOT / "Postman/App/StoryChronicle.swift").read_text(encoding="utf-8")
for beat in ("clean", "ramka", "fiftyeight", "names", "zorka", "signature", "marsh"):
    if f'id: "{beat}"' not in history:
        fail(f"history is missing {beat}")
for secret in ("включила К-2", "Агния", "Тишина"):
    if secret in history:
        fail(f"history names {secret}")

ch2 = json.loads((ROOT / "Postman/GameAssets/Data/chapter2_story.json").read_text(encoding="utf-8"))
if ch2["nextChapter"] != "Глава 3 «Болота»":
    fail("chapter 2 does not continue into the marshes")
if story["nextChapter"] != "Глава 4 «Город молчания» — скоро":
    fail("chapter 3 does not point at chapter 4")

if FAILS:
    print(f"{len(FAILS)} chapter 3 check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("chapter 3 checks ok")
