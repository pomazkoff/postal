import SwiftUI
import UIKit
import UserNotifications

struct MenuPerson: Identifiable {
    let id: String
    let name: String
    let text: String
    let image: UIImage?
}

/// Меню как почтовый стол: табличка, бумажные бирки разделов и один лист.
/// Мир остаётся под затемнением. Сумка и карта — те же экраны, что на HUD.
struct GameMenuView: View {
    @EnvironmentObject private var game: GameModel
    @EnvironmentObject private var engine: ChapterEngine
    @Environment(\.scenePhase) private var scenePhase

    let onClose: () -> Void
    let onMap: () -> Void
    let onBag: () -> Void

    @State private var people: [MenuPerson] = []
    @State private var auth: UNAuthorizationStatus = .notDetermined
    @State private var page: Page = .quest

    private enum Page: CaseIterable {
        case quest, people, about, settings
        var titleKey: String {
            switch self {
            case .quest: return "menu.quest.title"
            case .people: return "menu.people.title"
            case .about: return "menu.about.title"
            case .settings: return "menu.settings"
            }
        }
    }

    private var castToken: String {
        "\(AppLanguage.code)|\(game.chapterIndex)|\(game.chapterSteps)|\(engine.state.doneEvents.count)|\(engine.isFinished)"
    }

    private var remindersOn: Bool {
        ReminderSwitch.appearsOn(preferenceOn: ReminderPreference.isOn, auth: reminderAuth(auth))
    }

    var body: some View {
        FrameScreen(dim: 0.16) { m in
            let desk = deskLayout(m)
            ZStack {
                PlacedArt(name: "plaque", m: m, at: CGPoint(x: 585, y: 292), scale: 0.5) { e, f in
                    Text(L10n.text("menu.title"))
                        .font(Ink.title(92 * f))
                        .foregroundStyle(Ink.brown)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .frame(width: 420 * f)
                        .position(x: e.anchor("text").x * f, y: e.anchor("text").y * f)
                        .accessibilityAddTraits(.isHeader)
                }

                sectionTabs(m, centers: desk.centers, scale: desk.tagScale)

                paperSheet(m, scale: desk.sheetScale)
                    .position(m.point(585, Double(desk.sheetCenterY)))

                tagButton(L10n.text("menu.map"), at: CGPoint(x: 250, y: 2036), rotation: -6, m: m, action: onMap)
                tagButton(L10n.text("menu.bag"), at: CGPoint(x: 920, y: 2036), rotation: 5, m: m, action: onBag)
                ArrowButton(title: L10n.text("menu.close"), m: m, bottom: 2460, action: onClose)
            }
        }
        .onAppear { SoundPlayback.shared.effect("ui_paper_open") }
        .onDisappear { SoundPlayback.shared.effect("ui_paper_close") }
        .task(id: castToken) { people = game.menuPeople() }
        .task { await refreshAuth() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await refreshAuth() } }
        }
    }

    /// Бирки ниже таблички. Лист начинается под ними и не залезает на карту с сумкой.
    private func deskLayout(_ m: FrameMapper) -> (centers: [CGPoint], sheetCenterY: CGFloat, sheetScale: CGFloat, tagScale: CGFloat) {
        let tag = UIArt.entry("tag")
        let visible = min(MenuTabLayout.canvasWidth, m.size.width / max(m.scale, 0.01))
        var scale = MenuTabLayout.tagScale
        var tagSize = CGSize(width: tag.width * scale, height: tag.height * scale)
        let pair = 2 * tagSize.width + MenuTabLayout.gap + 2 * MenuTabLayout.margin
        if pair > visible, tagSize.width > 0 {
            scale *= (visible - MenuTabLayout.gap - 2 * MenuTabLayout.margin) / (2 * tagSize.width)
            tagSize = CGSize(width: tag.width * scale, height: tag.height * scale)
        }
        let columns = MenuTabLayout.columns(viewWidth: visible, itemWidth: tagSize.width,
                                            gap: MenuTabLayout.gap, margin: MenuTabLayout.margin)
        let plaqueBottom: CGFloat = 420
        let firstY = plaqueBottom + 16 + tagSize.height / 2
        let centers = MenuTabLayout.centers(columns: columns, tagSize: tagSize,
                                            visibleWidth: visible, firstCenterY: firstY)
        let tabsBottom = (centers.map(\.y).max() ?? firstY) + tagSize.height / 2
        let sheetScale: CGFloat = 0.58
        let sheetH = UIArt.entry("sheet").height * sheetScale
        let sheetY = min(tabsBottom + 28 + sheetH / 2, 1888)
        return (centers, sheetY, sheetScale, scale)
    }

    private func sectionTabs(_ m: FrameMapper, centers: [CGPoint], scale: CGFloat) -> some View {
        let pages = Page.allCases
        return ZStack {
            ForEach(Array(pages.enumerated()), id: \.offset) { i, item in
                let on = page == item
                Button { page = item } label: {
                    tabTag(L10n.text(item.titleKey), m: m, scale: scale)
                        .saturation(on ? 1 : 0.35)
                        .opacity(on ? 1 : 0.82)
                        .contentShape(Rectangle())
                }
                .buttonStyle(PressStyle())
                .position(m.point(Double(centers[i].x), Double(centers[i].y)))
                .accessibilityLabel(L10n.text(item.titleKey))
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }

    /// Крупная бирка: подпись может занять две строки, зона нажатия — вся бумага.
    private func tabTag(_ title: String, m: FrameMapper, scale: CGFloat) -> some View {
        ArtView(name: "tag", k: m.scale, scale: scale) { e, f in
            let w = e.value("textWidth") * f
            let top = e.anchor("line1")
            let bottom = e.anchor("line2")
            Text(title)
                .font(Ink.title(54 * f))
                .foregroundStyle(Ink.brown)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
                .frame(width: w, height: max(bottom.y - top.y + 80, 90) * f)
                .position(x: top.x * f, y: (top.y + bottom.y) / 2 * f)
        }
    }

    private func paperSheet(_ m: FrameMapper, scale: CGFloat) -> some View {
        return PaperArt(name: "sheet", k: m.scale, scale: scale) { size in
            ScrollView {
                pageBody(m)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.bottom, 8)
            }
            .frame(width: size.width, height: size.height)
        }
        .accessibilityElement(children: .contain)
    }

    @ViewBuilder
    private func pageBody(_ m: FrameMapper) -> some View {
        switch page {
        case .quest: quest(m)
        case .people: peopleSection(m)
        case .about: about(m)
        case .settings: settings(m)
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
        return VStack(alignment: .leading, spacing: m.length(18)) {
            Text(L10n.text("menu.quest.title"))
                .font(Ink.title(m.length(44)))
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
        VStack(alignment: .leading, spacing: m.length(28)) {
            Text(L10n.text("menu.people.title"))
                .font(Ink.title(m.length(44)))
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
        HStack(alignment: .top, spacing: m.length(18)) {
            if let image = person.image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .frame(width: m.length(160), height: m.length(220))
                    .accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: m.length(8)) {
                Text(person.name)
                    .font(Ink.title(m.length(36)))
                    .foregroundStyle(Ink.brown)
                if !person.text.isEmpty {
                    Text(person.text)
                        .font(Ink.font("hand", size: m.length(32)))
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
        VStack(alignment: .leading, spacing: m.length(16)) {
            Text(L10n.text("menu.about.title"))
                .font(Ink.title(m.length(44)))
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
        VStack(alignment: .leading, spacing: m.length(28)) {
            Text(L10n.text("menu.settings"))
                .font(Ink.title(m.length(44)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            language(m)
            reminders(m)
            sound(m)
        }
    }

    @State private var effectsLevel = SoundPrefs.effects
    @State private var ambienceLevel = SoundPrefs.ambience

    private func sound(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(14)) {
            Text(L10n.text("menu.sound"))
                .font(Ink.label(m.length(34)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            Text(L10n.text("menu.sound.effects"))
                .font(Ink.label(m.length(30)))
                .foregroundStyle(Ink.brown)
            soundRow(level: effectsLevel, m: m) { pick in
                effectsLevel = pick
                SoundPrefs.effects = pick
                SoundPlayback.shared.applyLevels()
            }
            Text(L10n.text("menu.sound.ambience"))
                .font(Ink.label(m.length(30)))
                .foregroundStyle(Ink.brown)
            soundRow(level: ambienceLevel, m: m) { pick in
                ambienceLevel = pick
                SoundPrefs.ambience = pick
                SoundPlayback.shared.applyLevels()
            }
            Text(L10n.text("menu.sound.note"))
                .font(Ink.font("hand", size: m.length(30)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .contain)
    }

    private func soundTitle(_ level: SoundLevel) -> String {
        switch level {
        case .silent: return L10n.text("menu.sound.silent")
        case .quiet: return L10n.text("menu.sound.quiet")
        case .mid: return L10n.text("menu.sound.mid")
        case .full: return L10n.text("menu.sound.full")
        }
    }

    private func soundRow(level: SoundLevel, m: FrameMapper, set: @escaping (SoundLevel) -> Void) -> some View {
        VStack(alignment: .leading, spacing: m.length(8)) {
            ForEach(SoundLevel.allCases, id: \.self) { item in
                let selected = level == item
                Button { set(item) } label: {
                    TagArt(line1: soundTitle(item),
                           line2: selected ? "·" : " ",
                           k: m.scale, small: true, scale: 0.92, size1: 60, size2: 32)
                        .saturation(selected ? 1 : 0.3)
                }
                .buttonStyle(PressStyle())
                .accessibilityLabel(soundTitle(item))
                .accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
    }

    private func language(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(14)) {
            Text(L10n.text("menu.language"))
                .font(Ink.label(m.length(34)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            languageTag(.system, title: L10n.text("menu.language.system"), m)
            languageTag(.ru, title: L10n.text("menu.language.ru"), m)
            languageTag(.en, title: L10n.text("menu.language.en"), m)
            Text(L10n.text("menu.language.note"))
                .font(Ink.font("hand", size: m.length(30)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
            if AppLanguage.choice == .system {
                Text(L10n.text("menu.language.system.note"))
                    .font(Ink.font("hand", size: m.length(30)))
                    .foregroundStyle(Ink.graphite)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .contain)
    }

    private func languageTag(_ choice: LanguageChoice, title: String, _ m: FrameMapper) -> some View {
        let selected = AppLanguage.choice == choice
        return Button { game.setLanguage(choice) } label: {
            TagArt(line1: title, line2: selected ? "·" : " ", k: m.scale, small: true, scale: 0.92, size1: 64, size2: 34)
                .saturation(selected ? 1 : 0.25)
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel(title)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func reminders(_ m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(14)) {
            Text(L10n.text("menu.reminders"))
                .font(Ink.label(m.length(34)))
                .foregroundStyle(Ink.brown)
                .accessibilityAddTraits(.isHeader)
            Text(L10n.text("menu.reminders.note"))
                .font(Ink.font("hand", size: m.length(30)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
            Text(wakeLine)
                .font(Ink.font("hand", size: m.length(28)))
                .foregroundStyle(Ink.graphite)
                .fixedSize(horizontal: false, vertical: true)
            Text(L10n.text(phoneStatusKey))
                .font(Ink.font("hand", size: m.length(32)))
                .foregroundStyle(Ink.pencil)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityLabel(L10n.text(phoneStatusKey))
            reminderTag(on: true, title: L10n.text("menu.reminders.game.on"), m: m)
            reminderTag(on: false, title: L10n.text("menu.reminders.game.off"), m: m)
            if auth == .denied {
                Button { openSettings() } label: {
                    Text(L10n.text("menu.reminders.openSettings"))
                        .font(Ink.title(m.length(32)))
                        .foregroundStyle(Ink.stampRed)
                        .underline()
                        .fixedSize(horizontal: false, vertical: true)
                }
                .buttonStyle(PressStyle())
                .accessibilityLabel(L10n.text("menu.reminders.openSettings"))
            }
        }
    }

    private func reminderTag(on wantOn: Bool, title: String, m: FrameMapper) -> some View {
        let selected = remindersOn == wantOn
        return Button { Task { await setReminders(wantOn) } } label: {
            TagArt(line1: title, line2: selected ? "·" : " ", k: m.scale, small: true, scale: 0.96, size1: 62, size2: 32)
                .saturation(selected ? 1 : 0.3)
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel(title)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func tagButton(_ title: String, at: CGPoint, rotation: Double, m: FrameMapper, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            TagArt(line1: title, line2: " ", k: m.scale, small: true, scale: 0.92, size1: 68, size2: 30)
                .rotationEffect(.degrees(rotation))
        }
        .buttonStyle(PressStyle())
        .position(m.point(at.x, at.y))
        .accessibilityLabel(title)
    }

    private var wakeLine: String {
        guard let note = BackgroundWakeNote.summary else { return L10n.text("menu.reminders.wake.none") }
        let time = DateFormatter.localizedString(from: note.date, dateStyle: .none, timeStyle: .short)
        return L10n.format("menu.reminders.wake.last", time, note.posted)
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
