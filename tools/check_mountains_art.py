#!/usr/bin/env python3
"""Принять лист гор, когда его сдадут. Пока файлов нет — это не ошибка."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "Postman/GameAssets/UI/map"
NEED = ["mountains.json", "mountains_color.jpg", "mountains_pencil.jpg"]
missing = [name for name in NEED if not (MAP / name).exists()]
if missing:
    print("mountains art not delivered yet (" + ", ".join(missing) + ")")
    raise SystemExit(0)

FAILS = []


def fail(msg):
    FAILS.append(msg)


try:
    from PIL import Image
except ImportError:
    print("Pillow is not installed; size check skipped")
    Image = None

raw = json.loads((MAP / "mountains.json").read_text(encoding="utf-8"))
if raw.get("size") != [1170, 2532]:
    fail(f"size {raw.get('size')}")
if raw.get("lengthSteps") != 25000 or raw.get("globalStart") != 20000:
    fail("length or global start is not chapter 2")
if raw.get("join") != [705.8, 2452.0] and raw.get("join") != [705.8, 2452]:
    fail(f"join {raw.get('join')}")
road = raw.get("road") or []
if len(road) < 2 or abs(road[0][0] - 705.8) > 0.6 or abs(road[0][1] - 2452) > 0.6:
    fail("the road must start at the saddle join")
known = {
    "sedlo": 0, "gar": 2800, "penki": 6500, "khomut": 11000,
    "repka": 15500, "krivulya": 16500, "gorlovina": 24000,
}
for place in raw.get("settlements") or []:
    if known.get(place.get("id")) != place.get("step"):
        fail(f"unknown or moved place {place.get('id')} step {place.get('step')}")

if Image is not None:
    color = Image.open(MAP / "mountains_color.jpg")
    pencil = Image.open(MAP / "mountains_pencil.jpg")
    if color.size != (1170, 2532) or pencil.size != (1170, 2532):
        fail(f"image size color {color.size} pencil {pencil.size}")
    valley = Image.open(MAP / "map_color.jpg").crop((0, 0, 1170, 560))
    band = color.crop((0, 1972, 1170, 2532))
    # Дорога может лечь на середину шва. Края должны остаться долиной.
    v = list(valley.resize((117, 56)).getdata())
    b = list(band.resize((117, 56)).getdata())
    drift = 0
    n = 0
    for (x, y), (p, q) in zip(((i % 117, i // 117) for i in range(len(v))), zip(v, b)):
        if 40 <= x <= 80:
            continue
        if isinstance(p, int):
            drift += abs(p - q)
        else:
            drift += sum(abs(a - c) for a, c in zip(p[:3], q[:3]))
        n += 1
    if n and drift / n > 40:
        fail(f"the join band no longer matches the valley top (mean channel drift {drift / n:.1f})")

if FAILS:
    print(f"{len(FAILS)} mountain art check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("mountain art accepted")
