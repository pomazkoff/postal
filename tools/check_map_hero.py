#!/usr/bin/env python3
"""Карта: тап по отмеченным местам. Мир: тап по почтальону. Шарф не перекрашен.

Сборка не проверялась на устройстве. Компас, дорога и туман карточек не получают.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


map_src = read("Postman/UI/MapScreen.swift")
world = read("Postman/Scene/WorldScene.swift")
rig = read("Postman/Scene/PostmanRigNode.swift")
en = read("Postman/Resources/en.lproj/Localizable.strings")
ru = read("Postman/Resources/ru.lproj/Localizable.strings")
places = json.loads(read("Postman/GameAssets/UI/map/map.json"))["settlements"]
ids = [p["id"] for p in places]
if ids != ["pochta", "svai", "zvonarnya", "kadushki", "nii", "sedlo"]:
    fail(f"unexpected map marks: {ids}")

if "openPlace(place)" not in map_src or "openPostman()" not in map_src:
    fail("map marks must open a note")
if map_src.count("openPlace(place)") < 3:
    fail("icon, stake and name tag should each open the place")
ahead = map_src.split("private func openPlace", 1)[1].split("private func openPostman", 1)[0]
# Arrival text is only in the reached branch, before the ahead string.
if ahead.find("arrivals") > ahead.find("map.place.ahead"):
    fail("a place still in the fog must not show its arrival line")
if "map.place.been" not in ahead or "map.place.ahead" not in ahead:
    fail("reached and unreached places need the neutral lines")
if "allowsHitTesting(false)" not in map_src.split("map.compass", 1)[1].split("map.stepsOf", 1)[0]:
    fail("the compass must stay decorative")
dashes = map_src.split("struct WalkedDashes", 1)[1]
if "onTapGesture" in dashes or "openPlace" in dashes:
    fail("the road dashes are not a card")

if "playNod(reduceMotion:" not in rig or "guard !reduceMotion" not in rig:
    fail("Reduce Motion must skip the nod")
if "Affine2D.rotate" not in rig.split("part == .head", 1)[1].split("pose.apply", 1)[0]:
    fail("the nod must be a rig rotation, not a scale")
if "hitsPostman" not in world or "onPostmanTap" not in world:
    fail("a tap on the hero must be separate from resident taps")
if world.split("if let key = residentKey", 1)[1].split("hitsPostman", 1)[0].find("onResidentTap") < 0:
    fail("a resident under the tap still wins")
if "UIAccessibility.isReduceMotionEnabled" not in world:
    fail("the world tap must read Reduce Motion")

for key in ("map.place.ahead", "map.place.been"):
    if f'"{key}"' not in en or f'"{key}"' not in ru:
        fail(f"missing {key}")
if "onboarding.card0.body" not in map_src:
    fail("the postman card must reuse the existing introduction, not a new biography")

# Кроме шарфа на голове и торсе части рига не трогаем. Сам шарф проверяет check_scarf_assets.py.
import subprocess
diff = subprocess.check_output(
    ["git", "diff", "--name-only", "db8526f7bdd94d8244147f1ca29ea4e60251f8c1", "--", "Postman/GameAssets/Rig"],
    cwd=ROOT, text=True)
extra = [line for line in diff.splitlines() if line and not line.endswith(("torso.png", "head.png"))]
if extra:
    fail(f"rig assets besides the scarf changed: {extra}")

if FAILS:
    print(f"{len(FAILS)} map/hero check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print(f"map/hero checks ok ({len(ids)} places + postman)")
