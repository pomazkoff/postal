import SwiftUI

/// Бумажная карточка «Первый почтовый рейс». Закрытие возвращает к тому, что уже было на экране.
struct FirstMailCard: View {
    let reading: FirstMailReading
    let onContinue: () -> Void

    var body: some View {
        FrameScreen(dim: 0.55) { m in
            ZStack {
                PlacedArt(name: "plaque", m: m, at: CGPoint(x: 585, y: 360), scale: 0.62) { e, f in
                    Text(L10n.text("firstmail.title"))
                        .font(Ink.title(64 * f))
                        .foregroundStyle(Ink.brown)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .minimumScaleFactor(0.6)
                        .frame(width: e.body.width * 0.8 * f)
                        .position(x: e.anchor("text").x * f, y: e.anchor("text").y * f)
                        .accessibilityAddTraits(.isHeader)
                }
                .allowsHitTesting(false)

                PaperArt(name: "sheet", k: m.scale, scale: 0.78) { size in
                    VStack(alignment: .leading, spacing: m.length(22)) {
                        Text(L10n.text("firstmail.body"))
                            .font(Ink.font("hand", size: m.length(40)))
                            .foregroundStyle(Ink.pencil)
                            .fixedSize(horizontal: false, vertical: true)
                        Text(L10n.text(reading.key))
                            .font(Ink.font("hand", size: m.length(40)))
                            .foregroundStyle(Ink.brown)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(width: size.width, height: size.height, alignment: .topLeading)
                }
                .position(m.point(585, 1280))
                .allowsHitTesting(false)

                ArrowButton(title: L10n.text("firstmail.continue"), m: m, bottom: 2360, action: onContinue)
            }
        }
        .accessibilityElement(children: .contain)
    }
}

extension FirstMailReading {
    var key: String {
        switch self {
        case .inBag: return "firstmail.inBag"
        case .atPost: return "firstmail.atPost"
        case .delivered: return "firstmail.delivered"
        case .unreachable: return "firstmail.unreachable"
        }
    }
}
