import SwiftUI

/// Чтение письма (ui/v4 screen_letter.jpg): лист по центру, конверт с адресом слева внизу,
/// вложение справа, кнопка «в сумку». Тексты — дословно из letters-ch1.md (через chapter1_story.json).
/// Секретное письмо Пимена: снаружи читается счёт; «вскрыть» — с подтверждением, Вера заметит.
struct LetterScreen: View {
    @EnvironmentObject var engine: ChapterEngine
    let itemID: String
    let onClose: () -> Void

    @State var page = 0
    @State var confirmOpen = false

    private struct Page {
        let paper: String
        let font: String
        let text: String
        let tape: Bool
        let caption: String?
    }

    /// Своя глава первая. Улика из прошлой главы лежит в её сюжете, не в текущем.
    var item: StoryConfig.Item? {
        if let own = engine.story.item(itemID) { return own }
        for chapter in [3, 2, 1] where chapter != engine.story.chapter {
            if let found = StoryConfig.load(chapter: chapter).item(itemID) { return found }
        }
        return nil
    }

    private var pages: [Page] {
        guard let item else { return [] }
        guard let r = item.reader else {
            return [Page(paper: "sheet_form", font: "draft", text: item.text, tape: false, caption: nil)]
        }
        if let outside = item.outside {
            var list = [Page(paper: "sheet_form", font: "tape", text: outside, tape: true,
                             caption: L10n.text("letter.outside"))]
            if engine.isOpened(item.id) {
                list.append(Page(paper: "sheet_telegram", font: "tape", text: item.text, tape: true, caption: L10n.text("letter.inside")))
            }
            return list
        }
        let note = engine.note(for: item)
        var list = [Page(paper: r.paper == "sheet_telegram" && note != nil ? "sheet" : r.paper,
                         font: r.font, text: item.text, tape: r.font == "tape", caption: nil)]
        if let note {
            list.append(Page(paper: "sheet_telegram", font: "violet", text: note, tape: false, caption: L10n.text("letter.note")))
        }
        return list
    }

    var body: some View {
        FrameScreen(dim: 0.7) { m in
            ZStack {
                Color.clear.contentShape(Rectangle()).onTapGesture { onClose() }
                if let item {
                    let all = pages
                    let current = all[min(page, max(0, all.count - 1))]
                    sheet(current, count: all.count, m: m)
                        .id(page)
                        .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                                removal: .opacity))
                    if let r = item.reader {
                        envelope(item, r, m: m)
                        attachments(r, m: m)
                    }
                    caption(item, m: m)
                    if item.kind == "secret" && !engine.isOpened(item.id) && engine.status(item.id) == .inBag {
                        openTag(m)
                    }
                    bagButton(m)
                }
            }
        }
        .confirmationDialog(L10n.text("letter.open.title"), isPresented: $confirmOpen, titleVisibility: .visible) {
            Button(L10n.text("letter.open"), role: .destructive) {
                engine.open(itemID)
                withAnimation(.easeInOut(duration: 0.3)) { page = 1 }
            }
            Button(L10n.text("letter.leave"), role: .cancel) {}
        } message: {
            Text(L10n.text("letter.open.message"))
        }
        .onAppear { SoundPlayback.shared.effect("mail_unfold") }
        .onChange(of: page) { _, _ in SoundPlayback.shared.effect("mail_unfold") }
    }

    // MARK: Лист

    private func sheet(_ p: Page, count: Int, m: FrameMapper) -> some View {
        let e = UIArt.entry(p.paper)
        let k = m.scale
        let center = CGPoint(x: 585, y: 857.5)
        let baked = BakedArt.caption(for: p.paper)
        let heading = [p.caption, baked].compactMap { $0 }.joined(separator: "\n")
        return PaperArt(name: p.paper, k: k) { size in
            VStack(alignment: .leading, spacing: 0) {
                if !heading.isEmpty {
                    Text(heading)
                        .font(Ink.label(m.length(30)))
                        .foregroundStyle(Ink.brown.opacity(0.6))
                        .padding(.bottom, m.length(14))
                }
                ScrollView(.vertical, showsIndicators: false) {
                    if p.tape {
                        TapeText(text: p.text, width: size.width, k: k)
                    } else {
                        Text(engine.resolve(p.text))
                            .font(Ink.font(p.font, size: m.length(p.font == "hand" ? 46 : 40)))
                            .foregroundStyle(Ink.color(p.font))
                            .lineSpacing(m.length(p.font == "hand" ? 6 : 10))
                            .frame(width: size.width, alignment: .leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                if count > 1 {
                    Text(page + 1 < count ? L10n.text("letter.next") : L10n.text("letter.start"))
                        .font(Ink.label(m.length(30)))
                        .foregroundStyle(Ink.brown.opacity(0.55))
                        .frame(maxWidth: .infinity, alignment: .trailing)
                        .padding(.top, m.length(8))
                }
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            guard count > 1 else { return }
            withAnimation(.easeInOut(duration: 0.3)) { page = (page + 1) % count }
        }
        .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                anchor: CGPoint(x: e.bodyCenter.x * k, y: e.bodyCenter.y * k),
                at: m.point(center.x, center.y))
    }

    // MARK: Конверт и вложения

    @ViewBuilder
    private func envelope(_ item: StoryConfig.Item, _ r: StoryConfig.Reader, m: FrameMapper) -> some View {
        let name = engine.isOpened(item.id) ? (r.envelopeOpened ?? r.envelope) : r.envelope
        if let name {
            let e = UIArt.entry(name)
            let topLeft = CGPoint(x: 44, y: 1700)
            let center = CGPoint(x: topLeft.x + e.body.width / 2, y: topLeft.y + e.body.height / 2)
            PlacedArt(name: name, m: m, at: center, rotation: -4) { e, f in
                let a = e.anchor("address")
                VStack(spacing: 2 * f) {
                    ForEach(Array(r.address.enumerated()), id: \.offset) { _, line in
                        Text(engine.resolve(line))
                            .font(item.kind == "secret" ? Ink.font("tape", size: 30 * f) : Ink.font("hand", size: 34 * f))
                            .foregroundStyle(Ink.pencil)
                            .lineLimit(1).minimumScaleFactor(0.5)
                    }
                }
                .frame(width: e.body.width * 0.62 * f)
                .position(x: a.x * f, y: a.y * f)
                if let stamp = r.stamp {
                    let s = e.anchor("stamp")
                    StampView(lines: stamp.map { engine.resolve($0) }, k: f)
                        .position(x: s.x * f, y: s.y * f)
                        .rotationEffect(.degrees(-12))
                }
            }
            .allowsHitTesting(false)
        }
    }

    @ViewBuilder
    private func attachments(_ r: StoryConfig.Reader, m: FrameMapper) -> some View {
        if let a = r.attachment {
            let e = UIArt.entry(a)
            let center = CGPoint(x: 520 + e.body.width / 2, y: 1640 + e.body.height / 2)
            PlacedArt(name: a, m: m, at: center, rotation: 5) { e, f in
                if let date = r.attachmentDate {
                    let d = e.anchor("date")
                    Text(engine.resolve(date))
                        .font(Ink.font("draft", size: 30 * f))
                        .foregroundStyle(Ink.brown)
                        .position(x: d.x * f, y: d.y * f)
                }
            }
            .allowsHitTesting(false)
        }
        if let a2 = r.attachment2 {
            let e = UIArt.entry(a2)
            let center = CGPoint(x: 790 + e.body.width / 2 * 0.8, y: 1760 + e.body.height / 2 * 0.8)
            PlacedArt(name: a2, m: m, at: center, scale: 0.8, rotation: -9)
                .allowsHitTesting(false)
        }
    }

    @ViewBuilder
    private func caption(_ item: StoryConfig.Item, m: FrameMapper) -> some View {
        if let c = item.reader?.attachmentCaption {
            let baked = BakedArt.caption(for: item.reader?.attachment)
            let shown = baked.map { c + "\n" + $0 } ?? c
            Text(shown)
                .font(Ink.label(m.length(32)))
                .foregroundStyle(Ink.chalk.opacity(0.85))
                .multilineTextAlignment(.center)
                .frame(width: m.length(620))
                .position(m.point(item.reader?.attachment == nil ? 760 : 585, item.reader?.attachment == nil ? 1860 : 2190))
                .allowsHitTesting(false)
                .accessibilityLabel(shown)
        }
    }

    private func openTag(_ m: FrameMapper) -> some View {
        let e = UIArt.entry("tag_small")
        let hole = e.anchor("hole")
        let k = m.scale
        let at = CGPoint(x: 140, y: 2300)
        return ZStack {
            TagArt(line1: L10n.text("letter.seal.line1"), line2: L10n.text("letter.seal.line2"), k: k, small: true)
                .contentShape(Rectangle())
                .onTapGesture { confirmOpen = true }
                .pinned(size: CGSize(width: e.width * k, height: e.height * k),
                        anchor: CGPoint(x: hole.x * k, y: hole.y * k),
                        at: m.point(at.x, at.y), rotation: 6)
            PlacedArt(name: "nail", m: m, at: at)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.text("letter.seal.a11y"))
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { confirmOpen = true }
    }

    private func bagButton(_ m: FrameMapper) -> some View {
        let e = UIArt.entry("btn_bag")
        let b = e.body
        let center = CGPoint(x: 905, y: 2420 - b.height / 2)
        return Button(action: onClose) {
            ArtView(name: "btn_bag", k: m.scale) { e, f in
                Text(L10n.text("letter.bag"))
                    .font(Ink.label(34 * f))
                    .foregroundStyle(Ink.chalk)
                    .shadow(color: .black.opacity(0.5), radius: 0, x: 0, y: 1.5 * f)
                    .position(x: e.bodyCenter.x * f, y: (e.body.maxY + 4) * f)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PressStyle())
        .pinned(size: CGSize(width: e.width * m.scale, height: e.height * m.scale),
                anchor: CGPoint(x: e.bodyCenter.x * m.scale, y: e.bodyCenter.y * m.scale),
                at: m.point(center.x, center.y))
        .accessibilityLabel(L10n.text("letter.bag.a11y"))
    }
}

/// Текст на обрывках телеграфной ленты: по строке на обрывок (письмо Пимена).
struct TapeText: View {
    let text: String
    let width: CGFloat
    let k: CGFloat

    private var strips: [String] {
        var out: [String] = []
        for line in text.split(separator: "\n") {
            var cur = ""
            for word in line.split(separator: " ") {
                let next = cur.isEmpty ? String(word) : cur + " " + String(word)
                if next.count > 34 && !cur.isEmpty {
                    out.append(cur); cur = String(word)
                } else {
                    cur = next
                }
            }
            if !cur.isEmpty { out.append(cur) }
        }
        return out
    }

    var body: some View {
        let e = UIArt.entry("tape_line")
        let scale = min(1, width / max(1, e.width * k))
        VStack(alignment: .leading, spacing: 10 * k) {
            ForEach(Array(strips.enumerated()), id: \.offset) { i, s in
                ZStack {
                    Image(uiImage: HUDImages.image(e.image))
                        .resizable()
                        .frame(width: e.width * k * scale, height: e.height * k * scale)
                    Text(s)
                        .font(Ink.font("tape", size: 30 * k * scale))
                        .foregroundStyle(Color(red: 0.16, green: 0.13, blue: 0.10))
                        .lineLimit(1).minimumScaleFactor(0.5)
                        .padding(.horizontal, 24 * k * scale)
                        .frame(width: e.width * k * scale)
                }
                .rotationEffect(.degrees(i % 2 == 0 ? -0.8 : 0.9))
                .offset(x: CGFloat(i % 3) * 4 * k)
            }
        }
    }
}

/// Круглый фиолетовый штемпель с двумя строками (место · дата).
struct StampView: View {
    let lines: [String]
    let k: CGFloat

    var body: some View {
        ZStack {
            Image(uiImage: HUDImages.image(UIArt.entry("stamp_violet").image))
                .resizable()
                .frame(width: 192 * k, height: 192 * k)
            VStack(spacing: 2 * k) {
                ForEach(Array(lines.enumerated()), id: \.offset) { _, l in
                    Text(l)
                        .font(Ink.font("draft", size: 26 * k))
                        .foregroundStyle(Ink.violet.opacity(0.8))
                        .lineLimit(1).minimumScaleFactor(0.5)
                }
            }
            .frame(width: 130 * k)
        }
        .frame(width: 192 * k, height: 192 * k)
    }
}
