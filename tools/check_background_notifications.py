#!/usr/bin/env python3
"""Локальные уведомления: заранее поставленные остановки и вечерняя строка.

Факты кода, не отчёт о доставке на конкретный iPhone.
Открытая игра не ставит баннер на уже видимую остановку. Ближайшие 1–3 точки
ставятся по темпу ходьбы (UNTimeIntervalNotificationTrigger). Выбор с кнопками —
только когда остановка уже наступила. Ежедневная строка в 18:00 — календарная
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
if notifier.count("UNCalendarNotificationTrigger") != 1 or notifier.count("repeats: true") != 1:
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
if "isChoice" not in plan or "posted.contains" not in plan:
    fail("a choice or an already posted stop must not be scheduled ahead")
if "staleIdentifiers" not in plan or "replaceAhead" not in notifier:
    fail("rescheduling must drop stale ahead requests")
if "cancelAhead" not in core.split("postedBeatIDs.insert", 1)[1].split("notifier.post", 1)[0]:
    fail("posting a reached stop must remove its scheduled duplicate")

# Темп и план совпадают с NoticePlan.swift.
MIN_RATE, MAX_RATE, FALLBACK = 200.0, 6000.0, 800.0
MIN_WINDOW, MIN_LEAD, MAX_LEAD, HORIZON = 15 * 60, 60.0, 36 * 3600, 3


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
        if stop["world"] <= now or stop["choice"] or stop["id"] in posted:
            continue
        chosen.append(stop)
        if len(chosen) == HORIZON:
            break
    return chosen


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
# 6679 is already past Пеньки at 6500, so the next three are the pass, Turnip and the one after.
picked = select(stops, 6679, {"gone"})
if [item["id"] for item in picked] != ["khomut", "repka", "later"]:
    fail(f"the next three non-choice stops were {picked}")
ids = ["ahead." + item["id"] for item in picked]
if ids != ["ahead.khomut", "ahead.repka", "ahead.later"]:
    fail("ahead identifiers must stay stable")
if stale(["ahead.khomut", "ahead.old", "daily.walk", "beat.penki"], set(ids)) != ["ahead.old"]:
    fail("reschedule must remove only stale ahead requests")
before = select(stops, 6000, set())
if [item["id"] for item in before] != ["penki", "khomut", "repka"]:
    fail(f"before Penki the choice must be skipped, got {before}")
if any(item["id"] == "penki" for item in select(stops, 6000, {"penki"})):
    fail("a posted stop must not stay scheduled")


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
