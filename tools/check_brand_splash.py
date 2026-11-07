#!/usr/bin/env python3
"""Static check: supplied Mazkof splash image and a single launch gate. Not an iOS run."""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "Postman/Assets.xcassets/MazkofGamesLogo.imageset/mazkof_games_clay.png"
SPLASH = (ROOT / "Postman/UI/BrandSplash.swift").read_text(encoding="utf-8")
ROOT_VIEW = (ROOT / "Postman/App/PostmanApp.swift").read_text(encoding="utf-8")
PBX = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text(encoding="utf-8")

fails = []

def check(ok, msg):
    if not ok:
        fails.append(msg)

im = Image.open(PNG)
check(im.size == (1920, 1080), f"size {im.size}")
check(im.mode == "RGB", f"mode {im.mode}")
rgb = im.convert("RGB")
w, h = rgb.size
for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
    check(rgb.getpixel(xy) == (0, 0, 0), f"corner {xy} {rgb.getpixel(xy)}")

check(".scaledToFit()" in SPLASH, "splash is not aspect-fit")
check("Color.black" in SPLASH, "splash background is not black")
check("Text(" not in SPLASH, "splash draws a system caption")
check("MazkofGamesLogo" in SPLASH, "splash does not use the supplied image")
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
