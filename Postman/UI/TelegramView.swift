import SwiftUI

/// Телеграмма-задание в правом столбе (ui/v3): пластилиновый бланк card_telegram, текст живой.
struct TelegramView: View {
    let text: String
    let rect: HUDLayout.RightAnchored
    let m: FrameMapper

    var body: some View {
        let e = UIArt.entry("card_telegram")
        let scale = CGFloat(rect.width) / e.body.width
        let k = m.scale
        let center = CGPoint(x: rect.right - rect.width / 2, y: rect.y + rect.height / 2)
        PaperArt(name: "card_telegram", k: k, scale: scale) { size in
            VStack(spacing: m.length(8)) {
                Text(L10n.text("telegram.title"))
                    .font(HUDFonts.font("Oswald", size: m.length(26), weight: 600))
                    .kerning(m.length(3))
                    .foregroundStyle(Ink.stampRed)
                    .lineLimit(1).minimumScaleFactor(0.6)
                Text(text.uppercased())
                    .font(HUDFonts.font("Oswald", size: m.length(30), weight: 420))
                    .foregroundStyle(Ink.brown)
                    .multilineTextAlignment(.center)
                    .lineSpacing(m.length(2))
                    .minimumScaleFactor(0.6)
            }
            .frame(width: size.width, height: size.height)
        }
        .pinned(size: CGSize(width: e.width * k * scale, height: e.height * k * scale),
                anchor: CGPoint(x: e.bodyCenter.x * k * scale, y: e.bodyCenter.y * k * scale),
                at: m.point(center.x, center.y), rotation: -4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.format("telegram.a11y", text))
    }
}

/// Бирка «1 760 / до Звонарни» (левый верх, ui/v3) — пластилиновая бирка tag на гвоздике.
struct DistanceTagView: View {
    let settlement: Settlement?
    let stepsLeft: Int?
    let rect: HUDLayout.Rect
    let m: FrameMapper

    var body: some View {
        let e = UIArt.entry("tag")
        let scale = CGFloat(rect.width) / e.body.width
        let k = m.scale
        let center = CGPoint(x: rect.x + rect.width / 2, y: rect.y + rect.height / 2)
        let line1: String
        let line2: String
        if let settlement, let stepsLeft {
            line1 = Format.steps(stepsLeft)
            line2 = L10n.format("distance.to", settlement.nameGenitive)
        } else {
            line1 = L10n.text("distance.done.place")
            line2 = "\(Format.chapters(1)) \(L10n.text("distance.done.tail"))"
        }
        return TagArt(line1: line1, line2: line2, k: k, scale: scale, size1: 60, size2: 40)
            .pinned(size: CGSize(width: e.width * k * scale, height: e.height * k * scale),
                    anchor: CGPoint(x: e.bodyCenter.x * k * scale, y: e.bodyCenter.y * k * scale),
                    at: m.point(center.x, center.y), rotation: 7)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(line2): \(line1)")
    }
}
