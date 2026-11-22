#!/usr/bin/env python3
"""Cut official ch4 strip v5.3 into Chapter3-style tiles.

Places are 1:1 (no downscale), sky is punched with a Lab/variance mask,
local sky cards keep the strip's unique atmosphere (dawn / dusk / night)
without opaque rectangles, road is a generic tileable RGBA path, and
bg_far / bg_mid fill the vertical the way Chapter 3 does.

Does not copy the 11700px strip into the repo. Does not delete
residents / ambient / taps / map.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = Path("/workspace/walking-sim")
STRIP = ART / "chapter4/art/strip/ch4_strip_v53_full.png"
CHARS = ART / "chapter4/art/characters"
MAP = ART / "map_stvor_v3/out"
OUT = ROOT / "Postman/GameAssets"
CH = OUT / "Chapter4"

W_PLACE, H_PHONE, GY = 1170, 2532, 1720
H_CROP = GY + 40  # 1760: road line + 40px sink, same as ch3
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
    print(f"  {path.relative_to(OUT)} {arr.shape} {path.stat().st_size // 1024}KB")


def labAB(rgb):
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    return lab[:, :, 0], lab[:, :, 1] - 128, lab[:, :, 2] - 128


def variance(gray):
    g = gray.astype(np.float32)
    mu = cv2.blur(g, (13, 13))
    return np.clip(cv2.blur(g * g, (13, 13)) - mu * mu, 0, None)


def segment_alpha(rgb):
    """1 = keep (terrain / buildings / trees), 0 = punch (sky / atmosphere)."""
    h, w, _ = rgb.shape
    L, A, B = labAB(rgb)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    var = variance(gray)
    chroma = np.sqrt(A * A + B * B)
    y = np.arange(h)[:, None]
    protected = (var > 90) | (A < -6) | ((chroma > 28) & (var > 80) & (L < 150))
    pale = (L > 155) & (var < 80) & (chroma < 28)
    dusk = (L > 140) & (var < 80) & (A > 0) & (B > 8) & (chroma < 50)
    night = (L < 170) & (var < 120) & (chroma < 22) & (B >= A - 8) & (A > -10)
    like = (pale | dusk | night) & (y < GY - 120) & (~protected)
    sky = np.zeros((h, w), np.uint8)
    for x in range(w):
        ref = np.array([L[0:8, x].mean(), A[0:8, x].mean(), B[0:8, x].mean()])
        for yy in range(h):
            if protected[yy, x] and yy > 20:
                if yy < 400 and like[yy, x]:
                    sky[yy, x] = 255
                    continue
                break
            d = np.sqrt(
                (L[yy, x] - ref[0]) ** 2
                + (A[yy, x] - ref[1]) ** 2
                + (B[yy, x] - ref[2]) ** 2
            )
            thr = 28 if yy < 900 else 18 if yy < 1300 else 12
            if (d < thr or like[yy, x]) and not (protected[yy, x] and yy > 20 and yy >= 400):
                sky[yy, x] = 255
                ref = 0.9 * ref + 0.1 * np.array([L[yy, x], A[yy, x], B[yy, x]])
            else:
                if yy + 8 < h and (
                    like[yy + 8, x]
                    or (
                        not protected[yy + 8, x]
                        and np.sqrt(
                            (L[yy + 8, x] - ref[0]) ** 2
                            + (A[yy + 8, x] - ref[1]) ** 2
                            + (B[yy + 8, x] - ref[2]) ** 2
                        )
                        < thr
                    )
                ):
                    sky[yy, x] = 255
                    continue
                break
    sky = np.maximum(sky, like.astype(np.uint8) * 255)
    upper = np.zeros_like(sky)
    upper[: int(GY * 0.62)] = 1
    sky_u = cv2.morphologyEx(sky * upper, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    sky = np.where(upper, sky_u, sky)
    terrain = (sky == 0).astype(np.uint8)
    _n, labels = cv2.connectedComponents(terrain, 8)
    bot = set(np.unique(labels[GY - 60 :]))
    bot.discard(0)
    keep = np.isin(labels, list(bot)).astype(np.uint8) * 255
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    inv = (keep == 0).astype(np.uint8) * 255
    ff = inv.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    for x in (0, w - 1):
        for yy in (0, h - 1):
            if ff[yy, x] == 255:
                cv2.floodFill(ff, mask, (x, yy), 0)
    n3, lab3 = cv2.connectedComponents((ff == 255).astype(np.uint8))
    for i in range(1, n3):
        if (lab3 == i).sum() < 8000:
            keep[lab3 == i] = 255
    n2, lab2 = cv2.connectedComponents((keep > 0).astype(np.uint8))
    for i in range(1, n2):
        if (lab2 == i).sum() < 80:
            keep[lab2 == i] = 0
    dist = cv2.distanceTransform(keep, cv2.DIST_L2, 5)
    alpha = np.clip(dist / 2.0, 0, 1)
    alpha[GY - 20 :] = np.maximum(alpha[GY - 20 :], (keep[GY - 20 :] > 0).astype(np.float32))
    return alpha, keep, labels, bot


def feather_horizontal(alpha, px=80):
    if alpha.shape[1] < 4:
        return alpha
    px = min(px, alpha.shape[1] // 3)
    t = np.linspace(0, 1, px, dtype=np.float32)
    out = alpha.copy()
    out[:, :px] *= t
    out[:, -px:] *= t[::-1]
    return out


def hex_mean(img, y0, y1, x0, x1):
    p = img[y0:y1, x0:x1].mean(axis=(0, 1))
    return "#{:02X}{:02X}{:02X}".format(*[int(c) for c in p])


def make_tileable_x(img, overlap=200):
    """Blend right edge into the left so the crop tiles horizontally."""
    h, w = img.shape[:2]
    overlap = min(overlap, w // 4)
    body_w = w - overlap
    out = img[:, :body_w].copy()
    t = np.linspace(0, 1, overlap, dtype=np.float32)[None, :, None]
    left = img[:, :overlap].astype(np.float32)
    right = img[:, w - overlap :].astype(np.float32)
    out[:, :overlap] = (left * t + right * (1 - t)).round().astype(img.dtype)
    return out


def cut_place(strip, idx):
    x0 = idx * W_PLACE
    tile = strip[0:H_CROP, x0 : x0 + W_PLACE]
    alpha, keep, labels, bot = segment_alpha(tile)
    ys, xs = np.where(alpha > 0.15)
    pad = 24
    if len(xs) < 200:
        y0, y1, xa, xb = 0, H_CROP, 0, W_PLACE
    else:
        y0 = max(0, int(ys.min()) - pad)
        y1 = H_CROP  # always include the road / sink
        xa = max(0, int(xs.min()) - pad)
        xb = min(W_PLACE, int(xs.max()) + pad)
        # Don't cut a pole or facade on the edge: if content is close to a
        # phone-frame edge, keep the full width so the official composition holds.
        if xa <= 40:
            xa = 0
        if xb >= W_PLACE - 40:
            xb = W_PLACE
    crop = tile[y0:y1, xa:xb]
    a = alpha[y0:y1, xa:xb]
    rgba = np.dstack([crop, (np.clip(a, 0, 1) * 255).round().astype(np.uint8)])
    # Sky card is always the full phone frame (y=0..GY+40) so unique dawn/dusk/night
    # fills the screen even when the place itself is tight-cropped.
    sky_a = feather_horizontal(1.0 - alpha, px=90)
    sky_rgba = np.dstack([tile, (np.clip(sky_a, 0, 1) * 255).round().astype(np.uint8)])
    meta = {
        "y0": int(y0),
        "y1": int(y1),
        "xa": int(xa),
        "xb": int(xb),
        "pixelSize": [int(rgba.shape[1]), int(rgba.shape[0])],
        "height": int(rgba.shape[0]),  # 1:1 with the crop
        "sink": 40,
        "dx": round(xa - 0.55 * W_PLACE, 1),
        "skyHeight": int(H_CROP),
        "skyDx": round(0 - 0.55 * W_PLACE, 1),
    }
    return rgba, sky_rgba, meta, (alpha, tile)


def cut_clouds(strip):
    """Floating upper blobs (clouds, moon) as Chapter4/sky sprites."""
    clouds = []
    for idx, tag in ((0, "dawn"),):
        x0 = idx * W_PLACE
        tile = strip[0:H_CROP, x0 : x0 + W_PLACE]
        alpha, keep, labels, bot = segment_alpha(tile)
        # components that were terrain-colored but not bottom-connected
        terrain = ((alpha > 0.3) | (keep > 0)).astype(np.uint8)
        # rebuild all non-sky from a looser pass: leftover after keep
        leftover = ((alpha < 0.15) == False) & (keep == 0)  # noqa: E712
        # use original connected components of ~sky inverse minus keep
        inv = (keep == 0).astype(np.uint8)
        # floating = not sky-like and not keep? Actually clouds are in the
        # 'terrain' of the first pass before bottom-connect. Re-run labels
        # on (1-sky_like but we don't have sky). Use upper opaque leftovers
        # from the tile where keep is 0 but color is cloudy (textured, not atmos).
        L, A, B = labAB(tile)
        gray = cv2.cvtColor(tile, cv2.COLOR_RGB2GRAY)
        var = variance(gray)
        chroma = np.sqrt(A * A + B * B)
        cloudish = (var > 70) & (keep == 0) & (np.arange(H_CROP)[:, None] < 1100)
        # also the moon: mid-gray crescent, some texture, in night slice
        if tag == "night":
            cloudish |= ((L > 40) & (L < 160) & (chroma < 25) & (keep == 0) & (np.arange(H_CROP)[:, None] < 900))
        cloudish = cloudish.astype(np.uint8) * 255
        cloudish = cv2.morphologyEx(cloudish, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        n, lab = cv2.connectedComponents((cloudish > 0).astype(np.uint8))
        for i in range(1, n):
            m = lab == i
            if m.sum() < 2500:
                continue
            ys, xs = np.where(m)
            y0, y1 = max(0, ys.min() - 8), min(H_CROP, ys.max() + 8)
            xa, xb = max(0, xs.min() - 8), min(W_PLACE, xs.max() + 8)
            if (y1 - y0) < 30 or (xb - xa) < 40:
                continue
            crop = tile[y0:y1, xa:xb]
            a = m[y0:y1, xa:xb].astype(np.float32)
            dist = cv2.distanceTransform((a > 0).astype(np.uint8), cv2.DIST_L2, 5)
            a = np.clip(dist / 2.0, 0, 1)
            rgba = np.dstack([crop, (a * 255).round().astype(np.uint8)])
            name = f"cloud_{tag}_{len(clouds)}"
            clouds.append((name, rgba, y0, xa, idx))
    return clouds


def make_road(strip):
    """Generic clay path, 2400×680 RGBA, transparent above the road, tileable.

    Only a clean sand patch is used (shlagbaum, between the barrier gear and
    the postman). Unique props — barrel, shovel, dog, feet — must not repeat.
    """
    # Empirically clean: x=305:425, y=GY-55:GY+25, no figures or posts.
    src = strip[GY - 55 : GY + 25, 305:425]
    tiles = []
    width = 0
    while width < 2800:
        i = len(tiles)
        patch = src if i % 2 == 0 else np.ascontiguousarray(src[:, ::-1])
        off = (i * 13) % max(1, patch.shape[1] // 4)
        patch = np.concatenate([patch[:, off:], patch[:, :off]], axis=1)
        tiles.append(patch)
        width += patch.shape[1]
    ribbon = make_tileable_x(np.concatenate(tiles, axis=1), overlap=40)
    if ribbon.shape[1] < 2400:
        ribbon = np.concatenate([ribbon, ribbon], axis=1)
    ribbon = ribbon[:, :2400]
    canvas = np.zeros((680, 2400, 4), np.uint8)
    h = ribbon.shape[0]
    canvas[680 - h :, : , :3] = ribbon
    a = np.ones((h, 2400), np.float32)
    fade = 16
    a[:fade] = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    canvas[680 - h :, :, 3] = (a * 255).round().astype(np.uint8)
    return canvas


def make_far_mid(strip):
    """Distant green ridges + yellow banks from Отстойники, same pixel sizes
    as the global far/mid layers. Peach sky is punched so the tile does not
    paint a rectangle over the chapter gradient. No foreground props.
    """
    def punch_hills(crop):
        L, A, B = labAB(crop)
        var = variance(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY))
        chroma = np.sqrt(A * A + B * B)
        sky = (L > 168) & (var < 350) & (A > -2) & (B > 4) & (chroma < 40)
        _n, lab = cv2.connectedComponents(sky.astype(np.uint8))
        top = set(np.unique(lab[0:4]))
        top.discard(0)
        alpha = (~np.isin(lab, list(top))).astype(np.float32)
        keep = (alpha > 0.5).astype(np.uint8)
        _n, lab = cv2.connectedComponents(keep)
        bot = set(np.unique(lab[-4:]))
        bot.discard(0)
        alpha = np.isin(lab, list(bot)).astype(np.float32)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)
        return np.dstack([crop, (np.clip(alpha, 0, 1) * 255).round().astype(np.uint8)])

    def tile_sil(src_rgba, out_w, out_h, content_frac):
        sh, sw = src_rgba.shape[:2]
        ch = int(out_h * content_frac)
        cw = max(8, int(sw * (ch / sh)))
        scaled = np.array(Image.fromarray(src_rgba).resize((cw, ch), Image.Resampling.LANCZOS))
        flip = np.ascontiguousarray(scaled[:, ::-1])
        pieces, width, i = [], 0, 0
        while width < out_w + cw + 80:
            pieces.append(scaled if i % 2 == 0 else flip)
            width += pieces[-1].shape[1]
            i += 1
        row = make_tileable_x(np.concatenate(pieces, axis=1), overlap=min(80, cw // 3))
        if row.shape[1] < out_w:
            row = np.concatenate([row, row], axis=1)
        row = row[:, :out_w]
        canvas = np.zeros((out_h, out_w, 4), np.uint8)
        y0 = out_h - ch
        canvas[y0:] = row
        fade = max(8, int(ch * 0.10))
        canvas[y0 : y0 + fade, :, 3] = (
            canvas[y0 : y0 + fade, :, 3].astype(np.float32)
            * np.linspace(0.2, 1, fade, dtype=np.float32)[:, None]
        ).round().astype(np.uint8)
        return canvas

    # Empirically clean hill crop (no key, no fence, no poles).
    far_src = punch_hills(strip[1288:1460, 1520:1920])
    mid_src = punch_hills(strip[1320:1500, 1520:1910])
    far = tile_sil(far_src, 2636, 1236, content_frac=0.42)
    mid = tile_sil(mid_src, 2636, 1040, content_frac=0.58)
    return far, mid


def cut_ug(strip, x, w=1148):
    y0, y1 = GY, min(strip.shape[0], GY + 415)
    x0 = max(0, min(strip.shape[1] - w, x))
    tile = strip[y0:y1, x0 : x0 + w]
    if tile.shape[0] < 415 or tile.shape[1] < 1148:
        canvas = np.zeros((415, 1148, 3), np.uint8)
        canvas[: tile.shape[0], : tile.shape[1]] = tile
        if tile.shape[0] < 415:
            canvas[tile.shape[0] :] = tile[-1:, : min(1148, tile.shape[1])]
        tile = canvas
    return tile


def copy_resized_png(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    im = Image.open(dest)
    print(f"  {dest.relative_to(OUT)} {im.size} {dest.stat().st_size // 1024}KB")



def punch_shlagbaum_postman(rgba):
    """The official phone mockup paints the postman into slice 0. Remove him so
    the live rig is the only figure; keep the red/white barrier arm."""
    h, w = rgba.shape[:2]
    x0, x1, y0, y1 = 500, 760, 1280, 1720
    mask = np.zeros((h, w), np.uint8)
    mask[:, :] = cv2.GC_BGD
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    mask[1480:1620, 560:680] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    rgb = rgba[:, :, :3].copy()
    cv2.grabCut(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), mask,
                (x0, y0, x1 - x0, y1 - y0), bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    pm = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    pm[:y0] = 0; pm[y1:] = 0; pm[:, :x0] = 0; pm[:, x1:] = 0
    pm = cv2.morphologyEx(pm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    pm[1710:] = 0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    red = (r > 140) & (r > g + 35) & (r > b + 25)
    white = (r > 180) & (g > 150) & (b > 120) & (r - g < 50) & (g - b < 40)
    protect = np.zeros((h, w), bool)
    protect[1540:1705] = (red | white)[1540:1705]
    protect = cv2.dilate(protect.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    pm[protect] = 0
    out = rgba.copy()
    out[:, :, 3] = np.where(pm > 0, 0, out[:, :, 3])
    alpha = out[:, :, 3]
    for yy in range(1560, 1700):
        xs = np.where((pm[yy] == 0) & protect[yy] & (alpha[yy] > 200))[0]
        holes = np.where((alpha[yy] < 20) & (np.arange(w) >= x0) & (np.arange(w) <= x1))[0]
        if len(xs) < 5 or len(holes) == 0:
            continue
        for x in holes:
            srcx = int(xs[np.argmin(np.abs(xs - x))])
            if abs(srcx - x) < 80:
                out[yy, x] = out[yy, srcx]
    return out


def main():
    print("load strip", STRIP)
    strip = np.array(Image.open(STRIP).convert("RGB"))
    assert strip.shape[1] == 11700 and strip.shape[0] == 2604, strip.shape

    for sub in ("places", "road", "underground", "sky"):
        (CH / sub).mkdir(parents=True, exist_ok=True)

    # Remove previous place / road / sky cuts we are replacing (not residents).
    for pat in (
        "places/place_*_main.png",
        "places/sky_*.png",
        "places/bg_far_ridges_tile.png",
        "places/bg_mid_fields_tile.png",
        "road/*.png",
        "sky/*.png",
        "underground/ug_*.png",
    ):
        for p in CH.glob(pat):
            p.unlink()

    sky_day_top = hex_mean(strip, 8, 80, 80, 1090)
    sky_day_bot = hex_mean(strip, 900, 1100, 80, 1090)
    sky_dusk_top = hex_mean(strip, 8, 80, 4 * 1170 + 80, 5 * 1170 - 80)
    sky_dusk_bot = hex_mean(strip, 700, 1000, 4 * 1170 + 80, 4 * 1170 + 240)
    sky_night_top = hex_mean(strip, 8, 80, 9 * 1170 + 80, 10 * 1170 - 80)
    sky_night_bot = hex_mean(strip, 700, 1100, 9 * 1170 + 400, 9 * 1170 + 800)
    print("sky day", sky_day_top, sky_day_bot)
    print("sky dusk", sky_dusk_top, sky_dusk_bot)
    print("sky night", sky_night_top, sky_night_bot)

    place_meta = []
    sky_meta = []
    for name, step, idx in PLACES:
        rgba, sky_rgba, meta, _ = cut_place(strip, idx)
        if name == "shlagbaum":
            rgba = punch_shlagbaum_postman(rgba)
        save_png(rgba, CH / "places" / f"place_{name}_main.png")
        save_png(sky_rgba, CH / "places" / f"sky_{name}.png")
        opaque = (rgba[:, :, 3] > 10).mean() * 100
        print(f"    {name} opaque {opaque:.1f}% dx={meta['dx']} {meta['pixelSize']}")
        place_meta.append(
            {
                "image": f"places/place_{name}_main",
                "layer": "main",
                "step": step,
                "dx": meta["dx"],
                "height": meta["height"],
                "sink": meta["sink"],
                "z": 10,
                "pixelSize": meta["pixelSize"],
                "y0": meta["y0"],
                "xa": meta["xa"],
            }
        )
        # Sky card shares the same crop / dx / height / sink so it sits
        # exactly behind the place (main, z=-5). No mid parallax.
        sky_meta.append(
            {
                "image": f"places/sky_{name}",
                "layer": "main",
                "step": step,
                "dx": meta.get("skyDx", -0.55 * W_PLACE),
                "height": meta.get("skyHeight", H_CROP),
                "sink": 40,
                "z": -5,
                "pixelSize": [W_PLACE, meta.get("skyHeight", H_CROP)],
            }
        )

    far, mid = make_far_mid(strip)
    save_png(far, CH / "places" / "bg_far_ridges_tile.png")
    save_png(mid, CH / "places" / "bg_mid_fields_tile.png")

    road = make_road(strip)
    save_png(road, CH / "road" / "road_main.png")

    save_png(cut_ug(strip, 800), CH / "underground" / "ug_neutral_tile.png")
    for name, step, idx in PLACES:
        save_png(cut_ug(strip, idx * W_PLACE + 10), CH / "underground" / f"ug_{name}.png")

    # Optional drifting clouds for installStvorSky. Fail soft if a crop is empty.
    try:
        clouds = cut_clouds(strip)
        cloud_list = []
        for name, rgba, y0, xa, idx in clouds:
            save_png(rgba, CH / "sky" / f"{name}.png")
            cloud_list.append(
                {
                    "file": name,
                    "pixelSize": [int(rgba.shape[1]), int(rgba.shape[0])],
                    "y0": int(y0),
                    "slice": int(idx),
                }
            )
    except Exception as e:
        print("cloud cut failed (non-fatal):", e)
        cloud_list = []

    # Residents / ambient / map are already in the tree from the previous
    # install. Recopy only if missing, never delete them.
    if CHARS.exists():
        for rid in ("kolya", "pavel", "nyura", "agnia"):
            dest = CH / "residents" / rid / "full.png"
            src = CHARS / "residents" / rid / "full.png"
            if src.exists() and not dest.exists():
                copy_resized_png(src, dest)
        amb_dir = CHARS / "ambient"
        if amb_dir.exists():
            (CH / "ambient").mkdir(exist_ok=True)
            for src in amb_dir.glob("*.png"):
                dest = CH / "ambient" / src.name
                if not dest.exists():
                    copy_resized_png(src, dest)

    if MAP.exists() and (OUT / "UI/map").exists():
        md = OUT / "UI/map"
        for fn in ("stvor_color.jpg", "stvor_pencil.jpg", "stvor_field.png"):
            if (MAP / fn).exists() and not (md / fn).exists():
                shutil.copy2(MAP / fn, md / fn)

    meta = {
        "sky_top": sky_day_top,
        "sky_bot": sky_day_bot,
        "sky_dusk_top": sky_dusk_top,
        "sky_dusk_bot": sky_dusk_bot,
        "sky_night_top": sky_night_top,
        "sky_night_bot": sky_night_bot,
        "places": place_meta,
        "sky_cards": sky_meta,
        "road": {"road_main": [int(road.shape[1]), int(road.shape[0])]},
        "clouds": cloud_list,
        "bg_far": [2636, 1236],
        "bg_mid": [2636, 1040],
    }
    (CH / "install_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Chapter4 bytes",
        sum(p.stat().st_size for p in CH.rglob("*") if p.is_file()) / 1e6,
        "MB",
    )


if __name__ == "__main__":
    main()
