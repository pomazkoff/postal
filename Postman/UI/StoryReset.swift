import SwiftUI

/// Подтверждение «Сбросить историю» (для тестов). Вызывается из DEBUG-панели и скрытым жестом —
/// долгим нажатием 3 с на часах (HUD) или на табличке «Долина» на карте; работает и в Release/TestFlight.
struct StoryResetAlert: ViewModifier {
    @EnvironmentObject private var game: GameModel
    @Binding var isPresented: Bool

    func body(content: Content) -> some View {
        content.alert(L10n.text("reset.title"), isPresented: $isPresented) {
            Button(L10n.text("reset.confirm"), role: .destructive) { game.resetStory() }
            Button(L10n.text("reset.cancel"), role: .cancel) {}
        } message: {
            Text(L10n.text("reset.message"))
        }
    }
}

extension View {
    func storyResetAlert(isPresented: Binding<Bool>) -> some View {
        modifier(StoryResetAlert(isPresented: isPresented))
    }
}

enum StoryReset {
    /// Длительность скрытого долгого нажатия.
    static let holdSeconds: Double = 3
}
