import SwiftUI

/// Сумка (ui/v4 screen_bag.jpg): две полки с письмами на бирках, под ними сумка с тремя отделениями.
/// Режим разбора (утро на Почте): тап по письму — в сумку, тап по отделению — обратно, «В путь» — подтвердить.
/// Обычный режим: что сейчас несём; тап по бирке или письму — прочитать.
/// Координаты — кадр 1170×2532, как в ui_ch1.json → layout.bag.
struct BagScreen: View {
    enum Mode { case sort, view }

    @EnvironmentObject var engine: ChapterEngine
    let mode: Mode
    let onRead: (String) -> Void
    let onClose: () -> Void

    @State var selected: [String] = []

    // layout.bag
    let shelves: [CGPoint] = [CGPoint(x: 2, y: 506), CGPoint(x: 2, y: 976)]
    struct Slot { let cx: Double; let base: Double; let tag: CGPoint; let angle: Double }
    let slots: [Slot] = [
        Slot(cx: 270, base: 552, tag: CGPoint(x: 160, y: 590), angle: -4),
        Slot(cx: 880, base: 552, tag: CGPoint(x: 770, y: 590), angle: 3),
        Slot(cx: 270, base: 1022, tag: CGPoint(x: 160, y: 1060), angle: -3),
        Slot(cx: 880, base: 1022, tag: CGPoint(x: 770, y: 1060), angle: 4),
    ]
    let titleHole = CGPoint(x: 595, y: 236)
    let bagRing = CGPoint(x: 470, y: 1262)

    private var shelfItems: [StoryConfig.Item] {
        switch mode {
        case .sort: return Array((engine.sortCandidates + engine.pocketItems).prefix(4))
        case .view: return Array((engine.bagItems + engine.pocketItems).prefix(4))
        }
    }

    private var bagContents: [StoryConfig.Item] {
        switch mode {
        case .sort: return selected.compactMap { engine.story.item($0) }
        case .view: return engine.bagItems
        }
    }

    var body: some View {
        FrameScreen(dim: 0.66) { m in
            ZStack {
                // Тап мимо — закрыть (только в обычном режиме: разбор нужно подтвердить).
                Color.clear.contentShape(Rectangle())
                    .onTapGesture { if mode == .view { onClose() } }

                ForEach(shelves.indices, id: \.self) { i in
                    PlacedArt(name: "shelf", m: m, anchor: "origin", at: shelves[i])
                }

                ForEach(Array(shelfItems.enumerated()), id: \.element.id) { index, item in
                    shelfSlot(item, slot: slots[index], m: m)
                }

                titleTag(m)
                bag(m)

                ArrowButton(title: mode == .sort ? L10n.text("bag.go") : L10n.text("bag.close"), m: m) {
                    if mode == .sort { engine.confirmSort(selected: selected) }
                    onClose()
                }
            }
        }
        .transition(.opacity)
        .onAppear { SoundPlayback.shared.effect("mail_bag") }
    }

    // MARK: Полка

    @ViewBuilder
    private func shelfSlot(_ item: StoryConfig.Item, slot: Slot, m: FrameMapper) -> some View {
        let inBag = mode == .sort && selected.contains(item.id)
        let art = engine.isOpened(item.id) ? (item.artOpened ?? item.art) : item.art
        if !inBag {
            PlacedArt(name: art, m: m, anchor: "bottom", at: CGPoint(x: slot.cx, y: slot.base),
                      rotation: slot.angle * 0.5, onTap: { tapItem(item) })
                .transition(.scale(scale: 0.6).combined(with: .opacity))
        }
        tag(for: item, slot: slot, m: m, dimmed: inBag)
    }

    private func tag(for item: StoryConfig.Item, slot: Slot, m: FrameMapper, dimmed: Bool) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let k = m.scale
        let line2: String
        if !item.takesSlot {
            line2 = L10n.text("bag.pocket")
        } else if dimmed {
            line2 = L10n.text("bag.inBag")
        } else {
            line2 = item.place
        }
        return ZStack {
            TagArt(line1: item.to, line2: line2, k: k)
                .opacity(dimmed ? 0.72 : 1)
                .contentShape(Rectangle())
                .onTapGesture { onRead(item.id) }
                .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                        anchor: CGPoint(x: hole.x * k, y: hole.y * k),
                        at: m.point(slot.tag.x, slot.tag.y), rotation: slot.angle)
            PlacedArt(name: "nail", m: m, at: slot.tag)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(item.to), \(line2)")
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { onRead(item.id) }
    }

    private func titleTag(_ m: FrameMapper) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let k = m.scale
        let line1 = mode == .sort ? L10n.text("bag.title.sort") : L10n.text("bag.title")
        let used = bagContents.count
        let slots = engine.story.slots
        let line2 = mode == .sort
            ? L10n.format("bag.slots", slots, Format.slots(slots))
            : L10n.format("bag.used", used, slots)
        return ZStack {
            TagArt(line1: line1, line2: line2, k: k)
                .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                        anchor: CGPoint(x: hole.x * k, y: hole.y * k),
                        at: m.point(titleHole.x, titleHole.y), rotation: -2)
            PlacedArt(name: "nail", m: m, at: titleHole)
        }
        .allowsHitTesting(false)
    }

    // MARK: Сумка

    private func bag(_ m: FrameMapper) -> some View {
        let back = UIArt.entry("bag_back")
        let ring = back.anchor("ring")
        let origin = CGPoint(x: bagRing.x - ring.x, y: bagRing.y - ring.y)
        let contents = bagContents
        let labelW = back.value("labelWidth")
        return ZStack {
            PlacedArt(name: "bag_back", m: m, anchor: "origin", at: origin)
            ForEach(Array(contents.enumerated()), id: \.element.id) { i, item in
                let s = back.anchor("slot\(min(i, 2))")
                PlacedArt(name: item.stick, m: m, anchor: "bottom",
                          at: CGPoint(x: origin.x + s.x, y: origin.y + s.y + 60),
                          onTap: { tapStick(item) })
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
            PlacedArt(name: "bag_front", m: m, anchor: "origin", at: origin)
                .allowsHitTesting(false)
            // Мелом на клапане отделений — кому.
            ForEach(Array(contents.enumerated()), id: \.element.id) { i, item in
                let l = back.anchor("label\(min(i, 2))")
                Text(item.to)
                    .font(HUDFonts.font("Neucha", size: m.length(34)))
                    .foregroundStyle(Ink.chalk.opacity(0.9))
                    .lineLimit(1).minimumScaleFactor(0.5)
                    .frame(width: m.length(labelW))
                    .position(m.point(origin.x + l.x, origin.y + l.y))
                    .allowsHitTesting(false)
            }
            PlacedArt(name: "nail", m: m, at: CGPoint(x: bagRing.x, y: bagRing.y - 8))
        }
    }

    // MARK: Действия

    private func tapItem(_ item: StoryConfig.Item) {
        guard mode == .sort, item.takesSlot else {
            onRead(item.id)
            return
        }
        guard !selected.contains(item.id), selected.count < engine.story.slots else { return }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { selected.append(item.id) }
    }

    private func tapStick(_ item: StoryConfig.Item) {
        guard mode == .sort else {
            onRead(item.id)
            return
        }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { selected.removeAll { $0 == item.id } }
    }
}
