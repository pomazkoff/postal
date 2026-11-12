import Foundation

/// Чистый план локальных уведомлений. Время остановки заранее неизвестно,
/// поэтому ближайшая точка ставится по темпу ходьбы, а не по календарю сюжета.
/// Если эта точка — выбор, заранее ставится сам пуш с кнопками, а не приглашение пройтись.
enum NoticePlan {
    static let minStepsPerHour = 200.0
    static let maxStepsPerHour = 6000.0
    static let fallbackStepsPerHour = 800.0
    static let minPaceWindow: TimeInterval = 15 * 60
    static let maxLead: TimeInterval = 36 * 3600
    static let minLead: TimeInterval = 60
    static let horizon = 1
    static let aheadPrefix = "ahead."
    static let immediatePrefix = "beat."
    static let dailyID = "daily.walk"
    static let dailyHour = 18

    struct Stop {
        var id: String
        var worldStep: Int
        var place: String
        var isChoice: Bool
        /// Заголовок и текст пуша выбора. Для обычной остановки пустые.
        var title: String
        var body: String
    }

    /// Тот же пуш, что поставился бы при наступлении выбора: категория и свои строки.
    struct ChoiceNotice {
        var eventID: String
        var title: String
        var body: String
    }

    struct Item {
        var id: String
        var identifier: String
        /// Форма после «До» (родительный). Пустая строка — безопасная фраза без названия.
        var genitive: String
        var after: TimeInterval
        var choice: ChoiceNotice?
    }

    /// Шагов в час по недавнему окну. Короткое или пустое окно — спокойный запасной темп.
    static func rate(steps: Int, seconds: TimeInterval) -> Double {
        guard seconds >= minPaceWindow, steps >= 0 else { return fallbackStepsPerHour }
        let perHour = Double(steps) / (seconds / 3600)
        return min(max(perHour, minStepsPerHour), maxStepsPerHour)
    }

    /// Сколько ждать, пока пройдут `distance` шагов. Не раньше минуты и не дальше полутора суток.
    static func lead(distance: Int, ratePerHour: Double) -> TimeInterval {
        let rate = min(max(ratePerHour, minStepsPerHour), maxStepsPerHour)
        let seconds = Double(max(0, distance)) / rate * 3600
        return min(max(seconds, minLead), maxLead)
    }

    /// Одна ближайшая остановка впереди. Уже отправленные пропускаются. Выбор не пропускается:
    /// если он ближайший, ставится именно он.
    static func select(stops: [Stop], currentWorldStep: Int, posted: Set<String>) -> [Stop] {
        var chosen: [Stop] = []
        for stop in stops where stop.worldStep > currentWorldStep && !posted.contains(stop.id) {
            chosen.append(stop)
            if chosen.count == horizon { break }
        }
        return chosen
    }

    static func items(stops: [Stop], currentWorldStep: Int, posted: Set<String>, ratePerHour: Double) -> [Item] {
        select(stops: stops, currentWorldStep: currentWorldStep, posted: posted).map { stop in
            let choice = stop.isChoice
                ? ChoiceNotice(eventID: stop.id, title: stop.title, body: stop.body)
                : nil
            return Item(id: stop.id,
                        identifier: aheadPrefix + stop.id,
                        genitive: stop.place,
                        after: lead(distance: stop.worldStep - currentWorldStep, ratePerHour: ratePerHour),
                        choice: choice)
        }
    }

    /// Запланированные заранее идентификаторы, которых больше нет в новом плане.
    static func staleIdentifiers(pending: [String], keeping: Set<String>) -> [String] {
        pending.filter { $0.hasPrefix(aheadPrefix) && !keeping.contains($0) }
    }

    /// Ежедневная строка в 18:00. Если сегодня уже ходили или открывали игру до 18:00, сегодняшний слот не ставим.
    /// После 18:00 повтор остаётся, чтобы завтрашняя строка не пропала вместе с сегодняшней.
    static func dailyShouldSchedule(remindersOn: Bool, walkedToday: Bool, openedToday: Bool, hour: Int, minute: Int) -> Bool {
        guard remindersOn else { return false }
        let pastSlot = hour > dailyHour || (hour == dailyHour && minute > 0)
        if walkedToday || openedToday { return pastSlot }
        return true
    }
}

/// День, когда игру открывали на экране. Нужен, чтобы не звать гулять того, кто уже заходил.
enum ForegroundDay {
    static let key = "postman.lastForegroundDay"

    static func noteOpened(_ date: Date = Date()) {
        UserDefaults.standard.set(Calendar.current.startOfDay(for: date), forKey: key)
    }

    static func openedToday(_ date: Date = Date()) -> Bool {
        guard let day = UserDefaults.standard.object(forKey: key) as? Date else { return false }
        return Calendar.current.isDate(day, inSameDayAs: date)
    }
}

/// HealthKit отказал, потому что телефон был заблокирован. Дочитать, когда данные снова доступны.
enum ProtectedCatchUp {
    static let key = "postman.steps.catchUpPending"

    static var pending: Bool { UserDefaults.standard.bool(forKey: key) }

    static func mark() { UserDefaults.standard.set(true, forKey: key) }

    static func clear() { UserDefaults.standard.set(false, forKey: key) }
}
