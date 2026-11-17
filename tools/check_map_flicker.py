#!/usr/bin/env python3
"""The parchment must not repaint on every step or crossfade when the picture changes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
screen = (ROOT / "Postman/UI/MapScreen.swift").read_text(encoding="utf-8")
FAILS = []


def fail(msg):
    FAILS.append(msg)


def key(threshold, step=0.02):
    if threshold >= 1.5:
        return 2.0
    return round(threshold / step) * step


# One step on the 30 000-step swamp sheet stays in the same bucket.
length = 30000
one = 1000 / length
assert key(one) == key((1000 + 1) / length)
# A move of one bucket is a new picture.
assert key(0.0) != key(0.02 + 1 / length)
# A finished sheet is one picture, not a new one per step.
assert key(2.0) == key(1.6)

if "enum MapRevealQuantizer" not in screen or "static let step = 0.02" not in screen:
    fail("map reveal is not quantized")
for raw in (
    ".task(id: swampRevealKey)",
    ".task(id: mountainRevealKey)",
    ".task(id: map?.revealThreshold",
):
    if raw in screen:
        fail(f"map task still restarts on the raw threshold: {raw}")
if screen.count(".task(id: MapRevealQuantizer.key(") != 3:
    fail("valley, mountain, and swamp tasks must all use the quantized key")
if "task?.cancel()" not in screen:
    fail("a newer map render does not cancel the previous one")
if "disablesAnimations = true" not in screen:
    fail("the picture swap can still fade")
if "guard !Task.isCancelled, slot.accepts" not in screen:
    fail("a stale render can still publish")
for name in ("revealed = image", "mountainPicture = image", "swampPicture = image"):
    if name not in screen:
        fail(f"missing picture store {name}")
if "swampPicture = nil" in screen or "mountainPicture = nil" in screen or "revealed = nil" in screen:
    fail("a refresh clears the picture before the next one is ready")
# The sheet fallback must be a cached UIImage, not a new one every layout pass.
body = screen.split("private func mountainLayer", 1)[-1].split("private func openMountain", 1)[0]
if "UIImage(contentsOfFile:" in body:
    fail("the mountain and swamp fallback reads the file on every pass")

if FAILS:
    print(f"{len(FAILS)} map flicker check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("map flicker checks ok")
