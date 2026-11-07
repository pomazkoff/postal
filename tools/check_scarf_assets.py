#!/usr/bin/env python3
"""Шарф: alpha как у глиняных частей до правки, красная только ткань, стык головы и торса одного тона.

Оригинальная alpha снята с c923382 (до подмены RGB). Рантайма нет.
"""
import hashlib
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "Postman/GameAssets/Rig/parts"
# sha256 сырых файлов до красной ткани (c923382).
OLD = {
    "torso.png": "16a4336e1ab57b9d02b3fc5c729a0c5bd6795b8612d24af643f17061f58386a2",
    "head.png": "081aee81b556da252ea37699f676d5ceba4ee75f402c5414869893ce1cc134fc",
}
SIZE = {"torso.png": (303, 416), "head.png": (286, 302)}
FAILS = []


def fail(msg):
    FAILS.append(msg)


def git_show(name):
    return subprocess.check_output(
        ["git", "show", f"c923382:Postman/GameAssets/Rig/parts/{name}"], cwd=ROOT)


def hue(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0 or mx == 0:
        return 0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


for name, old_hash in OLD.items():
    raw = git_show(name)
    if hashlib.sha256(raw).hexdigest() != old_hash:
        fail(f"{name} baseline is not c923382")
    old = Image.frombytes("RGBA", SIZE[name], raw) if False else None
    # git show is PNG bytes, not raw pixels
    import io
    old = Image.open(io.BytesIO(raw)).convert("RGBA")
    new = Image.open(PARTS / name).convert("RGBA")
    if new.size != SIZE[name] or new.mode != "RGBA":
        fail(f"{name} size/mode {new.size} {new.mode}")
    if old.size != new.size:
        fail(f"{name} size drifted")
    oa, na = old.getchannel("A").tobytes(), new.getchannel("A").tobytes()
    if oa != na:
        fail(f"{name} alpha is not the original cutout")
    op, npx = old.load(), new.load()
    w, h = new.size
    changed = 0
    warm = 0
    for y in range(h):
        for x in range(w):
            pr, pg, pb, pa = op[x, y]
            qr, qg, qb, qa = npx[x, y]
            if pa != qa:
                fail(f"{name} alpha pixel changed")
                break
            if (pr, pg, pb) == (qr, qg, qb):
                continue
            changed += 1
            # перекрашенный пиксель должен уйти в красный, а не в чужой цвет
            hh = hue(qr, qg, qb)
            if not (hh <= 25 or hh >= 345):
                warm += 1
    if changed < 1000:
        fail(f"{name} scarf recolor looks missing ({changed})")
    if warm > changed * 0.08:
        fail(f"{name} recolor left non-red pixels {warm}/{changed}")
    print(name, "rgb changed", changed, "non-red", warm)

# Стык: низ головы и верх торса в координатах исходника rig.json.
import json
rig = json.loads((ROOT / "Postman/GameAssets/Rig/rig.json").read_text())
head = Image.open(PARTS / "head.png").convert("RGBA")
torso = Image.open(PARTS / "torso.png").convert("RGBA")
ho, to = rig["offsets"]["head"], rig["offsets"]["torso"]

def reds(im, ox, oy, y0, y1):
    px = im.load()
    cols = []
    for y in range(im.size[1]):
        sy = oy + y
        if not (y0 <= sy < y1):
            continue
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            hh = hue(r, g, b)
            if (hh <= 20 or hh >= 345) and r > g + 25 and r > 70:
                cols.append((r, g, b))
    return cols

# Полоса стыка вокруг шеи, y исходника 320–400.
hc, tc = reds(head, ho[0], ho[1], 320, 400), reds(torso, to[0], to[1], 320, 400)
if len(hc) < 30 or len(tc) < 30:
    fail(f"scarf does not meet at the neck: head {len(hc)} torso {len(tc)}")
else:
    def avg(cols):
        n = len(cols)
        return tuple(sum(c[i] for c in cols) / n for i in range(3))
    ah, at = avg(hc), avg(tc)
    if abs(ah[0] - at[0]) > 45 or abs(ah[1] - at[1]) > 35:
        fail(f"neck scarf tones diverge head {ah} torso {at}")
    else:
        print("neck scarf", tuple(round(v) for v in ah), tuple(round(v) for v in at))

others = ["arm_upper.png", "arm_lower.png", "thigh.png", "shin.png", "foot.png", "staff.png"]
for name in others:
    cur = hashlib.sha256((PARTS / name).read_bytes()).hexdigest()
    base = hashlib.sha256(git_show(name)).hexdigest()
    if cur != base:
        fail(f"{name} should stay the clay original")

if FAILS:
    print(f"{len(FAILS)} scarf check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("scarf asset checks ok")
