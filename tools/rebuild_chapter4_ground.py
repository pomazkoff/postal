#!/usr/bin/env python3
"""Rebuild гл.4 road + underground the way гл.1–3 do it.

One seamless road tile and one seamless UG neutral in the official v5.3
palette (crop a uniform band, crossfade the wrap — same as env_ch1/tiles.py).
Unique underground finds become a few modules whose left/right edges are
identical to N. Places are recut as RGBA sprites without sky and without
the full-width ground strip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from install_chapter4_assets import (
    STRIP, CH, PLACES, CROP_X, W_PLACE, H_CROP, GY,
    cut_place, punch_shlagbaum_postman, punch_leftover_sky, punch_nab_haze,
    extract_moon, save_png, labAB, variance, make_tileable_x,
)

OUT_PREVIEW = Path("/tmp/ch4_qa_after3/inspect")
OUT_PREVIEW.mkdir(parents=True, exist_ok=True)


def seamless(im: np.ndarray, ov: int) -> np.ndarray:
    """env_ch1/tiles.py: crossfade the right overlap into the left edge."""
    a = im.astype(np.float32)
    w = a.shape[1]
    assert ov < w
    out = a[:, : w - ov].copy()
    t = np.linspace(0, 1, ov, dtype=np.float32)[None, :, None]
    out[:, :ov] = a[:, w - ov :] * (1 - t) + a[:, :ov] * t
    return np.clip(out, 0, 255).astype(im.dtype)


def x3_check(im: np.ndarray, path: Path, seam_color=(255, 0, 0)):
    if im.ndim == 2 or im.shape[2] == 3:
        rgb = im if im.ndim == 3 else np.dstack([im, im, im])
        a = np.full(rgb.shape[:2], 255, np.uint8)
        rgba = np.dstack([rgb, a])
    else:
        rgba = im
    h, w = rgba.shape[:2]
    canvas = np.zeros((h, w * 3, 4), np.uint8)
    for i in range(3):
        canvas[:, i * w : (i + 1) * w] = rgba
    vis = canvas[:, :, :3].copy()
    al = canvas[:, :, 3:4] / 255.0
    bg = np.zeros_like(vis)
    vis = (vis * al + bg * (1 - al)).astype(np.uint8)
    for i in (1, 2):
        vis[:, i * w] = seam_color
    Image.fromarray(vis).resize(
        (min(1600, vis.shape[1]), int(vis.shape[0] * min(1600, vis.shape[1]) / vis.shape[1])),
        Image.Resampling.LANCZOS,
    ).save(path, quality=92)
    print("  check", path.name)


def overlap_add_tile(src: np.ndarray, out_w: int, ov: int) -> np.ndarray:
    """Repeat a band with overlapped crossfades, then wrap-crossfade."""
    stride = src.shape[1] - ov
    n = int(np.ceil((out_w + ov) / stride)) + 2
    width = n * stride + ov
    ch = src.shape[2] if src.ndim == 3 else 1
    canvas = np.zeros((src.shape[0], width, ch), np.float32)
    wacc = np.zeros((width,), np.float32)
    t = np.ones(src.shape[1], np.float32)
    t[:ov] = np.linspace(0, 1, ov, dtype=np.float32)
    t[-ov:] = np.linspace(1, 0, ov, dtype=np.float32)
    for i in range(n):
        x = i * stride
        sl = src if src.ndim == 3 else src[:, :, None]
        canvas[:, x : x + src.shape[1]] += sl.astype(np.float32) * t[None, :, None]
        wacc[x : x + src.shape[1]] += t
    canvas /= np.maximum(wacc, 1e-4)[None, :, None]
    piece = canvas[:, : out_w + ov]
    return seamless(np.clip(piece, 0, 255).astype(np.uint8), ov)[:, :out_w]


def make_seamless_ug(strip: np.ndarray) -> np.ndarray:
    """Neutral UG tile 1148×415, horizontal clay strata, wrap-seamless.

    Source is a clean stretch of official v5.3 soil (mustard drips, brown
    layers) without the chain, barrel, boat or bone.
    """
    src = strip[GY : GY + 415, 1380:2100]
    return overlap_add_tile(src, 1148, ov=220)


def match_module_edges(mod: np.ndarray, N: np.ndarray, pure=90, blend=160) -> np.ndarray:
    """Ch1 seam.py without Flux: N owns the outer columns, center stays unique."""
    out = mod.astype(np.float32).copy()
    n = N.astype(np.float32)
    w = out.shape[1]
    out[:, :pure] = n[:, :pure]
    out[:, w - pure :] = n[:, w - pure :]
    for i in range(blend):
        t = (i + 1) / blend
        out[:, pure + i] = (1 - t) * n[:, pure + i] + t * out[:, pure + i]
        out[:, w - pure - 1 - i] = (1 - t) * n[:, w - pure - 1 - i] + t * out[:, w - pure - 1 - i]
    return np.clip(out, 0, 255).astype(np.uint8)


def make_ug_finds(strip: np.ndarray, N: np.ndarray) -> list[tuple[str, int, np.ndarray]]:
    """Intended finds only, full tiles with N edges. (name, step, tile)."""
    specs = [
        # chain under the barrier
        ("chain", 200, 40),
        # bone in the shlam cave
        ("bone", 17500, 3500),
        # boat on the naberezhnaya water
        ("boat", 32000, 7080),
    ]
    out = []
    for name, step, x in specs:
        tile = strip[GY : GY + 415, x : x + 1148]
        if tile.shape[1] < 1148:
            pad = np.zeros((415, 1148, 3), np.uint8)
            pad[:, : tile.shape[1]] = tile
            tile = pad
        tile = match_module_edges(tile, N)
        out.append((name, step, tile))
    return out


def make_seamless_road(strip: np.ndarray) -> np.ndarray:
    """2400×680 RGBA road, transparent above the path, wrap-seamless."""
    src = strip[GY - 55 : GY + 25, 300:500]  # 200×80 clean official sand
    band = overlap_add_tile(src, 2400, ov=80)
    canvas = np.zeros((680, 2400, 4), np.uint8)
    h = band.shape[0]
    canvas[680 - h :, :, :3] = band
    a = np.ones((h, 2400), np.float32)
    fade = 20
    a[:fade] = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    canvas[680 - h :, :, 3] = (a * 255).round().astype(np.uint8)
    return canvas


def defringe(rgba: np.ndarray, px: int = 2) -> np.ndarray:
    """Eat sky-colored and high-L fringe on the alpha edge (1–2 px)."""
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
    # also very thin bright halo
    fringe = edge & (~foliage) & (skyish | ((L > 170) & (chroma < 45)))
    out = rgba.copy()
    out[fringe, 3] = 0
    return out


def punch_ground(rgba: np.ndarray, y0_strip: int) -> np.ndarray:
    """Remove the full-width road/sand strip; keep a footprint under structures.

    Same idea as гл.1/3 place sprites: a hut sits on a small ground island,
    the seamless road tile shows everywhere else.
    """
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3]
    a = rgba[:, :, 3]
    L, A, B = labAB(rgb)
    chroma = np.sqrt(A * A + B * B)
    # strip y of each row
    # sand / clay path (ochre), in the road band
    rows = np.arange(h)[:, None] + y0_strip
    # Everything below the road line belongs to the UG tile, not the place.
    # IMPORTANT: punch must be a boolean mask. A uint8 mask (e.g. from
    # `~keep` on uint8) would be treated as fancy indices and do nothing.
    below = (rows >= GY) & (a > 0)
    in_band = (rows >= (GY - 52)) & (rows < GY) & (a > 10)
    # Horizontal bars (barrier arm, roofs, ground, long clouds) must not
    # mark every column as a support.
    horiz = cv2.morphologyEx(
        (a > 10).astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 150), np.uint8)
    )
    is_horiz = horiz.sum(axis=1) > 90
    body = (rows >= (GY - 260)) & (rows < (GY - 70)) & (a > 10) & (~is_horiz[:, None])
    low = (rows >= (GY - 130)) & (rows < (GY - 48)) & (a > 10) & (~is_horiz[:, None])
    grass = (A < -8) & (a > 10) & (rows >= (GY - 140)) & (rows < GY)
    support = (body.sum(axis=0) > 40) | (low.sum(axis=0) > 10) | grass.any(axis=0)
    support = cv2.dilate(
        support.astype(np.uint8).reshape(1, -1), np.ones((1, 13), np.uint8)
    ).reshape(-1) > 0
    # Official v5.3 path sand (Lab of the clean crop at x 300:500), plus
    # the darker/smoother DOF path under structures (B a bit lower, L lower)
    # only when the fill is smooth — so cobbles/planks/water stay.
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mu = cv2.blur(gray, (15, 5))
    var = cv2.blur((gray - mu) ** 2, (15, 5))
    tight = (np.abs(A - 7) < 11) & (B > 26) & (B < 58) & (L > 100) & (L < 185)
    wide = (np.abs(A - 7) < 12) & (B > 16) & (B < 58) & (L > 80) & (L < 185)
    is_sand = tight | (wide & (var < 14))
    # Feet under sand must come from nearby non-sand bases only — not from
    # a mid-air barrier arm in the body window, which is wider than the posts.
    near_ns = (
        (rows >= (GY - 80)) & (rows < (GY - 48)) & (a > 10)
        & (~is_sand) & (~is_horiz[:, None])
    )
    sand_feet = cv2.dilate(
        (near_ns.any(axis=0) | grass.any(axis=0)).astype(np.uint8).reshape(1, -1),
        np.ones((1, 11), np.uint8),
    ).reshape(-1) > 0
    punch = (below | (in_band & is_sand & ~sand_feet[None, :])).astype(bool)
    out = rgba.copy()
    out[punch, 3] = 0
    # Unique floors (promenade, courtyard) stay, but fade at the sprite
    # edges so they don't hard-cut against the seamless road tile.
    remaining = in_band & (~punch) & (~support[None, :])
    fade = 120
    ramp = np.ones(w, np.float32)
    if w > 2 * fade:
        ramp[:fade] = np.linspace(0, 1, fade)
        ramp[-fade:] = np.linspace(1, 0, fade)
    out[:, :, 3] = np.where(
        remaining,
        np.clip(out[:, :, 3] * ramp[None, :], 0, 255).astype(np.uint8),
        out[:, :, 3],
    )
    return out


def tight_crop(rgba: np.ndarray, meta: dict) -> tuple[np.ndarray, dict]:
    """Tight bbox like a гл.3 sprite, keep dx aligned to the official frame."""
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
    # meta['xa'] is already in slice coords (offset from official frame left)
    new = dict(meta)
    new["y0"] = int(meta["y0"] + y0)
    new["xa"] = int(meta["xa"] + xa)
    new["xb"] = int(meta["xa"] + xb)
    new["pixelSize"] = [int(crop.shape[1]), int(crop.shape[0])]
    new["height"] = int(crop.shape[0])
    # sink: sprite bottom should still sit on the road.
    # Original sink was 40 with crop bottom at H_CROP (=GY+40).
    # New bottom is at meta['y0']+y1 in strip coords.
    new_bottom = meta["y0"] + y1
    new["sink"] = int(new_bottom - GY)
    new["dx"] = round(new["xa"] - 0.55 * W_PLACE, 1)
    return crop, new


def mag_preview(rgba, path, tw=400):
    al = rgba[:, :, 3:4] / 255.0
    bg = np.zeros_like(rgba[:, :, :3])
    bg[:] = [200, 80, 160]
    comp = (rgba[:, :, :3] * al + bg * (1 - al)).astype(np.uint8)
    h, w = comp.shape[:2]
    Image.fromarray(comp).resize((tw, max(20, int(tw * h / w))), Image.Resampling.LANCZOS).save(
        path, quality=90
    )


def main():
    print("load strip", STRIP)
    strip = np.array(Image.open(STRIP).convert("RGB"))

    # --- seamless tiles ---
    N = make_seamless_ug(strip)
    save_png(N, CH / "underground" / "ug_neutral_tile.png", optimize=False)
    x3_check(N, OUT_PREVIEW / "new_ugN_x3.jpg")

    finds = make_ug_finds(strip, N)
    find_meta = []
    for name, step, tile in finds:
        save_png(tile, CH / "underground" / f"ug_{name}.png", optimize=False)
        x3_check(tile, OUT_PREVIEW / f"new_ug_{name}_x3.jpg")
        # also a N|find|N join check
        join = np.concatenate([N, tile, N], axis=1)
        Image.fromarray(join).resize((1200, 140), Image.Resampling.LANCZOS).save(
            OUT_PREVIEW / f"new_ug_{name}_joinN.jpg", quality=92
        )
        find_meta.append({"image": f"underground/ug_{name}", "step": step, "dx": 0.0})

    road = make_seamless_road(strip)
    save_png(road, CH / "road" / "road_main.png", optimize=False)
    x3_check(road, OUT_PREVIEW / "new_road_x3.jpg")

    # Remove old unique-per-place UG crops so they cannot sneak back in.
    keep = {"ug_neutral_tile.png"} | {f"ug_{n}.png" for n, _, _ in finds}
    for p in (CH / "underground").glob("ug_*.png"):
        if p.name not in keep:
            print("  drop leftover module", p.name)
            p.unlink()

    # --- places as sprites ---
    place_meta = []
    sprite_meta = []
    for name, step, idx in PLACES:
        rgba, meta, _ = cut_place(strip, idx, name)
        if name == "shlagbaum":
            rgba = punch_shlagbaum_postman(rgba)
        rgba = punch_leftover_sky(rgba)
        if name == "naberezhnaya":
            rgba = punch_nab_haze(rgba)
        rgba = punch_ground(rgba, meta["y0"])
        rgba = defringe(rgba, px=2)
        rgba, meta = tight_crop(rgba, meta)
        save_png(rgba, CH / "places" / f"place_{name}_main.png")
        mag_preview(rgba, OUT_PREVIEW / f"place_{name}.jpg")
        opaque = (rgba[:, :, 3] > 10).mean() * 100
        print(f"    {name} opaque {opaque:.1f}% dx={meta['dx']} sink={meta['sink']} {meta['pixelSize']}")
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
        # extra dark-sky punch already in extract_moon; defringe too
        moon["rgba"] = defringe(moon["rgba"], px=2)
        # tight again
        a = moon["rgba"][:, :, 3]
        ys, xs = np.where(a > 12)
        if len(xs) > 50:
            y0, y1 = max(0, ys.min() - 4), min(moon["rgba"].shape[0], ys.max() + 4)
            xa, xb = max(0, xs.min() - 4), min(moon["rgba"].shape[1], xs.max() + 4)
            dy, dx_ = int(y0), int(xa)
            moon["rgba"] = moon["rgba"][y0:y1, xa:xb]
            p = moon["prop"]
            p["dx"] = round(p["dx"] + dx_, 1)
            p["height"] = int(moon["rgba"].shape[0])
            p["pixelSize"] = [int(moon["rgba"].shape[1]), p["height"]]
            p["sink"] = int(p["sink"] + dy)
        save_png(moon["rgba"], CH / "places" / "sprite_moon.png")
        mag_preview(moon["rgba"], OUT_PREVIEW / "sprite_moon.jpg", tw=280)
        sprite_meta.append(moon["prop"])
        # punch moon off verkhnyaya place
        vpath = CH / "places" / "place_verkhnyaya_main.png"
        ver = np.array(Image.open(vpath))
        vmeta = next(p for p in place_meta if "verkhnyaya" in p["image"])
        sp = moon["prop"]
        moon_y_strip = sp["sink"] + GY - sp["height"]
        moon_x = int(round(sp["dx"] + 0.55 * W_PLACE))
        y = int(moon_y_strip - vmeta["y0"])
        x = moon_x - int(vmeta.get("xa") or 0)
        m = (moon["rgba"][:, :, 3] > 8).astype(np.uint8)
        m = cv2.dilate(m, np.ones((27, 27), np.uint8))
        mh, mw = m.shape
        canvas = np.zeros(ver.shape[:2], np.uint8)
        yy0, xx0 = max(0, y), max(0, x)
        yy1, xx1 = min(ver.shape[0], y + mh), min(ver.shape[1], x + mw)
        if yy1 > yy0 and xx1 > xx0:
            canvas[yy0:yy1, xx0:xx1] = m[(yy0 - y) : (yy1 - y), (xx0 - x) : (xx1 - x)]
            canvas[:, : max(0, 88 - int(vmeta.get("xa") or 0))] = 0
            ver[:, :, 3] = np.where(canvas > 0, 0, ver[:, :, 3])
            ver = defringe(ver, px=2)
            save_png(ver, vpath)
            mag_preview(ver, OUT_PREVIEW / "place_verkhnyaya.jpg")

    # keep existing sky colors / far mid / clouds in install_meta, replace places/sprites/ug
    meta_path = CH / "install_meta.json"
    meta = json.loads(meta_path.read_text())
    meta["places"] = place_meta
    meta["sprites"] = sprite_meta
    meta["sky_cards"] = []
    meta["ug_finds"] = find_meta
    meta["road"] = {"road_main": [int(road.shape[1]), int(road.shape[0])]}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("install_meta updated, finds", find_meta)


if __name__ == "__main__":
    main()
