import SwiftUI

/// Сумка поверх пластилиновой сцены: деревянные полки, бумажные бирки, кожаная сумка внизу.
/// «Почта» и «Личные вещи» — две группы полок. Если вещей больше, чем влезает, полки листаются.
/// Координаты — кадр 1170×2532.
struct BagScreen: View {
    enum Mode { case sort, view }

    @EnvironmentObject var engine: ChapterEngine
    let mode: Mode
    let onRead: (String) -> Void
    let onClose: () -> Void

    /// Окно полок. Ниже него стоит кожаная сумка, ещё ниже — стрелка «Закрыть».
    private let scrollTop = 390.0
    private let scrollHeight = 960.0
    private let bagRing = CGPoint(x: 400, y: 1415)
    private let titleHole = CGPoint(x: 585, y: 210)

    var body: some View {
        FrameScreen(dim: 0.66) { m in
            ZStack {
                Color.clear.contentShape(Rectangle())
                    .onTapGesture { if mode == .view { onClose() } }

                titleTag(m)
                shelves(m)
                leatherBag(m)

                ArrowButton(title: mode == .sort ? L10n.text("bag.go") : L10n.text("bag.close"), m: m, bottom: 2470) {
                    if mode == .sort {
                        engine.confirmSort(selected: engine.sortCandidates.map(\.id))
                    }
                    onClose()
                }
            }
        }
        .transition(.opacity)
        .onAppear { SoundPlayback.shared.effect("mail_bag") }
    }

    // MARK: Заголовок

    private func titleTag(_ m: FrameMapper) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let k = m.scale
        return ZStack {
            TagArt(line1: L10n.text("bag.title"), line2: L10n.text("bag.withYou"), k: k, size2: 34)
                .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                        anchor: CGPoint(x: hole.x * k, y: hole.y * k),
                        at: m.point(titleHole.x, titleHole.y), rotation: -2)
            PlacedArt(name: "nail", m: m, at: titleHole)
        }
        .allowsHitTesting(false)
    }

    // MARK: Полки

    private func shelves(_ m: FrameMapper) -> some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(spacing: 0) {
                group(L10n.text("bag.mail"), items: engine.mailItems, empty: L10n.text("bag.mail.empty"),
                      headerOnLeft: true, m: m)
                group(L10n.text("bag.personal"), items: engine.personalItems, empty: L10n.text("bag.personal.empty"),
                      headerOnLeft: false, m: m)
            }
            .frame(maxWidth: .infinity)
            .padding(.bottom, m.length(12))
        }
        .frame(width: m.length(1170), height: m.length(scrollHeight))
        .position(m.point(585, scrollTop + scrollHeight / 2))
    }

    private func group(_ title: String, items: [StoryConfig.Item], empty: String, headerOnLeft: Bool, m: FrameMapper) -> some View {
        let pairs = stride(from: 0, to: max(items.count, 1), by: 2).map { index -> (StoryConfig.Item?, StoryConfig.Item?) in
            if items.isEmpty { return (nil, nil) }
            let right = index + 1 < items.count ? items[index + 1] : nil
            return (items[index], right)
        }
        return VStack(spacing: 0) {
            sectionTag(title, onLeft: headerOnLeft, m: m)
            ForEach(Array(pairs.enumerated()), id: \.offset) { _, pair in
                shelf(pair.0, pair.1, empty: items.isEmpty ? empty : nil, m: m)
            }
        }
    }

    private func sectionTag(_ title: String, onLeft: Bool, m: FrameMapper) -> some View {
        let e = UIArt.entry("tag_small")
        let hole = e.anchor("hole")
        let f = m.scale
        let x = onLeft ? 210.0 : 585.0
        return ZStack {
            ArtView(name: "tag_small", k: f) { entry, scale in
                let top = entry.anchor("line1")
                let bottom = entry.anchor("line2")
                Text(title)
                    .font(Ink.title(46 * scale))
                    .foregroundStyle(Ink.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                    .frame(width: entry.value("textWidth") * scale)
                    .position(x: top.x * scale, y: (top.y + bottom.y) / 2 * scale)
            }
            .pinned(size: CGSize(width: e.width * f, height: e.height * f),
                    anchor: CGPoint(x: hole.x * f, y: hole.y * f),
                    at: CGPoint(x: m.length(x), y: m.length(96)), rotation: onLeft ? -3 : 2)
            place("nail", m: m, at: CGPoint(x: x, y: 96), scale: 0.8)
        }
        .frame(width: m.length(1170), height: m.length(170))
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func shelf(_ left: StoryConfig.Item?, _ right: StoryConfig.Item?, empty: String?, m: FrameMapper) -> some View {
        let height = 440.0
        let shelfY = 56.0
        let baseY = shelfY + 28
        let tagY = shelfY + 140
        return ZStack(alignment: .topLeading) {
            Color.clear
            place("shelf", m: m, anchor: "origin", at: CGPoint(x: 2, y: shelfY))
            itemSlot(left, empty: empty, cx: 290, base: baseY, tag: CGPoint(x: 175, y: tagY), angle: -4, m: m)
            if empty == nil {
                itemSlot(right, empty: nil, cx: 890, base: baseY, tag: CGPoint(x: 790, y: tagY), angle: 3, m: m)
            }
        }
        .frame(width: m.length(1170), height: m.length(height))
    }

    @ViewBuilder
    private func itemSlot(_ item: StoryConfig.Item?, empty: String?, cx: Double, base: Double, tag: CGPoint, angle: Double, m: FrameMapper) -> some View {
        if let item {
            let personal = BagPolicy.role(id: item.id, kind: item.kind) == .personal
            let line1 = personal ? L10n.text(keepKey(item.id)) : item.to
            let line2 = personal ? L10n.text("bag.look") : L10n.text(BagPolicy.actionKey(chapter: engine.story.chapter, id: item.id))
            place(item.art, m: m, anchor: "bottom", at: CGPoint(x: cx, y: base), scale: itemScale(item.art), rotation: angle * 0.4) {
                onRead(item.id)
            }
            tagButton(line1: line1, line2: line2, at: tag, angle: angle, m: m) { onRead(item.id) }
            place("nail", m: m, at: tag, scale: 0.85)
        } else if let empty {
            tagButton(line1: empty, line2: "", at: tag, angle: angle, m: m, action: nil)
            place("nail", m: m, at: tag, scale: 0.85)
        }
    }

    private func tagButton(line1: String, line2: String, at: CGPoint, angle: Double, m: FrameMapper, action: (() -> Void)?) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let f = m.scale * 0.9
        let size = CGSize(width: e.width * f, height: e.height * f)
        let anchor = CGPoint(x: hole.x * f, y: hole.y * f)
        let spot = CGPoint(x: m.length(at.x), y: m.length(at.y))
        return ArtView(name: "tag", k: m.scale, scale: 0.9) { entry, scale in
            let w = entry.value("textWidth") * scale
            let l1 = entry.anchor("line1")
            let l2 = entry.anchor("line2")
            Text(line1)
                .font(Ink.title(42 * scale))
                .foregroundStyle(Ink.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.45)
                .frame(width: w)
                .position(x: l1.x * scale, y: l1.y * scale)
            Text(line2)
                .font(Ink.label(28 * scale))
                .foregroundStyle(Ink.brown.opacity(0.9))
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.55)
                .frame(width: w, height: 72 * scale)
                .position(x: l2.x * scale, y: (l2.y + 10) * scale)
        }
        .contentShape(Rectangle())
        .onTapGesture { action?() }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(line2.isEmpty ? line1 : "\(line1). \(line2)")
        .accessibilityAddTraits(.isButton)
        .pinned(size: size, anchor: anchor, at: spot, rotation: angle)
    }

    /// Крупные бланки (телеграмма) садятся на полку так же, как конверт, и не закрывают соседнюю бирку.
    private func itemScale(_ name: String) -> CGFloat {
        let height = UIArt.entry(name).height
        return min(0.82, 200 / max(height, 1))
    }

    private func keepKey(_ id: String) -> String {
        switch id {
        case "animal_cat_stamp": return "bag.keep.animal_cat_stamp"
        case "animal_raven_scrap": return "bag.keep.animal_raven_scrap"
        case "animal_dog_horn": return "bag.keep.animal_dog_horn"
        default: return "bag.keep.other"
        }
    }

    // MARK: Кожаная сумка

    /// Сумка без меловых имён: три отделения больше не показывают, сколько писем можно нести.
    private func leatherBag(_ m: FrameMapper) -> some View {
        let back = UIArt.entry("bag_back")
        let ring = back.anchor("ring")
        let origin = CGPoint(x: bagRing.x - ring.x, y: bagRing.y - ring.y)
        return ZStack {
            PlacedArt(name: "bag_back", m: m, anchor: "origin", at: origin, scale: 0.9)
            PlacedArt(name: "bag_front", m: m, anchor: "origin", at: origin, scale: 0.9)
                .allowsHitTesting(false)
            PlacedArt(name: "nail", m: m, at: bagRing, scale: 0.9)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func place(_ name: String, m: FrameMapper, anchor: String = "center", at: CGPoint,
                       scale: CGFloat = 1, rotation: Double = 0, onTap: (() -> Void)? = nil) -> some View {
        let e = UIArt.entry(name)
        let f = m.scale * scale
        let a = PlacedArt<EmptyView>.anchorPoint(anchor, in: e)
        return ArtView(name: name, k: m.scale, scale: scale)
            .contentShape(Rectangle())
            .onTapGesture { onTap?() }
            .allowsHitTesting(onTap != nil)
            .pinned(size: CGSize(width: e.width * f, height: e.height * f),
                    anchor: CGPoint(x: a.x * f, y: a.y * f),
                    at: CGPoint(x: m.length(at.x), y: m.length(at.y)), rotation: rotation)
    }
}
