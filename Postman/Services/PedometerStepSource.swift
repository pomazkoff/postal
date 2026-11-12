import Foundation
import CoreMotion

/// Живые шаги, пока телефон заблокирован. HealthKit в этот момент часто молчит:
/// его данные защищены. Core Motion читается и в фоне, и на локскрине.
final class PedometerStepSource {
    static var isAvailable: Bool { CMPedometer.isStepCountingAvailable() }

    private let pedometer = CMPedometer()

    /// Системный отказ. Повторного окна отсюда нет.
    var accessDenied: Bool {
        let status = CMPedometer.authorizationStatus()
        return status == .denied || status == .restricted
    }

    /// Первый запрос показывает системное окно «Движение и фитнес», если его ещё не было.
    func requestAccess() async {
        guard Self.isAvailable else { return }
        _ = try? await steps(from: Date().addingTimeInterval(-60), to: Date())
    }

    func steps(from start: Date, to end: Date) async throws -> Int {
        let pedometer = self.pedometer
        return try await withCheckedThrowingContinuation { cont in
            pedometer.queryPedometerData(from: start, to: end) { data, error in
                if let error {
                    cont.resume(throwing: error)
                    return
                }
                cont.resume(returning: data?.numberOfSteps.intValue ?? 0)
            }
        }
    }
}
