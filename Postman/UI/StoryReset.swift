import SwiftUI

/// Подтверждение «Сбросить историю» (для тестов). Вызывается из DEBUG-панели и скрытым жестом —
/// долгим нажатием 3 с на часах (HUD) или на табличке «Долина» на карте; работает и в Release/TestFlight.
struct StoryResetAlert: ViewModifier {
    @EnvironmentObject private var game: GameModel
    @Binding var isPresented: Bool

    func body(content: Content) -> some View {
        content.alert("Сбросить историю?", isPresented: $isPresented) {
            Button("Сбросить", role: .destructive) { game.resetStory() }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text("Письма, выборы, события и журнал начнутся заново. Шаги будут считаться с этой минуты, уведомления удалятся. Снова откроется обучение.")
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
