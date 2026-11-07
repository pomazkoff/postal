import Foundation

/// Правила меню, которые можно сверить без симулятора (tools/check_game_menu.py).
/// Язык и напоминания здесь только решают, что записать и что показать. Системное
/// разрешение на уведомления отсюда не меняется.

enum LanguageChoice: String, CaseIterable {
    case system
    case ru
    case en
}

enum LanguageResolution {
    /// system: русский телефон остаётся русским, любой другой язык — английский.
    static func code(choice: LanguageChoice, systemPrefersRussian: Bool) -> String {
        switch choice {
        case .ru: return "ru"
        case .en: return "en"
        case .system: return systemPrefersRussian ? "ru" : "en"
        }
    }
}

enum PluralRules {
    /// Те же категории, что в Localizable.stringsdict (у нуля своя строка).
    static func category(_ n: Int, russian: Bool) -> String {
        if n == 0 { return "zero" }
        if russian {
            let n = abs(n)
            let mod10 = n % 10
            let mod100 = n % 100
            if mod10 == 1 && mod100 != 11 { return "one" }
            if (2...4).contains(mod10) && !(12...14).contains(mod100) { return "few" }
            return "many"
        }
        return n == 1 ? "one" : "other"
    }
}

enum MetPeople {
    struct EventRef {
        let id: String
        let resident: String?
        let companion: String?
    }

    /// Сколько шагов главы уже пройдено. Будущая глава — ноль, прошлая — вся длина.
    static func reached(index: Int, active: Int, activeSteps: Int, length: Int) -> Int {
        if index < active { return length }
        if index > active { return 0 }
        return max(0, min(length, activeSteps))
    }

    /// Кого уже можно показать. Пустой прогресс никого не открывает.
    /// Событие даёт resident и companion. Житель на обочине — только если почтальон
    /// уже дошёл до его шага. А.Л. стоит за пределом главы и сюда не попадает.
    static func ids(events: [EventRef], done: Set<String>,
                     residents: [(id: String, step: Int)], reached: Int) -> [String] {
        var seen: [String] = []
        func add(_ id: String?) {
            guard let id, !id.isEmpty, !seen.contains(id) else { return }
            seen.append(id)
        }
        for event in events where done.contains(event.id) {
            add(event.resident)
            add(event.companion)
        }
        for resident in residents.sorted(by: { $0.step < $1.step }) where resident.step > 0 && resident.step <= reached {
            add(resident.id)
        }
        return seen
    }
}

enum QuestLine {
    enum Kind: String { case active, empty, finished }

    static func kind(finished: Bool, telegram: String?) -> Kind {
        if finished { return .finished }
        if let telegram, !telegram.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return .active
        }
        return .empty
    }
}

enum ReminderSwitch {
    enum Auth: String { case notDetermined, denied, allowed }
    /// setOn ничего не ставит в центр уведомлений. setOff снимает только ожидающие.
    /// request — первый явный запрос. openSettings — система уже отказала, разрешение не подделываем.
    enum Effect: String { case setOn, setOffCancelPending, request, openSettings }

    static func apply(wantOn: Bool, auth: Auth) -> Effect {
        if !wantOn { return .setOffCancelPending }
        switch auth {
        case .notDetermined: return .request
        case .denied: return .openSettings
        case .allowed: return .setOn
        }
    }

    /// Включённым выглядит только когда игрок этого хочет и телефон действительно разрешил.
    static func appearsOn(preferenceOn: Bool, auth: Auth) -> Bool {
        preferenceOn && auth == .allowed
    }
}

/// Хочет ли игра сама ставить остановки. Выключение не трогает системное разрешение.
/// Системный запрос отсюда не уходит: его вызывает только явное включение в меню.
enum ReminderPreference {
    static let key = "postman.remindersEnabled"

    static var isOn: Bool {
        if UserDefaults.standard.object(forKey: key) == nil { return true }
        return UserDefaults.standard.bool(forKey: key)
    }

    static func setOn(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: key)
    }

    /// Ставить локальное уведомление.
    /// Явный «выкл» — никогда. Явный «вкл» — только когда iOS уже разрешила.
    /// Ключа ещё нет: ставим, если телефон уже разрешил или статус ещё не прочитан
    /// (так уже разрешившие не теряют остановку до чтения настроек).
    /// Прочитанный «не спрашивали» и «запрещено» без явного включения — не ставим и не спрашиваем.
    static func allowsPosting(known: ReminderSwitch.Auth?) -> Bool {
        if UserDefaults.standard.object(forKey: key) != nil {
            guard UserDefaults.standard.bool(forKey: key) else { return false }
            return known == .allowed
        }
        if let known { return known == .allowed }
        return true
    }
}
