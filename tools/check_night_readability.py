#!/usr/bin/env python3
"""Night readability: warm fill on the postman and the road, not on the sky or the day scene.

This is NOT an iOS build and NOT a SpriteKit runtime test. It checks the Swift contract
and simulates the existing night shader plus the additive fill on real clay pixels.
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
ROAD = ROOT / "Postman/GameAssets/Chapter1/road/road_main_ogorody_1.png"


def cgfloat(name):
    match = re.search(rf"static let {name}: CGFloat = ([0-9.]+)", READABILITY)
    if not match:
        raise AssertionError(f"missing CGFloat {name}")
    return float(match.group(1))


def night_fill_falloff(distance):
    """Mirror of Readability.nightFillFalloff."""
    x = min(1.0, max(0.0, distance))
    inv = 1 - x * x
    return inv * inv


def night_amount(tint, night_luma):
    """Mirror of Readability.nightAmount."""
    luma = 0.299 * tint[0] + 0.587 * tint[1] + 0.114 * tint[2]
    return max(0.0, min(1.0, (1 - luma) / max(0.05, 1 - night_luma)))


def night_fill_strength(amount):
    """Mirror of Readability.nightFillStrength: squared so dawn/sunset stay gentle."""
    x = min(1.0, max(0.0, amount))
    return x * x


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def channel_gains(tint, share, bright, lamp, lantern, max_gain):
    """Mirror of Readability.updateNight, before the sprite multiply."""
    amount = night_amount(tint, cgfloat("nightLuma"))
    keep = 1 - share
    boost = 1 + bright * amount
    gains = []
    for channel, warm in zip(tint, lantern):
        undo = max(0.05, channel) ** (-keep)
        lantern_scale = 1 + (warm - 1) * lamp * amount
        gains.append(min(max_gain, undo * boost * lantern_scale))
    return amount, gains


def shader_then_tint(rgb, gains, tint, saturation):
    """Existing hero shader: saturate, gain, clamp to 1, then the world multiply."""
    luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    saturated = tuple(luma + (channel - luma) * saturation for channel in rgb)
    pre = tuple(min(1.0, max(0.0, channel * gain)) for channel, gain in zip(saturated, gains))
    return tuple(channel * tone for channel, tone in zip(pre, tint))


def add_fill(rgb, alpha, color, falloff):
    return tuple(min(1.0, channel + alpha * warm * falloff) for channel, warm in zip(rgb, color))


def luma255(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) * 255


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


class NightReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.night = hex_rgb("8090B8")
        self.sunset = hex_rgb("F0C6A0")
        self.day = (1.0, 1.0, 1.0)
        self.lantern = (cgfloat("nightFillRed"), cgfloat("nightFillGreen"), cgfloat("nightFillBlue"))
        # Lantern used by the existing shader is a tuple in source, not these fills.
        self.shader_lantern = (1.0, 0.86, 0.64)
        self.share = cgfloat("nightTintShare")
        self.bright = cgfloat("nightBrightness")
        self.lamp = cgfloat("lanternAmount")
        self.max_gain = cgfloat("maxGain")
        self.sat = cgfloat("nightSaturation")

    def test_constants_stay_local_and_soft(self):
        self.assertLess(cgfloat("heroNightFillAlpha"), 0.4)
        self.assertLess(cgfloat("roadNightFillAlpha"), cgfloat("heroNightFillAlpha"))
        self.assertGreater(cgfloat("roadNightFillAlpha"), 0.05)
        self.assertEqual(cgfloat("nightFillZ"), 920)
        self.assertGreater(self.lantern[0], self.lantern[2] + 0.4)
        # Face sits above the road band; the hero pool has to be the thing lighting it.
        self.assertGreater(cgfloat("heroNightFillLift"), cgfloat("roadNightFillLift") + cgfloat("roadNightFillHeight") / 2 - 40)
        self.assertLess(cgfloat("heroNightFillLift"), 430)

    def test_falloff_is_center_only(self):
        self.assertAlmostEqual(night_fill_falloff(0), 1)
        self.assertAlmostEqual(night_fill_falloff(1), 0)
        self.assertAlmostEqual(night_fill_falloff(1.4), 0)
        self.assertGreater(night_fill_falloff(0.2), 0.85)
        self.assertLess(night_fill_falloff(0.85), 0.2)
        self.assertIn("let inv = 1 - x * x", READABILITY)
        self.assertIn("return inv * inv", READABILITY)

    def test_day_has_no_fill_and_deep_night_does(self):
        night_luma = cgfloat("nightLuma")
        self.assertAlmostEqual(night_fill_strength(night_amount(self.day, night_luma)), 0, places=6)
        self.assertAlmostEqual(night_fill_strength(night_amount(self.night, night_luma)), 1, places=2)
        sunset = night_fill_strength(night_amount(self.sunset, night_luma))
        self.assertLess(sunset, 0.25)
        self.assertGreater(sunset, 0.05)
        dawn = hex_rgb("F2ECE2")
        self.assertLess(night_fill_strength(night_amount(dawn, night_luma)), 0.04)

    def test_sky_keys_and_global_tint_are_unchanged(self):
        self.assertIn('"tint": "#8090B8"', AMBIENT)
        self.assertIn('"skyTop": "#07131F"', AMBIENT)
        self.assertIn('"tint": "#FFFFFF"', AMBIENT)
        # The fill must not retint the whole frame.
        self.assertNotIn("tintNode.color", SCENE[SCENE.index("func updateNightFill"):SCENE.index("func updateNightFill") + 1800])

    def test_fill_is_post_tint_additive_and_gated(self):
        body_start = SCENE.index("private func installNightFill()")
        body = SCENE[body_start:SCENE.index("private func cameraUnitsPerWorldUnit()")]
        self.assertIn("blendMode = .add", body)
        self.assertEqual(body.count("blendMode = .add"), 2)
        self.assertIn("zPosition = Readability.nightFillZ", body)
        self.assertIn('name = "heroNightFill"', body)
        self.assertIn('name = "roadNightFill"', body)
        update = SCENE[SCENE.index("private func updateNightFill()"):]
        update = update[:update.index("\n    // MARK:") if "\n    // MARK:" in update else 2500]
        self.assertIn("Readability.enabled", update)
        self.assertIn("Readability.nightAmount", update)
        self.assertIn("Readability.nightFillStrength", update)
        self.assertIn("strength >= 0.02", update)
        update_fn = SCENE[SCENE.index("override func update"):SCENE.index("// MARK: Camera")]
        self.assertIn("updateNightFill()", update_fn)
        # Above the ambient multiply, not instead of it.
        ambient = (ROOT / "Postman/Scene/AmbientLayer.swift").read_text()
        self.assertIn("tintNode.zPosition = 900", ambient)
        self.assertLess(900, cgfloat("nightFillZ"))

    def test_hero_clay_lifts_without_washing_out_or_lighting_the_sky(self):
        amount, gains = channel_gains(self.night, self.share, self.bright, self.lamp, self.shader_lantern, self.max_gain)
        self.assertAlmostEqual(amount, 1, places=2)
        saturation = 1 + self.sat * amount
        strength = night_fill_strength(amount)
        hero_alpha = cgfloat("heroNightFillAlpha") * strength
        samples = opaque_pixels(HEAD, 2)
        self.assertGreater(len(samples), 1000)
        lit = []
        dark_plain = []
        for pixel in samples:
            base = shader_then_tint(pixel, gains, self.night, saturation)
            # Face/torso pool is near the center of the ellipse.
            filled = add_fill(base, hero_alpha, self.lantern, night_fill_falloff(0.16))
            plain = luma255(base)
            if plain < 55:
                dark_plain.append((plain, luma255(filled), filled))
            lit.append(luma255(filled))
        lit.sort()
        dark_plain.sort()
        p20 = lit[int(0.20 * (len(lit) - 1))]
        p50 = lit[int(0.50 * (len(lit) - 1))]
        p95 = lit[int(0.95 * (len(lit) - 1))]
        # Dark clay (cheeks, folds) leaves the crushed band; highlights stay clay, not white.
        self.assertGreater(p20, 70, p20)
        self.assertGreater(p50, 110, p50)
        self.assertLess(p95, 210, p95)
        # The darkest sockets stay darker than the lifted midtones.
        darkest = dark_plain[max(0, len(dark_plain) // 10)]
        self.assertLess(darkest[1], p50 - 25)
        # Warm, not the cool night tint: red stays above blue on a mid pixel.
        mid = samples[len(samples) // 2]
        filled = add_fill(shader_then_tint(mid, gains, self.night, saturation), hero_alpha, self.lantern, 0.9)
        self.assertGreater(filled[0], filled[2] + 0.12)
        # Well above the pool the falloff is zero, so roofs and sky are not filled.
        half_height = 860 / 2
        self.assertEqual(night_fill_falloff(700 / half_height), 0)

    def test_road_is_readable_and_still_night_and_day_road_is_untouched(self):
        strength = night_fill_strength(night_amount(self.night, cgfloat("nightLuma")))
        road_alpha = cgfloat("roadNightFillAlpha") * strength
        samples = opaque_pixels(ROAD, 6)
        self.assertGreater(len(samples), 200)
        night_lumas = []
        center_lumas = []
        day_lumas = []
        for pixel in samples:
            toned = tuple(channel * tone for channel, tone in zip(pixel, self.night))
            # Shoulder of the band (the path near the hero's feet) and the band center.
            night_lumas.append(luma255(add_fill(toned, road_alpha, self.lantern, night_fill_falloff(0.35))))
            center_lumas.append(luma255(add_fill(toned, road_alpha, self.lantern, 1)))
            day_lumas.append(luma255(pixel))
        night_lumas.sort()
        center_lumas.sort()
        day_lumas.sort()
        night_mid = night_lumas[len(night_lumas) // 2]
        center_mid = center_lumas[len(center_lumas) // 2]
        day_mid = day_lumas[len(day_lumas) // 2]
        raw_night = sorted(luma255(tuple(c * t for c, t in zip(p, self.night))) for p in samples)
        raw_mid = raw_night[len(raw_night) // 2]
        self.assertGreater(night_mid, raw_mid + 15)
        self.assertGreater(night_mid, 70)
        self.assertGreater(center_mid, 80)
        # Even the middle of the strip stays under the daytime clay.
        self.assertLess(center_mid, day_mid - 5)
        # Day strength is zero, so the same add cannot move a day pixel.
        self.assertAlmostEqual(night_fill_strength(night_amount(self.day, cgfloat("nightLuma"))), 0, places=6)

    def test_sky_pixel_is_outside_both_lights(self):
        # Design frame 1170x2532, road line 1720 from the top. Scene Y grows upward.
        road_y = 2532 - 1720
        band_top = road_y + cgfloat("roadNightFillLift") + cgfloat("roadNightFillHeight") / 2
        sky_y = 2532 - 200  # high in the night sky
        self.assertLess(band_top, sky_y - 400)
        feet_y = road_y - 30
        pool_center = feet_y + cgfloat("heroNightFillLift")
        pool_top = pool_center + 860 / 2
        self.assertLess(pool_top, sky_y - 250)
        # Face (~370px above the feet) is inside the hero pool and above the road band.
        face_y = feet_y + 370
        self.assertGreater(face_y, band_top - 30)
        self.assertLess(abs(face_y - pool_center), 860 / 2 * 0.45)


if __name__ == "__main__":
    unittest.main(verbosity=2)
