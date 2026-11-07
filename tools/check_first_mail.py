#!/usr/bin/env python3
"""Deeplink «Первый почтовый рейс»: маршрут, отложенный показ, честный статус l1.

Это разбор правил и исходников. Запуск на iOS здесь не делается и PASS холодного
или тёплого старта не заявляется.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


SCHEME = "mazkofpostman"
HOST = "first-mail"
EXACT = "mazkofpostman://first-mail"


def route(url: str):
    """Тот же разбор, что FirstMailLink.route: scheme + host, путь пустой или /."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if (parsed.scheme or "").lower() != SCHEME:
        return False
    if (parsed.hostname or "").lower() != HOST:
        return False
    return parsed.path in ("", "/")


def classify(status, delivery_done):
    if status == "delivered":
        return "delivered"
    if delivery_done:
        return "unreachable"
    if status == "inBag":
        return "inBag"
    if status == "atPost":
        return "atPost"
    return "unreachable"


def should_show(splash, onboarding, pending):
    return splash and onboarding and pending


if route(EXACT) is not True:
    fail("exact URL must open the card")
if route("mazkofpostman://first-mail/") is not True:
    fail("a trailing slash is the same card")
if route("mazkofpostman://first-mail?ref=event") is not True:
    fail("a query on the exact route still opens the same card")
for bad in (
    "https://mazkofpostman/first-mail",
    "mazkofpostman://other",
    "mazkofpostman://first-mail/extra",
    "postman://first-mail",
    "mazkofpostman://",
    "",
    "mazkofpostman://first-mail/first-mail",
):
    if route(bad):
        fail(f"must ignore {bad!r}")

if classify("inBag", False) != "inBag":
    fail("in bag, delivery not done")
if classify("atPost", False) != "atPost":
    fail("on the shelf")
if classify("delivered", True) != "delivered":
    fail("delivered wins over the done flag")
if classify("delivered", False) != "delivered":
    fail("delivered status is enough")
if classify("atPost", True) != "unreachable":
    fail("the stop already happened without the letter")
if classify("inBag", True) != "unreachable":
    fail("a finished stop is not described as still ahead")
for other in ("onRoad", "inPocket", "leftBehind", "sent", "lostWind", "read"):
    if classify(other, False) != "unreachable":
        fail(f"{other} must not look like a successful or pending handoff")

if should_show(False, True, True) or should_show(True, False, True) or should_show(True, True, False):
    fail("the card waits for splash, onboarding, and a real route")
if not should_show(True, True, True):
    fail("after splash and onboarding the pending card can show")

# repeated URL only keeps the flag; the helper must not grow a second errand
pending = False
def receive(ok):
    global pending
    if ok:
        pending = True
receive(route(EXACT))
receive(route(EXACT))
if pending is not True:
    fail("a second URL must keep the same card, not a new errand")
receive(route("mazkofpostman://nope"))
if pending is not True:
    fail("a bad URL must not clear the card that is already up")

link = (ROOT / "Postman/App/FirstMailLink.swift").read_text(encoding="utf-8")
app = (ROOT / "Postman/App/PostmanApp.swift").read_text(encoding="utf-8")
delegate = (ROOT / "Postman/App/AppDelegate.swift").read_text(encoding="utf-8")
model = (ROOT / "Postman/App/GameModel.swift").read_text(encoding="utf-8")
plist = (ROOT / "Postman/Info.plist").read_text(encoding="utf-8")
card = (ROOT / "Postman/UI/FirstMailCard.swift").read_text(encoding="utf-8")

if 'static let exactURL = "mazkofpostman://first-mail"' not in link:
    fail("exact URL missing from the parser")
if "<string>mazkofpostman</string>" not in plist or "CFBundleURLSchemes" not in plist:
    fail("the scheme is not registered in Info.plist")
if ".onOpenURL" not in app or "FirstMailGate.shouldShow" not in app:
    fail("the window does not defer the card")
if "launchOptions?[.url]" not in delegate:
    fail("cold launch URL is not kept")
if "requestAuthorization" in link or "requestAuthorization" in card:
    fail("the deeplink must not start a permission prompt")
receive_fn = model.split("func receiveFirstMail", 1)[1].split("func pullFirstMailInbox", 1)[0]
for forbidden in ("process()", "confirmSort", "jumpToSteps", "resetStory", "items["):
    if forbidden in receive_fn:
        fail(f"receiving a URL must not {forbidden}")
dismiss = model.split("func dismissFirstMail", 1)[1].split("func firstMailReading", 1)[0]
if "firstMailPending = false" not in dismiss:
    fail("continue must only hide the card")
if "engine." in dismiss or "scene." in dismiss:
    fail("continue must not touch the story or the camera")

ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
for key in ("firstmail.title", "firstmail.body", "firstmail.inBag", "firstmail.atPost",
            "firstmail.delivered", "firstmail.unreachable", "firstmail.continue"):
    if f'"{key}"' not in ru or f'"{key}"' not in en:
        fail(f"missing string {key}")
if "2900" not in ru or "2900" not in en:
    fail("the step of the real handoff must stay in the copy")
for banned in ("7 дн", "7 day", "награда", "reward", "календар"):
    if banned.lower() in ru.lower() or banned.lower() in en.lower():
        # only scan the firstmail lines
        pass
import re
def values(text):
    return "\n".join(re.findall(r'"firstmail\.[^"]+"\s*=\s*"((?:\\.|[^"\\])*)"', text))
blob = (values(ru) + values(en)).lower()
for banned in ("7 дн", "7 day", "награда", "reward", "календар", "calendar"):
    if banned in blob:
        fail(f"first-mail copy promises {banned}")

if FAILS:
    print(f"{len(FAILS)} first-mail check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("first-mail route checks ok (not an iOS cold/warm launch)")
