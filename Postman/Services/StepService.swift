import Foundation
import UIKit
import Combine

/// Источник шагов для игры: «сегодня» и «всего с начала игры» (с полуночи дня старта, всегда ≥ «сегодня»).
/// Режимы: HealthKit (устройство) и fake (симулятор / нет HealthKit / вручную в DEBUG).
/// Debug-шаги («+500 шагов») прибавляются в обоих режимах.
@MainActor
final class StepService: ObservableObject {
    enum Mode: String, CaseIterable {
        case healthKit
        case fake

        var title: String {
            switch self {
            case .healthKit: return L10n.text("steps.mode.health")
            case .fake: return L10n.text("steps.mode.fake")
            }
        }
    }

    @Published private(set) var todaySteps: Int = 0
    @Published private(set) var totalSteps: Int = 0
    @Published private(set) var mode: Mode
    @Published private(set) var lastError: String?
    /// Шагов в час по последним четырём часам. Короткое окно даёт спокойный запасной темп.
    @Published private(set) var stepsPerHour: Double = NoticePlan.fallbackStepsPerHour
    /// true после первого успешного/неуспешного чтения — до этого totalSteps не трогает сцену.
    private(set) var hasLoaded = false

    private let store: ProgressStore
    private let health = HealthKitStepSource()
    private let pedometer = PedometerStepSource()
    private var refreshTimer: Timer?
    private var isRefreshing = false
    private var pendingRefresh = false
    /// Не принять старый HealthKit-ответ после «Сбросить историю» во время await.
    private var startGeneration = 0

    init(store: ProgressStore) {
        self.store = store
        if let raw = store.stepModeRaw, let saved = Mode(rawValue: raw) {
            mode = saved
        } else {
            mode = StepService.defaultMode
        }
        if !HealthKitStepSource.isAvailable { mode = .fake }
    }

    static var defaultMode: Mode {
        #if targetEnvironment(simulator)
        return .fake
        #else
        return HealthKitStepSource.isAvailable ? .healthKit : .fake
        #endif
    }

    var isHealthKitAvailable: Bool { HealthKitStepSource.isAvailable }

    // MARK: Permission

    func requestAuthorization() async {
        // «Движение и фитнес» — живые шаги на заблокированном телефоне. Это не второй запрос уведомлений.
        await pedometer.requestAccess()
        guard mode == .healthKit else { return }
        do {
            try await health.requestAuthorization()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    // MARK: Lifecycle

    /// Запустить обновления (вызывать после онбординга и при возврате в приложение).
    func start() {
        if mode == .healthKit {
            health.startObserving { [weak self] in
                Task { @MainActor in await self?.refresh() }
            }
        }
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
        Task { await refresh() }
    }

    /// Фоновое чтение шагов по сигналу HealthKit (см. AppCore). completion — когда всё обработано.
    func startBackgroundDelivery(onWake: @escaping (@escaping () -> Void) -> Void) {
        guard mode == .healthKit else { return }
        health.startBackgroundDelivery(onWake)
    }

    /// Сброс истории: забыть прочитанные значения — следующее чтение считается первым.
    func resetForNewStart() {
        startGeneration += 1
        hasLoaded = false
        lastError = nil
        todaySteps = 0
        totalSteps = 0
        stepsPerHour = NoticePlan.fallbackStepsPerHour
        StepLedger.clear()
        ProtectedCatchUp.clear()
    }

    func stop() {
        refreshTimer?.invalidate()
        refreshTimer = nil
        health.stopObserving()
    }

    func refresh() async {
        if isRefreshing {
            pendingRefresh = true
            return
        }
        isRefreshing = true
        repeat {
            pendingRefresh = false
            await performRefresh()
        } while pendingRefresh
        isRefreshing = false
    }

    private func performRefresh() async {
        let generation = startGeneration
        let now = Date()
        let dayStart = Calendar.current.startOfDay(for: now)
        // Игра считает шаги ЦЕЛЫМИ днями: старт = полночь дня онбординга.
        // Иначе в день старта «сегодня» (с полуночи) больше «всего» (с минуты онбординга).
        // Если игра начата сегодня, «всего» == «сегодня».
        var start = min(Calendar.current.startOfDay(for: store.gameStartDate ?? now), dayStart)
        // После «Сбросить историю» — с точной минуты сброса; «сегодня» тогда тоже не раньше старта (всего ≥ сегодня).
        var todayStart = dayStart
        if store.exactStart, let exact = store.gameStartDate {
            start = min(exact, now)
            todayStart = max(dayStart, start)
        }
        var healthToday: Int?
        var healthTotal: Int?
        var protected = false
        if mode == .healthKit {
            if !UIApplication.shared.isProtectedDataAvailable {
                protected = true
            } else {
                do {
                    healthToday = try await health.steps(from: todayStart, to: now)
                    healthTotal = try await health.steps(from: start, to: now)
                    guard generation == startGeneration else { pendingRefresh = true; return }
                    lastError = nil
                    ProtectedCatchUp.clear()
                    StepLedger.save(total: healthTotal ?? 0, at: now)
                } catch {
                    guard generation == startGeneration else { pendingRefresh = true; return }
                    lastError = error.localizedDescription
                    protected = HealthKitStepSource.isProtectedData(error)
                }
            }
        }

        var pedToday: Int?
        var pedWindow: Int?
        var pedSinceHealth: Int?
        let paceWindow = 4 * 60 * 60.0
        if PedometerStepSource.isAvailable {
            do {
                pedToday = try await pedometer.steps(from: todayStart, to: now)
                let paceStart = now.addingTimeInterval(-paceWindow)
                let paceSteps = try await pedometer.steps(from: paceStart, to: now)
                stepsPerHour = NoticePlan.rate(steps: paceSteps, seconds: paceWindow)
                if healthTotal == nil, let at = StepLedger.at {
                    pedSinceHealth = try await pedometer.steps(from: at, to: now)
                }
                let week = now.addingTimeInterval(-7 * 24 * 3600)
                if start >= week {
                    pedWindow = try await pedometer.steps(from: start, to: now)
                }
                guard generation == startGeneration else { pendingRefresh = true; return }
            } catch {
                guard generation == startGeneration else { pendingRefresh = true; return }
                if lastError == nil { lastError = error.localizedDescription }
            }
        }

        if protected { ProtectedCatchUp.mark() }
        let haveReading = healthToday != nil || pedToday != nil || healthTotal != nil || pedWindow != nil || pedSinceHealth != nil
        if mode == .healthKit && !haveReading {
            // Телефон заблокирован или оба источника молчат — не обнуляем уже известные шаги.
            if hasLoaded || UIApplication.shared.applicationState != .active || protected { return }
        }

        let previousRealToday = max(0, todaySteps - store.debugExtraToday)
        let previousRealTotal = max(0, totalSteps - store.debugExtraTotal)
        let sameDay = hasLoaded && Calendar.current.isDateInToday(StepLedger.todayStamp ?? .distantPast)
        var today = max(healthToday ?? 0, pedToday ?? 0)
        if sameDay { today = max(today, previousRealToday) }

        var total: Int
        if let healthTotal {
            total = healthTotal
        } else if let base = StepLedger.total, let since = pedSinceHealth {
            total = base + max(0, since)
        } else if let pedWindow {
            total = pedWindow
        } else {
            total = previousRealTotal
        }
        if let pedWindow { total = max(total, pedWindow) }
        if hasLoaded { total = max(total, previousRealTotal) }
        total = max(total, today)
        StepLedger.noteToday(now)

        // Debug-шаги («+500») идут и в «сегодня», и во «всего».
        // debugExtraToday обнуляется с новым днём, debugExtraTotal копится — поэтому total ≥ today и тут.
        today += store.debugExtraToday
        total += store.debugExtraTotal
        // Страховка: «всего» включает сегодняшний день, поэтому не может быть меньше «сегодня»
        // (статистика HealthKit по разным интервалам может немного расходиться из‑за дедупликации источников).
        total = max(total, today)
        hasLoaded = true
        todaySteps = today
        totalSteps = total
    }

    // MARK: Debug

    func addDebugSteps(_ n: Int) {
        store.debugExtraToday += n
        store.debugExtraTotal += n
        Task { await refresh() }
    }

    /// Поставить «всего» не ниже уже посчитанных шагов Здоровья. Лишнее пишется в debug-добавку.
    func setDebugTotal(_ target: Int) {
        let realTotal = max(0, totalSteps - store.debugExtraTotal)
        let goal = max(0, target)
        store.debugExtraTotal = max(0, goal - realTotal)
        totalSteps = realTotal + store.debugExtraTotal
        Task { await refresh() }
    }

    func setMode(_ newMode: Mode) {
        guard newMode != mode else { return }
        if newMode == .healthKit && !HealthKitStepSource.isAvailable { return }
        stop()
        mode = newMode
        store.stepModeRaw = newMode.rawValue
        if newMode == .healthKit {
            Task {
                await requestAuthorization()
                start()
            }
        } else {
            start()
        }
    }
}

/// Последнее удачное чтение «Здоровья». Пока телефон заблокирован, к нему прибавляются
/// только новые шаги Motion, а не вся история ещё раз.
enum StepLedger {
    static let totalKey = "postman.steps.healthTotal"
    static let atKey = "postman.steps.healthAt"
    static let todayKey = "postman.steps.todayStamp"

    static var total: Int? {
        guard UserDefaults.standard.object(forKey: totalKey) != nil else { return nil }
        return UserDefaults.standard.integer(forKey: totalKey)
    }

    static var at: Date? { UserDefaults.standard.object(forKey: atKey) as? Date }

    static var todayStamp: Date? { UserDefaults.standard.object(forKey: todayKey) as? Date }

    static func save(total: Int, at date: Date) {
        UserDefaults.standard.set(total, forKey: totalKey)
        UserDefaults.standard.set(date, forKey: atKey)
    }

    static func noteToday(_ date: Date) {
        UserDefaults.standard.set(Calendar.current.startOfDay(for: date), forKey: todayKey)
    }

    static func clear() {
        let defaults = UserDefaults.standard
        defaults.removeObject(forKey: totalKey)
        defaults.removeObject(forKey: atKey)
        defaults.removeObject(forKey: todayKey)
    }
}
