#!/usr/bin/env python3
"""No raw localization keys in chapter 4: every key the chapter can show (handoff notes, bag
labels, handed captions, History, taps, residents, story copy) exists in RU and EN."""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "Postman/Resources"
FAILS: list[str] = []
def fail(msg): FAILS.append(msg)

def strings(path: Path) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'^"((?:[^"\\]|\\.)+)"\s*=\s*"((?:[^"\\]|\\.)*)";', path.read_text(encoding="utf-8"), re.M):
        out[m.group(1)] = m.group(2)
    return out

ru = strings(RES / "ru.lproj/Localizable.strings")
en = strings(RES / "en.lproj/Localizable.strings")
def need(key, why):
    for lang, table in (("ru", ru), ("en", en)):
        if not table.get(key, "").strip():
            fail(f"{lang}: no {key} ({why})")

bag = (ROOT / "Postman/App/BagPolicy.swift").read_text(encoding="utf-8")
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter4_story.json").read_text(encoding="utf-8"))
items = {i["id"]: i for i in story["items"]}

# Drops: (4, "id") ... [Drop(event: "x", ...), ...]
drops: dict[str, list[str]] = {}
for m in re.finditer(r'case ((?:\(4, "[^"]+"\)(?:,\s*)?)+):\s*return \[(.*?)\]', bag, re.S):
    ids = re.findall(r'\(4, "([^"]+)"\)', m.group(1))
    events = re.findall(r'Drop\(event: "([^"]+)"', m.group(2))
    for i in ids:
        drops[i] = events
if not drops:
    fail("could not read chapter 4 drops from BagPolicy")
captions = dict(re.findall(r'case "([^"]+)": return "(bag\.handed\.[^"]+)"', bag))
for item_id, events in drops.items():
    for ev in events:
        # settleCarried / migrate log: bag.handoff.<trigger> (finale -> bag.handoff.4.finale)
        need("bag.handoff.4.finale" if ev == "finale" else f"bag.handoff.{ev}", f"handoff note for {item_id}")
    kind = items.get(item_id, {}).get("kind", "")
    personal = not (kind in ("letter", "parcel", "secret") or item_id in ("l4", "l9"))
    if personal:
        for ev in events:
            if ev not in captions:
                fail(f"BagPolicy.handoffCaptionKey has no case for {ev} ({item_id} shows «Сдано»)")
            else:
                need(captions[ev], f"shelf caption for {item_id}")
    for ev in events[1:]:
        need(f"bag.act.drop.4.{ev}", f"bag label for {item_id} after the first drop")
for item_id in items:
    need(f"bag.act.4.{item_id}", "bag label")

# History: every key the chronicle can ask for.
chron = (ROOT / "Postman/App/StoryChronicle.swift").read_text(encoding="utf-8")
for key in set(re.findall(r'"(history\.main\.[a-z0-9_.]+)"', chron)):
    need(key, "History")
ch4_beats = re.findall(r'Beat\(id: "([^"]+)", chapterID: 4,', chron)
for b in ch4_beats:
    need(f"history.main.{b}.title", "History title")
titles = [ru.get(f"history.main.{b}.title") for b in ch4_beats]
dups = {t for t in titles if t and titles.count(t) > 1}
if dups:
    fail(f"chapter 4 History has two entries with one title: {sorted(dups)}")

# Taps.
taps = json.loads((ROOT / "Postman/GameAssets/Data/chapter4_taps.json").read_text(encoding="utf-8"))
for t in taps:
    need(f"tap.ch4.{t['id']}", "tap")
    need(f"tap.ch4.{t['id']}.title", "tap title")

# Residents and story copy (RU in json, EN in L10n/en.json).
lore = json.loads((ROOT / "Postman/GameAssets/Data/resident_lore.json").read_text(encoding="utf-8"))
enj = json.loads((ROOT / "Postman/GameAssets/L10n/en.json").read_text(encoding="utf-8"))
s4 = enj["stories"]["4"]
for r in story["residents"]:
    if r["id"] not in lore:
        fail(f"no RU lore for {r['id']}")
    if r["id"] not in enj["lore"]:
        fail(f"no EN lore for {r['id']}")
    if r["id"] not in s4.get("residents", {}):
        fail(f"no EN name for {r['id']}")
for e in story["events"]:
    spec = s4["events"].get(e["id"])
    if spec is None:
        fail(f"no EN copy for event {e['id']}")
        continue
    for k in ("lines", "push"):
        if len(e.get(k) or []) != len(spec.get(k) or []):
            fail(f"EN {e['id']}.{k}: {len(spec.get(k) or [])} lines for {len(e.get(k) or [])}")
    for o in e.get("options") or []:
        if o["id"] not in (spec.get("options") or {}):
            fail(f"no EN option {e['id']}.{o['id']}")
    if e.get("fallback") and not spec.get("fallback"):
        fail(f"no EN fallback for {e['id']}")
for i in story["items"]:
    if i["id"] not in s4["items"]:
        fail(f"no EN copy for item {i['id']}")

if FAILS:
    print(f"{len(FAILS)} chapter 4 key check(s) failed:")
    for f in FAILS:
        print(" -", f)
    raise SystemExit(1)
print(f"chapter 4 keys ok ({len(drops)} drops, {len(ch4_beats)} History beats, {len(taps)} taps)")
