#!/usr/bin/env python3
"""Консольный прыжок в главу 3 и прокрутка общей карты.

Прыжок должен ставить тот же мировой шаг, что и пеший приход.
Бирка не имеет права всегда писать «Седло», когда глава уже другая.
Холст карты включает лист болот, и жест лежит на этом холсте, а не на экране.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


game = read("Postman/App/GameModel.swift")
go = game.split("func developerGo", 1)[1].split("var developerDay", 1)[0]
if "setDebugTotal(worldStep)" not in go:
    fail("a chapter jump does not advance the step count to the world step")
if "forceChapterBaseSteps = steps.totalSteps - local" not in go:
    fail("a jump past the health total does not pin the virtual step")
if "forceChapterIndex = nil" not in go:
    fail("a jump that the step count can reach still leaves the force on")
if "jumpToSteps(worldSteps" not in go:
    fail("a chapter jump does not move the walking scene")
world_steps = game.split("func worldSteps", 1)[1].split("func ", 1)[0]
if "forceChapterIndex == chapterIndex" in world_steps:
    fail("world position ignores the forced chapter when the HUD index lags")
if "forcedChapter()" not in world_steps:
    fail("world position is not taken from the forced chapter")

tag = read("Postman/UI/TelegramView.swift")
done = tag.split("struct DistanceTagView", 1)[1].split("struct ", 1)[0]
if "donePlace" not in done:
    fail("the finished-chapter tag has no place from the active chapter")
if 'L10n.text("distance.done.place")' in done and "donePlace.isEmpty" not in done:
    fail("the finished-chapter tag is still hardcoded to the saddle")
hud = read("Postman/UI/HUDView.swift")
if "donePlace: game.chapter.settlements.last?.name" not in hud:
    fail("the HUD does not pass the active chapter's last place")

scene = read("Postman/Scene/WorldScene.swift")
if "marshVeil" in scene or "updateMarshVeil" in scene or "UIColor(white: 0.86" in scene:
    fail("the full-screen marsh veil is still drawn")
if "stepUnderCamera" not in scene:
    fail("chapter sky still follows the postman while the camera looks elsewhere")
if "func breathe" not in scene or "breathe(node)" not in scene:
    fail("residents without an idle sheet never breathe")
if "addMarshReeds" not in scene:
    fail("chapter 3 has no swaying reeds of its own")
ug = scene.split("func buildUnderground", 1)[1].split("// MARK: Progress API", 1)[0]
if ug.count("MarshSurface.shader") < 2:
    fail("swamp water does not shimmer on the chapter 3 underground")
if "inChapter(chapter)" not in ug:
    fail("underground tiles are not taken from the chapter folder")

ambient = json.loads(read("Postman/GameAssets/Data/ambient.json"))
matches = {item["match"] for item in ambient["sway"]}
for prefix in ("taps/reeds", "road/mid_hill_firs", "places/el_buried_horn", "places/el_fog_bank",
               "road/prop_signpost"):
    if prefix not in matches:
        fail(f"sway does not cover {prefix}")

screen = read("Postman/UI/MapScreen.swift")
if "atlas.contentSize.height * m.scale" not in screen:
    fail("the map gesture frame is still the screen, so the swamp sheet is outside the drag")
atlas = read("Postman/Model/MapAtlas.swift")
if "origin.y + valley.size[1] + lift" not in atlas:
    fail("map content height no longer includes the lift that makes room for the swamps")

# Та же геометрия, что у MapAtlas.make: верх болот y=0, низ долины — высота холста.
mountains = json.loads((ROOT / "Postman/GameAssets/UI/map/mountains.json").read_text(encoding="utf-8"))
swamps = json.loads((ROOT / "Postman/GameAssets/UI/map/swamps.json").read_text(encoding="utf-8"))
valley = json.loads((ROOT / "Postman/GameAssets/UI/map/map.json").read_text(encoding="utf-8"))
world = json.loads((ROOT / "Postman/GameAssets/Data/world.json").read_text(encoding="utf-8"))
chapters = world["chapters"]
if chapters[2]["startStep"] != 45000 or chapters[2]["lengthSteps"] != 30000:
    fail("chapter 3 is not world steps 45000–75000")
if chapters[2]["assetsFolder"] != "Chapter3":
    fail("chapter 3 walking art is not its own folder")

end_y = mountains["road"][-1][1]
join_y = swamps["join"][1]
lift = -(end_y - join_y)
origin_y = 2452.0 - 480.0
height = origin_y + valley["size"][1] + lift
if height < swamps["size"][1]:
    fail(f"map content {height} is shorter than the swamp sheet")
swamp_top_road = min(p[1] for p in swamps["road"])
screen_h = 2532.0
min_pan = screen_h - height
max_pan = 0.0
if swamp_top_road < 0 or swamp_top_road > screen_h:
    fail("the highest swamp road point is not on the first screen of the canvas")
if not (height > screen_h and min_pan < -1 and abs(max_pan) < 1):
    fail(f"pan cannot travel from the valley bottom to the swamp top ({min_pan}..{max_pan})")
# Пан 0 ставит y=0 холста к верху экрана — это верх болот, из долины и с Седла.
valley_bottom = origin_y + lift + valley["size"][1]
if abs(valley_bottom - height) > 1:
    fail("the valley does not sit on the bottom of the scrollable canvas")
if lift + mountains["size"][1] > height:
    fail("the mountain sheet hangs below the canvas")

# Прыжок на старт главы 3 — мировой шаг 45000, не сырой total и не конец главы.
if "let worldStep = target.startStep + local" not in go:
    fail("the jump target is not the chapter start plus the local step")

if FAILS:
    print(f"{len(FAILS)} console jump check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("console jump checks ok (chapter 3 step, place tag, map canvas, no full-screen veil)")
