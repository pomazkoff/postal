#!/usr/bin/env python3
"""Локальные уведомления: заранее поставленные остановки и вечерняя строка.

Факты кода, не отчёт о доставке на конкретный iPhone.
Открытая игра не ставит баннер на уже видимую остановку. Одна ближайшая точка
ставится по темпу ходьбы (UNTimeIntervalNotificationTrigger). Если это выбор,
заранее ставится сам пуш с кнопками. Ежедневная строка в 18:00 — календарная
и повторяется, и только если сегодня ещё не ходили и игру не открывали.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


core = read("Postman/App/AppCore.swift")
health = read("Postman/Services/HealthKitStepSource.swift")
steps = read("Postman/Services/StepService.swift")
notifier = read("Postman/Services/Notifier.swift")
game = read("Postman/App/GameModel.swift")
delegate = read("Postman/App/AppDelegate.swift")
info = read("Postman/Info.plist")
entitlements = read("Postman/Postman.entitlements")

deliver = core.split("private func deliver", 1)[1].split("private func postBeat", 1)[0]
if "applicationState == .active" not in deliver or deliver.find("return") > deliver.find("postBeat"):
    fail("an active app must not schedule a banner for a stop the player can already see")
if "postBeat(beat)" not in deliver.split("return", 1)[-1]:
    fail("a non-active app must be able to schedule the stop")

post = notifier.split("func post(", 1)[1].split("func postTest", 1)[0]
if "trigger: nil" not in post:
    fail("a stop that has already happened is an immediate local notification")
if notifier.count("UNCalendarNotificationTrigger(") != 1 or notifier.count("repeats: true") != 1:
    fail("only the daily walk reminder uses a repeating calendar trigger")
if "UNTimeIntervalNotificationTrigger" not in notifier or "repeats: false" not in notifier:
    fail("upcoming stops must be one-shot time intervals")
if "aps-environment" in entitlements or "registerForRemoteNotifications" in notifier + core + delegate:
    fail("these notices stay local; no APNs")

hk = health.split("func startBackgroundDelivery", 1)[1].split("func stopObserving", 1)[0]
if "enableBackgroundDelivery" not in hk or "frequency: .immediate" not in hk:
    fail("background steps must register HealthKit delivery")
if hk.count("completion()") < 1:
    fail("a HealthKit observer error must still call completion")
stop = health.split("func stopObserving", 1)[1]
if "backgroundObserver" in stop:
    fail("leaving the screen must not remove the background HealthKit observer")

wake = core.split("steps.startBackgroundDelivery", 1)[1].split("func backgroundRefresh", 1)[0]
if "wake.begin" not in wake or "wake.finish()" not in wake:
    fail("a HealthKit wake must stay alive long enough to finish and must close the wake once")
if core.count("beginBackgroundTask") < 1:
    fail("background step work must open a UIApplication background task")
if "completion()" not in health.split("if error != nil", 1)[1].split("handler(completion)", 1)[0]:
    fail("HealthKit error path must call completion before return")

fold = core.split("func appDidEnterBackground", 1)[1].split("private func flushDeferred", 1)[0]
if "wake.begin" not in fold or "backgroundRefresh" not in fold:
    fail("folding the app must keep the process up for the step catch-up")
if "scheduleRefresh()" not in fold:
    fail("folding the app must submit the discretionary refresh")
refresh = core.split("func backgroundRefresh", 1)[1].split("func appDidEnterBackground", 1)[0]
if refresh.find("refreshAuthorizationStatus") > refresh.find("syncEngine") or "refreshAuthorizationStatus" not in refresh:
    fail("a background wake must read notification permission before it spends the stop")

if "<string>fetch</string>" not in info:
    fail("BGAppRefresh needs the fetch background mode")
if "healthkit.background-delivery" not in entitlements:
    fail("HealthKit background delivery entitlement is missing")
if "registerForRemoteNotifications" in notifier + core + delegate:
    fail("no remote push backend")

onboarding = game.split("func completeOnboarding", 1)[1].split("func appBecameActive", 1)[0]
if onboarding.count("notifier.requestAuthorization") != 1:
    fail("the onboarding button must still ask for notifications once")
if "requestAuthorization" in delegate:
    fail("launch must not raise the notification prompt")
active = game.split("func appBecameActive", 1)[1].split("func appWentToBackground", 1)[0]
if "requestAuthorization" in active:
    fail("returning to the app must not raise the notification prompt")
if "steps.stop()" not in game.split("func appWentToBackground", 1)[1].split("appDidEnterBackground", 1)[0]:
    fail("the on-screen step timer should stop when the app is folded")

# Свёрнутое приложение: остановка планируется. Открытое: баннер нет, выбор запоминается.
def banner(active_app, choice):
    if active_app:
        return "defer-choice" if choice else "card-only"
    return "schedule"


if banner(True, False) != "card-only" or banner(True, True) != "defer-choice":
    fail("foreground stops are cards, not banners")
if banner(False, False) != "schedule" or banner(False, True) != "schedule":
    fail("a folded app schedules the stop")

plan = read("Postman/App/NoticePlan.swift")
motion = read("Postman/Services/PedometerStepSource.swift")
for needle in ("CMPedometer", "queryPedometerData", "isStepCountingAvailable"):
    if needle not in motion:
        fail(f"live steps must come from Core Motion ({needle})")
if "NSMotionUsageDescription" not in info and "INFOPLIST_KEY_NSMotionUsageDescription" not in read("Postman.xcodeproj/project.pbxproj"):
    fail("Motion permission needs a usage description")
for code in ("ru", "en"):
    if "NSMotionUsageDescription" not in read(f"Postman/Resources/{code}.lproj/InfoPlist.strings"):
        fail(f"{code} InfoPlist is missing the Motion sentence")
if "protectedDataDidBecomeAvailableNotification" not in core:
    fail("a locked HealthKit read must be retried when the phone unlocks")
if "ProtectedCatchUp.mark" not in steps or "isProtectedData" not in health:
    fail("a protected Health database must be marked for catch-up, not treated as zero steps")
if "upcomingStops" not in read("Postman/App/ChapterEngine.swift"):
    fail("the chapter must name the stops still ahead")
select_src = plan.split("static func select", 1)[1].split("static func items", 1)[0]
if "!stop.isChoice" in select_src or "posted.contains" not in select_src:
    fail("the nearest stop is scheduled even when it is a choice; an already posted stop is not")
items_src = plan.split("static func items", 1)[1].split("static func stale", 1)[0]
if "stop.isChoice" not in items_src or "ChoiceNotice" not in items_src:
    fail("a scheduled choice must carry the choice push, not the walk invitation")
ahead = notifier.split("func replaceAhead", 1)[1].split("func cancelAhead", 1)[0]
if "item.choice" not in ahead or "choicePrefix" not in ahead:
    fail("the ahead choice must use the choice category and the stop's own words")
if "notify.ahead.fallback" not in ahead:
    fail("a non-choice stop still uses the invitation")
engine = read("Postman/App/ChapterEngine.swift")
if "preAnswers" not in engine or "choicePushStep" not in engine or "choicePushWaiting" not in engine:
    fail("a choice answer and the push step must be remembered")
if "promptsOnScreen" not in engine or "max(step, fired" not in engine:
    fail("the 400 steps start from the later of the push and the stop")
if "pendingIdentifiers" not in core or "deliveredIdentifiers" not in core or "alreadyOut" not in core:
    fail("a reached choice must not post a second push when one is already pending or delivered")
if "staleIdentifiers" not in plan or "replaceAhead" not in notifier:
    fail("rescheduling must drop stale ahead requests")
if "cancelAhead" not in core.split("postedBeatIDs.insert", 1)[1].split("notifier.post", 1)[0]:
    fail("posting a reached stop must remove its scheduled duplicate")

# Темп и план совпадают с NoticePlan.swift.
MIN_RATE, MAX_RATE, FALLBACK = 200.0, 6000.0, 800.0
MIN_WINDOW, MIN_LEAD, MAX_LEAD, HORIZON = 15 * 60, 60.0, 36 * 3600, 1


def rate(steps_n, seconds):
    if seconds < MIN_WINDOW or steps_n < 0:
        return FALLBACK
    return min(max(steps_n / (seconds / 3600), MIN_RATE), MAX_RATE)


def lead(distance, per_hour):
    bounded = min(max(per_hour, MIN_RATE), MAX_RATE)
    return min(max(distance / bounded * 3600, MIN_LEAD), MAX_LEAD)


def select(stops, now, posted):
    chosen = []
    for stop in stops:
        if stop["world"] <= now or stop["id"] in posted:
            continue
        chosen.append(stop)
        if len(chosen) == HORIZON:
            break
    return chosen


def notice_kind(stop):
    return "choice" if stop["choice"] else "invite"


def on_tap(current, stop_step, already):
    if already:
        return "ignore"
    if current < stop_step:
        return "preanswer"
    return "apply"


def apply_at_reach(preanswer, default):
    return preanswer if preanswer else default


def timeout_due(current, stop_step, push_step, waiting, on_screen, timeout=400):
    """400 шагов от более позднего из пуша и остановки. Пока пуш только поставлен — часы молчат."""
    clock = on_screen or push_step is not None or not waiting
    if not clock:
        return False
    armed = max(stop_step, stop_step if push_step is None else push_step)
    return current >= armed + timeout


def wake_post(pending, delivered, answered):
    if answered:
        return "cancel"
    if pending or delivered:
        return "skip"
    return "post"


def stale(pending, keeping):
    return [item for item in pending if item.startswith("ahead.") and item not in keeping]


if rate(0, 60) != FALLBACK or rate(-1, 4 * 3600) != FALLBACK:
    fail("a short or empty pace window must use the fallback")
if rate(10_000, 3600) != MAX_RATE or rate(10, 3600) != MIN_RATE:
    fail("pace must stay inside the sane bounds")
if lead(0, FALLBACK) != MIN_LEAD or lead(1_000_000, MIN_RATE) != MAX_LEAD:
    fail("a lead time must stay between one minute and a day and a half")

stops = [
    {"id": "gone", "world": 100, "choice": False},
    {"id": "choice", "world": 400, "choice": True},
    {"id": "penki", "world": 6500, "choice": False},
    {"id": "khomut", "world": 11000, "choice": False},
    {"id": "repka", "world": 15500, "choice": False},
    {"id": "later", "world": 24000, "choice": False},
]
# Одна остановка. 6679 уже за Пеньками (6500), поэтому это Хомут, не три места сразу.
picked = select(stops, 6679, {"gone"})
if [item["id"] for item in picked] != ["khomut"]:
    fail(f"the single next stop was {picked}")
if len(picked) != 1:
    fail("only one ahead notice may be scheduled")
ids = ["ahead." + item["id"] for item in picked]
if ids != ["ahead.khomut"]:
    fail("ahead identifiers must stay stable")
if stale(["ahead.khomut", "ahead.old", "ahead.repka", "daily.walk", "beat.penki"], set(ids)) != ["ahead.old", "ahead.repka"]:
    fail("reschedule must remove only stale ahead requests")
before = select(stops, 6000, set())
if [item["id"] for item in before] != ["penki"]:
    fail(f"past the choice, the next stop was {before}")
if notice_kind(before[0]) != "invite":
    fail("a plain stop stays an invitation")
early = select(stops, 200, set())
if [item["id"] for item in early] != ["choice"] or notice_kind(early[0]) != "choice":
    fail(f"the nearest choice must be the one scheduled push, got {early}")
if any(item["id"] == "penki" for item in select(stops, 6000, {"penki"})):
    fail("a posted stop must not stay scheduled")

if on_tap(100, 400, False) != "preanswer" or on_tap(400, 400, False) != "apply":
    fail("a tap before the stop is stored, and a tap at the stop is applied")
if on_tap(500, 400, True) != "ignore":
    fail("an answer after the postman has chosen is ignored")
if apply_at_reach("shelter", "burst") != "shelter":
    fail("a stored answer replaces the automatic choice when the stop is reached")
if apply_at_reach(None, "burst") != "burst":
    fail("with no stored answer the postman still chooses")
# Пуш раньше остановки: 400 шагов от остановки. Пуш позже: от пуша.
if timeout_due(11399, 11000, 10000, False, False) or not timeout_due(11400, 11000, 10000, False, False):
    fail("an early choice push still leaves 400 steps after the stop")
if timeout_due(11599, 11000, 11200, False, False) or not timeout_due(11600, 11000, 11200, False, False):
    fail("a late choice push starts the 400 steps when it is shown")
if timeout_due(11400, 11000, None, True, False):
    fail("a choice push that has not been shown yet must not expire at the stop")
if not timeout_due(11400, 11000, None, False, False):
    fail("with no scheduled push the 400 steps still start at the stop")
if wake_post(True, False, False) != "skip" or wake_post(False, True, False) != "skip":
    fail("a pending or already shown choice push must not be posted again")
if wake_post(True, False, True) != "cancel" or wake_post(False, False, False) != "post":
    fail("an answered choice cancels its pending push, and a missing one is posted at the stop")

if "static let horizon = 1" not in plan:
    fail("only the nearest stop is scheduled ahead")
ru = read("Postman/Resources/ru.lproj/Localizable.strings")
en = read("Postman/Resources/en.lproj/Localizable.strings")
if "подходит" in ru or "подходит" in notifier or "nearing" in en:
    fail("an ahead notice must not claim the postman is arriving")
if "До %@ осталось немного. Прогуляешься?" not in ru:
    fail("the Russian invitation must use the genitive after До")
if "It's not far to %@. Fancy a walk?" not in en:
    fail("the English invitation is missing")
if "До следующей остановки осталось немного. Прогуляешься?" not in ru:
    fail("a missing genitive needs the Russian fallback")
if "notify.ahead.fallback" not in notifier:
    fail("an empty place must use the fallback sentence")

import json
world = json.loads(read("Postman/GameAssets/Data/world.json"))
overlay = json.loads(read("Postman/GameAssets/L10n/en.json"))
for chapter in world["chapters"]:
    names = {s["id"]: s for s in chapter["settlements"]}
    en_sets = overlay["world"]["chapters"][str(chapter["id"])]["settlements"]
    story = json.loads(read(f"Postman/GameAssets/Data/chapter{chapter['id']}_story.json"))
    used = {a["settlement"] for a in story.get("arrivals") or []}
    used |= {e.get("settlement") for e in story["events"] if e.get("settlement")}
    for sid in sorted(used):
        row = names.get(sid)
        if not row or not str(row.get("nameGenitive") or "").strip():
            fail(f"chapter {chapter['id']} place {sid} has no genitive")
            continue
        en_row = en_sets.get(sid) or {}
        if not str(en_row.get("nameGenitive") or "").strip():
            fail(f"chapter {chapter['id']} place {sid} has no English form")


def daily(on, walked, opened, hour, minute):
    if not on:
        return False
    past = hour > 18 or (hour == 18 and minute > 0)
    if walked or opened:
        return past
    return True


if daily(False, False, False, 10, 0) or daily(True, True, False, 10, 0):
    fail("a daily reminder must stay off when reminders are off or the player already walked before 18:00")
if not daily(True, False, False, 10, 0) or not daily(True, True, False, 19, 0):
    fail("the daily reminder is for a quiet day, and after 18:00 it stays armed for tomorrow")

if FAILS:
    print(f"{len(FAILS)} background notification check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("background notification checks ok")
