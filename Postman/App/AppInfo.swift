import Foundation

enum AppInfo {
    /// Отображаемое имя берётся из Info.plist (CFBundleDisplayName ← APP_DISPLAY_NAME в Config/App.xcconfig).
    static var displayName: String {
        (Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String)
            ?? (Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String)
            ?? "Почтальон"
    }
}

enum Format {
    private static let formatter: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.numberStyle = .decimal
        f.groupingSeparator = "\u{00A0}"
        f.maximumFractionDigits = 0
        return f
    }()

    /// 21460 → «21 460»
    static func steps(_ value: Int) -> String {
        formatter.string(from: NSNumber(value: value)) ?? "\(value)"
    }

    /// 1 письмо, 2 письма, 5 писем
    static func letters(_ n: Int) -> String {
        let mod10 = n % 10, mod100 = n % 100
        if mod10 == 1 && mod100 != 11 { return "письмо" }
        if (2...4).contains(mod10) && !(12...14).contains(mod100) { return "письма" }
        return "писем"
    }
}
