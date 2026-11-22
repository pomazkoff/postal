#!/usr/bin/env python3
"""Scene-accurate offline preview of гл.4 (and a гл.3 comparison frame).

Reproduces WorldScene / WorldGeometry for a 1170×2532 design frame:
  x = step * 1.17, cameraLead = (0.5-0.55)*1170, visible = [camX-W/2, camX+W/2]
  prop: anchor bottom-left, y = roadY - sink, height from JSON, aspect from pixelSize
  far/mid: tiled, layer.x = camX*(1-k), tiles laid in local x, fade/brightness as config
  sky: chapter gradient, with гл.4 day→dusk→night lerp
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Postman/GameAssets"
OUT = Path("/tmp/ch4_qa_after2/scene")
W, H = 1170, 2532
PPS = 1.17
ROAD_LINE_Y = 1720  # from top
ROAD_Y = H - ROAD_LINE_Y  # 812 from bottom
CAM_LEAD = (0.5 - 0.55) * W  # -58.5
CH4_START = 75000
CH3_START = 45000

# Cached textures
_TEX = {}


def load_tex(rel: str) -> np.ndarray:
    """RGBA uint8 array, or None if missing."""
    if rel in _TEX:
        return _TEX[rel]
    # rel is like Chapter4/places/foo or places/foo with folder known by caller
    p = ASSETS / f"{rel}.png"
    if not p.exists():
        p = ASSETS / f"{rel}.jpg"
    if not p.exists():
        _TEX[rel] = None
        return None
    im = Image.open(p).convert("RGBA")
    _TEX[rel] = np.array(im)
    return _TEX[rel]


def hex_rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def lerp_hex(a: str, b: str, t: float) -> str:
    t = max(0, min(1, t))
    ca, cb = hex_rgb(a), hex_rgb(b)
    r = tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*r)


def stvor_sky(sky: dict, local: float) -> tuple[str, str]:
    day_t, day_b = sky["topColor"], sky["bottomColor"]
    dusk_t = sky.get("duskTopColor") or day_t
    dusk_b = sky.get("duskBottomColor") or day_b
    night_t = sky.get("nightTopColor") or "#1D2534"
    night_b = sky.get("nightBottomColor") or "#212832"
    if local < 20000:
        return day_t, day_b
    if local < 28000:
        t = (local - 20000) / 8000
        return lerp_hex(day_t, dusk_t, t), lerp_hex(day_b, dusk_b, t)
    if local < 36000:
        return dusk_t, dusk_b
    if local < 42000:
        t = (local - 36000) / 6000
        return lerp_hex(dusk_t, night_t, t), lerp_hex(dusk_b, night_b, t)
    return night_t, night_b


def gradient_sky(top: str, bottom: str, road_frac: float = ROAD_LINE_Y / H) -> np.ndarray:
    tcol, bcol = np.array(hex_rgb(top), np.float32), np.array(hex_rgb(bottom), np.float32)
    img = np.zeros((H, W, 3), np.float32)
    road = int(H * road_frac)
    for y in range(H):
        u = 0 if y >= road else (1 - y / max(1, road))  # y is from top here? 
        # Canvas is stored top-to-bottom. Gradient: topColor at y=0, bottomColor at road line and below.
        if y >= road:
            u = 1
        else:
            u = y / max(1, road)
        img[y] = tcol * (1 - u) + bcol * u
    return img.round().astype(np.uint8)


def blit(canvas: np.ndarray, tex: np.ndarray, x: float, y_bottom: float, width: float, height: float):
    """Paste tex into canvas. canvas is HxWx3 or HxWx4, y_bottom is from the BOTTOM of the design frame? 

    We store canvas top-to-bottom, so design y_from_bottom = y_bottom maps to row = H - y_bottom - height? 
    Sprite anchor is bottom-left in scene coords (y up). Scene y=0 is the bottom of the 2532 frame.
    PNG row 0 is the top of the sprite. Sprite occupies scene y in [y_bottom, y_bottom+height].
    Canvas row for scene y is (H-1-y) approximately: row = H - (y_bottom+height) at the top of the sprite.
    """
    if tex is None or width <= 1 or height <= 1:
        return
    dst_h, dst_w = int(round(height)), int(round(width))
    if tex.shape[1] != dst_w or tex.shape[0] != dst_h:
        tex = np.array(Image.fromarray(tex).resize((dst_w, dst_h), Image.Resampling.LANCZOS))
    top_row = int(round(H - (y_bottom + height)))
    left = int(round(x))
    # clip
    src = tex
    sy0 = sx0 = 0
    sy1, sx1 = src.shape[0], src.shape[1]
    dy0, dx0 = top_row, left
    dy1, dx1 = dy0 + sy1, dx0 + sx1
    if dx0 < 0:
        sx0 -= dx0
        dx0 = 0
    if dy0 < 0:
        sy0 -= dy0
        dy0 = 0
    if dx1 > W:
        sx1 -= dx1 - W
        dx1 = W
    if dy1 > H:
        sy1 -= dy1 - H
        dy1 = H
    if dx0 >= dx1 or dy0 >= dy1 or sx0 >= sx1 or sy0 >= sy1:
        return
    patch = src[sy0:sy1, sx0:sx1]
    dst = canvas[dy0:dy1, dx0:dx1]
    if patch.shape[2] == 4:
        a = patch[:, :, 3:4].astype(np.float32) / 255.0
        rgb = patch[:, :, :3].astype(np.float32)
        base = dst[:, :, :3].astype(np.float32)
        dst[:, :, :3] = (rgb * a + base * (1 - a)).round().astype(np.uint8)
        if dst.shape[2] == 4:
            dst[:, :, 3] = np.maximum(dst[:, :, 3], patch[:, :, 3])
    else:
        dst[:, :, :3] = patch[:, :, :3]


def blit_world(canvas, tex, world_left, y_bottom, width, height, view_left):
    """world_left is scene x of the sprite's left edge; view_left is visible left (camX-W/2)."""
    blit(canvas, tex, world_left - view_left, y_bottom, width, height)


def layout_tiles(view_left, cam_x, k, tile_w, half=None):
    """Yield world-scene x of each visible tile (left edge).

    Layer position.x = camX*(1-k). Tile local x = i*tile_w.
    Scene x = camX*(1-k) + i*tile_w.
    layout localMinX = k*camX - half, first = floor(localMinX/w)
    """
    if half is None:
        half = W / 2 + 64
    local_min = k * cam_x - half
    local_max = k * cam_x + half
    if tile_w <= 0:
        return
    first = int(np.floor(local_min / tile_w))
    last = int(np.floor(local_max / tile_w))
    for i in range(first, last + 1):
        local_x = i * tile_w
        scene_x = cam_x * (1 - k) + local_x
        yield scene_x


def fade_top(tex: np.ndarray, fraction: float) -> np.ndarray:
    if tex is None or fraction <= 0:
        return tex
    out = tex.copy()
    h = out.shape[0]
    n = max(1, int(h * fraction))
    ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
    if out.shape[2] == 4:
        out[:n, :, 3] = (out[:n, :, 3].astype(np.float32) * ramp).round().astype(np.uint8)
    return out


def darken(tex: np.ndarray, brightness: float) -> np.ndarray:
    if tex is None or brightness >= 0.999:
        return tex
    out = tex.copy()
    out[:, :, :3] = (out[:, :, :3].astype(np.float32) * brightness).round().astype(np.uint8)
    return out


def render_chapter_frame(world, chapter_id: int, local_step: float, label: str, assets_override: Path | None = None):
    """Render one 1170×2532 frame. assets_override points at a folder of places/road for 'before'."""
    ch = next(c for c in world["chapters"] if c["id"] == chapter_id)
    layers = world["layers"]
    folder = ch["assetsFolder"]
    global_step = ch["startStep"] + local_step
    post_x = global_step * PPS
    cam_x = post_x + CAM_LEAD
    view_left = cam_x - W / 2

    sky_cfg = ch.get("sky") or {"topColor": layers["sky"]["topColor"], "bottomColor": layers["sky"]["bottomColor"]}
    if chapter_id == 4:
        top, bot = stvor_sky(sky_cfg, local_step)
    else:
        top, bot = sky_cfg.get("topColor", layers["sky"]["topColor"]), sky_cfg.get("bottomColor", layers["sky"]["bottomColor"])
    canvas = gradient_sky(top, bot)

    def tex(rel_in_chapter: str):
        # rel_in_chapter like "places/foo"
        if assets_override is not None:
            p = assets_override / f"{rel_in_chapter}.png"
            if p.exists():
                key = f"ovr::{p}"
                if key not in _TEX:
                    _TEX[key] = np.array(Image.open(p).convert("RGBA"))
                return _TEX[key]
            # Honest "before": missing far/mid (and anything else not snapshotted)
            # must stay missing, not fall back to the new Chapter4 tiles.
            return None
        return load_tex(f"{folder}/{rel_in_chapter}")

    # FAR then MID
    for kind, spec, k, brightness_default in (
        ("far", layers["far"], layers["far"]["parallax"], 1.0),
        ("mid", layers["mid"], layers["mid"]["parallax"], 0.82),
    ):
        img = tex(spec["image"])
        if img is None:
            continue
        img = fade_top(img, float(spec.get("fadeTopFraction") or 0))
        br = float(spec.get("brightness") if spec.get("brightness") is not None else brightness_default)
        # Night: slightly darken far/mid in ch4 so they don't glow under a night sky
        if chapter_id == 4 and local_step >= 36000:
            nightness = min(1.0, (local_step - 36000) / 6000)
            br *= 1 - 0.55 * nightness
        img = darken(img, br)
        tile_h = float(spec["height"])
        aspect = spec["pixelSize"][0] / spec["pixelSize"][1]
        tile_w = round(tile_h * aspect)
        bottom_y = H - (spec["top"] + spec["height"])  # scene y of tile bottom
        for scene_x in layout_tiles(view_left, cam_x, k, tile_w):
            blit_world(canvas, img, scene_x, bottom_y, tile_w, tile_h, view_left)

    # Props: only those of this chapter (cropped layer). Main parallax = 1.
    # Sort by z
    props = sorted(ch.get("props") or [], key=lambda p: p.get("z", 0))
    for p in props:
        if p.get("layer") not in ("main", None):
            # far/mid props (old clouds) — skip in after; include in before if present
            if p.get("layer") == "far" and assets_override is not None:
                pass
            else:
                continue
        img = tex(p["image"])
        if img is None:
            continue
        ph = float(p["height"])
        ps = p.get("pixelSize") or [img.shape[1], img.shape[0]]
        pw = ph * (ps[0] / max(1, ps[1]))
        # world left = x(start+step) + dx
        world_left = (ch["startStep"] + p["step"]) * PPS + float(p.get("dx") or 0)
        y_bottom = ROAD_Y - float(p.get("sink") or 0)
        # cull
        if world_left + pw < view_left - 20 or world_left > view_left + W + 20:
            continue
        blit_world(canvas, img, world_left, y_bottom, pw, ph, view_left)

    # Underground (simple: modules + a hint of soil). Optional, for completeness.
    ug = ch.get("underground") or {}
    if ug:
        top = float(ug.get("top") or 1700)
        scale = float(ug.get("scale") or 2)
        tps = ug.get("tilePixelSize") or [1148, 415]
        tile_w = tps[0] * scale
        tile_h = tps[1] * scale
        top_y_scene = H - top  # scene y of UG top
        bottom_y = top_y_scene - tile_h
        # Neutrals from start-4W to end+4W (same as WorldScene.buildUnderground),
        # then thematic modules on top (z=1).
        length = ch.get("lengthSteps") or 0
        end_step = ch.get("endStep") or (ch["startStep"] + length)
        strip_start = ch["startStep"] * PPS - W * 4
        strip_end = end_step * PPS + W * 4
        nimg = tex(ug["neutralTile"]) if ug.get("neutralTile") else None
        if nimg is not None:
            x = strip_start
            while x < strip_end:
                if x + tile_w >= view_left - 20 and x <= view_left + W + 20:
                    blit_world(canvas, nimg, x, bottom_y, tile_w, tile_h, view_left)
                x += tile_w
        # modules near this step (drawn over neutrals)
        for m in ug.get("modules") or []:
            img = tex(m["image"])
            if img is None:
                continue
            world_left = (ch["startStep"] + m["step"]) * PPS + float(m.get("dx") or 0) - tile_w / 2
            if world_left + tile_w < view_left - 20 or world_left > view_left + W + 20:
                continue
            blit_world(canvas, img, world_left, bottom_y, tile_w, tile_h, view_left)

    # Postman marker: a simple 430-tall stand-in at screenX 0.55, feet at roadY-30
    # (the live rig). Drawn as a thin silhouette so we can judge scale, not as art.
    feet = 30
    ph = 430
    px = 0.55 * W
    # draw after world
    pil = Image.fromarray(canvas)
    draw = ImageDraw.Draw(pil, "RGBA")
    # feet at scene y = ROAD_Y-30 → row = H - (ROAD_Y-30) = ROAD_LINE_Y+30
    foot_row = ROAD_LINE_Y + feet
    head_row = foot_row - ph
    # simple figure
    draw.ellipse((px - 36, head_row, px + 36, head_row + 80), fill=(60, 50, 40, 180))
    draw.rectangle((px - 22, head_row + 70, px + 22, foot_row - 20), fill=(70, 55, 40, 160))
    draw.line((px + 22, head_row + 140, px + 70, foot_row - 80), fill=(80, 60, 40, 180), width=8)
    canvas = np.array(pil.convert("RGB"))

    # Caption
    pil = Image.fromarray(canvas)
    draw = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font = font_s = ImageFont.load_default()
    cap = f"{label}  local {int(local_step)}  global {int(global_step)}"
    draw.rectangle((0, 0, W, 70), fill=(0, 0, 0, 180))
    draw.text((24, 16), cap, fill=(255, 255, 255), font=font)
    return pil


def contact_sheet(images, cols, thumb_w, path, captions=None):
    thumbs = []
    for im in images:
        r = thumb_w / im.size[0]
        thumbs.append(im.resize((thumb_w, int(im.size[1] * r)), Image.Resampling.LANCZOS))
    if not thumbs:
        return
    tw, th = thumbs[0].size
    cap_h = 36
    rows = (len(thumbs) + cols - 1) // cols
    grid = Image.new("RGB", (cols * tw, rows * (th + cap_h)), (20, 20, 20))
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    for i, im in enumerate(thumbs):
        x, y = (i % cols) * tw, (i // cols) * (th + cap_h)
        grid.paste(im, (x, y))
        if captions and i < len(captions):
            draw.text((x + 8, y + th + 4), captions[i], fill=(240, 240, 240), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(path, quality=92)
    print("wrote", path, grid.size)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = OUT.parent  # /tmp/ch4_qa_after2
    root.mkdir(parents=True, exist_ok=True)
    world = json.loads((ASSETS / "Data/world.json").read_text())
    places = [
        ("shlagbaum", 0),
        ("otstoyniki", 4000),
        ("truby", 11000),
        ("shlam", 17500),
        ("kotelnaya", 21000),
        ("sarai", 25000),
        ("naberezhnaya", 32000),
        ("dvory", 36500),
        ("otdelenie", 39500),
        ("verkhnyaya", 45000),
    ]
    after = []
    for name, step in places:
        im = render_chapter_frame(world, 4, step, f"AFTER2 {name}")
        im.save(OUT / f"after_{name}.jpg", quality=92)
        after.append(im)
        print("after", name)

    # Frames on the borders between neighbouring places — seams show here.
    joins = []
    join_caps = []
    for i in range(len(places) - 1):
        n1, s1 = places[i]
        n2, s2 = places[i + 1]
        mid = (s1 + s2) // 2
        shots = [(f"{n1}_{n2}_mid", mid)]
        if s2 - s1 > 1800:
            shots.append((f"{n1}_leave", s1 + 800))
            shots.append((f"{n2}_arrive", s2 - 800))
        for label, step in shots:
            im = render_chapter_frame(world, 4, step, f"JOIN {label}")
            im.save(OUT / f"join_{label}.jpg", quality=92)
            joins.append(im)
            join_caps.append(f"{label} @{step}")
            print("join", label, step)

    ch3_otstoy = render_chapter_frame(world, 3, 30000, "CH3 otstoy (join)")
    ch3_otstoy.save(OUT / "ch3_otstoy_join.jpg", quality=92)
    ch3_before = render_chapter_frame(world, 3, 29200, "CH3 approaching join")
    ch3_before.save(OUT / "ch3_approach.jpg", quality=92)
    ch3_kam = render_chapter_frame(world, 3, 20000, "CH3 kamyshi (scale)")
    ch3_kam.save(OUT / "ch3_kamyshi.jpg", quality=92)
    ch3_gat = render_chapter_frame(world, 3, 4000, "CH3 gat (scale)")
    ch3_gat.save(OUT / "ch3_gat.jpg", quality=92)
    print("ch3 frames ok")

    caps = [n for n, _ in places]
    contact_sheet(after, 5, 390, root / "contact_places.jpg", caps)
    contact_sheet(joins, 5, 390, root / "contact_joins.jpg", join_caps)
    contact_sheet(
        [ch3_gat, ch3_kam, after[0], after[4]],
        4,
        390,
        root / "contact_scale_ch3_vs_ch4.jpg",
        ["ch3 gat", "ch3 kamyshi", "ch4 shlagbaum", "ch4 kotelnaya"],
    )
    contact_sheet(
        [ch3_before, ch3_otstoy, after[0]],
        3,
        400,
        root / "contact_join_ch3_ch4.jpg",
        ["ch3 approach", "ch3 otstoy (75000)", "ch4 shlagbaum (75000)"],
    )
    print("done, frames in", OUT)


if __name__ == "__main__":
    main()
