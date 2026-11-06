import UIKit
import UserNotifications

/// Точка входа для фоновых запусков: регистрирует BGAppRefresh, наблюдатель HealthKit
/// и делегат уведомлений ДО конца запуска (требование iOS), даже если сцена не создаётся.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let core = AppCore.shared
        UNUserNotificationCenter.current().delegate = core.notifier
        core.registerBackgroundTasks()
        core.startBackgroundObservation()
        return true
    }
}
