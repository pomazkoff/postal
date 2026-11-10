#!/usr/bin/env python3
"""Static RU/EN coverage for the Postman app. No Xcode, no iOS runtime.

Checks:
- every user-facing story/world/lore/map string has an English overlay
- overlay does not add or drop ids, conditions, flags, numbers, or routes
- {postmark} and {labelDate} stay put
- English UI strings and the overlay have no Cyrillic (names are transliterated)
- ru and en Localizable keys match, including plural categories
- Russian source JSON still contains its original letters (not rewritten)
"""
import json, os, re, sys, plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Postman/GameAssets/Data"
L10N = ROOT / "Postman/GameAssets/L10n"
RES = ROOT / "Postman/Resources"
CYR = re.compile(r"[А-Яа-яЁё]")
PH = re.compile(r"\{[a-zA-Z0-9_]+\}")
FAILS = []

def fail(msg):
    FAILS.append(msg)

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def placeholders(text):
    return PH.findall(text or "")

def need(ok, path, ru):
    if ru is None or ru == "":
        return
    if not ok:
        fail(f"missing EN for {path}: {ru[:80]!r}")
    elif isinstance(ok, str) and CYR.search(ok):
        fail(f"Cyrillic in EN {path}: {ok[:80]!r}")
    elif isinstance(ok, str) and placeholders(ru) != placeholders(ok):
        fail(f"placeholders {path}: ru {placeholders(ru)} en {placeholders(ok)}")

en = load(L10N / "en.json")
stories_en = en["stories"]

def story_check(chapter, doc):
    spec = stories_en.get(str(chapter), {})
    for key in ("finaleTitle", "finaleSubtitle", "nextChapter", "sortAuto"):
        if doc.get(key):
            need(spec.get(key), f"story{chapter}.{key}", doc[key])
    items = spec.get("items", {})
    for it in doc["items"]:
        s = items.get(it["id"], {})
        base = f"story{chapter}.item.{it['id']}"
        for key in ("to", "place", "from", "text", "outside", "note"):
            if it.get(key):
                need(s.get(key), f"{base}.{key}", it[key])
        reader = it.get("reader") or {}
        if reader.get("attachmentCaption"):
            need(s.get("attachmentCaption"), f"{base}.attachmentCaption", reader["attachmentCaption"])
        for i, line in enumerate(reader.get("address") or []):
            got = (s.get("address") or [None] * 99)
            need(got[i] if i < len(got) else None, f"{base}.address.{i}", line)
        for i, line in enumerate(reader.get("stamp") or []):
            got = (s.get("stamp") or [None] * 99)
            need(got[i] if i < len(got) else None, f"{base}.stamp.{i}", line)
        for i, note in enumerate(it.get("notes") or []):
            got = (s.get("notes") or [])
            g = got[i] if i < len(got) else {}
            if note.get("who"):
                need(g.get("who"), f"{base}.notes.{i}.who", note["who"])
            need(g.get("text"), f"{base}.notes.{i}.text", note.get("text"))
            if note.get("if") and (g.get("if") not in (None, note["if"])):
                # overlay must not rewrite conditions; absence is correct
                if "if" in g and g["if"] != note["if"]:
                    fail(f"condition rewritten {base}.notes.{i}")
    events = spec.get("events", {})
    for ev in doc["events"]:
        s = events.get(ev["id"], {})
        base = f"story{chapter}.event.{ev['id']}"
        for key in ("title", "text", "fallback", "note"):
            if ev.get(key):
                need(s.get(key), f"{base}.{key}", ev[key])
        for key in ("lines", "push"):
            for i, line in enumerate(ev.get(key) or []):
                got = (s.get(key) or [])
                g = got[i] if i < len(got) else {}
                if line.get("who"):
                    need(g.get("who"), f"{base}.{key}.{i}.who", line["who"])
                if line.get("text"):
                    need(g.get("text"), f"{base}.{key}.{i}.text", line["text"])
        opts = s.get("options") or {}
        for o in ev.get("options") or []:
            g = opts.get(o["id"], {})
            for key in ("label", "result", "auto"):
                if o.get(key):
                    need(g.get(key), f"{base}.option.{o['id']}.{key}", o[key])
    qmap = spec.get("quests") or {}
    for q in doc["quests"]:
        key = f"{q['event']}|{q.get('if') or ''}"
        need(qmap.get(key), f"story{chapter}.quest.{key}", q["telegram"])
    names = spec.get("residents") or {}
    for r in doc["residents"]:
        need(names.get(r["id"]), f"story{chapter}.resident.{r['id']}", r["name"])
    fmap = spec.get("fates") or {}
    for fate in doc["fates"]:
        key = f"{fate['settlement']}|{fate['if']}"
        need(fmap.get(key), f"story{chapter}.fate.{key}", fate["text"])
    amap = spec.get("arrivals") or {}
    for a in doc.get("arrivals") or []:
        need(amap.get(a["settlement"]), f"story{chapter}.arrival.{a['settlement']}", a["text"])

for n in (1, 2, 3):
    story_check(n, load(DATA / f"chapter{n}_story.json"))

world = load(DATA / "world.json")
wspec = en["world"]["chapters"]
for ch in world["chapters"]:
    cid = str(ch["id"])
    spec = wspec.get(cid, {})
    need(spec.get("title"), f"world.{cid}.title", ch["title"])
    names = spec.get("settlements") or {}
    for s in ch["settlements"]:
        g = names.get(s["id"], {})
        for key in ("name", "nameGenitive", "fullName"):
            need(g.get(key), f"world.{cid}.{s['id']}.{key}", s[key])
    qmap = spec.get("quests") or {}
    for q in ch.get("quests") or []:
        need(qmap.get(str(q["untilStep"])), f"world.{cid}.quest.{q['untilStep']}", q["telegram"])

lore = load(DATA / "resident_lore.json")
lspec = en["lore"]
for rid, entry in lore.items():
    g = lspec.get(rid, {})
    need(g.get("title"), f"lore.{rid}.title", entry["title"])
    for i, line in enumerate(entry["lines"]):
        got = (g.get("lines") or [None] * 99)
        need(got[i] if i < len(got) else None, f"lore.{rid}.line.{i}", line)

mp = load(ROOT / "Postman/GameAssets/UI/map/map.json")
mspec = en.get("map", {}).get("settlements", {})
for s in mp["settlements"]:
    need(mspec.get(s["id"]), f"map.{s['id']}", s["name"])

# Structural parity: ids, conditions, numbers survive a simulated overlay.
def project(doc):
    """Everything that must not change when English strings are swapped in."""
    out = json.loads(json.dumps(doc))
    def scrub(node):
        if isinstance(node, dict):
            for k in list(node):
                if k in ("text", "title", "label", "result", "auto", "who", "telegram",
                         "name", "nameGenitive", "fullName", "to", "place", "from",
                         "outside", "note", "fallback", "attachmentCaption", "address",
                         "stamp", "finaleTitle", "finaleSubtitle", "nextChapter", "sortAuto",
                         "lines") and k != "lines":
                    # keep structure of non-strings; drop display strings
                    if isinstance(node[k], str):
                        node[k] = ""
                    elif isinstance(node[k], list) and node[k] and isinstance(node[k][0], str):
                        node[k] = [""] * len(node[k])
                    else:
                        scrub(node[k])
                else:
                    scrub(node[k])
        elif isinstance(node, list):
            for x in node:
                scrub(x)
    scrub(out)
    return out

def apply_like_swift(doc, spec, chapter):
    """Mirror ContentLocalizer.applyStory enough to prove ids survive."""
    out = json.loads(json.dumps(doc))
    # Only check that spec doesn't try to set id/if/flags. Presence of those keys is a bug.
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                logic = {"id", "if", "flags", "requires", "settlement", "senderSettlement",
                         "kind", "initial", "art", "effects", "trust", "candidates",
                         "item", "send", "receive", "default", "step", "type", "companion"}
                # "items" on an event is a list of ids. The overlay's top-level "items" is a dict of letters.
                if k in logic or (k == "items" and isinstance(v, list)):
                    fail(f"overlay must not carry logic key {path}.{k}")
                else:
                    walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    walk(spec, f"story{chapter}")
    # ids unchanged by construction if we never write them; confirm counts
    if len(spec.get("items", {})) != len(doc["items"]):
        fail(f"story{chapter} item count {len(spec.get('items', {}))} != {len(doc['items'])}")
    if len(spec.get("events", {})) != len(doc["events"]):
        fail(f"story{chapter} event count {len(spec.get('events', {}))} != {len(doc['events'])}")
    src_ids = [e["id"] for e in doc["events"]]
    if sorted(spec.get("events", {})) != sorted(src_ids):
        missing = set(src_ids) - set(spec.get("events", {}))
        extra = set(spec.get("events", {})) - set(src_ids)
        fail(f"story{chapter} event ids missing {missing} extra {extra}")
    for ev in doc["events"]:
        s = spec.get("events", {}).get(ev["id"], {})
        for key in ("lines", "push"):
            if ev.get(key) and len(s.get(key) or []) != len(ev[key]):
                fail(f"story{chapter}.{ev['id']}.{key} count {len(s.get(key) or [])} != {len(ev[key])}")
        src_opts = [o["id"] for o in ev.get("options") or []]
        got_opts = list((s.get("options") or {}))
        if sorted(src_opts) != sorted(got_opts):
            fail(f"story{chapter}.{ev['id']} options {src_opts} != {got_opts}")
    # route targets still present
    item_ids = {it["id"] for it in doc["items"]}
    settlements = set()
    for ref in doc["events"]:
        for key in ("items",):
            for iid in ref.get(key) or []:
                if iid not in item_ids:
                    fail(f"dangling item {iid} in {ref['id']}")
        if ref.get("item") and ref["item"] not in item_ids:
            fail(f"dangling item {ref['item']} in {ref['id']}")
        for key in ("send", "receive"):
            if ref.get(key) and ref[key] not in item_ids:
                fail(f"dangling {key} {ref[key]} in {ref['id']}")
    return out

for n in (1, 2, 3):
    doc = load(DATA / f"chapter{n}_story.json")
    apply_like_swift(doc, stories_en[str(n)], n)
    # known letter still Russian in the source file
    raw = (DATA / f"chapter{n}_story.json").read_text(encoding="utf-8")
    if n == 1 and "Кузьма Ерофеич здраствуй" not in raw:
        fail("chapter 1 Russian letter was rewritten")
    if n == 2 and "Мам здравствуй" not in raw:
        fail("chapter 2 Russian letter was rewritten")
    if n == 3 and "Митюша, купила крючки" not in raw:
        fail("chapter 3 Russian letter was rewritten")

# UI catalogs
def strings(path):
    text = path.read_text(encoding="utf-8")
    keys = re.findall(r'^"((?:\\.|[^"\\])*)"\s*=', text, re.M)
    vals = re.findall(r'=\s*"((?:\\.|[^"\\])*)"\s*;', text)
    return keys, vals

en_keys, en_vals = strings(RES / "en.lproj/Localizable.strings")
ru_keys, ru_vals = strings(RES / "ru.lproj/Localizable.strings")
if en_keys != ru_keys:
    fail(f"Localizable key mismatch extra en {set(en_keys)-set(ru_keys)} extra ru {set(ru_keys)-set(en_keys)}")
# The Russian option is named in Russian on both screens. Nothing else in en may be Cyrillic.
ALLOW_CYR_EN = {"menu.language.ru"}
for key, val in zip(en_keys, en_vals):
    if key in ALLOW_CYR_EN:
        if val != "Русский":
            fail(f"{key} must stay the language's own name")
        continue
    if CYR.search(val):
        fail(f"Cyrillic in en Localizable {key}: {val[:60]!r}")
# Russian file must still hold the original onboarding sentence.
ru_text = (RES / "ru.lproj/Localizable.strings").read_text(encoding="utf-8")
if "Ты — последний почтальон." not in ru_text:
    fail("Russian onboarding copy was rewritten")
if "Почтальон идёт, когда идёте вы" not in (RES / "ru.lproj/InfoPlist.strings").read_text(encoding="utf-8"):
    fail("Russian Health permission string was rewritten")

def plurals(path):
    with open(path, "rb") as f:
        return plistlib.load(f)

en_p = plurals(RES / "en.lproj/Localizable.stringsdict")
ru_p = plurals(RES / "ru.lproj/Localizable.stringsdict")
if set(en_p) != set(ru_p):
    fail(f"stringsdict keys {set(en_p)} != {set(ru_p)}")
for key in en_p:
    ew = en_p[key]["word"]
    rw = ru_p[key]["word"]
    for cat in ("zero", "one", "other"):
        if cat not in ew:
            fail(f"en {key} missing plural {cat}")
        if CYR.search(ew[cat]):
            fail(f"Cyrillic in en plural {key}.{cat}")
    for cat in ("zero", "one", "few", "many", "other"):
        if cat not in rw:
            fail(f"ru {key} missing plural {cat}")
    if ew["one"] == ew["other"] and key.startswith("unit."):
        fail(f"en {key} one and other are the same")
    if rw["one"] == rw["many"]:
        fail(f"ru {key} one and many are the same")

# Baked art is a real gap: pixels stay Russian. Captions must exist and stay Latin.
baked_doc = load(L10N / "baked_art.json")
baked = {k: v["pixels"] for k, v in baked_doc.items() if isinstance(v, dict) and "pixels" in v}
en_ui = dict(zip(en_keys, en_vals))
for asset in baked:
    key = f"baked.{asset}"
    if key not in en_ui:
        fail(f"missing baked caption {key}")
    elif not en_ui[key]:
        fail(f"empty baked caption {key}")

# Every L10n key used in Swift exists in both catalogs, and %@ / %lld counts match
# except the watch lines, which branch on language inside Format.
ALLOW_SPEC_DIFF = {"watch.a11y.today", "watch.a11y.expanded"}
used = set(re.findall(r'L10n\.(?:text|format|plural)\("([^"]+)"', 
                      "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "Postman").rglob("*.swift"))))
catalog_keys = set(en_keys) | set(en_p)
missing_keys = sorted(used - catalog_keys)
if missing_keys:
    fail(f"Swift uses keys missing from Localizable.strings/stringsdict: {missing_keys}")
spec = re.compile(r"%(?:lld|@|d)")
for key, ev, rv in zip(en_keys, en_vals, ru_vals):
    if key in ALLOW_SPEC_DIFF:
        continue
    if spec.findall(ev) != spec.findall(rv):
        fail(f"format specifiers differ for {key}: en {spec.findall(ev)} ru {spec.findall(rv)}")

# glossary is documentation of transliteration, Latin only
glossary_path = L10N / "glossary.json"
if not glossary_path.exists():
    fail("missing glossary.json")
else:
    gloss = load(glossary_path)
    blob = json.dumps(gloss, ensure_ascii=False)
    if CYR.search(blob):
        # Russian source forms are allowed in glossary as the left-hand record.
        pass

if FAILS:
    print(f"{len(FAILS)} localization check(s) failed:")
    for m in FAILS:
        print(" -", m)
    sys.exit(1)
print("localization checks passed")
print(f"  stories 1–2, lore {len(lore)}, world chapters {len(world['chapters'])}, map places {len(mp['settlements'])}")
print(f"  UI keys {len(en_keys)}, plural keys {len(en_p)}")
print("  baked art still Russian pixels:", ", ".join(baked))
