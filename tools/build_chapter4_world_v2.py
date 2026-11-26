#!/usr/bin/env python3
"""Chapter 4 «Нижний Створ» world layout, v2 art (built like chapter 1).

Writes world.json → chapters[id=4] props/underground/sky and returns the tap
anchors for chapter4_taps.json. Every size comes from the PNG on disk.

Layers (chapter-local steps 0…45000):
  main  10 places (sink 40) + 3 companion el_* each, road strips per stretch
        (2400 px = 2051 steps, *_1/*_2 alternating), roadside props
  mid   mid_* props by zone (parallax 0.4, sink −300)
  far   far_* props + per-stretch clay clouds and the moon (parallax 0.1)
  fg    fg_* clumps (parallax 1.3, sink 850/900)
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

# id, step, dx (left edge from the hero), height; elements: (id, height, where)
PLACES = [
    ("shlagbaum", 300, 950, 1150, [("kettle", 430, "front"), ("mailbox", 600, "right"), ("tinfence", 520, "far_right")]),
    ("otstoyniki", 4000, -900, 1150, [("valves", 520, "front"), ("footbridge", 360, "right"), ("sluice", 700, "left")]),
    ("truby", 11000, -1100, 1250, [("servicebox", 420, "right"), ("nest", 380, "front"), ("ladder", 900, "far_right")]),
    ("shlam", 17500, -1000, 1150, [("stake", 650, "right"), ("barrow", 330, "front"), ("slab", 260, "left")]),
    ("kotelnaya", 21500, -900, 1450, [("coalpile", 420, "cover_left"), ("dryer", 520, "right"), ("okabox", 420, "far_right")]),
    ("sarai", 28000, -1100, 1150, [("door", 600, "right"), ("blanks", 420, "front"), ("ridge", 260, "left")]),
    ("naberezhnaya", 33500, -1100, 1200, [("tumba", 520, "right"), ("poplar", 1100, "far_right"), ("railing", 420, "left")]),
    ("dvory", 37000, -1000, 1200, [("gatebox", 620, "right"), ("laundry", 520, "left"), ("henhouse", 420, "far_right")]),
    ("otdelenie", 40000, -900, 1600, [("sacks", 600, "front"), ("counter", 520, "right"), ("postbox", 380, "far_right")]),
    ("verkhnyaya", 43000, -1000, 1150, [("bench", 340, "front"), ("gate", 620, "right"), ("lamp", 1000, "far_right")]),
]
# road stretch themes: (theme, from, to) — each stretch has its own verge and bank
THEMES = [("damba", 0, 8000), ("estakada", 8000, 14000), ("shlam", 14000, 20500), ("ugol", 20500, 25000),
          ("sklad", 25000, 32000), ("bereg", 32000, 36500), ("dvor", 36500, 42000), ("noch", 42000, 47200)]
ZONES = [(0, 8000, "A"), (8000, 21000, "B"), (21000, 32000, "C"), (32000, 47000, "D")]
ROAD_PROPS = {"A": [("valve_post", 420), ("lifebuoy_post", 380)],
              "B": [("power_pylon", 900), ("pipe_support", 420), ("marker_pole", 520), ("warning_sign", 480)],
              "C": [("telegraph_pole", 900), ("coal_barrow", 260)],
              "D": [("town_lamp", 800), ("post_pole_box", 520), ("water_pump", 380), ("bench_poplar", 260)]}
MID = {"A": [("dam_booth", 260), ("pond_saucer", 220), ("sluice", 280)],
       "B": [("trestle_low", 260), ("slag_heap", 240), ("rail_cart", 230)],
       "C": [("coal_heaps", 240), ("shed_row", 290), ("lamp_cart", 290)],
       "D": [("poplars", 290), ("laundry_yard", 250), ("roofs_bank", 280)]}
FAR = [("sluice_towers", 3000, -300, 520, -560), ("power_line", 7000, 200, 480, -600), ("chimneys", 12500, -200, 620, -560),
       ("pipe_trestle", 16500, 100, 260, -600), ("warehouses", 25500, -400, 300, -600), ("town_bank", 33500, -300, 420, -580),
       ("post_fog", 42500, -200, 260, -600)]
CLOUDS = [("fog_bank", 1500, -200, 230, -1420), ("ochre_trio", 6500, 250, 210, -1520), ("smog", 11500, -150, 240, -1450),
          ("factory_smoke", 16000, 200, 250, -1480), ("dusk", 22000, -250, 220, -1500), ("boiler_plume", 26500, 150, 260, -1430),
          ("town_cream", 32500, -100, 220, -1500), ("cold_fog", 38500, 200, 240, -1460)]
FG = {"A": [("reeds_rebar", 420)], "B": [("weeds_pipe", 400), ("rebar_tall", 1300)],
      "C": [("coal_nettle", 360)], "D": [("burdock", 420), ("hogweed", 1400)]}
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
    for pid, step, dx, h, els in PLACES:
        main = f"places/place_{pid}_main"; mw = width(main, h)
        props.append(prop(main, "main", step, dx, h, 40, z)); anchors[f"place_{pid}"] = props[-1]
        place_spans.append((step + dx / PPS, step + (dx + mw) / PPS))
        right_x = dx + mw
        for k, (eid, eh, where) in enumerate(els):
            img = f"places/el_{pid}_{eid}"; ew = width(img, eh)
            if where == "front": edx = dx + mw * 0.06
            elif where == "right": edx = right_x - ew * 0.25; right_x = edx + ew
            elif where == "far_right": edx = right_x + 60; right_x = edx + ew
            elif where == "left": edx = dx - ew * 0.7
            elif where == "cover_left": edx = dx - ew * 0.45      # hides the main sprite's left edge
            if pid == "shlagbaum": edx = max(edx, dx)           # never back onto chapter 3 «Отстой»
            props.append(prop(img, "main", step, edx, eh, 40, z + 1 + k)); anchors[f"el_{pid}_{eid}"] = props[-1]
        z += 5
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
    # mid props
    s, i = 1200, 0
    while s < 45000:
        lst = MID[zone(s)]; mid, mh = lst[i % len(lst)]
        props.append(prop(f"road/mid_{mid}", "mid", s, random.uniform(-450, -250), mh, -300, 1 + i)); i += 1
        s += random.randint(2600, 3300)
    for fid, st, dx, fh, sink in FAR:
        props.append(prop(f"road/far_{fid}", "far", st, dx, fh, sink, 2))
    for cid, st, dx, ch, sink in CLOUDS:
        props.append(prop(f"sky/cloud_{cid}", "far", st, dx, ch, sink, 0.5))
    props.append(prop("places/sprite_moon", "far", 41000, 150, 280, -1560, 0.6))
    # foreground clumps ~ every 1050 steps, tall ones rarely
    s, i = 400, 0
    while s < 45000:
        lst = FG[zone(s)]
        tall = [x for x in lst if x[1] > 1000]; low = [x for x in lst if x[1] <= 1000] or lst
        fid, fh = (tall[0] if tall and i % 6 == 5 else low[i % len(low)])
        k = 1.0 if fh > 1000 else random.uniform(0.8, 1.0)
        props.append(prop(f"foreground/fg_{fid}", "foreground", s, random.uniform(-600, 480), fh * k, 900 if fh > 1000 else 850, 1))
        i += 1; s += random.randint(850, 1250)
    return props, anchors

def build_underground(anchors):
    mods = []
    for pid, step, dx, h, _ in PLACES:
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

TAP_ANCHOR = {"kettle": "el_shlagbaum_kettle", "barrier": "el_shlagbaum_tinfence", "sluice": "el_otstoyniki_sluice",
              "key": "el_otstoyniki_valves", "nest": "el_truby_nest", "crust": "el_shlam_slab", "boiler": "place_kotelnaya",
              "pigeons": "el_sarai_ridge", "bench": "bench", "gate": "el_dvory_gatebox", "counter": "el_otdelenie_counter",
              "sign": "el_verkhnyaya_gate"}

def taps(anchors, ambient):
    order = ["kettle", "barrier", "ducks_gate", "sluice", "key", "crow", "nest", "crust", "boiler", "cat_soot", "pigeons", "bench", "gate", "counter", "sign"]
    amb = {"ducks_gate": "ambient/ducks", "crow": "ambient/crow", "cat_soot": "ambient/cat_soot"}
    out = []
    for tid in order:
        if tid in amb:
            p = next(x for x in ambient if x["image"] == amb[tid])
        else:
            p = anchors[TAP_ANCHOR[tid]]
        h = p["height"] if not p["image"].startswith("places/place_") else min(p["height"], 600)
        w = p["height"] * p["pixelSize"][0] / p["pixelSize"][1]
        # tap node: anchor bottom-centre, invisible — the prop itself is the art
        out.append({"id": tid, "step": p["step"], "dx": round(p["dx"] + w / 2, 1), "sprite": f"Chapter4/{p['image']}",
                    "height": h, "sink": p["sink"], "z": 12, "draw": False})
    return out

SKY = {"topColor": "#24505A", "bottomColor": "#A3A894",          # day: Отстойники
       "duskTopColor": "#2E3A4E", "duskBottomColor": "#B27A4E",  # Котельная
       "nightTopColor": "#1C3846", "nightBottomColor": "#7E8478"}  # Верхняя

if __name__ == "__main__":
    p, a = build_props(); u = build_underground(a)
    print(len(p), "props;", len(u["modules"]), "ug modules")
