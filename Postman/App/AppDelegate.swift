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
        if let url = launchOptions?[.url] as? URL {
            FirstMailInbox.note(url)
        }
        Task { @MainActor in
            await core.notifier.refreshAuthorizationStatus()
        }
        return true
    }

    /// Тот же адрес, если система отдаёт его делегату, а не только SwiftUI.
    /// Чужой или битый URL не меняет флаг.
    func application(_ application: UIApplication,
                     open url: URL,
                     options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        guard FirstMailLink.route(from: url) else { return false }
        FirstMailInbox.note(url)
        return true
    }
}
