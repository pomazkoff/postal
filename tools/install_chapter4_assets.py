#!/usr/bin/env python3
"""Cut official ch4 strip v5.3 into Chapter3-style tiles and install map/residents/ambient.
Does not copy the 11700px strip into the repo.
"""
from __future__ import annotations
import json, shutil
from pathlib import Path
import numpy as np, cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = Path("/workspace/walking-sim")
STRIP = ART / "chapter4/art/strip/ch4_strip_v53_full.png"
CHARS = ART / "chapter4/art/characters"
MAP = ART / "map_stvor_v3/out"
OUT = ROOT / "Postman/GameAssets"
CH = OUT / "Chapter4"
W_PLACE, H_PHONE, GY = 1170, 2532, 1720
PLACES = [
    ("shlagbaum", 0, 0),
    ("otstoyniki", 4000, 1),
    ("truby", 11000, 2),
    ("shlam", 17500, 3),
    ("kotelnaya", 21000, 4),
    ("sarai", 25000, 5),
    ("naberezhnaya", 32000, 6),
    ("dvory", 36500, 7),
    ("otdelenie", 39500, 8),
    ("verkhnyaya", 45000, 9),
]

def save_png(arr, path: Path, optimize=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path, optimize=optimize)
    print(f"  {path.relative_to(OUT)} {arr.shape} {path.stat().st_size//1024}KB")

def sky_mask(img):
    """Approximate sky+cloud in the upper band (same idea as v53)."""
    h, w, _ = img.shape
    y_cap = min(h, 1280)
    r, g, b = img[:,:,0].astype(np.int16), img[:,:,1].astype(np.int16), img[:,:,2].astype(np.int16)
    # clay/earth/metal: stronger chroma or dark
    not_sky = (
        ((r > g + 25) & (r > b + 15) & (r > 70)) |  # rust/clay
        ((g > r + 20) & (g > 80)) |  # foliage
        ((r < 70) & (g < 70) & (b < 70))  # dark holes
    )
    # also very textured mid/low
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mu = cv2.blur(gray, (21, 21))
    var = np.clip(cv2.blur(gray * gray, (21, 21)) - mu * mu, 0, None)
    m = np.ones((h, w), np.float32)
    m[not_sky] = 0
    m[y_cap:] = 0
    # keep high-variance "objects" even if bluish
    m[(var > 180) & (np.arange(h)[:, None] < y_cap)] *= 0.15
    m = cv2.GaussianBlur(m, (0, 0), 3)
    return np.clip(m, 0, 1)

def cut_place(strip, idx, name):
    x0 = idx * W_PLACE
    tile = strip[0:GY + 40, x0:x0 + W_PLACE]
    sm = sky_mask(strip[0:GY + 40, x0:x0 + W_PLACE])
    # content = not sky
    content = sm < 0.55
    ys, xs = np.where(content)
    if len(xs) < 200:
        # fallback: full mid band
        y0, y1, xa, xb = 200, GY + 40, 0, W_PLACE
    else:
        pad = 16
        y0 = max(0, int(ys.min()) - pad)
        y1 = min(tile.shape[0], int(ys.max()) + pad)
        xa = max(0, int(xs.min()) - pad)
        xb = min(W_PLACE, int(xs.max()) + pad)
        # keep a bit of sky halo but make sky transparent
    crop = tile[y0:y1, xa:xb]
    alpha = (1.0 - sm[y0:y1, xa:xb])
    alpha = np.clip(alpha * 1.15, 0, 1)
    # never eat the lower third (ground/buildings)
    split = int((GY - y0) * 0.72)
    if split > 0:
        alpha[split:] = np.maximum(alpha[split:], 0.97)
    rgba = np.dstack([crop, (alpha * 255).astype(np.uint8)])
    # scale down if taller than 1100
    h, w = rgba.shape[:2]
    if h > 1100 or w > 1170:
        scale = min(1100 / h, 1170 / w)
        nh, nw = int(h * scale), int(w * scale)
        rgba = np.array(Image.fromarray(rgba).resize((nw, nh), Image.Resampling.LANCZOS))
    return rgba, y0, xa

def cut_road_tile(strip, x, w=2400, h=680):
    # band around the road line
    y0 = GY - 420
    y1 = y0 + h
    x0 = max(0, min(strip.shape[1] - w, x))
    tile = strip[y0:y1, x0:x0 + w]
    return tile

def cut_ug(strip, x, w=1148):
    y0, y1 = GY, min(strip.shape[0], GY + 415)
    x0 = max(0, min(strip.shape[1] - w, x))
    tile = strip[y0:y1, x0:x0 + w]
    if tile.shape[0] < 415 or tile.shape[1] < 1148:
        canvas = np.zeros((415, 1148, 3), np.uint8)
        canvas[:tile.shape[0], :tile.shape[1]] = tile
        # pad with last row/col
        if tile.shape[0] < 415:
            canvas[tile.shape[0]:] = tile[-1:, :min(1148, tile.shape[1])]
        tile = canvas
    return tile

def copy_resized_png(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    im = Image.open(dest)
    print(f"  {dest.relative_to(OUT)} {im.size} {dest.stat().st_size//1024}KB")

def main():
    print("load strip", STRIP)
    strip = np.array(Image.open(STRIP).convert("RGB"))
    assert strip.shape[1] == 11700 and strip.shape[0] == 2604, strip.shape

    # clear previous Chapter4 if any
    if CH.exists():
        shutil.rmtree(CH)
    for sub in ("places", "road", "underground", "sky", "ambient", "residents", "taps", "foreground"):
        (CH / sub).mkdir(parents=True)

    # sky colors from first and last place
    def mean_row(y0, y1, x0, x1):
        p = strip[y0:y1, x0:x1].mean(axis=(0, 1))
        return "#{:02X}{:02X}{:02X}".format(*[int(c) for c in p])
    sky_top = mean_row(10, 80, 0, 1170)
    sky_bot = mean_row(900, 1100, 0, 1170)
    print("sky", sky_top, sky_bot)

    # cloud crops: hanging soft shapes from shlagbaum (place 0) and nab
    for name, (y0, y1, x0, x1) in {
        "cloud_hang": (80, 420, 40, 700),
        "cloud_right": (350, 850, 400, 1100),
        "cloud_nab": (0, 400, 7020, 8190),
    }.items():
        crop = strip[y0:y1, x0:x1]
        # soft alpha from sky-likeness (keep slightly opaque clay blobs)
        sm = sky_mask(strip[y0:y1, x0:x1])
        alpha = ((1 - sm) * 255).astype(np.uint8)
        # boost mid
        alpha = np.clip(alpha.astype(np.int16) * 2, 0, 255).astype(np.uint8)
        rgba = np.dstack([crop, alpha])
        save_png(rgba, CH / "sky" / f"{name}.png")

    place_meta = []
    for name, step, idx in PLACES:
        rgba, y0, xa = cut_place(strip, idx, name)
        path = CH / "places" / f"place_{name}_main.png"
        save_png(rgba, path)
        h, w = rgba.shape[:2]
        # design height: keep roughly 1:1 to crop vs road (crop ends near GY+40)
        height = int(round((GY + 40 - y0) * (h / rgba.shape[0]) if False else h))
        # height is the on-screen height; use image height (already design px)
        # dx: left edge so the crop's xa aligns roughly with place frame center
        # postman at screenX 0.55; we place the sprite so content is centered at the settlement
        dx = -w * 0.55 + (W_PLACE / 2 - (xa + w / 2)) * 0.15
        place_meta.append({
            "image": f"places/place_{name}_main",
            "layer": "main",
            "step": step,
            "dx": round(float(-w * 0.52), 1),
            "height": int(h),
            "sink": 40,
            "z": 10,
            "pixelSize": [int(w), int(h)],
        })

    # road tiles: industrial (x~0-5000), mid (x~5000-8000), city (x~8000-10000)
    road_specs = [
        ("road_prom", 200),
        ("road_mid", 5000),
        ("road_city", 8500),
    ]
    road_files = {}
    for name, x in road_specs:
        tile = cut_road_tile(strip, x)
        save_png(tile, CH / "road" / f"{name}.png")
        road_files[name] = [tile.shape[1], tile.shape[0]]

    # underground
    save_png(cut_ug(strip, 800), CH / "underground" / "ug_neutral_tile.png")
    for name, step, idx in PLACES:
        save_png(cut_ug(strip, idx * W_PLACE + 10), CH / "underground" / f"ug_{name}.png")

    # residents
    for rid in ("kolya", "pavel", "nyura", "agnia"):
        src = CHARS / "residents" / rid / "full.png"
        copy_resized_png(src, CH / "residents" / rid / "full.png")

    # ambient (approved animals only, no unnamed people)
    amb = {
        "ducks": "ducks.png",
        "dog_otstoyniki": "dog_otstoyniki.png",
        "fish": "fish.png",
        "crow": "crow.png",
        "crow_fly": "crow_fly.png",
        "dog_slag": "dog_slag.png",
        "lizard": "lizard.png",
        "cat_soot": "cat_soot.png",
        "pigeons": "pigeons.png",
        "cat_sarai": "cat_sarai.png",
        "dog_city": "dog_city.png",
        "sparrows": "sparrows.png",
        "chickens": "chickens.png",
        "cat_otdelenie": "cat_otdelenie.png",
    }
    amb_meta = []
    for key, fn in amb.items():
        src = CHARS / "ambient" / fn
        dest = CH / "ambient" / fn
        copy_resized_png(src, dest)
        im = Image.open(dest)
        amb_meta.append((key, fn, im.size))

    # map files
    md = OUT / "UI/map"
    for fn in ("stvor_color.jpg", "stvor_pencil.jpg", "stvor_field.png"):
        shutil.copy2(MAP / fn, md / fn)
        print("  map", fn, (md / fn).stat().st_size // 1024, "KB")
    for fn in MAP.glob("icon_*.png"):
        shutil.copy2(fn, md / fn.name)
        print("  icon", fn.name, (md / fn.name).stat().st_size // 1024, "KB")
    stvor = json.loads((MAP / "stvor.json").read_text())
    stvor["_comment"] = (
        "Лист Нижнего Створа v3, стык с официальным Отстоем болот "
        "(551.5, 2100.8). globalStart 75000, 45000 шагов."
    )
    # fix icon paths if needed; already UI/map/icon_*
    # normalize puffs points
    if stvor.get("puffs", {}).get("points") == [[]]:
        stvor["puffs"]["points"] = []
    (md / "stvor.json").write_text(json.dumps(stvor, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("  stvor.json written")

    meta = {
        "sky_top": sky_top,
        "sky_bot": sky_bot,
        "places": place_meta,
        "road": road_files,
        "ambient": [{"id": k, "file": fn, "pixelSize": [sz[0], sz[1]]} for k, fn, sz in amb_meta],
    }
    (CH / "install_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Chapter4 bytes", sum(p.stat().st_size for p in CH.rglob("*") if p.is_file()) / 1e6, "MB")

if __name__ == "__main__":
    main()
