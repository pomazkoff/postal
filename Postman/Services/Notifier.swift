import Foundation
import UIKit
import UserNotifications

/// Локальные уведомления остановок сюжета (одна строка на языке игры). Выбор — пуш с двумя кнопками
/// (категория "choice.<id события>", действия "opt.<id варианта>"); ответ уходит в AppCore.
/// Пуши ставятся сразу (trigger nil): время остановки заранее неизвестно — события считаются
/// при фоновом пробуждении (HealthKit / BGAppRefresh).
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    static let choicePrefix = "choice."
    static let optionPrefix = "opt."
    static let thread = "postman.chapter1"

    private var center: UNUserNotificationCenter { UNUserNotificationCenter.current() }

    func requestAuthorization() async -> Bool {
        (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Категории с кнопками для каждого выбора главы (регистрировать при запуске).
    func registerCategories(for story: StoryConfig) {
        var categories: Set<UNNotificationCategory> = []
        for event in story.events where event.type == .choice {
            let def = event.default ?? event.options?.first?.id
            let actions = (event.options ?? []).prefix(2).map {
                UNNotificationAction(identifier: Self.optionPrefix + $0.id,
                                     title: $0.id == def ? L10n.format("notify.ifQuiet", $0.label) : $0.label,
                                     options: [])
            }
            categories.insert(UNNotificationCategory(identifier: Self.choicePrefix + event.id,
                                                     actions: Array(actions), intentIdentifiers: [], options: []))
        }
        center.setNotificationCategories(categories)
    }

    func authorizationStatus() async -> UNAuthorizationStatus {
        await center.notificationSettings().authorizationStatus
    }

    /// Только ожидающие местные уведомления этой игры. Показанные и бейдж не трогаем,
    /// системное разрешение не меняем. Уже отправленные остановки остаются в postedBeatIDs,
    /// поэтому повторное включение их не дублирует.
    func cancelPending() {
        center.removeAllPendingNotificationRequests()
    }

    func post(title: String, body: String, id: String, choiceEventID: String?) {
        guard ReminderPreference.isOn else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.threadIdentifier = Self.thread
        if let choiceEventID {
            content.categoryIdentifier = Self.choicePrefix + choiceEventID
            content.userInfo = ["event": choiceEventID]
        }
        let request = UNNotificationRequest(identifier: "beat." + id, content: content, trigger: nil)
        center.add(request) { error in
            #if DEBUG
            if let error { print("Notifier: \(error.localizedDescription)") }
            #endif
        }
    }

    /// DEBUG: проверить, что разрешение и баннер реально работают (видно и при открытой игре).
    func postTest() {
        guard ReminderPreference.isOn else { return }
        let content = UNMutableNotificationContent()
        content.title = L10n.text("notify.test.title")
        content.body = L10n.text("notify.test.body")
        content.sound = .default
        content.threadIdentifier = Self.thread
        content.userInfo = ["test": true]
        let request = UNNotificationRequest(identifier: "beat.test." + String(Int(Date().timeIntervalSince1970)),
                                            content: content, trigger: nil)
        center.add(request) { error in
            #if DEBUG
            if let error { print("Notifier test: \(error.localizedDescription)") }
            #endif
        }
    }

    /// Пуш выбора больше не актуален (ответили в приложении / почтальон решил сам).
    func withdraw(id: String) {
        center.removeDeliveredNotifications(withIdentifiers: ["beat." + id])
    }

    /// Сброс истории: убрать и показанные, и запланированные пуши, обнулить бейдж.
    func removeAll() {
        center.removeAllPendingNotificationRequests()
        center.removeAllDeliveredNotifications()
        center.setBadgeCount(0) { _ in }
    }

    // MARK: UNUserNotificationCenterDelegate

    /// Приложение открыто — сюжетные остановки видны карточками, баннер не дублируем.
    /// Тестовый пуш из отладки показываем всегда, иначе его не проверить на экране.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        if notification.request.content.userInfo["test"] as? Bool == true {
            completionHandler([.banner, .sound, .badge])
        } else {
            completionHandler([])
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let action = response.actionIdentifier
        let eventID = response.notification.request.content.userInfo["event"] as? String
        DispatchQueue.main.async {
            MainActor.assumeIsolated {
                if let eventID, action.hasPrefix(Self.optionPrefix) {
                    AppCore.shared.answerChoice(eventID, option: String(action.dropFirst(Self.optionPrefix.count)))
                }
            }
            completionHandler()
        }
    }
}
