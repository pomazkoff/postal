import Foundation

/// Вход из карточки ивента «Глава 3. Болота». Только открывает карту на месте болот.
/// Не двигает шаги, главу, сумку и сюжет. Закрытые болота остаются под дымкой.
enum SwampsLink {
    static let scheme = "mazkofpostman"
    static let host = "swamps"
    /// Стабильный адрес. Другой host или путь не открывает карту.
    static let exactURL = "mazkofpostman://swamps"

    static func route(from url: URL) -> Bool {
        guard url.scheme?.lowercased() == scheme else { return false }
        guard url.host?.lowercased() == host else { return false }
        return url.path.isEmpty || url.path == "/"
    }
}

/// Куда смотрит карта, открытая по ссылке болот. Решается только по уже пройденным шагам.
enum SwampsFocus: Equatable {
    /// Глава 3 уже открыта: камера на почтальоне в болотах.
    case hero
    /// Глава 3 ещё впереди: камера на начале болот, лист под дымкой, карточка «столько-то шагов».
    case ahead(stepsLeft: Int)

    static func resolve(globalStep: Int, swampsStart: Int = SwampPlaces.globalStart) -> SwampsFocus {
        globalStep >= swampsStart ? .hero : .ahead(stepsLeft: max(0, swampsStart - globalStep))
    }
}

/// Ссылка болот, пришедшая до создания сцены. Только флаг.
enum SwampsInbox {
    static var pending = false

    static func note(_ url: URL) {
        guard SwampsLink.route(from: url) else { return }
        pending = true
    }
}
