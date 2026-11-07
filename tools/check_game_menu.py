#!/usr/bin/env python3
"""Меню дороги: кого встретили, поручение, язык, местные напоминания.

Правила совпадают с Postman/App/MenuLogic.swift. Здесь нет симулятора:
проверяются состояния и то, что Swift их не обходит.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def reached(index, active, active_steps, length):
    if index < active:
        return length
    if index > active:
        return 0
    return max(0, min(length, active_steps))


def met_ids(events, done, residents, reached_step):
    seen = []

    def add(i):
        if i and i not in seen:
            seen.append(i)

    for event in events:
        if event["id"] not in done:
            continue
        add(event.get("resident"))
        companion = event.get("companion") or {}
        add(companion.get("id"))
    for resident in sorted(residents, key=lambda r: r["step"]):
        if 0 < resident["step"] <= reached_step:
            add(resident["id"])
    return seen


def quest_kind(finished, telegram):
    if finished:
        return "finished"
    if telegram and telegram.strip():
        return "active"
    return "empty"


def language_code(choice, system_russian):
    if choice == "ru":
        return "ru"
    if choice == "en":
        return "en"
    return "ru" if system_russian else "en"


def plural_category(n, russian):
    if n == 0:
        return "zero"
    if russian:
        n = abs(n)
        mod10, mod100 = n % 10, n % 100
        if mod10 == 1 and mod100 != 11:
            return "one"
        if mod10 in (2, 3, 4) and mod100 not in (12, 13, 14):
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def reminder_effect(want_on, auth):
    if not want_on:
        return "setOffCancelPending"
    return {"notDetermined": "request", "denied": "openSettings", "allowed": "setOn"}[auth]


def appears_on(preference_on, auth):
    return preference_on and auth == "allowed"


# --- pure states ---
if met_ids([], set(), [{"id": "kuzma", "step": 10}], 0) != []:
    fail("empty road must not introduce anyone")
if met_ids(
    [{"id": "e_animal_rooster", "resident": "rooster"}],
    {"e_animal_rooster"},
    [{"id": "rooster", "step": 2800}, {"id": "kuzma", "step": 2900}, {"id": "agnia", "step": 99999}],
    2800,
) != ["rooster"]:
    fail("one done event must not open the rest of the road")
if met_ids(
    [{"id": "e_ramka", "companion": {"id": "ramka"}}],
    {"e_ramka"},
    [{"id": "agnia", "step": 99999}],
    4500,
) != ["ramka"]:
    fail("a done companion encounter should count as met")
if "agnia" in met_ids([], set(), [{"id": "agnia", "step": 99999}, {"id": "mitya", "step": 2900}], 20000):
    fail("A.L. is past the chapter and must stay hidden")
if met_ids([], set(), [{"id": "mitya", "step": 2900}], 2900) != ["mitya"]:
    fail("someone standing at a reached step has been met")
if met_ids([], set(), [{"id": "mitya", "step": 2900}], 2800) != []:
    fail("a resident ahead of the postman is not met yet")
if reached(1, 0, 100, 5000) != 0:
    fail("a future chapter contributes nobody")
if reached(0, 1, 100, 20000) != 20000:
    fail("a finished chapter keeps everyone the postman walked past")

if quest_kind(False, None) != "empty":
    fail("no telegram is the empty errand")
if quest_kind(False, "  ") != "empty":
    fail("blank telegram is empty")
if quest_kind(False, "Донести письмо") != "active":
    fail("a live telegram is the current errand")
if quest_kind(True, "ещё текст") != "finished":
    fail("a finished chapter wins over a leftover telegram")

if language_code("system", False) != "en":
    fail("system + non-Russian phone must stay English")
if language_code("system", True) != "ru":
    fail("system + Russian phone must stay Russian")
if language_code("en", True) != "en" or language_code("ru", False) != "ru":
    fail("an explicit language overrides the phone")

for n, cat in [(0, "zero"), (1, "one"), (2, "few"), (5, "many"), (11, "many"), (21, "one")]:
    if plural_category(n, True) != cat:
        fail(f"ru plural {n} -> {plural_category(n, True)}, expected {cat}")
for n, cat in [(0, "zero"), (1, "one"), (2, "other")]:
    if plural_category(n, False) != cat:
        fail(f"en plural {n} -> {plural_category(n, False)}, expected {cat}")

if reminder_effect(False, "allowed") != "setOffCancelPending":
    fail("turning reminders off must cancel pending, not the system switch")
if reminder_effect(True, "notDetermined") != "request":
    fail("the first explicit on must request permission")
if reminder_effect(True, "denied") != "openSettings":
    fail("a denial must open Settings instead of pretending to be on")
if reminder_effect(True, "allowed") != "setOn":
    fail("an allowed phone can turn the game reminders on without a new prompt")
if appears_on(True, "denied") or appears_on(True, "notDetermined"):
    fail("the switch must not look on until iOS has allowed it")
if not appears_on(True, "allowed") or appears_on(False, "allowed"):
    fail("the switch follows the saved preference only while iOS allows reminders")


def allows_posting(stored, known):
    """stored is None until the player chooses. known is None until iOS status is read."""
    if stored is not None:
        if not stored:
            return False
        return known == "allowed"
    if known is not None:
        return known == "allowed"
    return True


if not allows_posting(None, "allowed") or not allows_posting(True, "allowed"):
    fail("people who already allowed, or who turned reminders on, must still be scheduled")
if not allows_posting(None, None):
    fail("an unread status must not drop reminders for someone who already allowed them")
for known in ("notDetermined", "denied", None):
    if allows_posting(False, known):
        fail("an explicit off must not schedule")
if allows_posting(None, "notDetermined") or allows_posting(None, "denied"):
    fail("startup must not schedule, or ask, before the player turns reminders on")
if allows_posting(True, "notDetermined") or allows_posting(True, "denied"):
    fail("an on-switch without iOS permission must not queue a backlog")

# Real chapter: nobody at step 0, rooster only at his event, A.L. never by walking the chapter.
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8"))
events = [{"id": e["id"], "resident": e.get("resident"), "companion": e.get("companion")} for e in story["events"]]
residents = [{"id": r["id"], "step": r["step"]} for r in story["residents"]]
if met_ids(events, set(), residents, 0) != []:
    fail("chapter 1 at step 0 must be an empty cast")
rooster = met_ids(events, {"e_animal_rooster"}, residents, 2800)
if rooster != ["rooster"]:
    fail(f"partial cast should be just the rooster, got {rooster}")
walked = met_ids(events, set(), residents, 20000)
if "agnia" in walked or "kuzma" not in walked:
    fail("walking the chapter meets the road, not A.L.")
ramka = met_ids(events, {"e_ramka"}, residents, 4500)
if "ramka" not in ramka or "agnia" in ramka:
    fail("Ramka is met by her event; A.L. is not")

# --- source guards ---
logic = (ROOT / "Postman/App/MenuLogic.swift").read_text(encoding="utf-8")
loc = (ROOT / "Postman/App/Localization.swift").read_text(encoding="utf-8")
notifier = (ROOT / "Postman/Services/Notifier.swift").read_text(encoding="utf-8")
menu = (ROOT / "Postman/UI/GameMenuView.swift").read_text(encoding="utf-8")
hud = (ROOT / "Postman/UI/HUDView.swift").read_text(encoding="utf-8")
progress = (ROOT / "Postman/Services/ProgressStore.swift").read_text(encoding="utf-8")
core = (ROOT / "Postman/App/AppCore.swift").read_text(encoding="utf-8")
for needle in ("case system", "case ru", "case en", "systemPrefersRussian", "setOffCancelPending", "openSettings"):
    if needle not in logic and needle not in loc:
        fail(f"missing rule {needle}")
if 'hasPrefix("ru")' not in loc:
    fail("system language must keep the Russian-or-English fallback")
if "postman.language" not in loc or "postman.remindersEnabled" not in logic:
    fail("language or reminder preference is not stored")
reset = progress.split("func resetAll()", 1)[1].split("func resetStory", 1)[0]
if "postman.language" in reset or "postman.remindersEnabled" in reset:
    fail("story reset must not wipe language or reminder settings")
post = notifier.split("func post(", 1)[1].split("func postTest", 1)[0]
if "allowsPosting" not in post.split("UNMutableNotificationContent", 1)[0]:
    fail("posting must check the game switch before building a notification")
if "removeAllPendingNotificationRequests" not in notifier:
    fail("turning reminders off must remove pending requests")
if "requestAuthorization" in menu.split("case .setOffCancelPending", 1)[1].split("case .setOn", 1)[0]:
    fail("turning reminders off must not ask for permission")
set_on = menu.split("case .setOn:", 1)[1].split("case .request:", 1)[0]
if "notifier.post" in set_on or "postBeat" in set_on:
    fail("turning reminders back on must not post a second copy")
if "UIApplication.openSettingsURLString" not in menu:
    fail("a denial needs a real iOS Settings link")
if "registerForRemoteNotifications" in notifier or "aps-environment" in (ROOT / "Postman/Postman.entitlements").read_text(encoding="utf-8"):
    fail("menu must not add a remote push backend")
# adoptStep must not call process — language change is not a new beat.
adopt = (ROOT / "Postman/App/ChapterEngine.swift").read_text(encoding="utf-8").split("func adoptStep", 1)[1].split("private func isDone", 1)[0]
if "process()" in adopt:
    fail("language reload must not replay stops")
if "postedBeatIDs.removeAll" in core.split("func reloadLocalization", 1)[1].split("func switchToChapter", 1)[0]:
    fail("language reload must keep the set of stops already sent")
post_beat = core.split("private func postBeat", 1)[1].split("postedBeatIDs.insert", 1)[0]
if "allowsPosting" not in post_beat:
    fail("a stop must be refused before it is marked sent")

game = (ROOT / "Postman/App/GameModel.swift").read_text(encoding="utf-8")
onboarding_fn = game.split("func completeOnboarding", 1)[1].split("func appBecameActive", 1)[0]
if "notifier.requestAuthorization" in onboarding_fn:
    fail("onboarding must not request notification permission")
if "steps.requestAuthorization()" not in onboarding_fn or "askPermission: true" not in onboarding_fn:
    fail("onboarding must still ask for steps, then location")
if "refreshAuthorizationStatus" not in onboarding_fn:
    fail("onboarding must read notification status without asking")
active_fn = game.split("func appBecameActive", 1)[1].split("func appWentToBackground", 1)[0]
if "requestAuthorization" in active_fn:
    fail("returning to the app must not request notification permission")
if "askPermission: true" not in active_fn:
    fail("location on resume must stay")
delegate = (ROOT / "Postman/App/AppDelegate.swift").read_text(encoding="utf-8")
if "requestAuthorization" in delegate:
    fail("startup must not request notification permission")
prompt_calls = []
for path in (ROOT / "Postman").rglob("*.swift"):
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "notifier.requestAuthorization" in line:
            prompt_calls.append(f"{path.relative_to(ROOT)}:{lineno}")
        if "requestAuthorization(options:" in line and path.name != "Notifier.swift":
            fail(f"notification prompt outside Notifier.swift: {path.name}:{lineno}")
if len(prompt_calls) != 1 or not prompt_calls[0].startswith("Postman/UI/GameMenuView.swift:"):
    fail(f"notification prompt must be only the menu switch, got {prompt_calls}")
request_case = menu.split("case .request:", 1)[1].split("case .openSettings:", 1)[0]
if "notifier.requestAuthorization" not in request_case:
    fail("the menu's explicit on is no longer the prompt")
if "m.point(190, 2330)" not in hud or "m.point(990, 2330)" not in hud:
    fail("bag and map anchors moved")
if "m.point(168, 1480)" not in hud:
    fail("menu entry is missing from the free spot")
if "showMenu" not in hud.split("if engine.isFinished", 1)[1].split("return .none", 1)[0]:
    fail("menu must not cover a card, the journal, the bag or the map")

en = (ROOT / "Postman/Resources/en.lproj/Localizable.strings").read_text(encoding="utf-8")
ru = (ROOT / "Postman/Resources/ru.lproj/Localizable.strings").read_text(encoding="utf-8")
keys = [
    "menu.open", "menu.open.a11y", "menu.title", "menu.close",
    "menu.quest.title", "menu.quest.empty", "menu.quest.done",
    "menu.people.title", "menu.people.empty", "menu.people.a11y",
    "menu.about.title", "menu.about.body", "menu.map", "menu.bag",
    "menu.settings", "menu.language", "menu.language.system", "menu.language.ru",
    "menu.language.en", "menu.language.note", "menu.language.system.note",
    "menu.reminders", "menu.reminders.note",
    "menu.reminders.phone.allowed", "menu.reminders.phone.denied",
    "menu.reminders.phone.unknown", "menu.reminders.phone.quiet",
    "menu.reminders.openSettings", "menu.reminders.game.on", "menu.reminders.game.off",
]
for key in keys:
    if f'"{key}"' not in en or f'"{key}"' not in ru:
        fail(f"missing string {key}")
def catalog_value(text, key):
    match = re.search(rf'"{re.escape(key)}"\s*=\s*"((?:\\.|[^"\\])*)"', text)
    return match.group(1) if match else ""

for blob, label in ((en, "en"), (ru, "ru")):
    if re.search(r"chapter 3|chapter three|глав[аы] 3|APNs|remote push|пуш-сервер", blob, re.I):
        fail(f"{label} menu copy promises something the game does not have")
    hint = catalog_value(blob, "onboarding.start.hint").lower()
    if "notification" in hint or "уведомлен" in hint:
        fail(f"{label} start button still promises a notification prompt")
    notes = catalog_value(blob, "onboarding.perm.notes").lower()
    if "menu" not in notes and "меню" not in notes:
        fail(f"{label} onboarding still lists notifications as a start permission")
if "Ты — последний почтальон." not in ru:
    fail("Russian onboarding copy was rewritten")

if FAILS:
    print(f"{len(FAILS)} menu check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print(f"menu checks ok ({len(keys)} strings, cast/quest/language/reminder states)")
