#if DEBUG
import SwiftUI

/// Кнопки отладки (только DEBUG-сборка): +500 шагов, режим источника, сброс.
struct DebugPanel: View {
    @EnvironmentObject private var game: GameModel
    @State private var showMenu = false
    @State private var confirmReset = false

    private var debugMessage: String {
        var text = "Гл.\(game.chapterIndex+1) \(game.chapter.title)\nСегодня \(game.steps.todaySteps), всего \(game.steps.totalSteps)"
        if let error = game.steps.lastError { text += "\nОшибка: \(error)" }
        return text
    }

    private static var hourShift: String {
        let h = Int(AmbientLayer.debugHourOffset)
        return h == 0 ? "по часам" : "+\(h) ч"
    }

    private static var weatherTitle: String {
        if let o = WeatherService.debugOverride { return o.title }
        return "авто (\(WeatherService.shared.current.title), \(WeatherService.shared.sourceTitle))"
    }

    var body: some View {
        VStack(spacing: 6) {
            Button("+500 шагов") { game.steps.addDebugSteps(500) }
                .font(.system(size: 14, weight: .bold, design: .rounded))
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.black.opacity(0.6), in: Capsule())
                .foregroundStyle(.white)
            Button {
                showMenu = true
            } label: {
                Text("debug · \(game.steps.mode.title)")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.8))
            }
        }
        .confirmationDialog("Отладка", isPresented: $showMenu, titleVisibility: .visible) {
            Button("+5 000 шагов") { game.steps.addDebugSteps(5000) }
            Button("Время суток +3 ч (сейчас \(Self.hourShift))") {
                AmbientLayer.debugHourOffset = (AmbientLayer.debugHourOffset + 3).truncatingRemainder(dividingBy: 24)
                game.scene.ambient?.refreshTimeOfDay()
            }
            Button("Погода: \(Self.weatherTitle) → дальше") {
                let order: [Weather?] = [nil] + Weather.allCases.map { Optional($0) }
                let i = order.firstIndex(where: { $0 == WeatherService.debugOverride }) ?? 0
                WeatherService.debugOverride = order[(i + 1) % order.count]
                game.scene.weather?.refresh()
            }
            Button("Читаемость героев: \(Readability.enabled ? "вкл" : "выкл") → переключить") {
                Readability.enabled.toggle()
                game.scene.applyReadability()
            }
            Button("Выборы без игрока: \(game.engine.choiceMode.title) → дальше") {
                let all = ChapterEngine.ChoiceMode.allCases
                let i = all.firstIndex(of: game.engine.choiceMode) ?? 0
                game.engine.choiceMode = all[(i + 1) % all.count]
                AppCore.shared.syncEngine(total: game.steps.totalSteps)
            }
            ForEach(StepService.Mode.allCases, id: \.self) { mode in
                Button("Источник: \(mode.title)") { game.steps.setMode(mode) }
            }
            Button("Тестовый пуш") { AppCore.shared.postTestNotification() }
            Button(game.progress.forceChapterIndex != nil ? "Глава: Горы (сброс форса)" : "Форс глава 2 «Горы»") {
                if game.progress.forceChapterIndex != nil {
                    AppCore.shared.debugClearChapterForce()
                } else {
                    AppCore.shared.debugForceChapter2()
                }
                game.refreshChapterProgress()
                game.objectWillChange.send()
            }
            Button("Сбросить историю…", role: .destructive) { confirmReset = true }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text(debugMessage)
        }
        .storyResetAlert(isPresented: $confirmReset)
    }
}
#endif
