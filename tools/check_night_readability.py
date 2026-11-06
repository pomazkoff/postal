#!/usr/bin/env python3
"""Night readability stays on the figure pixels. No screen-space light quad.

The rejected build drew an additive yellow sprite. SpriteKit's add blend keeps the
texture RGB across the whole quad, so the gradient alpha became a hard rectangle
and a vertical seam. This check forbids that overlay and simulates the figure
shader on real clay. It is NOT an iOS or SpriteKit runtime test.

Run: python3 tools/check_night_readability.py
"""
import math
import re
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
READABILITY = (ROOT / "Postman/Scene/Readability.swift").read_text()
SCENE = (ROOT / "Postman/Scene/WorldScene.swift").read_text()
AMBIENT = (ROOT / "Postman/GameAssets/Data/ambient.json").read_text()
HEAD = ROOT / "Postman/GameAssets/Rig/parts/head.png"
TORSO = ROOT / "Postman/GameAssets/Rig/parts/torso.png"


def cgfloat(name):
    match = re.search(rf"static let {name}: CGFloat = ([0-9.]+)", READABILITY)
    if not match:
        raise AssertionError(f"missing CGFloat {name}")
    return float(match.group(1))


def night_amount(tint, night_luma):
    luma = 0.299 * tint[0] + 0.587 * tint[1] + 0.114 * tint[2]
    return max(0.0, min(1.0, (1 - luma) / max(0.05, 1 - night_luma)))


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luma(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def opaque_pixels(path, step):
    image = Image.open(path).convert("RGBA")
    pixels = []
    width, height = image.size
    for y in range(0, height, step):
        for x in range(0, width, step):
            pixel = image.getpixel((x, y))
            if pixel[3] > 200:
                pixels.append(tuple(channel / 255 for channel in pixel[:3]))
    return pixels


def channel_gains(tint, share, bright, lamp, lantern, max_gain, amount):
    keep = 1 - share
    boost = 1 + bright * amount
    gains = []
    for channel, warm in zip(tint, lantern):
        undo = max(0.05, channel) ** (-keep)
        lantern_scale = 1 + (warm - 1) * lamp * amount
        gains.append(min(max_gain, undo * boost * lantern_scale))
    return gains


def figure_shader(rgb, gains, tint, lift, shadow_end, saturation):
    """Mirror of Readability.nightShader, then the world multiply."""
    level = luma(rgb)
    shadow = min(1.0, max(0.0, 1.0 - level / shadow_end))
    rgb = tuple(channel * (1.0 + lift * shadow) for channel in rgb)
    level = luma(rgb)
    rgb = tuple(level + (channel - level) * saturation for channel in rgb)
    pre = tuple(min(1.0, max(0.0, channel * gain)) for channel, gain in zip(rgb, gains))
    return tuple(channel * tone for channel, tone in zip(pre, tint))


class NightReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.night = hex_rgb("8090B8")
        self.day = (1.0, 1.0, 1.0)
        self.share = cgfloat("nightTintShare")
        self.bright = cgfloat("nightBrightness")
        self.lamp = cgfloat("lanternAmount")
        self.lift = cgfloat("nightShadowLift")
        self.shadow_end = cgfloat("nightShadowEnd")
        self.sat = 1 + cgfloat("nightSaturation")
        self.max_gain = cgfloat("maxGain")
        self.lantern = (1.0, 0.86, 0.64)

    def test_overlay_quad_is_gone(self):
        # The runtime failure was an additive sprite, not a dark hero.
        for source, label in ((SCENE, "WorldScene"), (READABILITY, "Readability")):
            self.assertNotIn("heroNightFill", source, label)
            self.assertNotIn("roadNightFill", source, label)
            self.assertNotIn("nightFill", source, label)
            self.assertNotIn("makeNightFillImage", source, label)
            self.assertNotIn("blendMode = .add", source, label)
        self.assertNotIn("SKBlendMode.add", SCENE)
        self.assertNotIn("updateNightFill", SCENE)
        # The shader still only recolors figure texels.
        self.assertIn("texture2D(u_texture, v_tex_coord)", READABILITY)
        self.assertIn("u_lift", READABILITY)
        self.assertIn("partSprites", SCENE)

    def test_yellow_bias_is_off_and_sky_tint_unchanged(self):
        self.assertEqual(self.lamp, 0)
        self.assertLess(self.share, 0.35)
        self.assertGreater(self.share, 0.05)
        self.assertGreater(self.lift, 0.4)
        self.assertLess(self.lift, 1.8)
        self.assertIn('"tint": "#8090B8"', AMBIENT)
        self.assertIn('"skyTop": "#07131F"', AMBIENT)
        self.assertIn('"tint": "#FFFFFF"', AMBIENT)
        self.assertIn("tintNode.blendMode = .multiply",
                      (ROOT / "Postman/Scene/AmbientLayer.swift").read_text())

    def test_day_shader_stays_off(self):
        amount = night_amount(self.day, cgfloat("nightLuma"))
        self.assertAlmostEqual(amount, 0, places=6)
        update = SCENE[SCENE.index("private func updateNightFigures()"):]
        update = update[:update.index("private var nightFiguresDirty")]
        self.assertIn("n > 0.01", update)
        self.assertIn("want ? Readability.nightShader : nil", update)

    def test_clay_gets_brighter_without_turning_yellow_or_flat(self):
        amount = night_amount(self.night, cgfloat("nightLuma"))
        self.assertAlmostEqual(amount, 1, places=2)
        gains = channel_gains(self.night, self.share, self.bright, self.lamp,
                              self.lantern, self.max_gain, amount)
        # Gains compensate the cool tint. They must not push red far above blue.
        self.assertLess(gains[0] / gains[2], 1.45, gains)

        for path in (HEAD, TORSO):
            samples = opaque_pixels(path, 2)
            self.assertGreater(len(samples), 1000)
            raw = [tuple(channel * tone for channel, tone in zip(pixel, self.night)) for pixel in samples]
            lit = [figure_shader(pixel, gains, self.night, self.lift * amount,
                                 self.shadow_end, self.sat) for pixel in samples]
            raw_l = sorted(luma(pixel) * 255 for pixel in raw)
            lit_l = sorted(luma(pixel) * 255 for pixel in lit)
            src_l = sorted(luma(pixel) * 255 for pixel in samples)
            count = len(lit_l)
            p20, p50, p95 = (lit_l[int(q * (count - 1))] for q in (0.20, 0.50, 0.95))
            raw_p50 = raw_l[count // 2]
            day_p50 = src_l[count // 2]
            self.assertGreater(p20, 70, path.name)
            self.assertGreater(p50, raw_p50 + 30, path.name)
            self.assertLess(p50, day_p50 + 20, path.name)
            self.assertLess(p95, 170, path.name)
            # Hue stays the clay's own red-blue gap, not a yellow wash.
            src_gap = sum(pixel[0] - pixel[2] for pixel in samples) / count
            lit_gap = sum(pixel[0] - pixel[2] for pixel in lit) / count
            self.assertAlmostEqual(lit_gap, src_gap, delta=0.05, msg=path.name)
            # A flat yellow quad would collapse luma variation.
            def deviation(values):
                mid = sum(values) / len(values)
                return math.sqrt(sum((value - mid) ** 2 for value in values) / len(values))
            self.assertGreater(deviation([luma(pixel) for pixel in lit]) /
                               deviation([luma(pixel) for pixel in samples]), 0.45)
            # Eye sockets and the darkest clay stay darker than the lifted middle.
            dark = sorted(luma(pixel) * 255 for pixel in lit)[max(0, count // 10)]
            self.assertLess(dark, p50 - 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
