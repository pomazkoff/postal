#!/usr/bin/env python3
"""Rebuild Chapter2 only from the approved env_ch2/v7 layers (Pillow + numpy).

The exported sizes intentionally match the existing global layer metadata, so Chapter1
layout and all layer height/top values stay untouched. Optional --module-source points
at ORIGINAL exported UG modules, not already edge-treated output. No AI generation.
"""
from pathlib import Path
import argparse
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def seamless(image, overlap):
    """Periodic horizontal crossfade, like ch1 bgproc, with premultiplied alpha."""
    a = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255
    premul = a.copy()
    premul[..., :3] *= a[..., 3:4]
    width = a.shape[1]
    out = premul[:, :width - overlap].copy()
    t = np.linspace(0, 1, overlap, dtype=np.float32)[None, :, None]
    out[:, :overlap] = premul[:, -overlap:] * (1 - t) + premul[:, :overlap] * t
    # Exact identical boundary columns also survive subsequent downsampling/tiling.
    edge = (out[:, 0] + out[:, -1]) / 2
    out[:, 0] = edge
    out[:, -1] = edge
    rgb = np.divide(out[..., :3], out[..., 3:4], out=np.zeros_like(out[..., :3]), where=out[..., 3:4] > 0)
    return Image.fromarray(np.rint(np.concatenate((rgb, out[..., 3:4]), axis=2) * 255).clip(0, 255).astype("uint8"))


def terrain_layer(path, size):
    im = Image.open(path).convert("RGBA")
    bounds = im.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"Empty layer: {path}")
    # Shift the silhouette above transparent headroom instead of stretching thin peaks.
    # The old full canvas left the far peaks only at road level. Extend the bottom
    # colour column down behind the mid layer, preserving the approved mountain shapes.
    overlap = 500
    crop_width = min(im.width, round((size[0] + overlap) * im.height / size[1]))
    im = im.crop((0, 0, crop_width, im.height))
    raised = Image.new("RGBA", im.size)
    visible = im.crop((0, bounds[1], im.width, im.height))
    raised.paste(visible, (0, 0))
    if bounds[1] > 0:
        # Avoid vertical streaks from repeating the literal bottom row (dark seams
        # under the source cut-outs). Blend the last 48 rows into a quiet clay fill.
        pixels = np.array(raised, dtype=np.float32)
        source_pixels = np.asarray(visible, dtype=np.float32)
        sample = source_pixels[-min(96, visible.height):].reshape(-1, 4)
        opaque = sample[sample[:, 3] > 240]
        color = np.median(opaque, axis=0) if len(opaque) else np.array([70, 120, 110, 255])
        color[3] = 255
        blend = min(48, visible.height)
        t = np.linspace(0, 1, blend)[:, None, None]
        pixels[visible.height - blend:visible.height] = (
            pixels[visible.height - blend:visible.height] * (1 - t) + color * t)
        pixels[visible.height:] = color
        raised = Image.fromarray(np.rint(pixels).clip(0, 255).astype("uint8"))
    im = raised.resize((size[0] + overlap, size[1]), Image.Resampling.LANCZOS)
    return seamless(im, overlap)


def harmonize_edges(module, neutral, band=96):
    """Keep the module centre intact; join both sides to the same periodic soil profile."""
    a = np.asarray(module.convert("RGB"), dtype=np.float32).copy()
    n = np.asarray(neutral.convert("RGB"), dtype=np.float32)
    t = np.linspace(0, 1, band, dtype=np.float32)
    t = t * t * (3 - 2 * t)  # smoothstep, no visible cutoff inside the tile
    a[:, :band] = n[:, :band] * (1 - t[None, :, None]) + a[:, :band] * t[None, :, None]
    a[:, -band:] = a[:, -band:] * (1 - t[None, :, None]) + n[:, -band:] * t[None, :, None]
    return Image.fromarray(np.rint(a).clip(0, 255).astype("uint8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=Path("/workspace/walking-sim/env_ch2/v7"))
    ap.add_argument("--module-source", type=Path)
    args = ap.parse_args()
    dest = ROOT / "Postman/GameAssets/Chapter2"
    for name, src, size in [("bg_far_ridges_tile", "layer_far", (2636, 1236)),
                            ("bg_mid_fields_tile", "layer_mid", (2636, 1040))]:
        result = terrain_layer(args.source / f"{src}.png", size)
        result.save(dest / "places" / f"{name}.png", optimize=True)
        print(name, result.size)
    # Do not use the old Chapter1 neutral (different strata/cable/grass).
    ground = Image.open(args.source / "ground_master.png").convert("RGBA")
    ground = ground.resize((1348, 415), Image.Resampling.LANCZOS)
    neutral = seamless(ground, 200).convert("RGB")
    neutral.save(dest / "underground/ug_neutral_tile.png", optimize=True)
    print("ug_neutral_tile", neutral.size)
    if args.module_source:
        for path in sorted(args.module_source.glob("ug_*.png")):
            if path.stem == "ug_neutral_tile":
                continue
            im = Image.open(path)
            if im.size != neutral.size:
                raise ValueError(f"Unexpected module size {path}: {im.size}")
            harmonize_edges(im, neutral).save(dest / "underground" / path.name, optimize=True)
            print("matched edges:", path.name)


if __name__ == "__main__":
    main()
