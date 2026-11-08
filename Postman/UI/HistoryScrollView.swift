import SwiftUI
import UIKit

/// Почти полный лист: уже рассказанная дорога, крупно, с картинками, которые уже есть в игре.
struct HistoryScrollView: View {
    let onClose: () -> Void

    @EnvironmentObject private var game: GameModel
    @State private var facts: [HistoryFact] = []

    var body: some View {
        FrameScreen(dim: 0.62) { m in
            let frame = paperFrame(m)
            ZStack {
                paper(m, frame: frame)
                ArrowButton(title: L10n.text("map.close"), m: m, bottom: Double(frame.arrowBottom), action: onClose)
            }
        }
        .onAppear {
            facts = game.historyFacts()
            SoundPlayback.shared.effect("ui_paper_open")
        }
        .onDisappear { SoundPlayback.shared.effect("ui_paper_close") }
    }

    /// На полном кадре лист остаётся 1040×2200 с верхом на 80. Короткий телефон сжимает его в видимую полосу.
    private func paperFrame(_ m: FrameMapper) -> (centerY: CGFloat, width: CGFloat, height: CGFloat, arrowBottom: CGFloat) {
        let band = FrameEdges.visibleY(viewHeight: m.size.height, originY: m.origin.y, scale: m.scale)
        let safeDesign = ScreenInsets.bottom / max(m.scale, 0.01)
        let arrowBottom = FrameEdges.arrowBottom(visibleBottom: band.bottom, safeDesign: safeDesign, preferred: 2470)
        var top: CGFloat = 80
        var height: CGFloat = 2200
        if top < band.top + 12 || top + height > arrowBottom - 24 {
            top = band.top + 16
            height = max(1200, min(2200, arrowBottom - 36 - top))
        }
        return (top + height / 2, 1040, height, arrowBottom)
    }

    private func paper(_ m: FrameMapper, frame: (centerY: CGFloat, width: CGFloat, height: CGFloat, arrowBottom: CGFloat)) -> some View {
        let width = m.length(Double(frame.width))
        let height = m.length(Double(frame.height))
        let sheet = UIArt.entry("sheet")
        return ZStack(alignment: .top) {
            RoundedRectangle(cornerRadius: m.length(18), style: .continuous)
                .fill(Theme.paper)
                .overlay(RoundedRectangle(cornerRadius: m.length(18), style: .continuous)
                    .stroke(Theme.paperEdge, lineWidth: max(1, m.length(3))))
            Image(uiImage: HUDImages.image(sheet.image))
                .resizable()
                .scaledToFit()
                .frame(width: width)
                .accessibilityHidden(true)
            ScrollView {
                VStack(alignment: .leading, spacing: m.length(28)) {
                    Text(L10n.text("history.title"))
                        .font(Ink.title(m.length(64)))
                        .foregroundStyle(Ink.brown)
                        .accessibilityAddTraits(.isHeader)
                    if facts.isEmpty {
                        Text(L10n.text("history.empty"))
                            .font(Ink.font("hand", size: m.length(44)))
                            .foregroundStyle(Ink.pencil)
                            .fixedSize(horizontal: false, vertical: true)
                    } else {
                        let chapters = facts.map(\.chapterTitle)
                        ForEach(Array(facts.enumerated()), id: \.element.id) { index, fact in
                            if index == 0 || chapters[index] != chapters[index - 1] {
                                Text(fact.chapterTitle)
                                    .font(Ink.title(m.length(40)))
                                    .foregroundStyle(Ink.brown.opacity(0.8))
                            }
                            factBlock(fact, m: m)
                                .id(fact.id)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, m.length(24))
            }
            .scrollPosition(id: Binding(
                get: { game.historyAnchor },
                set: { game.historyAnchor = $0 }
            ))
            .padding(.horizontal, m.length(48))
            .padding(.vertical, m.length(56))
        }
        .frame(width: width, height: height)
        .position(m.point(585, Double(frame.centerY)))
        .accessibilityElement(children: .contain)
    }

    @ViewBuilder
    private func factBlock(_ fact: HistoryFact, m: FrameMapper) -> some View {
        VStack(alignment: .leading, spacing: m.length(12)) {
            Text(fact.heading)
                .font(Ink.title(m.length(48)))
                .foregroundStyle(Ink.brown)
                .fixedSize(horizontal: false, vertical: true)
            pictures(fact, m: m)
            Text(fact.text)
                .font(Ink.font("hand", size: m.length(42)))
                .foregroundStyle(Ink.pencil)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func pictures(_ fact: HistoryFact, m: FrameMapper) -> some View {
        let figure = residentImage(fact)
        let place = widePlace(fact)
        if figure != nil || place != nil {
            let both = figure != nil && place != nil
            HStack(alignment: .bottom, spacing: m.length(16)) {
                if let figure {
                    Image(uiImage: figure)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: m.length(both ? 340 : 640), maxHeight: m.length(both ? 520 : 780))
                        .accessibilityHidden(true)
                }
                if let place {
                    Image(uiImage: place)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: m.length(both ? 560 : 900), maxHeight: m.length(both ? 400 : 520))
                        .accessibilityHidden(true)
                }
            }
        }
    }

    private func residentImage(_ fact: HistoryFact) -> UIImage? {
        guard let id = fact.residentID else { return nil }
        let story = StoryConfig.load(chapter: fact.chapterID)
        guard let resident = story.residents.first(where: { $0.id == id }) else { return nil }
        return ResidentLibrary.figure(for: resident, assetsFolder: fact.assetsFolder)?.image
    }

    /// Узкий ящик не растягиваем на весь лист. Широкая картинка места показывается целиком.
    private func widePlace(_ fact: HistoryFact) -> UIImage? {
        guard let id = fact.placeID,
              let image = JournalAssets.placeImage(id, chapterFolder: fact.assetsFolder),
              image.size.height > 0,
              image.size.width / image.size.height >= 0.7 else { return nil }
        return image
    }
}
