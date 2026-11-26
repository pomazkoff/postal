#!/usr/bin/env python3
"""Chapter 4 «Нижний Створ» world layout, v2 art (built like chapter 1).

Writes world.json → chapters[id=4] props/underground/sky and returns the tap
anchors for chapter4_taps.json. Every size comes from the PNG on disk.

Layers (chapter-local steps 0…45000):
  main  10 places (sink 40) + up to 3 el_* beside each (never overlapping), road strips per stretch
        (2400 px = 2051 steps, *_1/*_2 alternating), roadside props
  mid   mid_* props by zone (parallax 0.4, sink −300)
  far   two far_* silhouettes + the moon (parallax 0.1); no hanging clouds
  fg    low fg_* clumps (parallax 1.3, sink 850)
  ug    one module under every place + fillers, neutral between (2296×830, scale 1.0)
"""
from __future__ import annotations
import json, random
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "Postman/GameAssets/Chapter4"
DATA = ROOT / "Postman/GameAssets/Data"
PPS = 1.17

def size(rel: str):
    with Image.open(A / f"{rel}.png") as im:
        return [im.width, im.height]

def prop(image, layer, step, dx, height, sink, z):
    return dict(image=image, layer=layer, step=int(step), dx=round(float(dx), 1), height=round(float(height), 1),
                sink=sink, z=z, pixelSize=size(image))

# id, step, dx (left edge of the main from the hero), height; elements left/right of the main: (id, height).
# Fix pass 1: every element stands BESIDE the main with a gap (no overlaps, no "front" pieces glued on),
# one whole drawing per place, nothing hanging in the sky.
GAP = 50
PLACES = [
    ("shlagbaum", 300, 950, 1150, [], []),
    ("otstoyniki", 4000, -900, 1150, [], [("sluice", 560)]),
    ("truby", 11000, -1100, 1250, [], []),
    ("shlam", 17500, -1000, 1150, [("slab", 260)], [("stake", 650)]),
    ("kotelnaya", 21500, -900, 1450, [("coalpile", 420)], [("dryer", 420), ("okabox", 380)]),
    ("sarai", 28000, -1100, 1150, [], [("door", 600), ("blanks", 400)]),
    ("naberezhnaya", 33500, -1100, 1300, [("railing", 300)], []),
    ("dvory", 37000, -1000, 1200, [("laundry", 480)], [("gatebox", 600), ("henhouse", 420)]),
    ("otdelenie", 40000, -900, 1450, [], []),
    ("verkhnyaya", 43000, -1000, 1150, [], [("gate", 620), ("bench", 340), ("lamp", 1000)]),
]
# road stretch themes: (theme, from, to) — each stretch has its own verge and bank
THEMES = [("damba", 0, 8000), ("estakada", 8000, 14000), ("shlam", 14000, 20500), ("ugol", 20500, 25000),
          ("sklad", 25000, 32000), ("bereg", 32000, 36500), ("dvor", 36500, 42000), ("noch", 42000, 47200)]
ZONES = [(0, 8000, "A"), (8000, 21000, "B"), (21000, 32000, "C"), (32000, 47000, "D")]
ROAD_PROPS = {"A": [("valve_post", 420), ("lifebuoy_post", 380)],
              "B": [("power_pylon", 900), ("pipe_support", 420), ("marker_pole", 520), ("warning_sign", 480)],
              "C": [("telegraph_pole", 900), ("coal_barrow", 260)],
              "D": [("town_lamp", 800), ("post_pole_box", 520), ("water_pump", 380), ("bench_poplar", 260)]}
# mid/far: only a few silhouettes whose base fades out (no plinths, no stacked shelves)
MID = [("coal_heaps", 22800, -350, 240), ("coal_heaps", 30200, -300, 220)]
FAR = [("chimneys", 12500, -200, 620, -560), ("warehouses", 25500, -400, 300, -600)]
MOON = ("places/sprite_moon", 43500, 150, 150, -1500)
# foreground: low clumps only, their tops stay well below the road line (never over the hero)
FG = {"A": [("reeds_rebar", 400)], "B": [("weeds_pipe", 380)], "C": [("coal_nettle", 340)], "D": [("burdock", 400)]}
UG_FILL = [("ug_fill_pipes", 7600), ("ug_fill_boot", 14300), ("ug_fill_stove", 24800), ("ug_fill_jars", 30800)]
UG_W, UG_H = 2296, 830

def zone(step):
    return next(z for a, b, z in ZONES if a <= step < b)

def width(img, h):
    w, hh = size(img); return h * w / hh

def build_props():
    random.seed(4)
    props, anchors, place_spans = [], {}, []
    z = 1
    for pid, step, dx, h, left, right in PLACES:
        main = f"places/place_{pid}_main"; mw = width(main, h)
        props.append(prop(main, "main", step, dx, h, 40, z)); anchors[f"place_{pid}"] = props[-1]
        lo, hi = dx, dx + mw
        x = dx
        for k, (eid, eh) in enumerate(left):
            img = f"places/el_{pid}_{eid}"; ew = width(img, eh); x = x - GAP - ew
            props.append(prop(img, "main", step, x, eh, 40, z + 1 + k)); anchors[f"el_{pid}_{eid}"] = props[-1]
            lo = min(lo, x)
        x = dx + mw
        for k, (eid, eh) in enumerate(right):
            img = f"places/el_{pid}_{eid}"; ew = width(img, eh); x = x + GAP
            props.append(prop(img, "main", step, x, eh, 40, z + 1 + len(left) + k)); anchors[f"el_{pid}_{eid}"] = props[-1]
            x += ew; hi = max(hi, x)
        place_spans.append((step + lo / PPS, step + hi / PPS))
        z += 6
    # road strips: one theme per stretch, z rising so a new stretch overlays the tail of the previous one
    for ti, (th, a, b) in enumerate(THEMES):
        s, k = a, 0
        while s < b:
            img = f"road/road_main_{th}_{1 + k % 2}"
            p = prop(img, "main", s, 0.0, size(img)[1], 40, round(-30 + ti * 0.1 + k * 0.001, 3))
            p["height"] = float(p["pixelSize"][1]); props.append(p)
            s += 2051; k += 1
    # roadside props every ~1250 steps, kept off the place sprites
    def free(s):
        return all(not (a - 350 <= s <= b + 250) for a, b in place_spans)
    s, i = 600, 0
    while s < 45000:
        if free(s):
            pid, ph = ROAD_PROPS[zone(s)][i % len(ROAD_PROPS[zone(s)])]
            img = f"road/prop_{pid}"
            props.append(prop(img, "main", s, random.uniform(-60, 60), ph, 40, -5))
            if pid == "bench_poplar" and "bench" not in anchors and 32000 <= s < 37000:
                anchors["bench"] = props[-1]
            i += 1
        s += random.randint(1050, 1450)
    if "bench" not in anchors:   # the Набережная bench tap needs its own bench
        props.append(prop("road/prop_bench_poplar", "main", 32200, 40, 260, 40, -5)); anchors["bench"] = props[-1]
    for i, (mid, st, dx, mh) in enumerate(MID):
        props.append(prop(f"road/mid_{mid}", "mid", st, dx, mh, -300, 1 + i))
    for fid, st, dx, fh, sink in FAR:
        props.append(prop(f"road/far_{fid}", "far", st, dx, fh, sink, 2))
    img, st, dx, mh, sink = MOON
    props.append(prop(img, "far", st, dx, mh, sink, 0.6))
    # foreground clumps ~ every 1050 steps
    s, i = 400, 0
    while s < 45000:
        lst = FG[zone(s)]
        fid, fh = lst[i % len(lst)]
        props.append(prop(f"foreground/fg_{fid}", "foreground", s, random.uniform(-600, 480), fh * random.uniform(0.8, 1.0), 850, 1))
        i += 1; s += random.randint(950, 1350)
    return props, anchors

def build_underground(anchors):
    mods = []
    for pid, step, dx, h, _l, _r in PLACES:
        mw = width(f"places/place_{pid}_main", h)
        mods.append({"image": f"underground/ug_{pid}", "step": step, "dx": round(dx + mw / 2, 1)})
    for img, st in UG_FILL:
        mods.append({"image": f"underground/{img}", "step": st, "dx": 0.0})
    # guard: modules must not overlap (centres ≥ one tile apart)
    xs = sorted(m["step"] * PPS + m["dx"] for m in mods)
    for a, b in zip(xs, xs[1:]):
        assert b - a >= UG_W - 1, f"underground modules overlap: {a:.0f} {b:.0f}"
    return {"neutralTile": "underground/ug_neutral_tile", "top": 1700, "scale": 1.0,
            "tilePixelSize": [UG_W, UG_H], "minGapFraction": 0.3, "modules": mods}

# taps on a part of a main drawing: (place, centre x, centre y from the top, width, height) — fractions of the main
TAP_REGION = {"kettle": ("shlagbaum", 0.53, 0.72, 0.13, 0.17), "barrier": ("shlagbaum", 0.55, 0.50, 0.50, 0.14),
              "key": ("otstoyniki", 0.79, 0.55, 0.12, 0.22), "nest": ("truby", 0.40, 0.56, 0.11, 0.09),
              "boiler": ("kotelnaya", 0.63, 0.79, 0.20, 0.18), "counter": ("otdelenie", 0.31, 0.62, 0.30, 0.26)}
# taps on a whole sprite (the sprite itself reacts)
TAP_ANCHOR = {"sluice": "el_otstoyniki_sluice", "crust": "el_shlam_slab", "bench": "bench", "gate": "el_dvory_gatebox",
              "sign": "el_verkhnyaya_gate"}
TAP_AMBIENT = {"ducks_gate": "ambient/ducks", "crow": "ambient/crow", "cat_soot": "ambient/cat_soot", "pigeons": "ambient/pigeons"}
TAP_REACT = {"kettle": ("steam", [0.5, 0.9]), "barrier": ("dust", [0.5, 0.5]), "ducks_gate": ("squash", None),
             "sluice": ("squash+dust", [0.5, 0.95]), "key": ("dust", [0.5, 0.9]), "crow": ("fly", None), "nest": ("dust", [0.5, 0.8]),
             "crust": ("squash+dust", [0.5, 0.9]), "boiler": ("flash+steam", [0.5, 0.7]), "cat_soot": ("hop", None),
             "pigeons": ("fly", None), "bench": ("squash", None), "gate": ("squash", None), "counter": ("flash", [0.5, 0.5]),
             "sign": ("squash", None)}

def taps(anchors, ambient):
    order = ["kettle", "barrier", "ducks_gate", "sluice", "key", "crow", "nest", "crust", "boiler", "cat_soot", "pigeons", "bench", "gate", "counter", "sign"]
    out = []
    for tid in order:
        react, at = TAP_REACT[tid]
        if tid in TAP_REGION:
            pid, cx, cy, rw, rh = TAP_REGION[tid]
            p = anchors[f"place_{pid}"]
            h = p["height"]; mw = h * p["pixelSize"][0] / p["pixelSize"][1]
            t = {"id": tid, "step": p["step"], "dx": round(p["dx"] + cx * mw, 1), "sprite": f"Chapter4/{p['image']}",
                 "height": round(rh * h, 1), "width": round(rw * mw, 1),
                 "sink": round(p["sink"] - (1 - cy - rh / 2) * h, 1), "z": 12, "draw": False}
        else:
            p = next(x for x in ambient if x["image"] == TAP_AMBIENT[tid]) if tid in TAP_AMBIENT else anchors[TAP_ANCHOR[tid]]
            w = p["height"] * p["pixelSize"][0] / p["pixelSize"][1]
            # tap node: anchor bottom-centre, invisible — the prop itself is the art and reacts
            t = {"id": tid, "step": p["step"], "dx": round(p["dx"] + w / 2, 1), "sprite": f"Chapter4/{p['image']}",
                 "height": p["height"], "sink": p["sink"], "z": 12, "draw": False, "target": f"{p['image']}|{p['step']}"}
        t["react"] = react
        if at: t["at"] = at
        out.append(t)
    return out

SKY = {"topColor": "#24505A", "bottomColor": "#A3A894",          # day: Отстойники
       "duskTopColor": "#2E3A4E", "duskBottomColor": "#B27A4E",  # Котельная
       "nightTopColor": "#1C3846", "nightBottomColor": "#7E8478"}  # Верхняя

if __name__ == "__main__":
    p, a = build_props(); u = build_underground(a)
    print(len(p), "props;", len(u["modules"]), "ug modules")
