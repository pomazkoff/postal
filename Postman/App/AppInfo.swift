import Foundation

enum AppInfo {
    /// Отображаемое имя берётся из Info.plist (CFBundleDisplayName, локали ru/en).
    static var displayName: String {
        (Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String)
            ?? (Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String)
            ?? L10n.text("app.name")
    }
}

enum Format {
    /// Русский: «21 460» с неразрывным пробелом, как раньше. Английский: «21,460».
    private static let russian: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.numberStyle = .decimal
        f.groupingSeparator = "\u{00A0}"
        f.maximumFractionDigits = 0
        return f
    }()

    private static let english: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "en_US")
        f.numberStyle = .decimal
        f.maximumFractionDigits = 0
        return f
    }()

    private static var formatter: NumberFormatter { AppLanguage.isRussian ? russian : english }

    static func steps(_ value: Int) -> String {
        formatter.string(from: NSNumber(value: value)) ?? "\(value)"
    }

    /// 0 letters, 1 letter, 2 letters. По-русски: письмо / письма / писем (0 — писем).
    static func letters(_ n: Int) -> String { L10n.plural("unit.letters", n) }

    static func stepsWord(_ n: Int) -> String { L10n.plural("unit.steps", n) }

    /// 0 chapters, 1 chapter, 2 chapters. По-русски: глав / глава / главы.
    static func chapters(_ n: Int) -> String { L10n.plural("unit.chapters", n) }

    static func slots(_ n: Int) -> String { L10n.plural("unit.slots", n) }

    static func watchToday(_ today: Int) -> String {
        if AppLanguage.isRussian { return L10n.format("watch.a11y.today", steps(today)) }
        return L10n.format("watch.a11y.today", steps(today), stepsWord(today))
    }

    static func watchExpanded(today: Int, total: Int) -> String {
        if AppLanguage.isRussian {
            return L10n.format("watch.a11y.expanded", steps(today), steps(total))
        }
        return L10n.format("watch.a11y.expanded", steps(today), stepsWord(today), steps(total), stepsWord(total))
    }
}
