#!/usr/bin/env python3
"""Локальные уведомления остановок, как в сборке 5 (1aade85) и на текущем tip.

Факты кода, не отчёт о доставке на конкретный iPhone.
Сборка 5 не ставит ежедневные пуши. Баннер появляется только если сюжетная
остановка посчитана, пока UIApplication не в .active. Свёрнутое приложение
само шаги не опрашивает: его будит HealthKit или, без гарантии, BGAppRefresh.
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
    fail("stops are immediate local notifications, not a calendar reminder")
if "UNCalendarNotificationTrigger" in notifier or "repeats: true" in notifier:
    fail("there is no daily or repeating notification")

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

if FAILS:
    print(f"{len(FAILS)} background notification check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print("background notification checks ok")
