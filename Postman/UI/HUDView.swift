import SwiftUI
import UIKit

/// HUD по макету ui/v3: бирка расстояния, карманные часы, телеграмма-задание, сумка и карта —
/// всё пластилиновое, в координатах кадра 1170×2532 (как сцена, .aspectFill) — см. HUDLayout.
/// Поверх — экраны главы (сумка, письмо, карта, карточки событий, «пока вас не было», итоги).
/// Пустые области не перехватывают касания — прокрутка ленты работает «сквозь» HUD.
struct HUDView: View {
    @EnvironmentObject private var game: GameModel
    @EnvironmentObject private var engine: ChapterEngine
    @State private var watchExpanded = false
    @State private var panel: Panel?
    @State private var showMenu = false
    @State private var showHistory = false
    @State private var letterID: String?
    @State private var confirmReset = false
    @State private var showDeveloper = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private enum Panel: Equatable {
        case bag
        case map
        case endCard
    }

    private let layout = HUDLayout.shared

    /// Что показать поверх мира сейчас (по приоритету).
    private enum Screen: Equatable {
        case journal
        case panel(Panel)
        case card(StoryCard)
        case resident(StoryCard)
        case sorting
        case journey
        case menu
        case history
        case none
    }

    private var screen: Screen {
        if let visit = game.residentVisit,
           let card = visit.engine.state.pendingCards.first(where: { $0.id == visit.cardID }) { return .resident(card) }
        if game.journal != nil { return .journal }
        if let panel { return .panel(panel) }
        if engine.needsSorting { return .sorting }
        if let card = engine.nextCard { return .card(card) }
        if JourneyCard.shouldShow(chapterID: game.chapter.id, finished: engine.isFinished,
                                  hasPendingCard: false, seen: engine.hasSeenJourneyCard) {
            return .journey
        }
        if engine.isFinished && !engine.state.endCardSeen && engine.nextCard == nil { return .panel(.endCard) }
        if showMenu { return .menu }
        if showHistory { return .history }
        return .none
    }

    var body: some View {
        ZStack {
            GeometryReader { geo in
                let m = FrameMapper(size: geo.size)
                ZStack {
                    // Нижние кнопки (часть «мира»: при раскрытых часах приглушаются вместе со сценой).
                    bottomButtons(m, safeBottom: max(geo.safeAreaInsets.bottom, ScreenInsets.bottom))

                    // Приглушение мира при раскрытых часах (яркость ×0.52 по ui-v3-notes); тап — свернуть.
                    if watchExpanded {
                        Color(red: 0.02, green: 0.06, blue: 0.07)
                            .opacity(1 - HUDLayout.dim.brightness)
                            .contentShape(Rectangle())
                            .onTapGesture { toggleWatch() }
                            .transition(.opacity)
                    }

                    // «Висящий» слой: бирка расстояния (левый верх) и телеграмма (правый столб).
                    hangingLayer(m)
                        .saturation(watchExpanded ? 0.75 : 1)
                        .brightness(watchExpanded ? -(1 - HUDLayout.dim.hangingLayer) * 0.5 : 0)
                        .allowsHitTesting(false)

                    // Часы.
                    if watchExpanded {
                        PocketWatchView(state: layout.expanded, mapper: m,
                                        today: game.steps.todaySteps, total: game.gameSteps,
                                        expanded: true, onTap: toggleWatch,
                                        onLongPress: { confirmReset = true },
                                        onDeveloperHold: openDeveloper)
                            .transition(.asymmetric(
                                insertion: .scale(scale: 0.45, anchor: anchor(layout.expanded, m)).combined(with: .opacity),
                                removal: .opacity))
                    } else {
                        PocketWatchView(state: layout.collapsed, mapper: m,
                                        today: game.steps.todaySteps, total: game.gameSteps,
                                        expanded: false, onTap: toggleWatch,
                                        onLongPress: { confirmReset = true },
                                        onDeveloperHold: openDeveloper)
                            .transition(.opacity)
                    }
                }
                .frame(width: geo.size.width, height: geo.size.height)
                .blur(radius: screen == .menu ? 14 : 0)
                .allowsHitTesting(screen != .menu)
                .accessibilityHidden(screen == .menu)
            }
            .ignoresSafeArea()

            #if DEBUG
            VStack {
                Spacer()
                DebugPanel().padding(.bottom, 8)
            }
            #endif

            chapterOverlay
            if showDeveloper {
                DeveloperConsole(onClose: { showDeveloper = false })
                    .zIndex(40)
            }
            if game.showHeroCard, screen == .none {
                HeroNote {
                    game.showHeroCard = false
                }
                .transition(.opacity)
                .zIndex(8)
            }
            if let note = game.marshNote, screen == .none {
                MarshNote(title: marshLine(note, title: true), text: marshLine(note, title: false)) {
                    game.marshNote = nil
                }
                .transition(.opacity)
                .zIndex(8)
            }
            if game.showAccessNote, screen == .none {
                AccessNote(onSettings: game.openSystemSettings, onClose: game.dismissAccessNote)
                    .transition(.opacity)
                    .zIndex(8)
            }
            if let id = letterID {
                LetterScreen(itemID: id) { closeLetter(id) }
                    .transition(.opacity)
                    .zIndex(10)
            }
        }
        .animation(reduceMotion ? .none : .easeInOut(duration: 0.25), value: screen)
        .animation(.easeInOut(duration: 0.25), value: letterID)
        .onChange(of: screen) { _, new in
            game.roadMenuOpen = new == .menu
            publishWorldCover(screen: new)
            if new != .none { game.showHeroCard = false; game.marshNote = nil }
        }
        .onChange(of: letterID) { _, _ in publishWorldCover(screen: screen) }
        .onChange(of: game.showHeroCard) { _, _ in publishWorldCover(screen: screen) }
        .onChange(of: game.marshNote) { _, _ in publishWorldCover(screen: screen) }
        .onChange(of: game.showAccessNote) { _, _ in publishWorldCover(screen: screen) }
        .storyResetAlert(isPresented: $confirmReset)
    }

    // MARK: Экраны главы

    @ViewBuilder
    private var chapterOverlay: some View {
        switch screen {
        case .journal:
            if let journal = game.journal {
                JournalScreen(journal: journal) { game.dismissJournal() }
            }
        case .sorting:
            BagScreen(mode: .sort, onRead: { letterID = $0 }, onClose: {})
        case .panel(.bag):
            BagScreen(mode: .view, onRead: { letterID = $0 }, onClose: { panel = nil })
        case .panel(.map):
            MapScreen(onShowEndCard: { panel = .endCard }, onClose: { panel = nil })
        case .panel(.endCard):
            EndCardView {
                engine.markEndCardSeen()
                panel = nil
            }
        case .journey:
            JourneyCardView {
                engine.markJourneyCardSeen()
            }
        case .menu:
            GameMenuView(
                onClose: { showMenu = false; game.roadMenuOpen = false },
                onMap: { showMenu = false; game.roadMenuOpen = false; panel = .map },
                onBag: { showMenu = false; game.roadMenuOpen = false; panel = .bag }
            )
        case .history:
            HistoryScrollView {
                showHistory = false
            }
        case .card(let card):
            StoryCardView(card: card) { finishCard(card) }
                .id(card.id)
        case .resident(let card):
            if let visit = game.residentVisit {
                StoryCardView(card: card, chapter: visit.chapter) {
                    if card.kind != .choice { visit.engine.dismissCard(card.id) }
                    game.endResidentVisit()
                }
                .environmentObject(visit.engine)
                .id("resident:\(visit.chapter.id):\(card.id):\(card.kind.rawValue)")
            }
        case .none:
            EmptyView()
        }
    }

    private func finishCard(_ card: StoryCard) {
        if card.kind != .choice { engine.dismissCard(card.id) }
        if card.kind == .finale, let id = engine.story.event(card.id)?.receive {
            letterID = id
        }
    }

    private func closeLetter(_ id: String) {
        letterID = nil
        engine.finishReading(id)
    }

    // MARK: Кнопки сумки и карты

    private func bottomButtons(_ m: FrameMapper, safeBottom: CGFloat) -> some View {
        let badge = bagBadge
        return ZStack {
            Button { openBag() } label: {
                ArtView(name: "hud_bag", k: m.scale) { e, f in
                    TagArt(line1: badge.line1, line2: badge.line2, k: f, small: true, scale: 0.8,
                           size1: 64, size2: 40)
                        .rotationEffect(.degrees(8))
                        .position(x: (e.body.maxX - 10) * f, y: (e.body.maxY - 30) * f)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(PressStyle())
            .pinned(size: artSize("hud_bag", m), anchor: bodyCenter("hud_bag", m), at: m.point(190, 2330))
            .accessibilityLabel(L10n.format("bag.a11y", badge.count, badge.line2))

            Button { panel = .map } label: {
                ArtView(name: "hud_map", k: m.scale)
                    .contentShape(Rectangle())
            }
            .buttonStyle(PressStyle())
            .pinned(size: artSize("hud_map", m), anchor: bodyCenter("hud_map", m), at: m.point(990, 2330))
            .accessibilityLabel(L10n.text("hud.map"))

            if screen == .none {
                menuButton(m, safeBottom: safeBottom)
                historyButton(m, safeBottom: safeBottom)
            }

            // «К почтальону»: деревянная стрелка с головой героя у края экрана, куда он ушёл.
            // Только когда почтальон за кадром и поверх мира ничего не открыто.
            if let off = game.postmanOffscreen, screen == .none {
                postmanButton(off, m)
                    .transition(.scale(scale: 0.6).combined(with: .opacity))
            }
        }
        .frame(width: m.size.width, height: m.size.height)
        .animation(.spring(response: 0.35, dampingFraction: 0.7), value: game.postmanOffscreen)
    }

    /// Бумажная бирка по центру между сумкой и картой. Корпуса не пересекает.
    private func menuButton(_ m: FrameMapper, safeBottom: CGFloat) -> some View {
        let scale = RoadMenuButton.tagScale
        let tag = UIArt.entry("tag_small")
        let bagArt = UIArt.entry("hud_bag")
        let mapArt = UIArt.entry("hud_map")
        let bag = RoadMenuButton.imageRect(width: bagArt.width, height: bagArt.height,
                                           bodyCenter: bagArt.bodyCenter, anchor: RoadMenuButton.bagAnchor)
        let map = RoadMenuButton.imageRect(width: mapArt.width, height: mapArt.height,
                                           bodyCenter: mapArt.bodyCenter, anchor: RoadMenuButton.mapAnchor)
        let button = CGSize(width: tag.width * scale, height: tag.height * scale)
        let safeDesign = safeBottom / max(m.scale, 0.01)
        let center = RoadMenuButton.pair(bag: bag, map: map, buttonSize: button,
                                         canvasHeight: RoadMenuButton.canvasHeight, safeBottom: safeDesign).menu
        return Button {
            showMenu = true
            game.roadMenuOpen = true
        } label: {
            ArtView(name: "tag_small", k: m.scale, scale: scale) { e, f in
                let top = e.anchor("line1")
                let bottom = e.anchor("line2")
                Text(L10n.text("menu.open"))
                    .font(Ink.title(62 * f))
                    .foregroundStyle(Ink.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .frame(width: e.value("textWidth") * f)
                    .position(x: top.x * f, y: (top.y + bottom.y) / 2 * f)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PressStyle())
        .position(m.point(Double(center.x), Double(center.y)))
        .accessibilityLabel(L10n.text("menu.open.a11y"))
    }

    /// Та же бирка, что «Меню», отражена по горизонтали и стоит сразу под ней.
    private func historyButton(_ m: FrameMapper, safeBottom: CGFloat) -> some View {
        let scale = RoadMenuButton.tagScale
        let tag = UIArt.entry("tag_small")
        let bagArt = UIArt.entry("hud_bag")
        let mapArt = UIArt.entry("hud_map")
        let bag = RoadMenuButton.imageRect(width: bagArt.width, height: bagArt.height,
                                           bodyCenter: bagArt.bodyCenter, anchor: RoadMenuButton.bagAnchor)
        let map = RoadMenuButton.imageRect(width: mapArt.width, height: mapArt.height,
                                           bodyCenter: mapArt.bodyCenter, anchor: RoadMenuButton.mapAnchor)
        let button = CGSize(width: tag.width * scale, height: tag.height * scale)
        let safeDesign = safeBottom / max(m.scale, 0.01)
        let center = RoadMenuButton.pair(bag: bag, map: map, buttonSize: button,
                                         canvasHeight: RoadMenuButton.canvasHeight, safeBottom: safeDesign).history
        return Button { showHistory = true } label: {
            ArtView(name: "tag_small", k: m.scale, scale: scale, flipX: true) { e, f in
                let top = e.anchor("line1")
                let bottom = e.anchor("line2")
                // Отражается только бумага. Буквы остаются прямыми и садятся в тот же якорь на зеркале.
                let textX = e.width - top.x
                Text(L10n.text("history.open"))
                    .font(Ink.title(52 * f))
                    .foregroundStyle(Ink.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .frame(width: e.value("textWidth") * f)
                    .position(x: textX * f, y: (top.y + bottom.y) / 2 * f)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PressStyle())
        .position(m.point(Double(center.x), Double(center.y)))
        .accessibilityLabel(L10n.text("history.open.a11y"))
    }

    private func postmanButton(_ off: WorldScene.Offscreen, _ m: FrameMapper) -> some View {
        let s: CGFloat = 0.72
        let e = UIArt.entry("btn_postman")
        let size = CGSize(width: e.width * m.scale * s, height: e.height * m.scale * s)
        let left = off == .left
        let c = e.bodyCenter
        let anchor = CGPoint(x: (left ? e.width - c.x : c.x) * m.scale * s, y: c.y * m.scale * s)
        return Button { game.returnToPostman() } label: {
            ArtView(name: "btn_postman", k: m.scale, scale: s, flipX: left)
                .contentShape(Rectangle())
        }
        .buttonStyle(PressStyle())
        .pinned(size: size, anchor: anchor, at: m.point(left ? 200 : 970, 1960), rotation: left ? 3 : -3)
        .accessibilityLabel(left ? L10n.text("hud.postman.left") : L10n.text("hud.postman.right"))
    }

    /// На бирке сумки — только почта. Личные вещи не называем письмами.
    /// Если писем нет, а находки есть, считаем находки своим словом.
    private var bagBadge: (line1: String, line2: String, count: Int) {
        let mail = engine.mailItems.count
        if mail > 0 { return ("\(mail)", Format.letters(mail), mail) }
        let things = engine.personalItems.count
        if things > 0 { return ("\(things)", Format.things(things), things) }
        return ("0", Format.letters(0), 0)
    }

    private func openBag() {
        panel = .bag
    }

    private func artSize(_ name: String, _ m: FrameMapper) -> CGSize {
        let e = UIArt.entry(name)
        return CGSize(width: e.width * m.scale, height: e.height * m.scale)
    }

    private func bodyCenter(_ name: String, _ m: FrameMapper) -> CGPoint {
        let c = UIArt.entry(name).bodyCenter
        return CGPoint(x: c.x * m.scale, y: c.y * m.scale)
    }

    /// Бирка и телеграмма стоят в своих зонах макета (не пересекаются с часами ни в одном состоянии).
    private func hangingLayer(_ m: FrameMapper) -> some View {
        let tag = layout.distanceTag
        let tg = watchExpanded ? layout.telegram.expanded : layout.telegram.collapsed
        return ZStack(alignment: .topLeading) {
            DistanceTagView(settlement: game.nextSettlement, stepsLeft: game.stepsToNextSettlement,
                            donePlace: game.chapter.settlements.last?.name ?? game.chapter.title,
                            rect: tag, m: m)
            if let quest = engine.questText {
                TelegramView(text: quest, rect: tg, m: m)
            }
        }
        .frame(width: m.size.width, height: m.size.height)
    }

    /// Точка, из которой «вырастают» раскрытые часы — верх нитки.
    private func anchor(_ state: HUDLayout.WatchState, _ m: FrameMapper) -> UnitPoint {
        let p = m.point(state.body[0] + state.body[2] / 2, state.y)
        return UnitPoint(x: p.x / max(m.size.width, 1), y: p.y / max(m.size.height, 1))
    }

    private func marshLine(_ id: String, title: Bool) -> String {
        var key = "tap."
        key += "ch3."
        key += id
        if title { key += ".title" }
        return L10n.text(key)
    }

    private func publishWorldCover(screen: Screen) {
        let covered = screen != .none || letterID != nil || game.showHeroCard || game.marshNote != nil || game.showAccessNote
        if game.worldCovered != covered {
            game.worldCovered = covered
            if covered { SoundPlayback.shared.stopAll() }
        }
    }

    private func openDeveloper() {
        confirmReset = false
        showDeveloper = true
    }

    private func toggleWatch() {
        withAnimation(.spring(response: 0.4, dampingFraction: 0.82)) {
            watchExpanded.toggle()
        }
    }
}

/// После отказа в шагах или месте. Игра под бумагой уже идёт. Системный вопрос отсюда не зовётся.
struct AccessNote: View {
    let onSettings: () -> Void
    let onClose: () -> Void

    var body: some View {
        FrameScreen(dim: 0.45) { m in
            ZStack {
                Color.clear.contentShape(Rectangle()).onTapGesture(perform: onClose)
                VStack(alignment: .leading, spacing: m.length(16)) {
                    Text(L10n.text("access.denied.title"))
                        .font(Ink.title(m.length(52)))
                        .foregroundStyle(Ink.brown)
                        .accessibilityAddTraits(.isHeader)
                    Text(L10n.text("access.denied.body"))
                        .font(Ink.font("hand", size: m.length(36)))
                        .foregroundStyle(Ink.pencil)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(action: onSettings) {
                        Text(L10n.text("access.denied.settings"))
                            .font(Ink.title(m.length(36)))
                            .foregroundStyle(Ink.chalk)
                            .frame(maxWidth: .infinity, minHeight: m.length(100))
                            .background(RoundedRectangle(cornerRadius: m.length(12), style: .continuous).fill(Theme.teal))
                    }
                    .buttonStyle(PressStyle())
                    Button(action: onClose) {
                        Text(L10n.text("access.denied.close"))
                            .font(Ink.title(m.length(36)))
                            .foregroundStyle(Ink.brown)
                            .frame(maxWidth: .infinity, minHeight: m.length(88))
                    }
                    .buttonStyle(PressStyle())
                }
                .padding(m.length(28))
                .frame(width: m.length(860))
                .background(
                    RoundedRectangle(cornerRadius: m.length(22), style: .continuous)
                        .fill(Theme.paper)
                        .overlay(RoundedRectangle(cornerRadius: m.length(22), style: .continuous).stroke(Theme.paperEdge, lineWidth: max(1, m.length(3))))
                )
            }
        }
    }
}

/// Нижний отступ окна. GeometryReader под ignoresSafeArea иногда отдаёт ноль.
enum ScreenInsets {
    static var bottom: CGFloat {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        let windows = scenes.flatMap(\.windows)
        return (windows.first { $0.isKeyWindow } ?? windows.first)?.safeAreaInsets.bottom ?? 0
    }
}
