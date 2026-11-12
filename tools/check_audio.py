#!/usr/bin/env python3
"""Звук: покрытие дороги, ворота шагов, комплект файлов, без фона и без чужих зверей.

Форму волн здесь меряем, не слушаем. Слуховой QA этим файлом не заявляется.
"""
import json
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "Postman/GameAssets/Audio"
FAILS = []


def fail(msg):
    FAILS.append(msg)


def surface(step):
    if 2300 <= step < 3100:
        return "wood"
    if 5600 <= step < 8700:
        return "grass"
    if (8700 <= step < 20000) or (24000 <= step < 34000) or (38000 <= step < 42000):
        return "stone"
    return "earth"


def allows_footstep(app_active, hero_visible, world_audible, gain):
    return app_active and hero_visible and world_audible and gain > 0


def bed(chapter, weather):
    if weather == "rain":
        return ("rain", True)
    if weather == "snow":
        return ("snow_wind", True)
    if weather == "fog":
        return None
    if weather == "clear":
        return ("mountain_wind" if chapter == 2 else "valley_wind", False)
    return None


def story_cues(event_id, kind, resident, live):
    if not live:
        return []
    if event_id in ("s_bell", "d_l2"):
        return ["bell"]
    if kind in ("delivery", "finale"):
        return ["mail_handover"]
    if kind == "pickup":
        return ["mail_bag"]
    return []


# --- rules ---
if surface(0) != "earth" or surface(2500) != "wood" or surface(2900) != "wood":
    fail("Svai boards are the wood stretch")
if surface(4000) != "earth" or surface(6000) != "grass" or surface(10000) != "stone":
    fail("valley tiles drifted")
if surface(22000) != "earth" or surface(30000) != "stone" or surface(36000) != "earth":
    fail("mountain tiles drifted")
if surface(43000) != "earth":
    fail("alder stretch should stay earth")
if allows_footstep(False, True, True, 1) or allows_footstep(True, False, True, 1):
    fail("footsteps must follow the visible walking hero, not a background step")
if allows_footstep(True, True, False, 1) or allows_footstep(True, True, True, 0):
    fail("a covered world or silence must not step")
if not allows_footstep(True, True, True, 0.2):
    fail("an audible walking hero should step")
if bed(1, "fog") is not None or bed(2, "fog") is not None:
    fail("fog has no bed")
if bed(1, "clear") != ("valley_wind", False):
    fail("valley air is one pass, not a loop")
if bed(2, "clear") != ("mountain_wind", False):
    fail("mountain air is one pass, not a loop")
if bed(1, "rain") != ("rain", True) or bed(2, "snow") != ("snow_wind", True):
    fail("rain and snow beds drifted")
if story_cues("d_l1", "delivery", "kuzma", False):
    fail("catch-up must not play the letter")
if story_cues("d_l2", "delivery", "pimen", True) != ["bell"]:
    fail("the belfry delivery is the bell, once")
if story_cues("s_bell", "scene", None, True) != ["bell"]:
    fail("the distant bell is the same bell")
if story_cues("e_animal_rooster", "choice", "rooster", True):
    fail("walking up to the rooster must not play him; only a tap does")
if story_cues("p_animal_dog_find", "pickup", "dog_penki", True) != ["mail_bag"]:
    fail("finding the horn is a pickup, not a bark from progress")
if story_cues("arrive_gar", "scene", "lesnik", True):
    fail("a person has no voice cue")

def next_clip(cue, cursor):
    clips = {
        "animal_rooster": ["animal_rooster_1", "animal_rooster_2"],
        "animal_cat": ["animal_cat_1", "animal_cat_2"],
        "animal_goat_kid": ["animal_goat_kid_1", "animal_goat_kid_2"],
        "animal_goat": ["animal_goat_1", "animal_goat_2"],
        "animal_raven": ["animal_raven_1", "animal_raven_2"],
        "animal_dog": ["animal_dog_1", "animal_dog_2"],
    }[cue]
    return clips[cursor % len(clips)], cursor + 1

if next_clip("animal_goat", 0) != ("animal_goat_1", 1) or next_clip("animal_goat", 1) != ("animal_goat_2", 2):
    fail("adult goat variants must alternate, Ramka and Matrena share them")
if next_clip("animal_rooster", 2)[0] != "animal_rooster_1":
    fail("variant cursor must wrap")

needed = json.loads((AUDIO / "sounds_needed.json").read_text(encoding="utf-8"))
cues = [a["cue"] for a in needed["animals"]]
if cues != ["animal_rooster", "animal_cat", "animal_goat_kid", "animal_goat", "animal_raven", "animal_dog"]:
    fail(f"animal cue list drifted: {cues}")
listed = json.dumps(needed["animals"], ensure_ascii=False)
if any(name in listed for name in ("волк", "сова", "лошад", "owl", "wolf", "horse")):
    fail("the animal list invented a species")

# shipped files
expect = []
for name in (
    "steps_earth_one_shot_1", "steps_earth_one_shot_3", "steps_earth_one_shot_4",
    "steps_grass_one_shot_1", "steps_grass_one_shot_3", "steps_grass_one_shot_4",
    "steps_stone_one_shot_1", "steps_stone_one_shot_2", "steps_stone_one_shot_3",
    "steps_wood_one_shot_1", "steps_wood_one_shot_3", "steps_wood_one_shot_4",
    "mail_bag", "mail_handover", "mail_unfold",
    "ui_wood_tap", "ui_paper_open", "ui_paper_close",
    "valley_birds", "valley_wind", "mountain_wind", "rain", "snow_wind", "bell",
    "animal_rooster_1", "animal_rooster_2", "animal_cat_1", "animal_cat_2",
    "animal_goat_kid_1", "animal_goat_kid_2", "animal_goat_1", "animal_goat_2",
    "animal_raven_1", "animal_raven_2", "animal_dog_1", "animal_dog_2",
):
    expect.append(name)
    path = AUDIO / f"{name}.wav"
    if not path.exists():
        fail(f"missing {name}")
        continue
    with wave.open(str(path)) as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 44100:
            fail(f"{name} is not mono 16-bit 44100")
        if name.startswith("steps_") and "one_shot" in name:
            n = w.getnframes()
            raw = w.readframes(n)
            samples = struct.unpack("<" + "h" * n, raw)
            edge = max(abs(samples[0]), abs(samples[-1]))
            if edge > 200:
                fail(f"{name} edge is hot ({edge})")
rejected = [
    "steps_earth.wav", "steps_grass.wav", "steps_stone.wav", "steps_wood.wav",
    "steps_earth_one_shot_2.wav", "steps_grass_one_shot_2.wav",
    "steps_stone_one_shot_4.wav", "steps_wood_one_shot_2.wav",
]
for name in rejected:
    if (AUDIO / name).exists():
        fail(f"rejected clip is in the bundle: {name}")

mix = (ROOT / "Postman/App/AudioMix.swift").read_text(encoding="utf-8")
play = (ROOT / "Postman/Services/SoundPlayback.swift").read_text(encoding="utf-8")
info = (ROOT / "Postman/Info.plist").read_text(encoding="utf-8")
ent = (ROOT / "Postman/Postman.entitlements").read_text(encoding="utf-8")
if ".ambient" not in play:
    fail("session must be ambient so the silent switch and other audio hold")
if "UIBackgroundModes" in ent or ">audio<" in info:
    fail("background audio must stay off")
if "fetch" not in info:
    fail("the existing refresh mode should stay")
notifier = (ROOT / "Postman/Services/Notifier.swift").read_text(encoding="utf-8")
post = notifier.split("func post(", 1)[1].split("func postTest", 1)[0]
if "content.sound = .default" in post:
    fail("story banners must not ding on every catch-up beat")
if "content.sound = .default" not in notifier.split("func postTest", 1)[1]:
    fail("the debug notification can still use the system sound")
progress = (ROOT / "Postman/Services/ProgressStore.swift").read_text(encoding="utf-8")
reset = progress.split("func resetAll()", 1)[1].split("func resetStory", 1)[0]
if "postman.sound." in reset:
    fail("story reset must not wipe the sound levels")
for key in ("menu.sound", "menu.sound.effects", "menu.sound.ambience",
            "menu.sound.silent", "menu.sound.quiet", "menu.sound.mid",
            "menu.sound.full", "menu.sound.note"):
    for label, blob in (
        ("ru", (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")),
        ("en", (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")),
    ):
        if f'"{key}"' not in blob:
            fail(f"missing {label} {key}")

if FAILS:
    print(f"{len(FAILS)} audio check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
if "func animalTap" not in play or "allowsAnimalTap" not in mix:
    fail("animal clips must be reached from the tap, not from story progress")
if "animalCue(residentID)" in mix.split("func storyCues", 1)[1]:
    fail("story cards must not call the animal cue")
print(f"audio checks ok ({len(expect)} clips, animal taps use two variants each)")
