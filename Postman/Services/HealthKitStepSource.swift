import Foundation
import HealthKit

/// Чтение шагов из HealthKit. Только чтение (toShare пустой).
final class HealthKitStepSource {
    private let store = HKHealthStore()
    private var observer: HKObserverQuery?
    private let stepType = HKQuantityType(.stepCount)

    static var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Телефон заблокирован: база «Здоровья» недоступна, это не ноль шагов.
    static func isProtectedData(_ error: Error) -> Bool {
        let ns = error as NSError
        return ns.domain == HKError.errorDomain && ns.code == HKError.Code.errorDatabaseInaccessible.rawValue
    }

    /// Показывает системный диалог (один раз). HealthKit НЕ сообщает, дал ли пользователь
    /// доступ на чтение: при отказе запросы просто возвращают 0.
    func requestAuthorization() async throws {
        try await store.requestAuthorization(toShare: [], read: [stepType])
    }

    /// Отказ на чтение шагов. Обычный пустой ответ — не отказ.
    func readDenied() async -> Bool {
        do {
            _ = try await steps(from: Date().addingTimeInterval(-60), to: Date())
            return false
        } catch {
            let ns = error as NSError
            guard ns.domain == HKError.errorDomain else { return false }
            return ns.code == HKError.Code.errorAuthorizationDenied.rawValue
        }
    }

    /// Было ли уже показано окно разрешений (а не «дан ли доступ»).
    func authorizationRequestStatus() async -> HKAuthorizationRequestStatus {
        await withCheckedContinuation { cont in
            store.getRequestStatusForAuthorization(toShare: [], read: [stepType]) { status, _ in
                cont.resume(returning: status)
            }
        }
    }

    /// Сумма шагов за интервал (HKStatisticsQuery .cumulativeSum убирает дубли iPhone/Watch).
    func steps(from start: Date, to end: Date) async throws -> Int {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        let type = stepType
        let store = self.store
        return try await withCheckedThrowingContinuation { cont in
            let query = HKStatisticsQuery(quantityType: type,
                                          quantitySamplePredicate: predicate,
                                          options: .cumulativeSum) { _, stats, error in
                if let error {
                    if let hk = error as? HKError, hk.code == .errorNoData {
                        cont.resume(returning: 0)
                    } else {
                        cont.resume(throwing: error)
                    }
                    return
                }
                let value = stats?.sumQuantity()?.doubleValue(for: .count()) ?? 0
                cont.resume(returning: Int(value.rounded()))
            }
            store.execute(query)
        }
    }

    /// Колбэк при появлении новых сэмплов шагов (пока приложение активно).
    func startObserving(_ onChange: @escaping () -> Void) {
        guard observer == nil else { return }
        let q = HKObserverQuery(sampleType: stepType, predicate: nil) { _, completion, _ in
            onChange()
            completion()
        }
        observer = q
        store.execute(q)
    }

    /// Фоновая доставка HealthKit: iOS будит приложение при новых шагах.
    /// Для stepCount система часто сама ограничивает до ~раза в час, но просим .immediate.
    /// Регистрировать при каждом запуске (application(_:didFinishLaunchingWithOptions:)).
    /// handler обязан вызвать completion, когда события обработаны и пуши поставлены.
    private var backgroundObserver: HKObserverQuery?

    func startBackgroundDelivery(_ handler: @escaping (@escaping () -> Void) -> Void) {
        guard Self.isAvailable, backgroundObserver == nil else { return }
        let q = HKObserverQuery(sampleType: stepType, predicate: nil) { _, completion, error in
            if error != nil {
                completion()
                return
            }
            handler(completion)
        }
        backgroundObserver = q
        store.execute(q)
        store.enableBackgroundDelivery(for: stepType, frequency: .immediate) { _, error in
            #if DEBUG
            if let error { print("HealthKit background delivery: \(error.localizedDescription)") }
            #endif
        }
    }

    func stopObserving() {
        if let observer { store.stop(observer) }
        observer = nil
    }
}
