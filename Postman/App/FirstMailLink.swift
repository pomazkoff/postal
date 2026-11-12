import Foundation

/// Единственный вход из карточки ивента. Не двигает шаги, сумку и камеру.
enum FirstMailLink {
    static let scheme = "mazkofpostman"
    static let host = "first-mail"
    /// Стабильный адрес. Другой host или путь не открывает экран.
    static let exactURL = "mazkofpostman://first-mail"

    static func route(from url: URL) -> Bool {
        guard url.scheme?.lowercased() == scheme else { return false }
        guard url.host?.lowercased() == host else { return false }
        return url.path.isEmpty || url.path == "/"
    }
}

/// Что честно сказать про письмо l1, ничего в сохранении не меняя.
enum FirstMailReading: Equatable {
    /// В сумке. Вручение записано на шаге 2900, экран его не отмечает.
    case inBag
    /// На полке Почты. В сумку отсюда не кладётся.
    case atPost
    /// Кузьма уже получил.
    case delivered
    /// Остановка уже прошла без письма, или статус не ведёт к этой доставке.
    case unreachable

    static func classify(status: ItemStatus, deliveryDone: Bool) -> FirstMailReading {
        if status == .delivered { return .delivered }
        if deliveryDone { return .unreachable }
        if status == .inBag { return .inBag }
        if status == .atPost { return .atPost }
        return .unreachable
    }
}

/// Карточка ждёт заставку и уже пройденный онбординг. Разрешений сама не просит.
enum FirstMailGate {
    static func shouldShow(splashDone: Bool, onboardingDone: Bool, pending: Bool) -> Bool {
        splashDone && onboardingDone && pending
    }
}

/// URL, пришедший до создания сцены. Только флаг, не сюжет.
enum FirstMailInbox {
    static var pending = false

    static func note(_ url: URL) {
        guard FirstMailLink.route(from: url) else { return }
        pending = true
    }
}
