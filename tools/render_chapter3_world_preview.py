#!/usr/bin/env python3
"""Offline layout of the chapter 3 walk. Not a device frame and not SpriteKit."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Postman/GameAssets"
OUT = Path("/opt/cursor/artifacts/chapter3-world")
OUT.mkdir(parents=True, exist_ok=True)

world = json.loads((ASSETS / "Data/world.json").read_text(encoding="utf-8"))
game = world["game"]
W, H = int(game["designWidth"]), int(game["designHeight"])
PPS = game["pixelsPerStep"]
ROAD_Y = game["roadLineY"]
SCREEN_X = game["postman"]["screenX"]
chapter = next(c for c in world["chapters"] if c["id"] == 3)


def world_x(step):
    return step * PPS


def camera_x(step):
    return world_x(step) + (0.5 - SCREEN_X) * W


def screen_left(world_left, cam, k, anchor_cam):
    scene_x = cam * (1 - k) + (world_left - anchor_cam * (1 - k))
    return scene_x - cam + W / 2


def paste(canvas, image, left, top):
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    x, y = int(round(left)), int(round(top))
    canvas.alpha_composite(image, (x, y))


def sky(canvas):
    top = tuple(int(chapter["sky"]["topColor"][i:i + 2], 16) for i in (1, 3, 5))
    bot = tuple(int(chapter["sky"]["bottomColor"][i:i + 2], 16) for i in (1, 3, 5))
    px = canvas.load()
    for y in range(H):
        t = min(1, y / ROAD_Y)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,)
        for x in range(W):
            px[x, y] = color


def tile_strip(canvas, rel, top, height, parallax, cam):
    image = Image.open(ASSETS / "Chapter3" / (rel + ".png")).convert("RGBA")
    tw = height * image.size[0] / image.size[1]
    scaled = image.resize((max(1, int(tw)), int(height)), Image.Resampling.LANCZOS)
    # Полоса стоит в мире с нуля и едет с параллаксом.
    origin = screen_left(0, cam, parallax, cam)
    x = origin
    while x > -scaled.size[0]:
        x -= scaled.size[0]
    while x < W:
        paste(canvas, scaled, x, top)
        x += scaled.size[0]


def main():
    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", 28)
    postman = Image.open(ASSETS / "UI/map/postman.png").convert("RGBA")
    ph = 430
    postman = postman.resize((max(1, int(ph * postman.size[0] / postman.size[1])), ph), Image.Resampling.LANCZOS)
    frames = [
        (49000, "world 49 000 · the Boardwalk"),
        (54000, "world 54 000 · the Mire"),
        (61500, "world 61 500 · the Old Channel"),
        (67500, "world 67 500 · the Gullet"),
    ]
    far = world["layers"]["far"]
    mid = world["layers"]["mid"]
    for step, caption in frames:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        sky(canvas)
        cam = camera_x(step)
        tile_strip(canvas, far["image"], far["top"], far["height"], far["parallax"], cam)
        tile_strip(canvas, mid["image"], mid["top"], mid["height"], mid["parallax"], cam)
        ug = chapter["underground"]
        tile_h = ug["tilePixelSize"][1] * ug["scale"]
        tile_strip(canvas, ug["neutralTile"], ug["top"], tile_h, world["layers"]["undergroundParallax"], cam)
        tile_w = ug["tilePixelSize"][0] * ug["scale"]
        placed = sorted(
            (world_x(chapter["startStep"] + m["step"]) + m["dx"] - tile_w / 2, m["image"])
            for m in ug["modules"]
        )
        cursor = placed[0][0] if placed else 0
        laid = []
        for i, (left, image) in enumerate(placed):
            if i and left - cursor < tile_w * ug["minGapFraction"]:
                left = cursor
            laid.append((left, image))
            cursor = left + tile_w
        for left, image in laid:
            screen = screen_left(left, cam, 1, cam)
            if screen > W or screen + tile_w < 0:
                continue
            module = Image.open(ASSETS / "Chapter3" / (image + ".png")).convert("RGBA")
            module = module.resize((int(tile_w), int(tile_h)), Image.Resampling.LANCZOS)
            paste(canvas, module, screen, ug["top"])
        order = {"far": 0, "mid": 1, "underground": 2, "main": 3, "foreground": 4}
        for prop in sorted(chapter["props"], key=lambda p: (order[p["layer"]], p.get("z", 0))):
            image = Image.open(ASSETS / "Chapter3" / (prop["image"] + ".png")).convert("RGBA")
            height = prop["height"]
            width = height * prop["pixelSize"][0] / prop["pixelSize"][1]
            scaled = image.resize((max(1, int(width)), max(1, int(height))), Image.Resampling.LANCZOS)
            k = {"far": far["parallax"], "mid": mid["parallax"], "main": 1.0,
                 "underground": 1.0, "foreground": 1.3}[prop["layer"]]
            anchor = camera_x(chapter["startStep"] + prop["step"])
            left = screen_left(world_x(chapter["startStep"] + prop["step"]) + prop["dx"], cam, k, anchor)
            top = ROAD_Y + prop["sink"] - height
            if left > W or left + scaled.size[0] < 0:
                continue
            paste(canvas, scaled, left, top)
        # Федя на Гати, если попадает в кадр.
        fedya = Image.open(ASSETS / "Chapter3/residents/fedya/full.png").convert("RGBA")
        fedya = fedya.resize((int(400 * fedya.size[0] / fedya.size[1]), 400), Image.Resampling.LANCZOS)
        fedya_step = chapter["startStep"] + 4800
        fedya_left = screen_left(world_x(fedya_step) + 220 - fedya.size[0] / 2, cam, 1, cam)
        if -fedya.size[0] < fedya_left < W:
            paste(canvas, fedya, fedya_left, ROAD_Y + 30 - 400)
        hero_left = W * SCREEN_X - postman.size[0] / 2
        paste(canvas, postman, hero_left, ROAD_Y + 30 - postman.size[1])
        plate = Image.new("RGBA", (W, 90), (40, 28, 18, 210))
        d = ImageDraw.Draw(plate)
        d.text((24, 16), "OFFLINE layout · not a device · not SpriteKit", fill=(244, 232, 210, 255), font=font)
        d.text((24, 48), caption, fill=(244, 232, 210, 255), font=font)
        canvas.alpha_composite(plate, (0, 0))
        path = OUT / f"world_{step}.jpg"
        canvas.convert("RGB").save(path, quality=85)
        print(path)


if __name__ == "__main__":
    main()
