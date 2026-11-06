import SwiftUI

/// Бумага с репликами + житель + рука с письмом. Общая основа для карточек событий.
private struct SpeechPaper: View {
    let m: FrameMapper
    let title: String
    var subtitle: String?
    let lines: [StoryConfig.Line]
    var body_: String?

    let scale: CGFloat = 0.95
    let top: CGFloat = 120

    var body: some View {
        let e = UIArt.entry("sheet_form")
        let k = m.scale
        let center = CGPoint(x: 585, y: top + e.body.height * scale / 2)
        PaperArt(name: "sheet_form", k: k, scale: scale) { size in
            VStack(alignment: .leading, spacing: m.length(22)) {
                VStack(alignment: .leading, spacing: m.length(4)) {
                    Text(title)
                        .font(Ink.title(m.length(56)))
                        .foregroundStyle(Ink.brown)
                        .lineLimit(2).minimumScaleFactor(0.6)
                    if let subtitle {
                        Text(subtitle)
                            .font(Ink.label(m.length(32)))
                            .foregroundStyle(Ink.brown.opacity(0.6))
                    }
                }
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: m.length(20)) {
                        if let body_ {
                            Text(body_)
                                .font(Ink.label(m.length(42)))
                                .foregroundStyle(Ink.pencil)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                            VStack(alignment: .leading, spacing: m.length(2)) {
                                if !line.who.isEmpty {
                                    Text(line.who)
                                        .font(Ink.title(m.length(30)))
                                        .foregroundStyle(Ink.stampRed.opacity(0.85))
                                }
                                Text(line.who.isEmpty ? line.text : "— " + line.text)
                                    .font(Ink.label(m.length(42)))
                                    .italic(line.who.isEmpty)
                                    .foregroundStyle(Ink.pencil)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .frame(width: size.width, alignment: .leading)
                }
            }
        }
        .pinned(size: CGSize(width: e.width * k * scale, height: e.height * k * scale),
                anchor: CGPoint(x: e.bodyCenter.x * k * scale, y: e.bodyCenter.y * k * scale),
                at: m.point(center.x, center.y))
    }
}

/// Житель: фигура из residents (если уже нарисован) + табличка с именем.
private struct ResidentFigure: View {
    let resident: StoryConfig.Resident?
    let m: FrameMapper
    var assetsFolder: String? = nil
    var cx: Double = 330
    var bottom: Double = 2050
    var height: Double = 640

    var body: some View {
        ZStack {
            if let resident {
                if let fig = ResidentLibrary.figure(for: resident, assetsFolder: assetsFolder) {
                    let h = m.length(height / Double(max(0.5, fig.groundFraction)))
                    let w = h * fig.image.size.width / max(1, fig.image.size.height)
                    Image(uiImage: fig.image)
                        .resizable()
                        .interpolation(.high)
                        .frame(width: w, height: h)
                        .shadow(color: .black.opacity(0.45), radius: m.length(14), x: m.length(10), y: m.length(14))
                        .position(x: m.point(cx, 0).x, y: m.point(0, bottom).y - m.length(height) + h / 2)
                    plaque(resident.name, y: bottom + 70)
                } else {
                    plaque(resident.name, y: bottom - 160)
                }
            }
        }
        .allowsHitTesting(false)
    }

    private func plaque(_ name: String, y: Double) -> some View {
        PlacedArt(name: "plaque", m: m, at: CGPoint(x: cx, y: y), scale: 0.62, rotation: -3) { e, f in
            let t = e.anchor("text")
            Text(name)
                .font(Ink.title(64 * f))
                .foregroundStyle(Ink.chalk)
                .shadow(color: .black.opacity(0.4), radius: 0, x: 0, y: 2 * f)
                .lineLimit(1).minimumScaleFactor(0.5)
                .frame(width: e.body.width * 0.8 * f)
                .position(x: t.x * f, y: t.y * f)
        }
    }
}

/// Карточка события: вручение, подбор, сцена, выбор, финальная выемка.
struct StoryCardView: View {
    @EnvironmentObject var engine: ChapterEngine
    @EnvironmentObject var game: GameModel
    let card: StoryCard
    /// Визит к жителю другой главы: её подписи и арт, без смены активной главы.
    var chapter: ChapterConfig? = nil
    /// Закрыть (для выбора — после ответа; для финала — перейти к письму 7).
    let onDone: () -> Void

    @State var chosen: StoryConfig.Option? = nil

    var event: StoryConfig.Event? { engine.story.event(card.id) }
    private var storyChapter: ChapterConfig { chapter ?? game.chapter }
    private var placeName: String {
        storyChapter.settlements.first { $0.id == card.settlement }?.fullName ?? card.settlement
    }

    var body: some View {
        FrameScreen(dim: 0.6) { m in
            ZStack {
                switch card.kind {
                case .delivery: delivery(m)
                case .pickup: pickup(m)
                case .scene: scene(m)
                case .choice: choice(m)
                case .finale: finale(m)
                }
            }
        }
        .transition(.opacity)
    }

    // MARK: Вручение

    @ViewBuilder
    private func delivery(_ m: FrameMapper) -> some View {
        let resident = engine.story.resident(card.resident)
        SpeechPaper(m: m, title: placeName, subtitle: card.items.isEmpty ? L10n.text("card.nothing") : L10n.text("card.delivery"),
                    lines: card.lines)
        ResidentFigure(resident: resident, m: m, assetsFolder: storyChapter.assetsFolder)
        if let first = card.items.first, let item = engine.story.item(first) {
            PlacedArt(name: "hand", m: m, anchor: "bottom", at: CGPoint(x: 900, y: 2190), rotation: -8)
                .allowsHitTesting(false)
            PlacedArt(name: engine.isOpened(item.id) ? (item.artOpened ?? item.art) : item.art, m: m,
                      at: CGPoint(x: 800, y: 1690), scale: 1.25, rotation: -14)
                .allowsHitTesting(false)
            if card.items.count > 1 {
                Text(L10n.format("card.more", card.items.count - 1))
                    .font(Ink.label(m.length(36)))
                    .foregroundStyle(Ink.chalk)
                    .position(m.point(800, 1900))
            }
        }
        ArrowButton(title: L10n.text("card.next"), m: m, bottom: 2460, action: onDone)
    }

    // MARK: Подбор

    @ViewBuilder
    private func pickup(_ m: FrameMapper) -> some View {
        let got = card.items.first
        let left = card.missed.first
        SpeechPaper(m: m, title: placeName, subtitle: got != nil ? L10n.text("card.newLetter") : (left != nil ? L10n.text("card.bagFull") : nil),
                    lines: card.lines)
        if let resident = engine.story.resident(card.resident) {
            ResidentFigure(resident: resident, m: m, assetsFolder: storyChapter.assetsFolder, cx: 280)
        }
        if let id = got ?? left, let item = engine.story.item(id) {
            PlacedArt(name: item.art, m: m, at: CGPoint(x: card.resident == nil ? 585 : 820, y: 1720),
                      scale: 1.5, rotation: got != nil ? -6 : 4)
                .opacity(got != nil ? 1 : 0.55)
                .allowsHitTesting(false)
            TagArt(line1: item.to, line2: got != nil ? item.place : L10n.text("card.leftHere"), k: m.scale, scale: 0.9)
                .pinned(size: CGSize(width: UIArt.entry("tag").width * m.scale * 0.9,
                                     height: UIArt.entry("tag").height * m.scale * 0.9),
                        anchor: CGPoint(x: UIArt.entry("tag").anchor("hole").x * m.scale * 0.9,
                                        y: UIArt.entry("tag").anchor("hole").y * m.scale * 0.9),
                        at: m.point(card.resident == nil ? 420 : 660, 1990), rotation: 5)
                .allowsHitTesting(false)
        }
        ArrowButton(title: got != nil ? L10n.text("card.toBag") : L10n.text("card.next"), m: m, bottom: 2460, action: onDone)
    }

    // MARK: Сцена

    @ViewBuilder
    private func scene(_ m: FrameMapper) -> some View {
        SpeechPaper(m: m, title: card.title ?? placeName, lines: card.lines, body_: card.text)
        ResidentFigure(resident: engine.story.resident(card.resident), m: m, assetsFolder: storyChapter.assetsFolder)
        ArrowButton(title: card.id.hasPrefix("resident:") ? L10n.text("card.ok") : L10n.text("card.next"),
                    m: m, bottom: 2460, action: onDone)
    }

    // MARK: Выбор

    @ViewBuilder
    private func choice(_ m: FrameMapper) -> some View {
        SpeechPaper(m: m, title: card.title ?? placeName, subtitle: placeName,
                    lines: chosen.map { [StoryConfig.Line(who: "", text: $0.result, if: nil)] } ?? [],
                    body_: card.text)
        if let chosen {
            ArrowButton(title: L10n.text("card.next"), m: m, bottom: 2460) {
                engine.resolveChoice(card.id, option: chosen.id)
                onDone()
            }
        } else {
            let options = event?.options ?? []
            ForEach(Array(options.enumerated()), id: \.element.id) { i, option in
                optionTag(option, index: i, m: m)
            }
        }
    }

    /// Вариант «в характере» почтальона (его выберет он сам, если игрок промолчит).
    private var defaultOptionID: String? { event?.default ?? event?.options?.first?.id }

    private func optionTag(_ option: StoryConfig.Option, index: Int, m: FrameMapper) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let k = m.scale
        let at = CGPoint(x: index == 0 ? 120 : 560, y: index == 0 ? 1760 : 1960)
        let rot = index == 0 ? -5.0 : 4.0
        return ZStack {
            TagArt(line1: index == 0 ? "← \(option.label)" : "\(option.label) →",
                   line2: option.id == defaultOptionID ? L10n.text("card.ifQuiet") : "", k: k, scale: 1.1)
                .contentShape(Rectangle())
                .onTapGesture {
                    withAnimation(.easeInOut(duration: 0.25)) { chosen = option }
                }
                .pinned(size: CGSize(width: e.width * k * 1.1, height: e.height * k * 1.1),
                        anchor: CGPoint(x: hole.x * k * 1.1, y: hole.y * k * 1.1),
                        at: m.point(at.x, at.y), rotation: rot)
            PlacedArt(name: "nail", m: m, at: at)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(option.label)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { withAnimation { chosen = option } }
    }

    // MARK: Финал (выемка на Седле)

    @ViewBuilder
    private func finale(_ m: FrameMapper) -> some View {
        SpeechPaper(m: m, title: placeName,
                    subtitle: L10n.format("card.finale.steps", Format.steps(20_000), Format.stepsWord(20_000)),
                    lines: card.lines)
        if let l7 = engine.story.item(event?.receive ?? "l7") {
            PlacedArt(name: l7.art, m: m, at: CGPoint(x: 585, y: 1800), scale: 1.5, rotation: -4)
                .allowsHitTesting(false)
        }
        ArrowButton(title: L10n.text("card.read"), m: m, bottom: 2460, action: onDone)
    }
}

/// Итоговая карточка главы: судьбы писем и доверие поселений.
struct EndCardView: View {
    @EnvironmentObject var engine: ChapterEngine
    @EnvironmentObject var game: GameModel
    let onClose: () -> Void

    var body: some View {
        FrameScreen(dim: 0.72) { m in
            ZStack {
                let e = UIArt.entry("sheet")
                let k = m.scale
                PaperArt(name: "sheet", k: k) { size in
                    ScrollView(.vertical, showsIndicators: false) {
                        VStack(alignment: .leading, spacing: m.length(18)) {
                            ForEach(engine.story.trustSettlements + ["sedlo"], id: \.self) { sid in
                                let fates = engine.fates.filter { $0.settlement == sid }
                                if !fates.isEmpty || engine.story.trustSettlements.contains(sid) {
                                    settlementBlock(sid, fates: fates, m: m)
                                }
                            }
                            Text(engine.story.nextChapter)
                                .font(Ink.label(m.length(34)))
                                .foregroundStyle(Ink.brown.opacity(0.6))
                                .padding(.top, m.length(10))
                        }
                        .frame(width: size.width, alignment: .leading)
                    }
                }
                .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                        anchor: CGPoint(x: e.bodyCenter.x * k, y: e.bodyCenter.y * k),
                        at: m.point(585, 1120))

                PlacedArt(name: "plaque", m: m, at: CGPoint(x: 585, y: 330), rotation: -2) { e, f in
                    let t = e.anchor("text")
                    VStack(spacing: 0) {
                        Text(engine.story.finaleTitle)
                            .font(Ink.title(58 * f))
                        Text(engine.story.finaleSubtitle)
                            .font(Ink.label(40 * f))
                    }
                    .foregroundStyle(Ink.chalk)
                    .shadow(color: .black.opacity(0.4), radius: 0, x: 0, y: 2 * f)
                    .lineLimit(1).minimumScaleFactor(0.5)
                    .frame(width: e.body.width * 0.86 * f)
                    .position(x: t.x * f, y: t.y * f)
                }
                .allowsHitTesting(false)

                ArrowButton(title: L10n.text("card.close"), m: m, bottom: 2460, action: onClose)
            }
        }
    }

    private func settlementBlock(_ sid: String, fates: [StoryConfig.Fate], m: FrameMapper) -> some View {
        let name = game.chapter.settlements.first { $0.id == sid }?.name ?? sid
        let trust = engine.trust(sid)
        return VStack(alignment: .leading, spacing: m.length(4)) {
            HStack(spacing: m.length(10)) {
                Text(name)
                    .font(Ink.title(m.length(40)))
                    .foregroundStyle(Ink.brown)
                if engine.story.trustSettlements.contains(sid) {
                    HStack(spacing: m.length(2)) {
                        ForEach(0..<min(5, abs(trust)), id: \.self) { _ in
                            Image(uiImage: HUDImages.image(UIArt.entry(trust > 0 ? "pin" : "pin_red").image))
                                .resizable()
                                .frame(width: m.length(trust > 0 ? 40 : 46), height: m.length(trust > 0 ? 46 : 52))
                        }
                    }
                    Text(trust == 0 ? L10n.text("card.trust.even") : (trust > 0 ? L10n.format("card.trust.plus", trust) : L10n.format("card.trust.signed", trust)))
                        .font(Ink.label(m.length(28)))
                        .foregroundStyle(Ink.brown.opacity(0.6))
                }
            }
            ForEach(Array(fates.enumerated()), id: \.offset) { _, fate in
                Text(fate.text)
                    .font(Ink.label(m.length(36)))
                    .foregroundStyle(Ink.pencil)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
