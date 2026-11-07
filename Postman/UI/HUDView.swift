import SwiftUI

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
    @State private var letterID: String?
    @State private var confirmReset = false

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
        case menu
        case none
    }

    private var screen: Screen {
        if let visit = game.residentVisit,
           let card = visit.engine.state.pendingCards.first(where: { $0.id == visit.cardID }) { return .resident(card) }
        if game.journal != nil { return .journal }
        if let panel { return .panel(panel) }
        if engine.needsSorting { return .sorting }
        if let card = engine.nextCard { return .card(card) }
        if engine.isFinished && !engine.state.endCardSeen && engine.nextCard == nil { return .panel(.endCard) }
        if showMenu { return .menu }
        return .none
    }

    var body: some View {
        ZStack {
            GeometryReader { geo in
                let m = FrameMapper(size: geo.size)
                ZStack {
                    // Нижние кнопки (часть «мира»: при раскрытых часах приглушаются вместе со сценой).
                    bottomButtons(m)

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
                                        onLongPress: { confirmReset = true })
                            .transition(.asymmetric(
                                insertion: .scale(scale: 0.45, anchor: anchor(layout.expanded, m)).combined(with: .opacity),
                                removal: .opacity))
                    } else {
                        PocketWatchView(state: layout.collapsed, mapper: m,
                                        today: game.steps.todaySteps, total: game.gameSteps,
                                        expanded: false, onTap: toggleWatch,
                                        onLongPress: { confirmReset = true })
                            .transition(.opacity)
                    }
                }
                .frame(width: geo.size.width, height: geo.size.height)
            }
            .ignoresSafeArea()

            #if DEBUG
            VStack {
                Spacer()
                DebugPanel().padding(.bottom, 8)
            }
            #endif

            chapterOverlay
            if let id = letterID {
                LetterScreen(itemID: id) { closeLetter(id) }
                    .transition(.opacity)
                    .zIndex(10)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: screen)
        .animation(.easeInOut(duration: 0.25), value: letterID)
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
        case .menu:
            GameMenuView(
                onClose: { showMenu = false },
                onMap: { showMenu = false; panel = .map },
                onBag: { showMenu = false; panel = .bag }
            )
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
    }

    // MARK: Кнопки сумки и карты

    private func bottomButtons(_ m: FrameMapper) -> some View {
        let count = engine.bagItems.count + engine.pocketItems.count
        return ZStack {
            Button { openBag() } label: {
                ArtView(name: "hud_bag", k: m.scale) { e, f in
                    TagArt(line1: "\(count)", line2: Format.letters(count), k: f, small: true, scale: 0.8,
                           size1: 64, size2: 40)
                        .rotationEffect(.degrees(8))
                        .position(x: (e.body.maxX - 10) * f, y: (e.body.maxY - 30) * f)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(PressStyle())
            .pinned(size: artSize("hud_bag", m), anchor: bodyCenter("hud_bag", m), at: m.point(190, 2330))
            .accessibilityLabel(L10n.format("bag.a11y", count, Format.letters(count)))

            Button { panel = .map } label: {
                ArtView(name: "hud_map", k: m.scale)
                    .contentShape(Rectangle())
            }
            .buttonStyle(PressStyle())
            .pinned(size: artSize("hud_map", m), anchor: bodyCenter("hud_map", m), at: m.point(990, 2330))
            .accessibilityLabel(L10n.text("hud.map"))

            // Слева посредине: не на бирке, не на телеграмме, не на сумке и не на карте.
            if screen == .none {
                Button { showMenu = true } label: {
                    Text(L10n.text("menu.open"))
                        .font(Ink.title(m.length(48)))
                        .foregroundStyle(Ink.brown)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .padding(.horizontal, m.length(36))
                        .padding(.vertical, m.length(40))
                        .background(
                            RoundedRectangle(cornerRadius: m.length(12), style: .continuous)
                                .fill(Theme.paper)
                                .overlay(
                                    RoundedRectangle(cornerRadius: m.length(12), style: .continuous)
                                        .stroke(Theme.paperEdge, lineWidth: max(1, m.length(3)))
                                )
                        )
                }
                .buttonStyle(PressStyle())
                .position(m.point(168, 1480))
                .accessibilityLabel(L10n.text("menu.open.a11y"))
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

    private func toggleWatch() {
        withAnimation(.spring(response: 0.4, dampingFraction: 0.82)) {
            watchExpanded.toggle()
        }
    }
}
