import SwiftUI

/// Цвета из style-guide.md §3 и макетов ui/v3–v4 (плейсхолдеры до финальной отрисовки UI).
enum Theme {
    static let paper = Color(red: 0.91, green: 0.85, blue: 0.70)      // бумага бирок/телеграммы
    static let paperEdge = Color(red: 0.62, green: 0.50, blue: 0.33)
    static let ink = Color(red: 0.20, green: 0.15, blue: 0.10)         // #322A1D-ish
    static let brassLight = Color(red: 0.86, green: 0.71, blue: 0.42)
    static let brassDark = Color(red: 0.48, green: 0.35, blue: 0.17)
    static let leather = Color(red: 0.55, green: 0.33, blue: 0.20)
    static let leatherDark = Color(red: 0.36, green: 0.21, blue: 0.12)
    static let teal = Color(red: 0.10, green: 0.33, blue: 0.38)        // #1A5460
    static let ochre = Color(red: 0.76, green: 0.56, blue: 0.24)       // #C28F3E
    static let brick = Color(red: 0.65, green: 0.33, blue: 0.17)       // #A6542C
    static let waxRed = Color(red: 0.80, green: 0.24, blue: 0.14)      // #CD3C23 (только акценты героя/печати)

    static func serif(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .serif)
    }
}

/// Бумажная бирка (как «до Звонарни / 1 760» и бирка на сумке).
struct PaperTag<Content: View>: View {
    let rotation: Double
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(Theme.paper)
                    .shadow(color: .black.opacity(0.45), radius: 4, x: 1, y: 3)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(Theme.paperEdge, lineWidth: 1.5)
            )
            .rotationEffect(.degrees(rotation))
    }
}
