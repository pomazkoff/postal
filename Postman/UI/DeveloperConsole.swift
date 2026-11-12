import SwiftUI
import UIKit

/// Скрытый вход: удержание часов дольше короткого сброса истории.
enum DeveloperHold {
    static let seconds: Double = 10
}

/// Коммит, на котором собрана эта копия исходников. Номер билда берётся из бандла.
enum DeveloperStamp {
    static let sha = "ede7cfdcca75b9153c5e271cef17b362baafb8e6"
}

/// Тап, короткое долгое нажатие и удержание 10 с на одной зоне. Короткое срабатывает на 3-й секунде, как раньше.
struct WatchHoldTarget: UIViewRepresentable {
    var onTap: () -> Void
    var onShortHold: () -> Void
    var onLongHold: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onTap: onTap, onShortHold: onShortHold, onLongHold: onLongHold)
    }

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tap))
        let hold = UILongPressGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.hold(_:)))
        hold.minimumPressDuration = StoryReset.holdSeconds
        hold.allowableMovement = 28
        tap.require(toFail: hold)
        view.addGestureRecognizer(tap)
        view.addGestureRecognizer(hold)
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.onTap = onTap
        context.coordinator.onShortHold = onShortHold
        context.coordinator.onLongHold = onLongHold
    }

    final class Coordinator: NSObject {
        var onTap: () -> Void
        var onShortHold: () -> Void
        var onLongHold: () -> Void
        private var timer: Timer?

        init(onTap: @escaping () -> Void, onShortHold: @escaping () -> Void, onLongHold: @escaping () -> Void) {
            self.onTap = onTap
            self.onShortHold = onShortHold
            self.onLongHold = onLongHold
        }

        @objc func tap() { onTap() }

        @objc func hold(_ gesture: UILongPressGestureRecognizer) {
            switch gesture.state {
            case .began:
                onShortHold()
                timer?.invalidate()
                let wait = max(0.1, DeveloperHold.seconds - StoryReset.holdSeconds)
                timer = Timer.scheduledTimer(withTimeInterval: wait, repeats: false) { [weak self] _ in
                    self?.onLongHold()
                }
            case .ended, .cancelled, .failed:
                timer?.invalidate()
                timer = nil
            default:
                break
            }
        }
    }
}

/// Служебная консоль. Не в стиле игры. Открывается в Release тем же жестом, что и в отладке.
struct DeveloperConsole: View {
    @EnvironmentObject private var game: GameModel
    var onClose: () -> Void

    @State private var stepText = ""
    @State private var confirmReset = false
    @State private var auth = "…"
    @State private var pending: [Notifier.PendingNote] = []

    var body: some View {
        NavigationStack {
            List {
                Section("Сейчас") {
                    row("Шаги сегодня", "\(game.steps.todaySteps)")
                    row("Всего", "\(game.steps.totalSteps)")
                    row("В главе", "\(game.chapterSteps) / \(game.chapter.lengthSteps)")
                    row("Глава", "\(game.chapter.id) · \(game.chapter.title)")
                    row("День", "\(game.developerDay)")
                    row("Версия", versionLine)
                    row("SHA", DeveloperStamp.sha)
                }
                Section("Шаги") {
                    Button("+500") { game.steps.addDebugSteps(500) }
                    Button("+5000") { game.steps.addDebugSteps(5000) }
                    HStack {
                        TextField("всего шагов", text: $stepText)
                            .keyboardType(.numberPad)
                        Button("Установить") { applySteps() }
                    }
                }
                Section("Перейти") {
                    ForEach(Array(game.world.chapters.enumerated()), id: \.element.id) { index, chapter in
                        Button("Глава \(chapter.id) · \(chapter.title)") {
                            game.developerGo(chapterIndex: index, localStep: 0)
                        }
                    }
                    ForEach(game.chapter.settlements) { place in
                        Button("\(place.name) · шаг \(place.step)") {
                            guard let index = game.world.chapters.firstIndex(where: { $0.id == game.chapter.id }) else { return }
                            game.developerGo(chapterIndex: index, localStep: place.step)
                        }
                    }
                }
                Section("Пуши") {
                    row("Напоминания", ReminderPreference.isOn ? "вкл" : "выкл")
                    row("Разрешение iOS", auth)
                    if pending.isEmpty {
                        Text("Запланированных нет")
                    } else {
                        ForEach(pending) { note in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(note.title)
                                Text("\(note.when) · \(note.id)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    Button("Обновить пуши") { Task { await reloadPushes() } }
                }
                Section("Последние события") {
                    let entries = Array(game.engine.state.log.suffix(12).reversed())
                    if entries.isEmpty {
                        Text("Журнал пуст")
                    } else {
                        ForEach(Array(entries.enumerated()), id: \.offset) { _, entry in
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(entry.step) · \(entry.kind ?? "событие")")
                                    .font(.caption)
                                Text(entry.title ?? entry.text)
                                    .lineLimit(3)
                            }
                        }
                    }
                }
                Section {
                    Button("Сбросить прогресс", role: .destructive) { confirmReset = true }
                }
            }
            .navigationTitle("Консоль")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Закрыть", action: onClose)
                }
            }
        }
        .storyResetAlert(isPresented: $confirmReset)
        .task { await reloadPushes() }
    }

    private var versionLine: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "—"
        let build = info?["CFBundleVersion"] as? String ?? "—"
        return "\(version) (\(build))"
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundStyle(.secondary).multilineTextAlignment(.trailing)
        }
    }

    private func applySteps() {
        let digits = stepText.filter(\.isNumber)
        guard let value = Int(digits) else { return }
        game.steps.setDebugTotal(value)
    }

    private func reloadPushes() async {
        let status = await AppCore.shared.notifier.authorizationStatus()
        switch status {
        case .notDetermined: auth = "не спрашивали"
        case .denied: auth = "запрещено"
        case .authorized: auth = "разрешено"
        case .provisional: auth = "временное"
        case .ephemeral: auth = "эфемерное"
        @unknown default: auth = "неизвестно"
        }
        pending = await AppCore.shared.notifier.pendingNotes()
    }
}
