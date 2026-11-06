#!/usr/bin/env python3
"""Night exposure is the shared world tint. The hero is not graded separately.

Full night was #8090B8 (luma ~0.56), which left houses, trees, ground and the
postman in one dark grade. The tint is now lighter and still cool. Sky colours
are unchanged: AmbientLayer divides the sky by the tint before the multiply.
This is not an iOS runtime test.

Run: python3 tools/check_night_readability.py
"""
import json
import re
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
READABILITY = (ROOT / "Postman/Scene/Readability.swift").read_text()
SCENE = (ROOT / "Postman/Scene/WorldScene.swift").read_text()
AMBIENT = json.loads((ROOT / "Postman/GameAssets/Data/ambient.json").read_text())
OLD_NIGHT = (0x80 / 255, 0x90 / 255, 0xB8 / 255)


def cgfloat(name):
    match = re.search(rf"static let {name}: CGFloat = ([0-9.]+)", READABILITY)
    if not match:
        raise AssertionError(f"missing CGFloat {name}")
    return float(match.group(1))


def parse_hex(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luma(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def grade(pixel, tint):
    return tuple(channel * tone for channel, tone in zip(pixel, tint))


def opaque(path, step=4):
    image = Image.open(path).convert("RGBA")
    pixels = []
    for y in range(0, image.size[1], step):
        for x in range(0, image.size[0], step):
            pixel = image.getpixel((x, y))
            if pixel[3] > 200:
                pixels.append(tuple(channel / 255 for channel in pixel[:3]))
    return pixels


def night_keys():
    return [key for key in AMBIENT["timeOfDay"] if key.get("skyTop") == "#07131F"]


class NightWorldTests(unittest.TestCase):
    def test_shared_cool_tint_lifts_the_world_and_not_the_sky_or_day(self):
        nights = night_keys()
        self.assertGreaterEqual(len(nights), 3)
        tint = parse_hex(nights[0]["tint"])
        self.assertTrue(all(key["tint"] == nights[0]["tint"] for key in nights))
        self.assertEqual(nights[0]["tint"], "#C6CDDF")
        self.assertGreater(luma(tint), luma(OLD_NIGHT) * 1.25)
        self.assertLess(luma(tint), 0.88)
        # Cool, not a yellow or white wash.
        self.assertGreaterEqual(tint[2], tint[1])
        self.assertGreaterEqual(tint[1], tint[0])
        self.assertLess(tint[0], 0.90)
        evening = next(key for key in AMBIENT["timeOfDay"] if key["hour"] == 20)
        self.assertEqual(evening["tint"], "#D2CDDB")
        self.assertGreater(luma(parse_hex(evening["tint"])), luma(tint))
        day = [key for key in AMBIENT["timeOfDay"] if key["hour"] in (10, 16.5)]
        self.assertTrue(all(key["tint"] == "#FFFFFF" for key in day))
        # Sky keys that make the night sky stay put. divided(by:) must not clamp.
        for key in nights:
            sky = parse_hex(key["skyTop"])
            self.assertTrue(all(channel / tone < 1 for channel, tone in zip(sky, tint)))
            self.assertEqual(key["skyTop"], "#07131F")
        self.assertEqual(cgfloat("nightFigureGain"), 1)
        self.assertIn("extra > 0.01 ? n : 0", READABILITY)
        for gone in ("blendMode = .add", "heroNightFill", "roadNightFill", "nightTintShare"):
            self.assertNotIn(gone, SCENE)
            self.assertNotIn(gone, READABILITY)

    def test_real_pixels_get_brighter_without_a_hero_cutout_or_whiteout(self):
        tint = parse_hex(night_keys()[0]["tint"])
        samples = {
            "head": ROOT / "Postman/GameAssets/Rig/parts/head.png",
            "fir road": ROOT / "Postman/GameAssets/Chapter2/road/road_main_fir.png",
            "far ridges": ROOT / "Postman/GameAssets/Chapter2/places/bg_far_ridges_tile.png",
            "underground": ROOT / "Postman/GameAssets/Chapter2/underground/ug_neutral_tile.png",
        }
        gains = []
        for name, path in samples.items():
            pixels = opaque(path)
            self.assertGreater(len(pixels), 500, name)
            before = [luma(grade(pixel, OLD_NIGHT)) for pixel in pixels]
            after = [luma(grade(pixel, tint)) for pixel in pixels]
            mid_before = sorted(before)[len(before) // 2]
            mid_after = sorted(after)[len(after) // 2]
            self.assertGreater(mid_after, mid_before * 1.25, name)
            self.assertLess(mid_after, 0.85, name)
            # No channel is pushed to white, and a teal or sand pixel does not flip to yellow-only.
            graded = [grade(pixel, tint) for pixel in pixels]
            self.assertLess(max(max(pixel) for pixel in graded), 0.98, name)
            gains.append(mid_after / mid_before)
        # Hero, road, hills and soil move by the same tint, so the figure is not a separate cutout.
        self.assertLess(max(gains) - min(gains), 0.08, gains)


def write_contact_sheet():
    tint = parse_hex(night_keys()[0]["tint"])
    labels = ("day", "old night", "new night")
    rows = (
        ("head", ROOT / "Postman/GameAssets/Rig/parts/head.png"),
        ("fir road", ROOT / "Postman/GameAssets/Chapter2/road/road_main_fir.png"),
    )
    thumb = 240
    pad = 8
    sheet = Image.new("RGB", (64 + 3 * (thumb + pad), 24 + 2 * (thumb + pad)), (12, 18, 28))
    draw = ImageDraw.Draw(sheet)
    for column, label in enumerate(labels):
        draw.text((64 + pad + column * (thumb + pad), 4), label, fill=(230, 230, 230))
    for row, (name, path) in enumerate(rows):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb, thumb))
        pixels = [tuple(channel / 255 for channel in pixel[:3]) for pixel in image.getdata()]
        alpha = [pixel[3] / 255 for pixel in image.getdata()]
        modes = (pixels, [grade(pixel, OLD_NIGHT) for pixel in pixels], [grade(pixel, tint) for pixel in pixels])
        y = 24 + row * (thumb + pad)
        draw.text((4, y + 8), name, fill=(230, 230, 230))
        for column, colored in enumerate(modes):
            x = 64 + pad + column * (thumb + pad)
            composed = Image.new("RGBA", image.size)
            composed.putdata([
                tuple(int(max(0, min(255, channel * 255))) for channel in color) + (int(a * 255),)
                for color, a in zip(colored, alpha)
            ])
            under = Image.new("RGBA", image.size, (12, 18, 28, 255))
            under.alpha_composite(composed)
            sheet.paste(under.convert("RGB"), (x, y))
    out = Path("/opt/cursor/artifacts/night-world-brightness.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


if __name__ == "__main__":
    write_contact_sheet()
    unittest.main(verbosity=2)
