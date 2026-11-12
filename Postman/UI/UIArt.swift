import SwiftUI
import UIKit

/// Пластилиновые элементы интерфейса главы 1: GameAssets/UI/ui_ch1.json + UI/ch1/*.png
/// (генерирует tools/build_ch1_ui_assets.py из исходников ui/v4/cut и ui/v3/cut).
/// Размеры и якоря — в пикселях кадра макета 1170×2532: на экран переводятся через FrameMapper.
struct UIArt: Decodable {
    struct Entry: Decodable {
        let image: String
        let width: CGFloat
        let height: CGFloat
        let anchors: [String: [CGFloat]]

        var size: CGSize { CGSize(width: width, height: height) }

        func anchor(_ key: String) -> CGPoint {
            guard let a = anchors[key], a.count >= 2 else { return CGPoint(x: width / 2, y: height / 2) }
            return CGPoint(x: a[0], y: a[1])
        }

        /// Прямоугольник самого предмета без тени: [x, y, w, h].
        var body: CGRect {
            guard let b = anchors["body"], b.count == 4 else { return CGRect(origin: .zero, size: size) }
            return CGRect(x: b[0], y: b[1], width: b[2], height: b[3])
        }

        var bodyCenter: CGPoint { CGPoint(x: body.midX, y: body.midY) }

        func value(_ key: String) -> CGFloat { anchors[key]?.first ?? 0 }
    }

    let art: [String: Entry]

    static let shared: UIArt = {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("UI/ui_ch1.json")
        guard let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode(UIArt.self, from: data) else {
            assertionFailure("Нет UI/ui_ch1.json — запустите tools/build_ch1_ui_assets.py")
            return UIArt(art: [:])
        }
        return decoded
    }()

    static func entry(_ name: String) -> Entry {
        shared.art[name] ?? Entry(image: "UI/ch1/" + name, width: 100, height: 100, anchors: [:])
    }
}

/// Картинка из UI/ch1 в масштабе кадра (k — точки экрана на пиксель кадра, × scale) +
/// живые подписи поверх в координатах картинки.
struct ArtView<Overlay: View>: View {
    let name: String
    let k: CGFloat
    var scale: CGFloat = 1
    var flipX = false
    @ViewBuilder var overlay: (UIArt.Entry, CGFloat) -> Overlay

    var body: some View {
        let e = UIArt.entry(name)
        let f = k * scale
        ZStack(alignment: .topLeading) {
            Image(uiImage: HUDImages.image(e.image))
                .resizable()
                .interpolation(.high)
                .frame(width: e.width * f, height: e.height * f)
                .scaleEffect(x: flipX ? -1 : 1, y: 1)
            overlay(e, f)
        }
        .frame(width: e.width * f, height: e.height * f, alignment: .topLeading)
    }
}

extension ArtView where Overlay == EmptyView {
    init(name: String, k: CGFloat, scale: CGFloat = 1, flipX: Bool = false) {
        self.init(name: name, k: k, scale: scale, flipX: flipX) { _, _ in EmptyView() }
    }
}

extension View {
    /// Ставит вид размера `size` так, чтобы его точка `anchor` (в точках вида) оказалась в `point`,
    /// и поворачивает вокруг этой точки.
    func pinned(size: CGSize, anchor: CGPoint, at point: CGPoint, rotation: Double = 0) -> some View {
        let unit = UnitPoint(x: size.width > 0 ? anchor.x / size.width : 0.5,
                             y: size.height > 0 ? anchor.y / size.height : 0.5)
        return self
            .frame(width: size.width, height: size.height)
            .rotationEffect(.degrees(rotation), anchor: unit)
            .position(x: point.x + size.width / 2 - anchor.x, y: point.y + size.height / 2 - anchor.y)
    }
}

/// Пластилиновый элемент, поставленный якорем в точку кадра макета.
struct PlacedArt<Overlay: View>: View {
    let name: String
    let m: FrameMapper
    /// Якорь картинки: ключ из ui_ch1.json или "center" (центр предмета без тени).
    var anchor: String = "center"
    /// Точка кадра 1170×2532.
    let at: CGPoint
    var scale: CGFloat = 1
    var rotation: Double = 0
    var flipX = false
    var onTap: (() -> Void)? = nil
    @ViewBuilder var overlay: (UIArt.Entry, CGFloat) -> Overlay

    var body: some View {
        let e = UIArt.entry(name)
        let f = m.scale * scale
        let a = Self.anchorPoint(anchor, in: e)
        ArtView(name: name, k: m.scale, scale: scale, flipX: flipX, overlay: overlay)
            .contentShape(Rectangle())
            .onTapGesture { onTap?() }
            .allowsHitTesting(onTap != nil)
            .pinned(size: CGSize(width: e.width * f, height: e.height * f),
                    anchor: CGPoint(x: a.x * f, y: a.y * f),
                    at: m.point(at.x, at.y), rotation: rotation)
    }

    /// "center" — центр предмета, "bottom" — середина низа предмета, "origin" — левый верх картинки,
    /// иначе — именованный якорь из ui_ch1.json.
    static func anchorPoint(_ key: String, in e: UIArt.Entry) -> CGPoint {
        switch key {
        case "center": return e.bodyCenter
        case "bottom": return CGPoint(x: e.body.midX, y: e.body.maxY)
        case "top": return CGPoint(x: e.body.midX, y: e.body.minY)
        case "origin": return .zero
        default: return e.anchor(key)
        }
    }
}

extension PlacedArt where Overlay == EmptyView {
    init(name: String, m: FrameMapper, anchor: String = "center", at: CGPoint,
         scale: CGFloat = 1, rotation: Double = 0, flipX: Bool = false, onTap: (() -> Void)? = nil) {
        self.init(name: name, m: m, anchor: anchor, at: at, scale: scale, rotation: rotation, flipX: flipX,
                  onTap: onTap) { _, _ in
            EmptyView()
        }
    }
}

/// Шрифты и цвета чернил писем.
enum Ink {
    static let pencil = Color(red: 0.23, green: 0.22, blue: 0.24)
    static let graphite = Color(red: 0.30, green: 0.29, blue: 0.31)
    static let violet = Color(red: 0.36, green: 0.22, blue: 0.55)
    static let brown = Color(red: 0.27, green: 0.18, blue: 0.11)
    static let chalk = Color(red: 0.95, green: 0.92, blue: 0.84)
    static let stampRed = Color(red: 0.62, green: 0.20, blue: 0.14)

    /// Почерк Мити (Neucha), машинка/бланк (Oswald), лента (Oswald), фиолетовый химкарандаш (Kurale).
    static func font(_ style: String, size: CGFloat) -> Font {
        switch style {
        case "hand": return HUDFonts.font("Neucha", size: size)
        case "draft", "tape": return HUDFonts.font("Oswald", size: size, weight: 420)
        case "violet": return HUDFonts.font("Kurale", size: size)
        default: return HUDFonts.font("Kurale", size: size)
        }
    }

    static func color(_ style: String) -> Color {
        switch style {
        case "violet": return violet
        case "draft", "tape": return brown
        default: return pencil
        }
    }

    static func label(_ size: CGFloat) -> Font { HUDFonts.font("Kurale", size: size) }
    static func title(_ size: CGFloat) -> Font { HUDFonts.font("YesevaOne", size: size) }
}

/// Бумажная бирка (tag / tag_small) с двумя живыми строками.
struct TagArt: View {
    let line1: String
    let line2: String
    let k: CGFloat
    var small = false
    var scale: CGFloat = 1
    var size1: CGFloat = 50
    var size2: CGFloat = 38

    var body: some View {
        ArtView(name: small ? "tag_small" : "tag", k: k, scale: scale) { e, f in
            let w = e.value("textWidth") * f
            let l1 = e.anchor("line1"), l2 = e.anchor("line2")
            Text(line1)
                .font(Ink.title(size1 * f * (small ? 0.62 : 1)))
                .foregroundStyle(Ink.brown)
                .lineLimit(1).minimumScaleFactor(0.45)
                .frame(width: w)
                .position(x: l1.x * f, y: l1.y * f)
            Text(line2)
                .font(Ink.label(size2 * f * (small ? 0.62 : 1)))
                .foregroundStyle(Ink.brown.opacity(0.85))
                .lineLimit(1).minimumScaleFactor(0.45)
                .frame(width: w)
                .position(x: l2.x * f, y: l2.y * f)
        }
    }
}

/// Полноэкранный слой в координатах кадра макета (как сцена: aspectFill).
struct FrameScreen<Content: View>: View {
    var dim: Double = 0.62
    @ViewBuilder var content: (FrameMapper) -> Content

    var body: some View {
        GeometryReader { geo in
            let m = FrameMapper(size: geo.size)
            ZStack {
                // Мир приглушён: тёмная бирюза из палитры (style-guide §3).
                Color(red: 0.03, green: 0.09, blue: 0.10).opacity(dim)
                    .contentShape(Rectangle())
                content(m)
            }
            .frame(width: geo.size.width, height: geo.size.height)
        }
        .ignoresSafeArea()
    }
}

/// Деревянная стрелка-указатель с надписью («В путь», «Дальше») — кнопка.
struct ArrowButton: View {
    let title: String
    let m: FrameMapper
    var right: Double = 1136
    var bottom: Double = 2420
    var flip = false
    let action: () -> Void

    var body: some View {
        let e = UIArt.entry("arrow")
        let b = e.body
        // Правый нижний угол предмета (без тени) — в (right, bottom) кадра.
        let center = CGPoint(x: CGFloat(right) - b.width / 2, y: CGFloat(bottom) - b.height / 2)
        Button(action: action) {
            ArtView(name: "arrow", k: m.scale, flipX: flip) { e, f in
                let t = e.anchor("text")
                Text(title)
                    .font(Ink.title(44 * f))
                    .foregroundStyle(Ink.chalk)
                    .shadow(color: .black.opacity(0.35), radius: 0, x: 0, y: 1.5 * f)
                    .lineLimit(1).minimumScaleFactor(0.5)
                    .frame(width: b.width * 0.62 * f)
                    .position(x: (flip ? e.width - t.x : t.x) * f, y: t.y * f)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PressStyle())
        .pinned(size: CGSize(width: e.width * m.scale, height: e.height * m.scale),
                anchor: CGPoint(x: e.bodyCenter.x * m.scale, y: e.bodyCenter.y * m.scale),
                at: m.point(center.x, center.y))
        .accessibilityLabel(title)
    }
}

/// Нажатие пластилина: чуть вдавить.
struct PressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.95 : 1)
            .brightness(configuration.isPressed ? -0.05 : 0)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { _, down in
                if down { SoundPlayback.shared.effect("ui_wood_tap") }
            }
    }
}

/// Бумага (sheet / sheet_form / sheet_telegram / card_telegram) с текстом в области textTL…textBR.
struct PaperArt<Content: View>: View {
    let name: String
    let k: CGFloat
    var scale: CGFloat = 1
    @ViewBuilder var content: (CGSize) -> Content

    var body: some View {
        ArtView(name: name, k: k, scale: scale) { e, f in
            let tl = e.anchor("textTL"), br = e.anchor("textBR")
            let size = CGSize(width: (br.x - tl.x) * f, height: (br.y - tl.y) * f)
            content(size)
                .frame(width: size.width, height: size.height, alignment: .topLeading)
                .position(x: (tl.x + br.x) / 2 * f, y: (tl.y + br.y) / 2 * f)
        }
    }
}
