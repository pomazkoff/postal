import SwiftUI
import UIKit
import UserNotifications

struct MenuPerson: Identifiable {
    let id: String
    let name: String
    let text: String
    let image: UIImage?
}

/// Меню дороги: поручение, уже встреченные, об игре, язык и местные напоминания.
/// Сумка и карта — те же экраны, что кнопки на HUD.
struct GameMenuView: View {
    @EnvironmentObject private var game: GameModel
    @EnvironmentObject private var engine: ChapterEngine
    @Environment(\.scenePhase) private var scenePhase

    let onClose: () -> Void
    let onMap: () -> Void
    let onBag: () -> Void

    @State private var people: [MenuPerson] = []
    @State private var auth: UNAuthorizationStatus = .notDetermined

    private var castToken: String {
        "\(AppLanguage.code)|\(game.chapterIndex)|\(game.chapterSteps)|\(engine.state.doneEvents.count)|\(engine.isFinished)"
    }

    private var remindersOn: Bool {
        ReminderSwitch.appearsOn(preferenceOn: ReminderPreference.isOn, auth: reminderAuth(auth))
    }

    var body: some View {
        FrameScreen(dim: 0.72) { m in
            ZStack {
                RoundedRectangle(cornerRadius: m.length(28), style: .continuous)
                    .fill(Theme.paper)
                    .overlay(
                        RoundedRectangle(cornerRadius: m.length(28), style: .continuous)
                            .stroke(Theme.paperEdge, lineWidth: max(1, m.length(4)))
                    )
                    .frame(width: m.length(1020), height: m.length(1860))
                    .position(m.point(585, 1240))

                ScrollView {
                    VStack(alignment: .leading, spacing: m.length(36)) {
                        Text(L10n.text("menu.title"))
                            .font(Ink.title(m.length(64)))
                            .foregroundStyle(Ink.brown)
                            .accessibilityAddTraits(.isHeader)

                        quest(m)
                        peopleSection(m)
                        about(m)
                        settings(m)
                        links(m)
                    }
                    .padding(.horizontal, m.length(36))
                    .padding(.vertical, m.length(28))
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(width: m.length(980), height: m.length(1740))
                .clipped()
                .position(m.point(585, 1240))

                ArrowButton(title: L10n.text("menu.close"), m: m, bottom: 2380, action: onClose)
            }
        }
        .task(id: castToken) { people = game.menuPeople() }
        .task { await refreshAuth() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await refreshAuth() } }
        }
    }

    private func quest(_ m: FrameMapper) -> some View {
        let kind = QuestLine.kind(finished: engine.isFinished, telegram: engine.questText)
        let body: String = {
            switch kind {
            case .active: return engine.questText ?? ""
            case .empty: return L10n.text("menu.quest.empty")
            case .finished: return L10n.text("menu.quest.done")
            }
        }()
        return VStack(alignment: .leading, spacing: m.length(12)) {
            Text(L10n.text("menu.quest.title"))
                .font(Ink.title(m.length(46)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            Text(body)
                .font(Ink.font("hand", size: m.length(40)))
                .foregroundStyle(Ink.pencil)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }

    private func peopleSection(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(22)) {
            Text(L10n.text("menu.people.title"))
                .font(Ink.title(m.length(46)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            if people.isEmpty {
                Text(L10n.text("menu.people.empty"))
                    .font(Ink.font("hand", size: m.length(40)))
                    .foregroundStyle(Ink.pencil)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                ForEach(people) { person in
                    personRow(person, m)
                }
            }
        }
    }

    private func personRow(_ person: MenuPerson, _ m: FrameMapper) -> some View {
        HStack(alignment: .top, spacing: m.length(20)) {
            if let image = person.image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .frame(width: m.length(180), height: m.length(240))
                    .accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: m.length(8)) {
                Text(person.name)
                    .font(Ink.title(m.length(40)))
                    .foregroundStyle(Ink.brown)
                if !person.text.isEmpty {
                    Text(person.text)
                        .font(Ink.font("hand", size: m.length(34)))
                        .foregroundStyle(Ink.pencil)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(person.text.isEmpty
                            ? person.name
                            : L10n.format("menu.people.a11y", person.name, person.text))
    }

    private func about(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(12)) {
            Text(L10n.text("menu.about.title"))
                .font(Ink.title(m.length(46)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            Text(L10n.text("menu.about.body"))
                .font(Ink.font("hand", size: m.length(36)))
                .foregroundStyle(Ink.pencil)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }

    private func settings(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(22)) {
            Text(L10n.text("menu.settings"))
                .font(Ink.title(m.length(46)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            language(m)
            reminders(m)
        }
    }

    private func language(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(12)) {
            Text(L10n.text("menu.language"))
                .font(Ink.label(m.length(36)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            languageButton(.system, title: L10n.text("menu.language.system"), m)
            languageButton(.ru, title: L10n.text("menu.language.ru"), m)
            languageButton(.en, title: L10n.text("menu.language.en"), m)
            Text(L10n.text("menu.language.note"))
                .font(Ink.font("hand", size: m.length(32)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
            if AppLanguage.choice == .system {
                Text(L10n.text("menu.language.system.note"))
                    .font(Ink.font("hand", size: m.length(32)))
                    .foregroundStyle(Ink.graphite)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .contain)
    }

    private func languageButton(_ choice: LanguageChoice, title: String, _ m: FrameMapper) -> some View {
        let selected = AppLanguage.choice == choice
        return Button { game.setLanguage(choice) } label: {
            HStack {
                Text(selected ? "●" : "○")
                    .font(Ink.label(m.length(32)))
                    .accessibilityHidden(true)
                Text(title)
                    .font(Ink.label(m.length(38)))
                Spacer(minLength: 0)
            }
            .foregroundStyle(Ink.brown)
            .frame(minHeight: m.length(120))
            .padding(.horizontal, m.length(18))
            .background(
                RoundedRectangle(cornerRadius: m.length(12), style: .continuous)
                    .fill(selected ? Theme.brassLight.opacity(0.55) : Color.white.opacity(0.28))
            )
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel(title)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func reminders(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(12)) {
            Text(L10n.text("menu.reminders"))
                .font(Ink.label(m.length(36)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            Text(L10n.text("menu.reminders.note"))
                .font(Ink.font("hand", size: m.length(32)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
            Text(L10n.text(phoneStatusKey))
                .font(Ink.label(m.length(34)))
                .foregroundStyle(Ink.pencil)
                .accessibilityLabel(L10n.text(phoneStatusKey))
            Toggle(isOn: Binding(
                get: { remindersOn },
                set: { want in Task { await setReminders(want) } }
            )) {
                Text(remindersOn ? L10n.text("menu.reminders.game.on") : L10n.text("menu.reminders.game.off"))
                    .font(Ink.label(m.length(34)))
                    .foregroundStyle(Ink.brown)
            }
            .tint(Theme.teal)
            .frame(minHeight: m.length(120))
            if auth == .denied {
                Button { openSettings() } label: {
                    Text(L10n.text("menu.reminders.openSettings"))
                        .font(Ink.label(m.length(36)))
                        .foregroundStyle(Ink.chalk)
                        .frame(maxWidth: .infinity, minHeight: m.length(120))
                        .background(
                            RoundedRectangle(cornerRadius: m.length(12), style: .continuous)
                                .fill(Theme.teal)
                        )
                }
                .buttonStyle(PressStyle())
                .accessibilityLabel(L10n.text("menu.reminders.openSettings"))
            }
        }
    }

    private func links(_ m: FrameMapper) -> some View {
        HStack(spacing: m.length(16)) {
            linkButton(L10n.text("menu.map"), m, action: onMap)
            linkButton(L10n.text("menu.bag"), m, action: onBag)
        }
    }

    private func linkButton(_ title: String, _ m: FrameMapper, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(Ink.title(m.length(40)))
                .foregroundStyle(Ink.brown)
                .frame(maxWidth: .infinity, minHeight: m.length(120))
                .background(
                    RoundedRectangle(cornerRadius: m.length(14), style: .continuous)
                        .stroke(Theme.paperEdge, lineWidth: max(1, m.length(3)))
                )
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel(title)
    }

    private var phoneStatusKey: String {
        switch auth {
        case .authorized, .ephemeral: return "menu.reminders.phone.allowed"
        case .provisional: return "menu.reminders.phone.quiet"
        case .denied: return "menu.reminders.phone.denied"
        case .notDetermined: return "menu.reminders.phone.unknown"
        @unknown default: return "menu.reminders.phone.unknown"
        }
    }

    private func reminderAuth(_ status: UNAuthorizationStatus) -> ReminderSwitch.Auth {
        switch status {
        case .notDetermined: return .notDetermined
        case .denied: return .denied
        case .authorized, .provisional, .ephemeral: return .allowed
        @unknown default: return .denied
        }
    }

    private func refreshAuth() async {
        auth = await AppCore.shared.notifier.authorizationStatus()
    }

    /// Включение просит разрешение только пока система его не спрашивала.
    /// Отказ открывает настройки iOS и не рисует тумблер включённым.
    /// Выключение снимает ожидающие уведомления игры и ничего не пишет в разрешение.
    private func setReminders(_ wantOn: Bool) async {
        let effect = ReminderSwitch.apply(wantOn: wantOn, auth: reminderAuth(auth))
        switch effect {
        case .setOffCancelPending:
            ReminderPreference.setOn(false)
            AppCore.shared.notifier.cancelPending()
        case .setOn:
            ReminderPreference.setOn(true)
        case .request:
            let granted = await AppCore.shared.notifier.requestAuthorization()
            ReminderPreference.setOn(granted)
            await refreshAuth()
        case .openSettings:
            openSettings()
        }
    }

    private func openSettings() {
        guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
        UIApplication.shared.open(url)
    }
}
