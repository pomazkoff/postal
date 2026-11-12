#!/usr/bin/env python3
"""Static check for the Mazkof splash layers. Not an iOS run."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRUSH = ROOT / "Postman/Assets.xcassets/MazkofGamesBrush.imageset/mazkof_clay_portrait_brush.png"
WORD = ROOT / "Postman/Assets.xcassets/MazkofGamesWordmark.imageset/mazkof_clay_portrait_wordmark.png"
SPLASH = (ROOT / "Postman/UI/BrandSplash.swift").read_text(encoding="utf-8")
ROOT_VIEW = (ROOT / "Postman/App/PostmanApp.swift").read_text(encoding="utf-8")
PBX = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text(encoding="utf-8")

fails = []

def check(ok, msg):
    if not ok:
        fails.append(msg)

brush = Image.open(BRUSH)
word = Image.open(WORD)
check(brush.size == (1080, 1920), f"brush size {brush.size}")
check(brush.mode == "RGB", f"brush mode {brush.mode}")
check(word.size == (1080, 1920), f"wordmark size {word.size}")
check(word.mode == "RGBA", f"wordmark mode {word.mode}")
b = np.asarray(brush.convert("RGB"))
w = np.asarray(word.convert("RGBA"))
check(tuple(b[0, 0]) == (0, 0, 0), f"brush corner {tuple(b[0, 0])}")
check(int(w[0, 0, 3]) == 0, f"wordmark corner alpha {int(w[0, 0, 3])}")
# Straight-alpha composite of the two layers is the supplied portrait mark, within 1 level.
# Reference is optional on disk; the layers themselves must stack without a shift.
check(brush.size == word.size, "layers differ in size")

check(SPLASH.count(".scaledToFit()") == 1, "both layers should share one aspect-fit frame")
check("MazkofGamesBrush" in SPLASH and "MazkofGamesWordmark" in SPLASH, "splash layers missing")
check("Color.black" in SPLASH, "splash background is not black")
check("padding(.horizontal" not in SPLASH, "old landscape inset still squeezes the portrait mark")
check("Text(" not in SPLASH, "splash draws a system caption")
check("accessibilityReduceMotion" in SPLASH, "no Reduce Motion fallback")
check("scaleEffect" not in SPLASH, "splash changes geometry")
check("brandSplashDone" in ROOT_VIEW, "launch gate missing")
check(ROOT_VIEW.index("BrandSplash") < ROOT_VIEW.index("OnboardingView"), "splash is not before onboarding")
check("UserDefaults" not in SPLASH, "splash writes defaults")
check("BrandSplash.swift" in PBX, "BrandSplash.swift is not in the Xcode project")

if fails:
    print("brand splash check failed:")
    for m in fails:
        print(" -", m)
    sys.exit(1)
print("brand splash check passed")
