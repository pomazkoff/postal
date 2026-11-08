import SwiftUI

/// Сумка: почта и личные вещи на деревянных бирках, ниже — сама сумка.
/// На бирке письма написано, куда его нести. Находку только рассматривают.
/// Координаты — кадр 1170×2532, как в ui_ch1.json.
struct BagScreen: View {
    enum Mode { case sort, view }

    @EnvironmentObject var engine: ChapterEngine
    let mode: Mode
    let onRead: (String) -> Void
    let onClose: () -> Void

    @State var selected: [String] = []

    let titleHole = CGPoint(x: 595, y: 236)
    let bagRing = CGPoint(x: 470, y: 1262)

    private var bagContents: [StoryConfig.Item] { engine.mailItems }

    var body: some View {
        FrameScreen(dim: 0.66) { m in
            ZStack {
                // Тап мимо — закрыть (только в обычном режиме: разбор нужно подтвердить).
                Color.clear.contentShape(Rectangle())
                    .onTapGesture { if mode == .view { onClose() } }

                titleTag(m)
                inventory(m)
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

    /// Почта и находки одним свитком. Бирка говорит, куда нести или что это просто посмотреть.
    private func inventory(_ m: FrameMapper) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: m.length(18)) {
                section(L10n.text("bag.mail"), items: engine.mailItems, empty: L10n.text("bag.mail.empty"), m: m)
                section(L10n.text("bag.personal"), items: engine.personalItems, empty: L10n.text("bag.personal.empty"), m: m)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.bottom, m.length(24))
        }
        .frame(width: m.length(980), height: m.length(760))
        .position(m.point(585, 780))
    }

    private func section(_ title: String, items: [StoryConfig.Item], empty: String, m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(8)) {
            Text(title)
                .font(Ink.title(m.length(40)))
                .foregroundStyle(Ink.brown)
            if items.isEmpty {
                Text(empty)
                    .font(Ink.font("hand", size: m.length(32)))
                    .foregroundStyle(Ink.pencil)
            } else {
                ForEach(items) { item in
                    carriedTag(item, m: m)
                }
            }
        }
    }

    private func carriedTag(_ item: StoryConfig.Item, m: FrameMapper) -> some View {
        let personal = BagPolicy.role(id: item.id, kind: item.kind) == .personal
        let line1 = personal ? L10n.text(keepKey(item.id)) : item.to
        let line2 = personal ? L10n.text("bag.look") : L10n.text(BagPolicy.actionKey(chapter: engine.story.chapter, id: item.id))
        return Button { onRead(item.id) } label: {
            HStack(alignment: .center, spacing: m.length(12)) {
                Image(uiImage: HUDImages.image(UIArt.entry(item.art).image))
                    .resizable()
                    .scaledToFit()
                    .frame(width: m.length(120), height: m.length(90))
                    .accessibilityHidden(true)
                TagArt(line1: line1, line2: line2, k: m.scale, scale: 0.78)
            }
        }
        .buttonStyle(PressStyle())
        .accessibilityLabel("\(line1). \(line2)")
    }

    private func keepKey(_ id: String) -> String {
        switch id {
        case "animal_cat_stamp": return "bag.keep.animal_cat_stamp"
        case "animal_raven_scrap": return "bag.keep.animal_raven_scrap"
        case "animal_dog_horn": return "bag.keep.animal_dog_horn"
        default: return "bag.keep.other"
        }
    }

    private func titleTag(_ m: FrameMapper) -> some View {
        let e = UIArt.entry("tag")
        let hole = e.anchor("hole")
        let k = m.scale
        let line1 = L10n.text("bag.title")
        let line2 = L10n.text("bag.withYou")
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
        let contents = Array(bagContents.prefix(3))
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

    private func tapStick(_ item: StoryConfig.Item) {
        guard mode == .sort else {
            onRead(item.id)
            return
        }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { selected.removeAll { $0 == item.id } }
    }
}
