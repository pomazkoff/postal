#!/usr/bin/env python3
"""Night figure shader: one brightness scale, no restored daytime yellow.

Rig PNGs are sandy (hue about 20 degrees). Undoing night tint #8090B8 per channel
boosts red more than blue and paints the hero back to that daytime sand. This
check uses every opaque texel of the real part PNGs. It is not an iOS runtime test.

Run: python3 tools/check_night_readability.py
"""
import math
import re
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
READABILITY = (ROOT / "Postman/Scene/Readability.swift").read_text()
SCENE = (ROOT / "Postman/Scene/WorldScene.swift").read_text()
PARTS = ROOT / "Postman/GameAssets/Rig/parts"
NIGHT = (0x80 / 255, 0x90 / 255, 0xB8 / 255)
PART_NAMES = ("head", "torso", "arm_upper", "arm_lower", "thigh", "shin", "foot", "staff")


def cgfloat(name):
    match = re.search(rf"static let {name}: CGFloat = ([0-9.]+)", READABILITY)
    if not match:
        raise AssertionError(f"missing CGFloat {name}")
    return float(match.group(1))


def night_amount(tint, night_luma):
    level = 0.299 * tint[0] + 0.587 * tint[1] + 0.114 * tint[2]
    return max(0.0, min(1.0, (1 - level) / max(0.05, 1 - night_luma)))


def luma(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def load_opaque(name):
    image = Image.open(PARTS / f"{name}.png").convert("RGBA")
    pixels = []
    for pixel in image.getdata():
        if pixel[3] > 200:
            pixels.append(tuple(channel / 255 for channel in pixel[:3]))
    return pixels


def tint_only(pixels, tint=NIGHT):
    return [tuple(channel * tone for channel, tone in zip(pixel, tint)) for pixel in pixels]


def scalar_night(pixels, gain, tint=NIGHT):
    """Mirror of nightShader plus the world multiply. Peak compress keeps hue."""
    output = []
    compressed = 0
    for pixel in pixels:
        scaled = tuple(channel * gain for channel in pixel)
        peak = max(scaled)
        if peak > 1:
            compressed += 1
            scaled = tuple(channel / peak for channel in scaled)
        output.append(tuple(channel * tone for channel, tone in zip(scaled, tint)))
    return output, compressed / len(pixels)


def rejected_shader(pixels, tint=NIGHT):
    """5c37c66: per-channel undo of the tint, shadow lift, slight saturation."""
    share, lift_max, end, sat = 0.22, 1.15, 0.50, 1.06
    keep = 1 - share
    gains = [min(2.4, max(0.05, tone) ** (-keep)) for tone in tint]
    output = []
    for rgb in pixels:
        level = luma(rgb)
        shadow = max(0.0, min(1.0, 1 - level / end))
        rgb = tuple(channel * (1 + lift_max * shadow) for channel in rgb)
        level = luma(rgb)
        rgb = tuple(level + (channel - level) * sat for channel in rgb)
        pre = tuple(min(1.0, max(0.0, channel * gain)) for channel, gain in zip(rgb, gains))
        output.append(tuple(channel * tone for channel, tone in zip(pre, tint)))
    return output


def percentile(values, q):
    ordered = sorted(values)
    return ordered[int(q * (len(ordered) - 1))]


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def deviation(values):
    mid = mean(values)
    return math.sqrt(sum((value - mid) ** 2 for value in values) / len(values))


def red_blue(pixels):
    return mean(pixel[0] - pixel[2] for pixel in pixels)


def gap_ratio(pixels):
    """Red-blue gap relative to luma. Brightness alone does not change it."""
    return mean((pixel[0] - pixel[2]) / max(0.02, luma(pixel)) for pixel in pixels)


def yellow_fraction(pixels):
    """Daytime sand test: red clearly above blue, not a neutral night brown."""
    return mean(1 if pixel[0] > pixel[1] > pixel[2] and pixel[0] - pixel[2] > 0.18 else 0
                for pixel in pixels)


def chroma_error(left, right):
    total = count = 0
    for a, b in zip(left, right):
        if min(a) < 0.03 or min(b) < 0.03:
            continue
        sa, sb = sum(a), sum(b)
        total += sum(abs(x / sa - y / sb) for x, y in zip(a, b))
        count += 1
    return total / max(1, count)


class NightReadabilityTests(unittest.TestCase):
    def test_source_parts_are_sandy_and_shader_is_scalar(self):
        # Evidence, not a palette we invented: opaque texels of the shipped PNGs.
        for name in ("head", "torso"):
            pixels = load_opaque(name)
            self.assertGreater(len(pixels), 10000)
            self.assertGreater(red_blue(pixels), 0.15, name)
            self.assertGreater(yellow_fraction(pixels), 0.40, name)
        self.assertEqual(cgfloat("nightFigureGain"), 1.35)
        for gone in ("nightTintShare", "nightShadowLift", "lanternAmount", "u_lift", "u_sat",
                     "heroNightFill", "roadNightFill", "blendMode = .add", "pow(max(0.05, t)"):
            self.assertNotIn(gone, READABILITY, gone)
            self.assertNotIn(gone, SCENE, gone)
        self.assertIn("c.rgb * u_gain", READABILITY)
        self.assertIn("limit / max(peak, 0.0001)", READABILITY)
        self.assertIn("n > 0.01", SCENE)
        self.assertIn("want ? Readability.nightShader : nil", SCENE)

    def test_day_is_unshaded(self):
        self.assertAlmostEqual(night_amount((1, 1, 1), cgfloat("nightLuma")), 0, places=6)
        amount = night_amount(NIGHT, cgfloat("nightLuma"))
        self.assertAlmostEqual(amount, 1, places=2)
        gain = 1 + (cgfloat("nightFigureGain") - 1) * amount
        self.assertAlmostEqual(gain, 1.35)

    def test_real_pixels_keep_night_hue_and_only_gain_brightness(self):
        gain = cgfloat("nightFigureGain")
        for name in PART_NAMES:
            source = load_opaque(name)
            cooled = tint_only(source)
            bright, compressed = scalar_night(source, gain)
            restored = rejected_shader(source)
            cool_l = [luma(pixel) * 255 for pixel in cooled]
            bright_l = [luma(pixel) * 255 for pixel in bright]
            day_l = [luma(pixel) * 255 for pixel in source]
            # Brighter than the night grade, still under the daytime sand.
            self.assertGreater(percentile(bright_l, 0.5), percentile(cool_l, 0.5) + 12, name)
            self.assertLess(percentile(bright_l, 0.5), percentile(day_l, 0.5) - 8, name)
            # Same hue as night-graded texture. The rejected shader puts daytime yellow back.
            self.assertLess(chroma_error(cooled, bright), 0.002, name)
            self.assertGreater(chroma_error(cooled, restored), 0.05, name)
            self.assertAlmostEqual(gap_ratio(bright), gap_ratio(cooled), delta=0.04, msg=name)
            self.assertLess(gap_ratio(bright) + 0.08, gap_ratio(source), name)
            self.assertLess(yellow_fraction(bright), 0.08, name)
            # Highlight compress is rare and does not flatten the body into one value.
            self.assertLess(compressed, 0.02, name)
            self.assertGreater(deviation(bright_l) / deviation(cool_l), 0.9, name)

    def test_premultiplied_edge_does_not_invent_color(self):
        # Straight opaque pixel and a half-alpha texel with the same straight color.
        gain = cgfloat("nightFigureGain")
        straight = (0.40, 0.31, 0.20)
        edge = tuple(channel * 0.5 for channel in straight)  # premultiplied
        opaque, _ = scalar_night([straight], gain)
        # Shader clamps the peak to alpha. Half alpha => peak limit 0.5 before the tint.
        scaled = tuple(channel * gain for channel in edge)
        peak = max(scaled)
        if peak > 0.5:
            scaled = tuple(channel * 0.5 / peak for channel in scaled)
        graded = tuple(channel * tone for channel, tone in zip(scaled, NIGHT))
        # Hue of the edge matches the opaque result; alpha was not turned into yellow RGB.
        self.assertLess(chroma_error(opaque, [graded]), 0.002)
        self.assertLess(max(scaled), 0.501)


def write_contact_sheet():
    """Day, night grade, rejected shader, scalar gain. Real head and torso texels."""
    gain = cgfloat("nightFigureGain")
    labels = ("day PNG", "night tint", "5c37c66", f"gain {gain:.2f}")
    thumb = 220
    pad = 8
    width = 64 + pad + len(labels) * (thumb + pad)
    height = 24 + 2 * (thumb + pad)
    sheet = Image.new("RGB", (width, height), (18, 28, 40))
    draw = ImageDraw.Draw(sheet)
    for column, label in enumerate(labels):
        draw.text((64 + pad + column * (thumb + pad), 4), label, fill=(230, 230, 230))
    for row, name in enumerate(("head", "torso")):
        image = Image.open(PARTS / f"{name}.png").convert("RGBA")
        image.thumbnail((thumb, thumb))
        pixels = [tuple(channel / 255 for channel in pixel[:3])
                  for pixel in image.getdata()]
        alpha = [pixel[3] / 255 for pixel in image.getdata()]
        modes = (
            pixels,
            tint_only(pixels),
            rejected_shader(pixels),
            scalar_night(pixels, gain)[0],
        )
        y = 24 + row * (thumb + pad)
        draw.text((4, y + thumb // 2), name, fill=(230, 230, 230))
        for column, colored in enumerate(modes):
            x = 64 + pad + column * (thumb + pad)
            composed = Image.new("RGBA", image.size)
            src = []
            for color, a in zip(colored, alpha):
                src.append(tuple(int(max(0, min(255, channel * 255))) for channel in color) + (int(a * 255),))
            composed.putdata(src)
            under = Image.new("RGBA", image.size, (18, 28, 40, 255))
            under.alpha_composite(composed)
            sheet.paste(under.convert("RGB"), (x, y))
    out = Path("/opt/cursor/artifacts/night-figure-pixels.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


if __name__ == "__main__":
    write_contact_sheet()
    unittest.main(verbosity=2)
