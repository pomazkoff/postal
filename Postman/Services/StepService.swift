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
    /// true после первого успешного/неуспешного чтения — до этого totalSteps не трогает сцену.
    private(set) var hasLoaded = false

    private let store: ProgressStore
    private let health = HealthKitStepSource()
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
        var today = 0
        var total = 0

        if mode == .healthKit {
            do {
                today = try await health.steps(from: todayStart, to: now)
                total = try await health.steps(from: start, to: now)
                guard generation == startGeneration else { pendingRefresh = true; return }
                lastError = nil
            } catch {
                guard generation == startGeneration else { pendingRefresh = true; return }
                lastError = error.localizedDescription
                // Телефон заблокирован (данные Здоровья защищены) или сбой чтения — не «теряем» шаги:
                // оставляем прошлые значения, сюжет догонит при следующем чтении.
                if hasLoaded || UIApplication.shared.applicationState != .active { return }
            }
        }
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
