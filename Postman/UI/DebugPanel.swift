#if DEBUG
import SwiftUI

/// Кнопки отладки (только DEBUG-сборка): +500 шагов, режим источника, сброс.
struct DebugPanel: View {
    @EnvironmentObject private var game: GameModel
    @State private var showMenu = false
    @State private var confirmReset = false

    private var debugMessage: String {
        var text = L10n.format("debug.status", game.chapterIndex + 1, game.chapter.title, game.steps.todaySteps, game.steps.totalSteps)
        if let error = game.steps.lastError { text += "\n" + L10n.format("debug.error", error) }
        return text
    }

    private static var hourShift: String {
        let h = Int(AmbientLayer.debugHourOffset)
        return h == 0 ? L10n.text("debug.hour.clock") : L10n.format("debug.hour.shift", h)
    }

    private static var weatherTitle: String {
        if let o = WeatherService.debugOverride { return o.title }
        return L10n.format("debug.weather.auto", WeatherService.shared.current.title, WeatherService.shared.sourceTitle)
    }

    var body: some View {
        VStack(spacing: 6) {
            Button(L10n.text("debug.plus500")) { game.steps.addDebugSteps(500) }
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
        .confirmationDialog(L10n.text("debug.menu"), isPresented: $showMenu, titleVisibility: .visible) {
            Button(L10n.text("debug.plus5000")) { game.steps.addDebugSteps(5000) }
            Button(L10n.format("debug.time", Self.hourShift)) {
                AmbientLayer.debugHourOffset = (AmbientLayer.debugHourOffset + 3).truncatingRemainder(dividingBy: 24)
                game.scene.ambient?.refreshTimeOfDay()
            }
            Button(L10n.format("debug.weather", Self.weatherTitle)) {
                let order: [Weather?] = [nil] + Weather.allCases.map { Optional($0) }
                let i = order.firstIndex(where: { $0 == WeatherService.debugOverride }) ?? 0
                WeatherService.debugOverride = order[(i + 1) % order.count]
                game.scene.weather?.refresh()
            }
            Button(L10n.format("debug.read", Readability.enabled ? L10n.text("debug.read.on") : L10n.text("debug.read.off"))) {
                Readability.enabled.toggle()
                game.scene.applyReadability()
            }
            Button(L10n.format("debug.choice", game.engine.choiceMode.title)) {
                let all = ChapterEngine.ChoiceMode.allCases
                let i = all.firstIndex(of: game.engine.choiceMode) ?? 0
                game.engine.choiceMode = all[(i + 1) % all.count]
                AppCore.shared.syncEngine(total: game.steps.totalSteps)
            }
            ForEach(StepService.Mode.allCases, id: \.self) { mode in
                Button(L10n.format("debug.source", mode.title)) { game.steps.setMode(mode) }
            }
            Button(L10n.text("debug.push")) { AppCore.shared.postTestNotification() }
            Button(game.progress.forceChapterIndex != nil ? L10n.text("debug.force.on") : L10n.text("debug.force.off")) {
                if game.progress.forceChapterIndex != nil {
                    AppCore.shared.debugClearChapterForce()
                } else {
                    AppCore.shared.debugForceChapter2()
                }
                game.refreshChapterProgress()
                game.objectWillChange.send()
            }
            Button(L10n.text("debug.reset"), role: .destructive) { confirmReset = true }
            Button(L10n.text("debug.cancel"), role: .cancel) {}
        } message: {
            Text(debugMessage)
        }
        .storyResetAlert(isPresented: $confirmReset)
    }
}
#endif
