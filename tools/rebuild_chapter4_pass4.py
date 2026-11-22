#!/usr/bin/env python3
"""Pass 4: rebuild гл.4 ground, sky objects and installer hooks.

- Opaque seamless UG tiles (no overlap-add ghosting). One neutral + two
  variants with inclusions; all share the same left/right edges and the
  same top lip, so they tile with each other.
- Unique finds (chain, bone, boat) as tight RGBA sprites on the UG layer,
  not full-tile replacements.
- Road tile includes the official clay lip / sand platform (кромка),
  wrap-seamless from several *different* official stretches.
- Places: punch leftover sky, remove torn clouds, punch everything below
  the road line, keep a ground island under structures, defringe.
- Clouds and moon as separate clean sprites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from install_chapter4_assets import (
    STRIP, CH, PLACES, W_PLACE, H_CROP, GY,
    cut_place, punch_shlagbaum_postman, punch_leftover_sky, punch_nab_haze,
    extract_moon, save_png, labAB, variance,
)

OUT = Path("/tmp/ch4_qa_after4/inspect")
OUT.mkdir(parents=True, exist_ok=True)

UG_H = 415
UG_OV = 80
PURE = 90
BLEND = 140
ROAD_H = 680
ROAD_SINK = 40


def seamless_x(im: np.ndarray, ov: int) -> np.ndarray:
    """Wrap-crossfade only (env_ch1/tiles.py). Does not overlap-add a crop."""
    a = im.astype(np.float32)
    w = a.shape[1]
    assert ov < w
    out = a[:, : w - ov].copy()
    t = np.linspace(0, 1, ov, dtype=np.float32)[None, :, None]
    out[:, :ov] = a[:, w - ov :] * (1 - t) + a[:, :ov] * t
    return np.clip(out, 0, 255).astype(im.dtype)


def quilt(segs: list[np.ndarray], out_w: int, ov: int = 80) -> np.ndarray:
    """Join *different* same-height segments end-to-end with a short crossfade."""
    assert segs
    h = segs[0].shape[0]
    ch = segs[0].shape[2] if segs[0].ndim == 3 else 1
    # Repeat the unique sequence (not a flipped palindrome) if we need more width.
    seq = list(segs)
    while sum(s.shape[1] - ov for s in seq) < out_w + ov:
        seq.extend(segs)
    canvas = np.zeros((h, out_w + ov, ch), np.float32)
    wacc = np.zeros((out_w + ov,), np.float32)
    x = 0
    for s in seq:
        sl = s if s.ndim == 3 else s[:, :, None]
        ww = sl.shape[1]
        t = np.ones(ww, np.float32)
        t[:ov] = np.linspace(0, 1, ov, dtype=np.float32)
        t[-ov:] = np.linspace(1, 0, ov, dtype=np.float32)
        x1 = min(x + ww, canvas.shape[1])
        tw = x1 - x
        canvas[:, x:x1] += sl[:, :tw].astype(np.float32) * t[:tw, None]
        wacc[x:x1] += t[:tw]
        x += ww - ov
        if x >= out_w + ov:
            break
    canvas /= np.maximum(wacc, 1e-4)[None, :, None]
    piece = np.clip(canvas, 0, 255).astype(np.uint8)
    return seamless_x(piece, ov)[:, :out_w]


def mag(rgba: np.ndarray, path: Path, tw: int = 800) -> None:
    if rgba.ndim == 2 or rgba.shape[2] == 3:
        rgb = rgba if rgba.ndim == 3 else np.dstack([rgba, rgba, rgba])
        a = np.full(rgb.shape[:2], 255, np.uint8)
        rgba = np.dstack([rgb, a])
    al = rgba[:, :, 3:4] / 255.0
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.zeros((h, w, 3), np.uint8)
    bg[((yy // 16) + (xx // 16)) % 2 == 0] = [200, 80, 160]
    bg[((yy // 16) + (xx // 16)) % 2 == 1] = [40, 40, 50]
    comp = (rgba[:, :, :3] * al + bg * (1 - al)).astype(np.uint8)
    sc = min(1.0, tw / max(1, w))
    Image.fromarray(comp).resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.Resampling.LANCZOS).save(
        path, quality=92
    )


def x3(im: np.ndarray, path: Path) -> None:
    if im.ndim == 2 or im.shape[2] == 3:
        rgb = im if im.ndim == 3 else np.dstack([im, im, im])
        a = np.full(rgb.shape[:2], 255, np.uint8)
        rgba = np.dstack([rgb, a])
    else:
        rgba = im
    canvas = np.concatenate([rgba, rgba, rgba], axis=1)
    # red seam marks
    vis = canvas.copy()
    w = rgba.shape[1]
    vis[:, w] = [255, 0, 0, 255]
    vis[:, 2 * w] = [255, 0, 0, 255]
    mag(vis, path, tw=1600)


def match_edges(mod: np.ndarray, N: np.ndarray, pure=PURE, blend=BLEND) -> np.ndarray:
    out = mod.astype(np.float32).copy()
    n = N.astype(np.float32)
    w = out.shape[1]
    h = min(out.shape[0], n.shape[0])
    out[:h, :pure] = n[:h, :pure]
    out[:h, w - pure :] = n[:h, n.shape[1] - pure :]
    for i in range(blend):
        t = (i + 1) / blend
        out[:h, pure + i] = (1 - t) * n[:h, pure + i] + t * out[:h, pure + i]
        out[:h, w - pure - 1 - i] = (1 - t) * n[:h, n.shape[1] - pure - 1 - i] + t * out[:h, w - pure - 1 - i]
    # shared top lip (continuous кромка)
    lip = 70
    ramp = np.linspace(1, 0, lip, dtype=np.float32)[:, None, None]
    out[:lip] = n[:lip, :w] * ramp + out[:lip] * (1 - ramp)
    return np.clip(out, 0, 255).astype(np.uint8)


def drop_teal_top(tile: np.ndarray, rows: int = 22) -> np.ndarray:
    """Replace a teal/green sliver at the very top with soil from just below."""
    out = tile.copy()
    src = out[rows : rows + 8].mean(axis=0, keepdims=True)
    for y in range(rows):
        t = y / max(1, rows)
        out[y] = (src * (1 - 0.15 * (1 - t)) + out[y] * (0.15 * (1 - t))).astype(np.uint8)
        out[y] = src.astype(np.uint8)
    # slight noise so it's not a flat cap
    out[:rows] = tile[rows : rows * 2][::-1] if tile.shape[0] > rows * 2 else src.astype(np.uint8)
    # actually: clone the ochre row band downward from row `rows`
    for y in range(rows):
        out[y] = tile[min(tile.shape[0] - 1, rows + (rows - 1 - y) % 6)]
    return out


def make_ug_tiles(strip: np.ndarray) -> tuple[np.ndarray, list[tuple[str, int, np.ndarray]]]:
    """Neutral + two inclusion variants. All 415 tall, wrap-seamless, shared edges."""
    y0, y1 = GY + 8, GY + 8 + UG_H
    # Clean official soil (no chain/boat/bone) used previously, no overlap-add.
    src_n = strip[y0:y1, 1380:2140]  # 760 px of official drips + soil
    src_n = drop_teal_top(src_n, 16)
    # Use native width after wrap (~680).
    N = seamless_x(src_n, UG_OV)
    # Make width even
    if N.shape[1] % 2:
        N = N[:, : N.shape[1] - 1]

    # Inclusion variants from official soil with extra texture (barrel/cracks, cobble-ish soil).
    # These are NOT water/cave tiles. Edges + top lip are taken from N.
    specs = [
        # cracked soil + pipe/barrel region under Трубы (object in the lower half)
        ("var_cracks", 8000, 2340),
        # pebble / rounded-stone soil near Дворы, if too unique we'll still N-edge it
        ("var_stones", 28000, 8200),
    ]
    variants = []
    for name, step, x in specs:
        tile = strip[y0:y1, x : x + N.shape[1] + UG_OV]
        if tile.shape[1] < N.shape[1] + UG_OV:
            pad = np.zeros((UG_H, N.shape[1] + UG_OV, 3), np.uint8)
            pad[:, : tile.shape[1]] = tile
            tile = pad
        tile = drop_teal_top(tile, 16)
        tile = seamless_x(tile, UG_OV)[:, : N.shape[1]]
        tile = match_edges(tile, N)
        variants.append((name, step, tile))
    return N, variants


def make_road(strip: np.ndarray) -> np.ndarray:
    """Official sand + clay lip, quilted from several *different* day stretches."""
    y0, y1 = GY - 140, GY + 25
    # Day ochre path runs (avoid night x~11264).
    runs = [
        (8734, 9068),
        (22, 244),
        (588, 778),
        (840, 1020),
        (1393, 1531),
        (5328, 5512),
        (5073, 5186),
        (2831, 2947),
        (5953, 6072),
        (8403, 8515),
    ]
    segs = []
    for a, b in runs:
        if b - a < 90:
            continue
        seg = strip[y0:y1, a:b]
        segs.append(seg)
    band = quilt(segs, 2400, ov=70)
    canvas = np.zeros((ROAD_H, 2400, 4), np.uint8)
    # Align so GY sits ROAD_SINK px above the bottom.
    # Band rows: 0 = GY-140, so GY is at row 140 of the band.
    gy_in_band = GY - y0
    dest_gy = ROAD_H - ROAD_SINK  # row of the road line on the canvas
    dest_y0 = dest_gy - gy_in_band
    dest_y1 = dest_y0 + band.shape[0]
    src_y0 = 0
    if dest_y0 < 0:
        src_y0 = -dest_y0
        dest_y0 = 0
    if dest_y1 > ROAD_H:
        band_h = ROAD_H - dest_y0
        band = band[src_y0 : src_y0 + band_h]
        dest_y1 = ROAD_H
    else:
        band = band[src_y0:]
        dest_y1 = dest_y0 + band.shape[0]
    canvas[dest_y0:dest_y1, :, :3] = band
    canvas[dest_y0:dest_y1, :, 3] = 255
    # Soften the top 16 px so the platform doesn't hard-cut against mid hills.
    fade = 16
    if dest_y1 - dest_y0 > fade:
        ramp = np.linspace(0, 255, fade, dtype=np.float32)
        canvas[dest_y0 : dest_y0 + fade, :, 3] = ramp.astype(np.uint8)[:, None]
    return canvas


def tight(rgba: np.ndarray, pad: int = 8) -> tuple[np.ndarray, tuple[int, int]]:
    a = rgba[:, :, 3]
    ys, xs = np.where(a > 12)
    if len(xs) < 20:
        return rgba, (0, 0)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(rgba.shape[0], int(ys.max()) + pad + 1)
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(rgba.shape[1], int(xs.max()) + pad + 1)
    return rgba[y0:y1, x0:x1], (x0, y0)


def extract_object(strip: np.ndarray, y0: int, y1: int, x0: int, x1: int, seed_rect) -> np.ndarray:
    """GrabCut an object from an official crop, punch smooth soil around it."""
    tile = strip[y0:y1, x0:x1].copy()
    h, w = tile.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    sx0, sy0, sx1, sy1 = seed_rect
    mask[sy0:sy1, sx0:sx1] = cv2.GC_PR_FGD
    inner = (
        max(0, sx0 + 8),
        max(0, sy0 + 8),
        min(w, sx1 - 8),
        min(h, sy1 - 8),
    )
    mask[inner[1] : inner[3], inner[0] : inner[2]] = cv2.GC_FGD
    # borders are sure bg
    mask[:2] = cv2.GC_BGD
    mask[-2:] = cv2.GC_BGD
    mask[:, :2] = cv2.GC_BGD
    mask[:, -2:] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(tile, cv2.COLOR_RGB2BGR), mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    keep = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    keep = cv2.morphologyEx(keep.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    # drop tiny crumbs
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep)
    if n > 1:
        keep_id = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        keep = (lab == keep_id).astype(np.uint8)
    dist = cv2.distanceTransform(keep, cv2.DIST_L2, 5)
    a = np.clip((dist - 0.3) / 1.8, 0, 1)
    rgba = np.dstack([tile, (a * 255).round().astype(np.uint8)])
    return rgba


def make_find_sprites(strip: np.ndarray) -> list[dict]:
    """Chain, bone, boat as tight sprites, not full UG tiles."""
    out = []
    # chain under the barrier, official x~40-700, in the UG band
    chain = extract_object(strip, GY + 80, GY + 415, 0, 720, (40, 40, 680, 300))
    # bone in the shlam cave ~ x 3500-4300
    bone = extract_object(strip, GY + 80, GY + 415, 3400, 4300, (80, 80, 820, 300))
    # boat on the water ~ x 7080-8000
    boat = extract_object(strip, GY + 120, GY + 415, 7000, 8200, (80, 40, 1100, 260))

    specs = [
        ("chain", 200, chain, 0),
        ("bone", 17500, bone, 3500 + 80 - 0),  # placeholder, recomputed below
        ("boat", 32000, boat, 0),
    ]
    # recompute dx from official x of tight crop vs postman at that step
    origins = {"chain": 0, "bone": 3400, "boat": 7000}
    y0s = {"chain": GY + 80, "bone": GY + 80, "boat": GY + 120}
    names = {"chain": chain, "bone": bone, "boat": boat}
    steps = {"chain": 200, "bone": 17500, "boat": 32000}
    sprites = []
    for name, rgba in names.items():
        crop, (xa, ya) = tight(rgba, pad=6)
        # defringe lightly
        crop = defringe(crop, px=2)
        save_png(crop, CH / "underground" / f"find_{name}.png", optimize=False)
        mag(crop, OUT / f"find_{name}.jpg", tw=500)
        # official left of crop in strip x
        off_x = origins[name] + xa
        off_y0 = y0s[name] + ya  # strip y of top
        h, w = crop.shape[:2]
        # bottom in strip y
        bottom = off_y0 + h
        sink = int(bottom - GY)
        # world: postman at step is at screen 0.55*W; sprite left at official x
        # relative to the frame whose step we're using... use dx so that
        # world_left = x(start+step)+dx equals official x mapped through pixelsPerStep?
        # Official strip is 11700 px = 45000 steps → 11700/45000=0.26 px/step, but the
        # game uses 1.17 px/step (10x, one official frame = 1170 design px = 1000 steps).
        # Place at the same step, dx so the sprite sits near the postman / official spot.
        # Official object x within the 1170 frame containing this step:
        frame = int(round(steps[name] / 1000))  # 0, 17, 32 → slices 0, 17? 17500/1000=17.5, places are every 1000 local steps = 1170 px
        # local official x = off_x, step is place-ish
        # postman at that step is at official x = (step/45000)*11700 = step * 0.26, no:
        # 1000 steps = 1170 design px, official x = (step / 1000) * 1170
        postman_official_x = (steps[name] / 1000.0) * W_PLACE
        # but we want the sprite's left at official off_x in design coords (1:1 with official px)
        # dx = official_left - postman_x_in_design
        # postman design x at step relative to chapter start: wait,
        # world_left = geo.x(start+step) + dx, and geo.x uses 1.17*step.
        # For places, dx = xa - 0.55*W_PLACE so the official frame's left (+xa) lines up
        # with the camera/postman convention. Same here: treat official x as xa in a
        # virtual frame whose left is floor(off_x / 1)? 
        # Simpler: dx = off_x - (steps[name]/1000)*W_PLACE - 0? 
        # place shlagbaum step 0, xa=0, dx=-0.55*1170=-643.5, meaning the frame left
        # is 643.5 left of the postman (who is at 0.55 of the 1170 frame).
        # For a sprite at official x=off_x, the "frame" is the whole strip,
        # dx = off_x - 0.55*W_PLACE - (step/1000)*W_PLACE
        dx = round(off_x - 0.55 * W_PLACE - (steps[name] / 1000.0) * W_PLACE, 1)
        prop = {
            "image": f"underground/find_{name}",
            "layer": "underground",
            "step": steps[name],
            "dx": dx,
            "height": int(h),
            "sink": int(sink),
            "z": 2,
            "pixelSize": [int(w), int(h)],
        }
        print(f"  find {name} {w}x{h} sink={sink} dx={dx} official_x={off_x}")
        sprites.append(prop)
    return sprites


def defringe(rgba: np.ndarray, px: int = 3) -> np.ndarray:
    a = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    L, A, B = labAB(rgb)
    chroma = np.sqrt(A * A + B * B)
    opaque = (a > 10).astype(np.uint8)
    er = cv2.erode(opaque, np.ones((px * 2 + 1, px * 2 + 1), np.uint8))
    edge = (opaque > 0) & (er == 0)
    foliage = (A < -8) & (L < 185)
    skyish = ((L > 160) & (chroma < 35)) | ((L < 80) & (chroma < 25)) | (
        (A > -8) & (A < 8) & (B < 8) & (chroma < 22) & (L > 80)
    )
    cyan = (B < 2) & (A > -15) & (A < 12) & (L > 70) & (~foliage)
    fringe = edge & (~foliage) & (skyish | cyan | ((L > 160) & (chroma < 50)))
    out = rgba.copy()
    out[fringe, 3] = 0
    return out


def punch_atmosphere(rgba: np.ndarray) -> np.ndarray:
    """Remove leftover sky/haze. Flood from already-transparent pixels and the top."""
    rgb = rgba[:, :, :3]
    a = rgba[:, :, 3]
    h, w = a.shape
    L, A, B = labAB(rgb)
    chroma = np.sqrt(A * A + B * B)
    var = variance(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    foliage = (A < -8) & (L < 185) & (var > 25)
    # low-texture wash: pale, dusk, night, gray
    wash = (
        ((L > 145) & (chroma < 40) & (var < 70))
        | ((L > 80) & (L < 180) & (chroma < 22) & (var < 55) & (A > -8) & (A < 8))
        | ((L < 80) & (chroma < 25) & (var < 40))
    )
    wash &= ~foliage
    # Don't punch textured clay buildings (high var or strong ochre chroma)
    clay = (B > 18) & (chroma > 22) & (var > 40)
    wash &= ~clay
    # Flood from top row and from existing transparent into wash
    trans = (a <= 10).astype(np.uint8) * 255
    seed = trans.copy()
    seed[0] = 255
    kernel = np.ones((3, 3), np.uint8)
    mask_wash = (wash | (a <= 10)).astype(np.uint8) * 255
    # dilate-flood: grow seed inside mask_wash
    grown = seed.copy()
    for _ in range(max(h, w)):
        nxt = cv2.dilate(grown, kernel)
        nxt = cv2.bitwise_and(nxt, mask_wash)
        if np.array_equal(nxt, grown):
            break
        grown = nxt
    punch = (grown > 0) & (a > 10)
    # never punch the bottom 200 px (terrain)
    punch[-200:] = False
    out = rgba.copy()
    out[punch, 3] = 0
    return out


def punch_clouds_from_place(rgba: np.ndarray) -> np.ndarray:
    """Remove floating clay-cloud remnants from the place; clouds are separate sprites."""
    a = rgba[:, :, 3]
    h, w = a.shape
    L, A, B = labAB(rgba[:, :, :3])
    # bottom-connected = keep
    keep = np.zeros((h, w), np.uint8)
    keep[h - 1] = (a[h - 1] > 10).astype(np.uint8)
    for y in range(h - 2, -1, -1):
        seed = cv2.dilate(keep[y + 1].reshape(1, -1), np.ones((1, 3), np.uint8)).reshape(-1)
        keep[y] = ((a[y] > 10) & (seed > 0)).astype(np.uint8)
    floating = (a > 10) & (keep == 0)
    # only punch floating ochre/beige blobs in the upper 70%
    y = np.arange(h)[:, None]
    clayish = (B > 4) | ((L > 130) & (L < 230))
    punch = floating & clayish & (y < int(h * 0.72))
    out = rgba.copy()
    out[punch, 3] = 0
    return out


def punch_below_road(rgba: np.ndarray, y0_strip: int) -> np.ndarray:
    h = rgba.shape[0]
    out = rgba.copy()
    mask = (np.arange(h) + y0_strip) >= GY
    out[mask, :, 3] = 0
    return out


def punch_approach_sand(rgba: np.ndarray, y0_strip: int) -> np.ndarray:
    """Keep a ground island under structures; punch full-width approach sand."""
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3]
    a = rgba[:, :, 3]
    L, A, B = labAB(rgb)
    chroma = np.sqrt(A * A + B * B)
    rows = np.arange(h)[:, None] + y0_strip
    in_band = (rows >= (GY - 52)) & (rows < GY) & (a > 10)
    # support columns: structure above the path
    horiz = cv2.morphologyEx((a > 10).astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 150), np.uint8))
    is_horiz = horiz.sum(axis=1) > 90
    body = (rows >= (GY - 280)) & (rows < (GY - 60)) & (a > 10) & (~is_horiz[:, None])
    grass = (A < -8) & (a > 10) & (rows >= (GY - 140)) & (rows < GY)
    support = (body.sum(axis=0) > 35) | grass.any(axis=0)
    support = cv2.dilate(support.astype(np.uint8).reshape(1, -1), np.ones((1, 17), np.uint8)).reshape(-1) > 0
    island = np.zeros(w, bool)
    cols = np.where(support)[0]
    if len(cols):
        pad = 48
        island[max(0, int(cols.min()) - pad) : min(w, int(cols.max()) + pad + 1)] = True
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mu = cv2.blur(gray, (15, 5))
    var = cv2.blur((gray - mu) ** 2, (15, 5))
    is_sand = ((np.abs(A - 7) < 12) & (B > 16) & (B < 58) & (L > 80) & (L < 185) & (var < 40))
    punch = in_band & is_sand & (~island[None, :])
    out = rgba.copy()
    out[punch, 3] = 0
    # fade remaining unique floor at sprite edges
    remaining = in_band & (~punch)
    fade = 80
    ramp = np.ones(w, np.float32)
    if w > 2 * fade:
        ramp[:fade] = np.linspace(0, 1, fade)
        ramp[-fade:] = np.linspace(1, 0, fade)
    out[:, :, 3] = np.where(
        remaining[:, :, 0] if remaining.ndim == 3 else remaining,
        np.clip(out[:, :, 3] * ramp[None, :], 0, 255).astype(np.uint8),
        out[:, :, 3],
    )
    return out


def tight_place(rgba: np.ndarray, meta: dict) -> tuple[np.ndarray, dict]:
    a = rgba[:, :, 3]
    ys, xs = np.where(a > 12)
    if len(xs) < 80:
        return rgba, meta
    pad = 16
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(rgba.shape[0], int(ys.max()) + pad)
    xa = max(0, int(xs.min()) - pad)
    xb = min(rgba.shape[1], int(xs.max()) + pad)
    crop = rgba[y0:y1, xa:xb]
    new = dict(meta)
    new["y0"] = int(meta["y0"] + y0)
    new["xa"] = int(meta["xa"] + xa)
    new["xb"] = int(meta["xa"] + xb)
    new["pixelSize"] = [int(crop.shape[1]), int(crop.shape[0])]
    new["height"] = int(crop.shape[0])
    new_bottom = meta["y0"] + y1
    new["sink"] = int(new_bottom - GY)
    new["dx"] = round(new["xa"] - 0.55 * W_PLACE, 1)
    return crop, new


def extract_clouds(strip: np.ndarray) -> list[dict]:
    """Official clay clouds as separate sprites (shlagbaum + otstoyniki)."""
    sprites = []
    # slices 0 and 1, upper sky
    for slice_i, step, tag in ((0, 0, "shlag"), (1, 4000, "otst")):
        x0 = slice_i * W_PLACE
        tile = strip[0:1100, x0 : x0 + W_PLACE]
        rgb = tile
        h, w, _ = rgb.shape
        L, A, B = labAB(rgb)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        var = variance(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
        # sky model: per-column linear fit of low-var pixels
        resid = np.zeros((h, w), np.float32)
        for x in range(w):
            ys = np.where(var[:, x] < 25)[0]
            if len(ys) < 20:
                ys = np.arange(0, min(h, 200))
            # fit L
            p = np.polyfit(ys, L[ys, x], 1)
            pred = np.polyval(p, np.arange(h))
            resid[:, x] = np.abs(L[:, x] - pred)
        # clouds deviate from the sky and have some clay chroma or form
        cloud = (resid > 14) & (var > 6) & (L > 100) & (L < 235)
        # not terrain (bottom of this upper crop is already sky / hill tops — hills are lower)
        # drop bottom-connected in this crop only if they touch y=1099 AND are wide (hills)
        cloud = cv2.morphologyEx(cloud.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cloud = cv2.morphologyEx(cloud, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(cloud)
        # keep reasonably large components that don't sit on the bottom edge (hills)
        kept = np.zeros((h, w), np.uint8)
        for i in range(1, n):
            area = st[i, cv2.CC_STAT_AREA]
            y = st[i, cv2.CC_STAT_TOP]
            hh = st[i, cv2.CC_STAT_HEIGHT]
            if area < 400:
                continue
            # skip if mostly in the lower 150 px (hills / structures)
            if y + hh > h - 10 and y > 800:
                continue
            if y > 850:
                continue
            kept[lab == i] = 255
        if kept.sum() < 200:
            print(f"  no clouds in {tag}")
            continue
        # split into individual sprites (each component)
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(kept)
        # merge if many tiny — keep components >= 800, or the largest 3
        comps = [(st2[i, cv2.CC_STAT_AREA], i) for i in range(1, n2)]
        comps.sort(reverse=True)
        use = [i for a, i in comps if a >= 800][:4]
        for k, i in enumerate(use):
            m = (lab2 == i).astype(np.uint8)
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
            # reject if bbox is almost full-width (sky wash leak)
            if st2[i, cv2.CC_STAT_WIDTH] > w * 0.85:
                print(f"  skip full-width blob in {tag}")
                continue
            dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
            alpha = np.clip((dist - 0.4) / 2.0, 0, 1)
            rgba = np.dstack([rgb, (alpha * 255).round().astype(np.uint8)])
            crop, (xa, ya) = tight(rgba, pad=6)
            crop = defringe(crop, px=2)
            # skip if still huge and very rectangular (failed sky)
            ch, cw = crop.shape[:2]
            if cw > 900 and ch < 200:
                print(f"  skip strip-like {tag}_{k} {cw}x{ch}")
                continue
            fname = f"cloud_{tag}_{k}"
            save_png(crop, CH / "sky" / f"{fname}.png", optimize=False)
            mag(crop, OUT / f"{fname}.jpg", tw=600)
            dx = round(xa - 0.55 * W_PLACE, 1)
            sink = int((ya + ch) - GY)  # large negative (high in the sky)
            prop = {
                "image": f"sky/{fname}",
                "layer": "main",
                "step": step,
                "dx": dx,
                "height": int(ch),
                "sink": sink,
                "z": -8,
                "pixelSize": [int(cw), int(ch)],
            }
            print(f"  cloud {fname} {cw}x{ch} sink={sink} dx={dx}")
            sprites.append(prop)
    return sprites


def extract_moon_clean(strip: np.ndarray) -> dict | None:
    """Smooth crescent filled with official moon texture."""
    x0 = 9 * W_PLACE
    tile = strip[0:H_CROP, x0 : x0 + W_PLACE]
    # Official moon roughly x 120-340, y 230-680
    y0, y1, xa, xb = 200, 720, 100, 380
    crop = tile[y0:y1, xa:xb]
    h, w, _ = crop.shape
    L, A, B = labAB(crop)
    chroma = np.sqrt(A * A + B * B)
    # moon = brighter than night sky
    body = (L > 48) & ~((L < 72) & (chroma < 22) & (B < -4))
    body[:, :8] = 0  # keep lamp off
    body = cv2.morphologyEx(body.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    body = cv2.morphologyEx(body, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(body)
    if n <= 1:
        return None
    keep_id = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    body = (lab == keep_id).astype(np.uint8)
    # Fit a smooth crescent: difference of two circles around the component.
    ys, xs = np.where(body > 0)
    if len(xs) < 200:
        return None
    # outer circle: bounding of moon; inner: the dark bite
    # Use distance-smooth of the official mask, then close tiny holes that are
    # not the main inner crescent (components of ~body inside bbox that are small).
    inv = (1 - body).astype(np.uint8)
    # inner hole = inverted components that do not touch the crop border
    n3, lab3, st3, _ = cv2.connectedComponentsWithStats(inv)
    hole = np.zeros_like(body)
    for i in range(1, n3):
        ys2, xs2 = np.where(lab3 == i)
        if ys2.min() <= 1 or xs2.min() <= 1 or ys2.max() >= h - 2 or xs2.max() >= w - 2:
            continue
        hole[lab3 == i] = 1
    # fill pinholes in the body (not the main hole)
    filled = body.copy()
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    # restore the big inner hole
    if hole.any() and hole.sum() > 200:
        filled[hole > 0] = 0
        # slightly inflate the hole for a cleaner inner edge
        filled = filled & (~cv2.dilate(hole, np.ones((3, 3), np.uint8)))
    # smooth the outline: blur and threshold
    blur = cv2.GaussianBlur(filled.astype(np.float32), (7, 7), 0)
    smooth = (blur > 0.45).astype(np.uint8)
    dist = cv2.distanceTransform(smooth, cv2.DIST_L2, 5)
    alpha = np.clip((dist - 0.3) / 1.7, 0, 1)
    rgba = np.dstack([crop, (alpha * 255).round().astype(np.uint8)])
    # punch leftover night sky
    Lc, Ac, Bc = labAB(rgba[:, :, :3])
    chrom = np.sqrt(Ac * Ac + Bc * Bc)
    rgba[:, :, 3] = np.where((Lc < 68) & (chrom < 22), 0, rgba[:, :, 3])
    rgba, (tx, ty) = tight(rgba, pad=4)
    rgba = defringe(rgba, px=2)
    save_png(rgba, CH / "places" / "sprite_moon.png", optimize=False)
    mag(rgba, OUT / "sprite_moon.jpg", tw=320)
    hh, ww = rgba.shape[:2]
    dx = round((xa + tx) - 0.55 * W_PLACE, 1)
    sink = int((y0 + ty + hh) - GY)
    prop = {
        "image": "places/sprite_moon",
        "layer": "main",
        "step": 45000,
        "dx": dx,
        "height": int(hh),
        "sink": int(sink),
        "z": -6,
        "pixelSize": [int(ww), int(hh)],
    }
    print(f"  moon {ww}x{hh} sink={sink} dx={dx}")
    return prop


def recut_places(strip: np.ndarray) -> list[dict]:
    meta_list = []
    for name, step, idx in PLACES:
        rgba, meta, _ = cut_place(strip, idx, name)
        if name == "shlagbaum":
            rgba = punch_shlagbaum_postman(rgba)
        rgba = punch_clouds_from_place(rgba)
        rgba = punch_atmosphere(rgba)
        rgba = punch_leftover_sky(rgba)
        if name == "naberezhnaya":
            rgba = punch_nab_haze(rgba)
        rgba = punch_below_road(rgba, meta["y0"])
        rgba = punch_approach_sand(rgba, meta["y0"])
        rgba = defringe(rgba, px=3)
        rgba, meta = tight_place(rgba, meta)
        save_png(rgba, CH / "places" / f"place_{name}_main.png")
        mag(rgba, OUT / f"place_{name}.jpg", tw=480)
        print(f"  place {name} {meta['pixelSize']} sink={meta['sink']} dx={meta['dx']} opaque={(rgba[:,:,3]>10).mean()*100:.1f}%")
        meta_list.append({
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
        })
    return meta_list


def stamp_off(place_path: Path, place_meta: dict, sprite: np.ndarray, prop: dict, protect_left=0) -> None:
    ver = np.array(Image.open(place_path))
    moon_y_strip = prop["sink"] + GY - prop["height"]
    moon_x = int(round(prop["dx"] + 0.55 * W_PLACE))
    y = int(moon_y_strip - place_meta["y0"])
    x = moon_x - int(place_meta.get("xa") or 0)
    m = (sprite[:, :, 3] > 8).astype(np.uint8)
    m = cv2.dilate(m, np.ones((31, 31), np.uint8))
    mh, mw = m.shape
    canvas = np.zeros(ver.shape[:2], np.uint8)
    yy0, xx0 = max(0, y), max(0, x)
    yy1, xx1 = min(ver.shape[0], y + mh), min(ver.shape[1], x + mw)
    if yy1 > yy0 and xx1 > xx0:
        canvas[yy0:yy1, xx0:xx1] = m[(yy0 - y) : (yy1 - y), (xx0 - x) : (xx1 - x)]
        if protect_left:
            canvas[:, :protect_left] = 0
        ver[:, :, 3] = np.where(canvas > 0, 0, ver[:, :, 3])
        ver = defringe(ver, px=2)
        save_png(ver, place_path)
        mag(ver, OUT / "place_verkhnyaya.jpg", tw=480)
        print("  stamped moon off verkhnyaya")


def patch_installer() -> None:
    """Stop install_chapter4_assets.py from overwriting the new tiles."""
    p = Path(__file__).resolve().parent / "install_chapter4_assets.py"
    t = p.read_text()
    marker = "# PASS4: do not overwrite seamless tiles"
    if marker in t:
        print("  installer already patched")
        return
    old = """    road = make_road(strip)
    save_png(road, CH / "road" / "road_main.png")
    road_meta.append({
"""
    # more reliable: wrap the UG/road writes
    # Replace the specific cut_ug / make_road block in main
    start = t.find("    road = make_road(strip)")
    if start < 0:
        # try other pattern
        start = t.find("save_png(cut_ug(")
        print("  warning: make_road not found, searching cut_ug")
    if start < 0:
        print("  ERROR: could not patch installer")
        return
    # Find a safe start of the road/ug section — go back to 'road = make_road' or comment
    # We'll insert a return-from-block by replacing from make_road through ug loop.
    # Use a unique hook at the beginning of main's asset writes.
    hook = "    road = make_road(strip)"
    if hook not in t:
        print("  installer hook missing, writing a preamble in main instead")
        t = t.replace(
            "def main():",
            "def main():\n"
            "    " + marker + "\n"
            "    # Road + UG tiles are owned by rebuild_chapter4_pass4.py.\n"
            "    # Re-running this installer must not overwrite them with per-place crops.\n"
            "    import rebuild_chapter4_pass4 as _pass4\n"
            "    _pass4.main(skip_places=False)\n"
            "    return\n",
        )
        p.write_text(t)
        print("  installer main() now delegates to pass4")
        return
    # Replace from hook until after the ug_{name} loop
    end_tag = "        save_png(cut_ug(strip, idx * W_PLACE + 10), CH / \"underground\" / f\"ug_{name}.png\")"
    e = t.find(end_tag)
    if e < 0:
        t = t.replace(
            "def main():",
            "def main():\n    " + marker + "\n    import rebuild_chapter4_pass4 as _pass4\n    _pass4.main()\n    return\n",
        )
        p.write_text(t)
        print("  installer main() delegated (fallback)")
        return
    e = e + len(end_tag)
    replacement = (
        "    " + marker + "\n"
        "    # Tiles (road, UG neutral + variants, finds) are built by\n"
        "    # tools/rebuild_chapter4_pass4.py. Do not cut unique UG crops here.\n"
        "    import rebuild_chapter4_pass4 as _pass4\n"
        "    _pass4.build_tiles(np.array(Image.open(STRIP).convert('RGB')))\n"
    )
    t = t[:start] + replacement + t[e:]
    p.write_text(t)
    print("  installer road/UG writes replaced")


def build_tiles(strip: np.ndarray) -> dict:
    """Road + UG tiles + finds. Used by installer and main."""
    N, variants = make_ug_tiles(strip)
    save_png(N, CH / "underground" / "ug_neutral_tile.png", optimize=False)
    x3(N, OUT / "ugN_x3.jpg")
    # delete old full-tile finds if present
    for old in ("ug_chain", "ug_bone", "ug_boat", "ug_shlagbaum", "ug_otstoyniki",
                "ug_truby", "ug_shlam", "ug_kotelnaya", "ug_sarai", "ug_naberezhnaya",
                "ug_dvory", "ug_otdelenie", "ug_verkhnyaya"):
        p = CH / "underground" / f"{old}.png"
        if p.exists():
            p.unlink()
            print("  removed", p.name)
    var_meta = []
    for name, step, tile in variants:
        save_png(tile, CH / "underground" / f"ug_{name}.png", optimize=False)
        x3(tile, OUT / f"ug_{name}_x3.jpg")
        join = np.concatenate([N, tile, N], axis=1)
        Image.fromarray(join).resize((1200, max(40, int(1200 * join.shape[0] / join.shape[1]))), Image.Resampling.LANCZOS).save(
            OUT / f"ug_{name}_joinN.jpg", quality=92
        )
        var_meta.append({"image": f"underground/ug_{name}", "step": step, "dx": 0.0})
        print(f"  variant {name} {tile.shape} at step {step}")
    road = make_road(strip)
    save_png(road, CH / "road" / "road_main.png", optimize=False)
    x3(road, OUT / "road_x3.jpg")
    print(f"  road {road.shape} opaque rows={(road[:,:,3]>10).any(1).sum()}")
    finds = make_find_sprites(strip)
    return {
        "tilePixelSize": [int(N.shape[1]), int(N.shape[0])],
        "ug_variants": var_meta,
        "ug_find_sprites": finds,
        "road": {
            "image": "road/road_main",
            "height": ROAD_H,
            "sink": ROAD_SINK,
            "pixelSize": [int(road.shape[1]), int(road.shape[0])],
        },
    }


def main(skip_places: bool = False) -> None:
    print("load strip", STRIP)
    strip = np.array(Image.open(STRIP).convert("RGB"))
    tile_info = build_tiles(strip)
    clouds = extract_clouds(strip)
    moon = extract_moon_clean(strip)
    places = [] if skip_places else recut_places(strip)
    if moon is not None and places:
        vmeta = next((p for p in places if "verkhnyaya" in p["image"]), None)
        if vmeta:
            stamp_off(
                CH / "places" / "place_verkhnyaya_main.png",
                vmeta,
                np.array(Image.open(CH / "places" / "sprite_moon.png")),
                moon,
                protect_left=88,
            )
    # remove torn auto-loaded dawn scraps so installStvorSky won't pick them up
    for p in (CH / "sky").glob("cloud_dawn_*.png"):
        p.unlink()
        print("  removed", p.name)

    meta_path = CH / "install_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if places:
        meta["places"] = places
    # Torn cloud extracts and find sprites (chain/bone/boat with soil or water)
    # are saved on disk for later cleanup but are NOT placed: better absent
    # than ragged. Only the moon sprite is wired. Only the cracks variant
    # joins the neutral tile visually; stones is a different stratum.
    sprites = []
    if moon:
        sprites.append(moon)
    meta["sprites"] = sprites
    meta["ug_variants"] = [v for v in tile_info["ug_variants"] if "cracks" in v["image"]]
    meta["_held_back"] = {
        "clouds": [c.get("image") for c in clouds],
        "finds": [f.get("image") for f in tile_info["ug_find_sprites"]],
        "ug_variants_unused": [v for v in tile_info["ug_variants"] if "cracks" not in v["image"]],
    }
    meta["ug_finds"] = []  # no longer full-tile modules
    meta["tilePixelSize"] = tile_info["tilePixelSize"]
    meta["sky_cards"] = []
    meta["road"] = tile_info["road"]
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print("wrote", meta_path)
    patch_installer()
    print("pass4 done")


if __name__ == "__main__":
    main()
