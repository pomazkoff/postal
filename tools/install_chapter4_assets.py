#!/usr/bin/env python3
"""Cut official ch4 strip v5.3 into Chapter3-style tiles.

Places are 1:1 (no downscale), sky is punched with a Lab/variance mask,
leftover atmosphere on the panels is punched so a single chapter gradient
(applyChapterSky lerp day→dusk→night) can run continuously — no local sky
cards. Unique sprites (the Verkhnyaya moon, clay clouds already on the
panels) keep irregular alpha. Road is a generic tileable RGBA path, and
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

# Strip-absolute horizontal crop overrides. The yellow-red column with the
# pink shirt sits on the slice 7/8 cut (x=9360) and was split across Dvory
# and Otdelenie. Trim it off Dvory; give the whole column to Otdelenie.
CROP_X = {
    "dvory": (7 * W_PLACE, 9200),
    "otdelenie": (9200, 9 * W_PLACE),
}


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


def cut_place(strip, idx, name=None):
    x0 = idx * W_PLACE
    if name in CROP_X:
        xa_abs, xb_abs = CROP_X[name]
    else:
        xa_abs, xb_abs = x0, x0 + W_PLACE
    tile = strip[0:H_CROP, xa_abs:xb_abs]
    alpha, keep, labels, bot = segment_alpha(tile)
    ys, xs = np.where(alpha > 0.15)
    pad = 24
    if name in CROP_X:
        # Keep the requested width so the column trim / transplant is exact.
        y0, y1, xa, xb = 0, H_CROP, 0, tile.shape[1]
        if len(ys) >= 200:
            y0 = max(0, int(ys.min()) - pad)
    elif len(xs) < 200:
        y0, y1, xa, xb = 0, H_CROP, 0, tile.shape[1]
    else:
        y0 = max(0, int(ys.min()) - pad)
        y1 = H_CROP  # always include the road / sink
        xa = max(0, int(xs.min()) - pad)
        xb = min(tile.shape[1], int(xs.max()) + pad)
        if xa <= 40:
            xa = 0
        if xb >= tile.shape[1] - 40:
            xb = tile.shape[1]
    crop = tile[y0:y1, xa:xb]
    a = alpha[y0:y1, xa:xb]
    rgba = np.dstack([crop, (np.clip(a, 0, 1) * 255).round().astype(np.uint8)])
    meta = {
        "y0": int(y0),
        "y1": int(y1),
        "xa": int(xa_abs + xa - x0),
        "xb": int(xa_abs + xb - x0),
        "pixelSize": [int(rgba.shape[1]), int(rgba.shape[0])],
        "height": int(rgba.shape[0]),
        "sink": 40,
        "dx": round((xa_abs + xa - x0) - 0.55 * W_PLACE, 1),
    }
    return rgba, meta, (alpha, tile)
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
    """Remove the official painted postman. Rebuild the red/white barrier
    arm by cloning a clean stripe cycle; fill the sand under the legs;
    punch the body above the bar to transparent sky."""
    h, w = rgba.shape[:2]
    BAR_Y0, BAR_Y1 = 1494, 1580
    r = rgba[:, :, 0].astype(int)
    g = rgba[:, :, 1].astype(int)
    b = rgba[:, :, 2].astype(int)

    pm = np.zeros((h, w), np.uint8)
    pm[1300:1712, 470:690] = 1
    pm[1480:1695, 660:710] = 1
    dark = (r < 110) & (g < 100) & (b < 90) & (r + g + b < 280)
    pm[1620:1712, 460:700] |= dark[1620:1712, 460:700].astype(np.uint8)
    pm = cv2.morphologyEx(pm, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
    pm = cv2.dilate(pm, np.ones((7, 7), np.uint8))
    pm[1712:] = 0
    pm[:, :455] = 0
    pm[:, 720:] = 0
    green = (g > r + 10) & (g > b) & (g > 80)
    pm[1580:1712, 200:520] &= (~green[1580:1712, 200:520]).astype(np.uint8)

    out = rgba.copy()

    # Clone a clean red+cream cycle (x=318..496) into the overlap.
    src = rgba[BAR_Y0:BAR_Y1, 318:496]
    out[BAR_Y0:BAR_Y1, 500:678] = src
    out[BAR_Y0:BAR_Y1, 500:678, 3] = 255
    for i in range(10):
        t = (i + 1) / 10.0
        x = 500 + i
        col = (1 - t) * rgba[BAR_Y0:BAR_Y1, 496].astype(np.float32) + t * out[BAR_Y0:BAR_Y1, x].astype(np.float32)
        out[BAR_Y0:BAR_Y1, x] = np.clip(col, 0, 255).astype(np.uint8)
        out[BAR_Y0:BAR_Y1, x, 3] = 255
    for i in range(22):
        t = (i + 1) / 22.0
        x = 678 - 22 + i
        orig_x = min(678 + i, 730)
        col = (1 - t) * out[BAR_Y0:BAR_Y1, x].astype(np.float32) + t * rgba[BAR_Y0:BAR_Y1, orig_x].astype(np.float32)
        out[BAR_Y0:BAR_Y1, x] = np.clip(col, 0, 255).astype(np.uint8)
        out[BAR_Y0:BAR_Y1, x, 3] = 255

    # Sand under the legs: Telea, then force opaque in the figure's x-range.
    body = pm.copy()
    body[:BAR_Y1] = 0
    body = cv2.dilate(body, np.ones((9, 9), np.uint8))
    body[:BAR_Y1] = 0
    bgr = cv2.cvtColor(out[:, :, :3], cv2.COLOR_RGB2BGR)
    inb = cv2.inpaint(bgr, (body * 255).astype(np.uint8), 8, cv2.INPAINT_TELEA)
    in_rgb = cv2.cvtColor(inb, cv2.COLOR_BGR2RGB)
    # Prefer textured sand from a clean patch to the right, tiled into the hole.
    sand = rgba[1578:1712, 800:1040]
    sh, sw = sand.shape[:2]
    for y in range(1578, min(1712, h)):
        xs = np.where(body[y] > 0)[0]
        for x in xs:
            if x >= 500:
                out[y, x] = sand[(y - 1578) % sh, (x - 500) % sw]
            else:
                out[y, x, :3] = in_rgb[y, x]
                out[y, x, 3] = 255

    # Body above the bar → transparent (chapter sky shows through).
    head = pm.copy()
    head[BAR_Y0:] = 0
    out[:, :, 3] = np.where(head > 0, 0, out[:, :, 3])
    return out


def punch_leftover_sky(rgba):
    """Punch leftover atmosphere so the chapter gradient shows through.

    Only true sky/haze is removed: pale, gray-blue, night, and warm dawn/dusk
    that is either floating or touching the top edge. Bottom-connected clay
    (yellow walls, doors, laundry) is left alone.
    """
    rgb = rgba[:, :, :3]
    a = rgba[:, :, 3]
    h, w = a.shape
    L, A, B = labAB(rgb)
    chroma = np.sqrt(A * A + B * B)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    var = variance(gray)
    pale = (L > 160) & (chroma < 32) & (var < 80)
    peach = (L > 140) & (A > 8) & (B > 8) & (chroma < 50) & (var < 70)
    orange = (L > 130) & (L < 200) & (A > 5) & (B > 15) & (var < 55)
    night = (L < 80) & (chroma < 25) & (var < 40)
    grayblue = (L > 80) & (L < 180) & (A < 8) & (A > -8) & (B < 8) & (chroma < 22) & (var < 55)
    cool = pale | grayblue | night
    warm = peach | orange

    # Bottom-connected opaque (terrain / buildings / trees).
    opaque = (a > 10).astype(np.uint8)
    keep = np.zeros((h, w), np.uint8)
    keep[h - 1] = opaque[h - 1]
    for y in range(h - 2, -1, -1):
        row = opaque[y] & (keep[y + 1] | np.roll(keep[y + 1], 1) | np.roll(keep[y + 1], -1))
        # also horizontal fill along the row once
        changed = True
        acc = row.copy()
        # cheap: dilate the seed along x on this row, clipped to opaque
        seed = cv2.dilate(keep[y + 1].reshape(1, -1), np.ones((1, 3), np.uint8)).reshape(-1)
        keep[y] = opaque[y] & seed
    # one extra close so thin poles still count as ground-connected
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) & opaque

    def top_components(mask):
        n, lab = cv2.connectedComponents(mask.astype(np.uint8))
        if n <= 1:
            return np.zeros((h, w), bool)
        touch = set(int(v) for v in np.unique(lab[0]) if v > 0)
        return np.isin(lab, list(touch)) if touch else np.zeros((h, w), bool)

    # Foliage is green and textured and not a pale highlight. Cyan sky has
    # slightly negative A but L~200 and almost no variance — that is sky.
    foliage = (A < -8) & (L < 185) & (var > 30)
    punch = np.zeros((h, w), bool)
    punch |= cool & (a > 10) & (~foliage)
    punch |= warm & (a > 10) & (~foliage) & ((keep == 0) | top_components(warm & (a > 10)))
    punch[-200:] = False
    mask = punch.astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    out = rgba.copy()
    out[:, :, 3] = np.where(mask > 0, 0, out[:, :, 3])
    return out


def punch_nab_haze(rgba):
    """Gray textured haze on the right of Набережная — too much variance
    for the generic leftover punch, but it is not foliage."""
    L, A, B = labAB(rgba[:, :, :3])
    chroma = np.sqrt(A * A + B * B)
    var = variance(cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY))
    a = rgba[:, :, 3]
    fol = (A < -6) & (L < 185) & (var > 30)
    haze = (a > 10) & (A > -5) & (L > 70) & (L < 210) & (chroma < 28) & (~fol)
    haze[:, :700] = False
    haze[-250:] = False
    haze = cv2.morphologyEx(haze.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    haze = cv2.morphologyEx(haze, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    out = rgba.copy()
    out[:, :, 3] = np.where(haze > 0, 0, out[:, :, 3])
    return out



def extract_moon(strip):
    """Crescent moon on the Verkhnyaya slice, tight irregular alpha."""
    x0 = 9 * W_PLACE
    tile = strip[0:H_CROP, x0 : x0 + W_PLACE]
    h, w = tile.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    # Crescent body; lamp is to the left (~x=0..90) and must stay on the place.
    rect = (100, 200, 280, 500)
    mask[:, :] = cv2.GC_BGD
    mask[200:700, 100:380] = cv2.GC_PR_FGD
    mask[260:620, 140:330] = cv2.GC_FGD
    mask[:, :90] = cv2.GC_BGD
    mask[:180] = cv2.GC_BGD
    mask[720:] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(tile, cv2.COLOR_RGB2BGR), mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    moon = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    moon[:, :90] = 0
    moon = cv2.morphologyEx(moon, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    moon = cv2.morphologyEx(moon, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(moon > 0)
    if len(xs) < 400:
        print("  moon extract failed, skipping")
        return None
    y0, y1 = max(0, int(ys.min()) - 8), min(h, int(ys.max()) + 8)
    xa, xb = max(0, int(xs.min()) - 8), min(w, int(xs.max()) + 8)
    crop = tile[y0:y1, xa:xb]
    m = moon[y0:y1, xa:xb].astype(np.uint8)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    a = np.clip(dist / 2.0, 0, 1)
    rgba = np.dstack([crop, (a * 255).round().astype(np.uint8)])
    # Punch leftover night sky that GrabCut left inside the crescent / around it.
    Lc, Ac, Bc = labAB(rgba[:, :, :3])
    chromac = np.sqrt(Ac * Ac + Bc * Bc)
    skyish = (Lc < 75) & (chromac < 20)
    rgba[:, :, 3] = np.where(skyish, 0, rgba[:, :, 3])
    ys2, xs2 = np.where(rgba[:, :, 3] > 12)
    if len(xs2) > 200:
        yy0, yy1 = max(0, int(ys2.min()) - 4), min(rgba.shape[0], int(ys2.max()) + 4)
        xx0, xx1 = max(0, int(xs2.min()) - 4), min(rgba.shape[1], int(xs2.max()) + 4)
        rgba = rgba[yy0:yy1, xx0:xx1]
        y0 += yy0
        xa += xx0
    height = int(rgba.shape[0])
    return {
        "rgba": rgba,
        "prop": {
            "image": "places/sprite_moon",
            "layer": "main",
            "step": 45000,
            "dx": round(xa - 0.55 * W_PLACE, 1),
            "height": height,
            "sink": int(y0 + height - GY),
            "z": -6,
            "pixelSize": [int(rgba.shape[1]), height],
        },
    }


def main():
    print("load strip", STRIP)
    strip = np.array(Image.open(STRIP).convert("RGB"))
    assert strip.shape[1] == 11700 and strip.shape[0] == 2604, strip.shape

    for sub in ("places", "road", "underground", "sky"):
        (CH / sub).mkdir(parents=True, exist_ok=True)

    # PASS4 owns seamless road/UG tiles, place recuts, moon, and sky sprites.
    # A re-run of this installer must not delete or overwrite them (the old
    # loop cut unique UG crops per place and a thin road).
    ug_n = CH / "underground" / "ug_neutral_tile.png"
    road_p = CH / "road" / "road_main.png"
    if ug_n.exists() and road_p.exists():
        print("pass4 tiles present — leaving Chapter4 art and install_meta as-is")
        return

    # First-time install only: clear leftover sky cards and unique UG crops.
    for pat in (
        "places/sky_*.png",
        "sky/cloud_dawn_*.png",
        "underground/ug_chain.png",
        "underground/ug_bone.png",
        "underground/ug_boat.png",
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
    sprite_meta = []
    for name, step, idx in PLACES:
        rgba, meta, _ = cut_place(strip, idx, name)
        if name == "shlagbaum":
            rgba = punch_shlagbaum_postman(rgba)
        rgba = punch_leftover_sky(rgba)
        if name == "naberezhnaya":
            rgba = punch_nab_haze(rgba)
        save_png(rgba, CH / "places" / f"place_{name}_main.png")
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

    moon = extract_moon(strip)
    if moon is not None:
        save_png(moon["rgba"], CH / "places" / "sprite_moon.png")
        sprite_meta.append(moon["prop"])
        # Punch the same pixels off the Verkhnyaya panel so the sprite is
        # the only moon (otherwise a ragged copy sits on the place).
        vpath = CH / "places" / "place_verkhnyaya_main.png"
        ver = np.array(Image.open(vpath))
        vmeta = next(p for p in place_meta if "verkhnyaya" in p["image"])
        sp = moon["prop"]
        moon_y_strip = sp["sink"] + GY - sp["height"]
        moon_x = int(round(sp["dx"] + 0.55 * W_PLACE))
        y = int(moon_y_strip - vmeta["y0"])
        x = moon_x - int(vmeta.get("xa") or 0)
        m = (moon["rgba"][:, :, 3] > 8).astype(np.uint8)
        m = cv2.dilate(m, np.ones((31, 31), np.uint8))
        mh, mw = m.shape
        canvas = np.zeros(ver.shape[:2], np.uint8)
        yy0, xx0 = max(0, y), max(0, x)
        yy1, xx1 = min(ver.shape[0], y + mh), min(ver.shape[1], x + mw)
        if yy1 > yy0 and xx1 > xx0:
            canvas[yy0:yy1, xx0:xx1] = m[(yy0 - y):(yy1 - y), (xx0 - x):(xx1 - x)]
            canvas = cv2.dilate(canvas, np.ones((21, 21), np.uint8))
            canvas[:, :88] = 0  # keep the lamp
            ver[:, :, 3] = np.where(canvas > 0, 0, ver[:, :, 3])
            save_png(ver, vpath)

    far, mid = make_far_mid(strip)
    save_png(far, CH / "places" / "bg_far_ridges_tile.png")
    save_png(mid, CH / "places" / "bg_mid_fields_tile.png")

    # First-time path: build tiles + recut places via pass4, then stop.
    # pass4 writes install_meta (ug_variants, tilePixelSize, sprites, road).
    import rebuild_chapter4_pass4 as _pass4
    _pass4.main(skip_places=False)
    return

    # Unreachable. Kept so git blame still shows the old cloud-cut site.
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
        "sprites": sprite_meta,
        "sky_cards": [],
        "road": {"road_main": list((Image.open(CH / "road" / "road_main.png").size if (CH / "road" / "road_main.png").exists() else (2400, 680)))},
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
