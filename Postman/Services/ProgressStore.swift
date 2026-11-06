import Foundation

/// Всё, что сохраняется между запусками (UserDefaults).
final class ProgressStore {
    private let defaults: UserDefaults

    private enum Key {
        static let gameStartDate = "postman.gameStartDate"
        static let onboardingDone = "postman.onboardingDone"
        static let displayedSteps = "postman.displayedSteps"
        static let stepMode = "postman.stepMode"
        static let debugExtraTotal = "postman.debug.extraTotal"
        static let debugExtraToday = "postman.debug.extraToday"
        static let debugExtraDay = "postman.debug.extraDay"
        static let exactStart = "postman.exactStart"
        /// DEBUG/auto: nil = по шагам; 0/1 = форс главы.
        static let forceChapterIndex = "postman.forceChapterIndex"
        static let forceChapterBaseSteps = "postman.forceChapterBaseSteps"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    /// Момент начала игры: шаги считаются с него (HealthKit, сумма от этой даты до сейчас).
    var gameStartDate: Date? {
        get { defaults.object(forKey: Key.gameStartDate) as? Date }
        set { defaults.set(newValue, forKey: Key.gameStartDate) }
    }

    /// true после «Сбросить историю»: шаги считаются с точной минуты нового старта, а не с полуночи.
    var exactStart: Bool {
        get { defaults.bool(forKey: Key.exactStart) }
        set { defaults.set(newValue, forKey: Key.exactStart) }
    }

    var onboardingDone: Bool {
        get { defaults.bool(forKey: Key.onboardingDone) }
        set { defaults.set(newValue, forKey: Key.onboardingDone) }
    }

    /// Глобальные шаги позиции героя на единой ленте мира (не локальные шаги главы).
    var displayedSteps: Double {
        get { defaults.double(forKey: Key.displayedSteps) }
        set { defaults.set(newValue, forKey: Key.displayedSteps) }
    }

    var stepModeRaw: String? {
        get { defaults.string(forKey: Key.stepMode) }
        set { defaults.set(newValue, forKey: Key.stepMode) }
    }

    // MARK: Debug-шаги (кнопка «+500 шагов»)

    var debugExtraTotal: Int {
        get { defaults.integer(forKey: Key.debugExtraTotal) }
        set { defaults.set(newValue, forKey: Key.debugExtraTotal) }
    }

    /// Добавленные сегодня debug-шаги (обнуляются со сменой дня).
    var debugExtraToday: Int {
        get {
            guard let day = defaults.object(forKey: Key.debugExtraDay) as? Date,
                  Calendar.current.isDateInToday(day) else { return 0 }
            return defaults.integer(forKey: Key.debugExtraToday)
        }
        set {
            defaults.set(newValue, forKey: Key.debugExtraToday)
            defaults.set(Date(), forKey: Key.debugExtraDay)
        }
    }


    /// DEBUG: форс индекса главы (0=Долина, 1=Горы). nil — выбирать по шагам.
    var forceChapterIndex: Int? {
        get {
            guard defaults.object(forKey: Key.forceChapterIndex) != nil else { return nil }
            return defaults.integer(forKey: Key.forceChapterIndex)
        }
        set {
            if let newValue { defaults.set(newValue, forKey: Key.forceChapterIndex) }
            else { defaults.removeObject(forKey: Key.forceChapterIndex) }
        }
    }

    /// Реальный total в момент форса: от него считаются тестовые шаги главы, без накрутки total.
    var forceChapterBaseSteps: Int? {
        get {
            guard defaults.object(forKey: Key.forceChapterBaseSteps) != nil else { return nil }
            return defaults.integer(forKey: Key.forceChapterBaseSteps)
        }
        set {
            if let newValue { defaults.set(newValue, forKey: Key.forceChapterBaseSteps) }
            else { defaults.removeObject(forKey: Key.forceChapterBaseSteps) }
        }
    }

    func resetAll() {
        for k in [Key.gameStartDate, Key.onboardingDone, Key.displayedSteps, Key.stepMode,
                  Key.debugExtraTotal, Key.debugExtraToday, Key.debugExtraDay, Key.exactStart, Key.forceChapterIndex,
                  Key.forceChapterBaseSteps] {
            defaults.removeObject(forKey: k)
        }
    }

    /// «Сбросить историю»: новый старт — сейчас (шаги с этой минуты), онбординг заново.
    /// Источник шагов (HealthKit / тестовые) не трогаем.
    func resetStory(now: Date = Date()) {
        for k in [Key.onboardingDone, Key.displayedSteps,
                  Key.debugExtraTotal, Key.debugExtraToday, Key.debugExtraDay,
                  Key.forceChapterIndex, Key.forceChapterBaseSteps] {
            defaults.removeObject(forKey: k)
        }
        gameStartDate = now
        exactStart = true
    }
}
