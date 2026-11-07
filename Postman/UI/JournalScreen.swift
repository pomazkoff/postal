import SwiftUI
import UIKit

/// «Вот как развивалась история»: карусель бумажных карточек — всё, что случилось без игрока
/// с прошлого визита (прибытия, вручения, конверты, сцены, выборы — чьи). Закрыть → мир.
struct JournalScreen: View {
    let journal: ChapterEngine.Journal
    let onClose: () -> Void

    @EnvironmentObject var engine: ChapterEngine
    @EnvironmentObject var game: GameModel
    @State private var page = 0
    /// Непрерывный сдвиг пальца во время драга (px).
    @State private var dragX: CGFloat = 0
    @State private var pagerWidth: CGFloat = 1
    private var progress: CGFloat { CGFloat(page) - dragX / max(pagerWidth, 1) }
    private var indicatorIndex: Int { min(max(Int(progress.rounded()), 0), max(journal.entries.count - 1, 0)) }

    var body: some View {
        FrameScreen(dim: 0.6) { m in
            ZStack {
                Color.clear.contentShape(Rectangle()).onTapGesture { onClose() }
                    .onAppear { SoundPlayback.shared.effect("ui_paper_open") }
                header(m).position(m.point(585, 300))
                let entries = journal.entries
                if entries.isEmpty {
                    Text(L10n.text("journal.empty"))
                        .font(Ink.label(m.length(40))).foregroundStyle(Ink.chalk)
                        .position(m.point(585, 1200))
                } else {
                    cardPager(entries: entries, m: m)
                        .frame(width: m.length(1170), height: m.length(1780))
                        .position(m.point(585, 1300))
                    pager(count: entries.count, m: m).position(m.point(585, 2245))
                }
                ArrowButton(title: L10n.text("journal.go"), m: m, bottom: 2460, action: onClose)
            }
        }
        .transition(.opacity)
    }

    /// Тот же пейджер, что в онбординге: карточки едут за пальцем, scale/yaw/opacity по дистанции,
    /// картинка внутри едет сильнее рамки; отпускание — spring к странице.
    private func cardPager(entries: [LogEntry], m: FrameMapper) -> some View {
        let n = entries.count
        return GeometryReader { g in
            let pw = g.size.width
            ZStack {
                ForEach(Array(entries.enumerated()), id: \.offset) { i, entry in
                    let d = CGFloat(i) - progress
                    let ad = min(abs(d), 1.5)
                    if abs(d) < 1.6 {
                        JournalCard(entry: entry,
                                    place: JournalAssets.settlement(for: entry, in: game.chapter.settlements),
                                    resident: JournalAssets.resident(for: entry, in: engine.story),
                                    chapterFolder: game.chapter.assetsFolder,
                                    m: m,
                                    parallax: d)
                            .frame(width: pw)
                            .scaleEffect(1 - 0.08 * min(ad, 1))
                            .rotation3DEffect(.degrees(Double(-d) * 14), axis: (x: 0, y: 1, z: 0), perspective: 0.6)
                            .rotationEffect(.degrees(Double(d) * 3.5))
                            .offset(x: d * pw * 0.92, y: ad * m.length(40))
                            .opacity(1 - 0.45 * Double(min(ad, 1)))
                            .zIndex(Double(2 - ad))
                            .accessibilityHidden(i != page)
                    }
                }
            }
            .frame(width: pw, height: g.size.height)
            .contentShape(Rectangle())
            .onAppear { pagerWidth = pw }
            .onChange(of: pw) { _, v in pagerWidth = v }
            .gesture(
                DragGesture(minimumDistance: 10)
                    .onChanged { v in
                        guard abs(v.translation.width) > abs(v.translation.height) * 0.8 || dragX != 0 else { return }
                        var t = v.translation.width
                        if (page == 0 && t > 0) || (page == n - 1 && t < 0) { t *= 0.3 }
                        dragX = t
                    }
                    .onEnded { v in
                        let pr = v.predictedEndTranslation.width
                        var target = page
                        if dragX < -pw * 0.25 || pr < -pw * 0.5 { target += 1 }
                        if dragX > pw * 0.25 || pr > pw * 0.5 { target -= 1 }
                        target = min(max(target, 0), n - 1)
                        withAnimation(.spring(response: 0.55, dampingFraction: 0.78)) {
                            page = target
                            dragX = 0
                        }
                    }
            )
            .accessibilityAdjustableAction { dir in
                withAnimation(.spring(response: 0.55, dampingFraction: 0.8)) {
                    switch dir {
                    case .increment: page = min(page + 1, n - 1)
                    case .decrement: page = max(page - 1, 0)
                    default: break
                    }
                }
            }
        }
    }

    private func header(_ m: FrameMapper) -> some View {
        VStack(spacing: m.length(4)) {
            Text(L10n.text("journal.title"))
                .font(Ink.title(m.length(50)))
                .foregroundStyle(Ink.chalk)
                .lineLimit(1).minimumScaleFactor(0.6)
            HStack(alignment: .firstTextBaseline, spacing: m.length(10)) {
                Text("+" + Format.steps(journal.walked))
                    .font(Ink.title(m.length(56)))
                    .foregroundStyle(Ink.stampRed)
                Text(L10n.plural("journal.stepsSince", journal.walked))
                    .font(Ink.label(m.length(32)))
                    .foregroundStyle(Ink.chalk.opacity(0.85))
            }
            .lineLimit(1).minimumScaleFactor(0.5)
        }
        .shadow(color: .black.opacity(0.6), radius: m.length(6))
        .frame(width: m.length(1040))
        .allowsHitTesting(false)
    }

    private func pager(count: Int, m: FrameMapper) -> some View {
        VStack(spacing: m.length(10)) {
            if count <= 12 {
                HStack(spacing: m.length(14)) {
                    ForEach(0..<count, id: \.self) { i in
                        Circle()
                            .fill(i == indicatorIndex ? Ink.stampRed : Ink.chalk.opacity(0.45))
                            .frame(width: m.length(16 + 8 * max(0, 1 - abs(CGFloat(i) - progress))),
                                   height: m.length(16 + 8 * max(0, 1 - abs(CGFloat(i) - progress))))
                    }
                }
            }
            Text("\(min(indicatorIndex, count - 1) + 1) / \(count)")
                .font(Ink.font("draft", size: m.length(30)))
                .foregroundStyle(Ink.chalk.opacity(0.9))
        }
        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: indicatorIndex)
        .allowsHitTesting(false)
    }
}

/// Резолв картинок для записи журнала — на лету, без новых полей в LogEntry.
enum JournalAssets {
    private static var placeCache: [String: UIImage?] = [:]

    static func settlement(for entry: LogEntry, in settlements: [Settlement]) -> Settlement? {
        let names = [entry.place, entry.title].compactMap { $0?.lowercased() }
        for n in names {
            if let s = SaveNames.settlementID(matching: n, among: settlements) { return s }
        }
        return nil
    }

    static func resident(for entry: LogEntry, in story: StoryConfig) -> StoryConfig.Resident? {
        if let title = entry.title, let r = SaveNames.resident(matching: title, in: story.residents) {
            return r
        }
        // «письмо Вере», «письмо Кузьме» и старый русский сейв при английской локали.
        let words = entry.text.lowercased()
            .components(separatedBy: CharacterSet.letters.inverted).filter { !$0.isEmpty }
        return SaveNames.residentByStem(in: words, residents: story.residents)
    }

    /// places/place_<id>_main.png из папки главы; уменьшено для карточки. nil, если нет файла.
    static func placeImage(_ id: String, chapterFolder: String) -> UIImage? {
        let key = chapterFolder + "/" + id
        if let cached = placeCache[key] { return cached }
        let rel = "\(chapterFolder)/places/place_\(id)_main"
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent(rel + ".png")
        var img = UIImage(contentsOfFile: url.path)
        if let full = img, full.size.width > 900 {
            let s = 900 / full.size.width
            img = full.preparingThumbnail(of: CGSize(width: 900, height: full.size.height * s)) ?? full
        }
        placeCache[key] = img
        return img
    }
}

private struct JournalCard: View {
    let entry: LogEntry
    let place: Settlement?
    let resident: StoryConfig.Resident?
    let chapterFolder: String
    let m: FrameMapper
    /// index - progress: для параллакса картинки внутри рамки.
    var parallax: CGFloat = 0

    private static let time: DateFormatter = {
        let f = DateFormatter(); f.locale = AppLanguage.locale; f.dateFormat = "HH:mm"; return f
    }()
    private static let dayTime: DateFormatter = {
        let f = DateFormatter(); f.locale = AppLanguage.locale; f.dateFormat = "d MMM, HH:mm"; return f
    }()

    private var icon: String? {
        switch entry.kind {
        case "arrival": return "pin"
        case "delivery": return "env_plain"
        case "pickup": return "stick_plain"
        case "finale": return "env_ksenia"
        case "choice", "sort": return "tag_small"
        default: return nil
        }
    }

    private var stamp: String? {
        switch entry.by {
        case "postman": return L10n.text("journal.by.postman")
        case "player": return entry.kind == "choice" || entry.kind == "sort" ? L10n.text("journal.by.player") : nil
        default: return nil
        }
    }

    private var when: String {
        var parts = [Format.steps(entry.step) + " " + L10n.text("abbr.steps")]
        if let date = entry.date {
            let f = Calendar.current.isDateInToday(date) ? Self.time : Self.dayTime
            parts.append(f.string(from: date))
        }
        return parts.joined(separator: " · ")
    }

    private var caption: String {
        [entry.place, entry.title].compactMap { $0 }.joined(separator: " · ")
    }

    var body: some View {
        let k = m.scale
        let e = UIArt.entry("sheet")
        let maxW = m.length(1140), maxH = m.length(1770)
        let scale = min(maxW / max(1, e.width * k), maxH / max(1, e.height * k))
        PaperArt(name: "sheet", k: k, scale: scale) { size in
            VStack(alignment: .leading, spacing: m.length(16)) {
                picture(width: size.width, height: min(size.height * 0.55, size.width * 0.8))
                HStack(alignment: .firstTextBaseline) {
                    Text(caption)
                        .font(Ink.label(m.length(32)))
                        .foregroundStyle(Ink.brown.opacity(0.8))
                        .lineLimit(1).minimumScaleFactor(0.6)
                    Spacer(minLength: m.length(8))
                    Text(when)
                        .font(Ink.font("draft", size: m.length(26)))
                        .foregroundStyle(Ink.stampRed.opacity(0.8))
                        .lineLimit(1).minimumScaleFactor(0.6)
                }
                Rectangle().fill(Ink.brown.opacity(0.25)).frame(height: max(1, m.length(3)))
                Text(entry.text)
                    .font(Ink.label(m.length(40)))
                    .foregroundStyle(Ink.pencil)
                    .minimumScaleFactor(0.6)
                    .fixedSize(horizontal: false, vertical: true)
                if let stamp {
                    Text(stamp.uppercased())
                        .font(Ink.font("draft", size: m.length(26)))
                        .foregroundStyle(Ink.stampRed.opacity(0.85))
                        .padding(.horizontal, m.length(12))
                        .padding(.vertical, m.length(4))
                        .overlay(RoundedRectangle(cornerRadius: m.length(6))
                            .stroke(Ink.stampRed.opacity(0.75), lineWidth: max(1, m.length(3))))
                        .rotationEffect(.degrees(-4))
                }
                Spacer(minLength: 0)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func picture(width: CGFloat, height: CGFloat) -> some View {
        let placeImg = place.flatMap { JournalAssets.placeImage($0.id, chapterFolder: chapterFolder) }
        let fig = resident.flatMap { ResidentLibrary.figure(for: $0) }
        let r = m.length(18)
        let shift = -parallax * width * 0.22
        ZStack(alignment: .bottomTrailing) {
            RoundedRectangle(cornerRadius: r).fill(Ink.brown.opacity(0.12))
            if let placeImg {
                Image(uiImage: placeImg)
                    .resizable().interpolation(.high).scaledToFill()
                    .frame(width: width, height: height)
                    .scaleEffect(1.5)
                    .offset(x: shift)
                    .frame(width: width, height: height)
                    .clipShape(RoundedRectangle(cornerRadius: r))
            }
            if let fig {
                let h = height * 0.92
                let w = h * fig.image.size.width / max(1, fig.image.size.height)
                Image(uiImage: fig.image)
                    .resizable().interpolation(.high)
                    .frame(width: w, height: h)
                    .shadow(color: .black.opacity(0.45), radius: m.length(10), x: m.length(8), y: m.length(10))
                    .padding(.trailing, placeImg == nil ? (width - w) / 2 : m.length(20))
                    .offset(x: -shift * 0.8)
            }
            if placeImg == nil && fig == nil {
                if let icon {
                    let ie = UIArt.entry(icon)
                    let side = min(height * 0.6, m.length(260))
                    let fit = min(side / max(1, ie.width * m.scale), side / max(1, ie.height * m.scale))
                    ArtView(name: icon, k: m.scale, scale: fit)
                        .rotationEffect(.degrees(entry.step % 2 == 0 ? -5 : 4))
                        .frame(width: width, height: height)
                } else {
                    Text(entry.place ?? "")
                        .font(Ink.title(m.length(60)))
                        .foregroundStyle(Ink.brown.opacity(0.5))
                        .frame(width: width, height: height)
                }
            }
            if let resident, fig != nil {
                Text(resident.name)
                    .font(Ink.title(m.length(34)))
                    .foregroundStyle(Ink.brown)
                    .padding(.horizontal, m.length(14)).padding(.vertical, m.length(4))
                    .background(RoundedRectangle(cornerRadius: m.length(6)).fill(Ink.chalk))
                    .rotationEffect(.degrees(-3))
                    .padding(m.length(14))
                    .frame(width: width, height: height, alignment: .bottomLeading)
            }
        }
        .frame(width: width, height: height)
        .clipShape(RoundedRectangle(cornerRadius: r))
        .overlay(RoundedRectangle(cornerRadius: r).stroke(Ink.brown.opacity(0.45), lineWidth: max(1, m.length(4))))
    }
}
