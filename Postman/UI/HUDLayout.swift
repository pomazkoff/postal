import SwiftUI
import UIKit
import CoreText

/// Раскладка HUD в координатах кадра макета 1170×2532 (ui/v3).
/// Файл GameAssets/UI/hud_layout.json генерирует tools/build_watch_assets.py вместе с картинками часов.
struct HUDLayout: Decodable {
    struct TextSpec: Decodable {
        let cx: Double
        let cy: Double
        /// Центр строки (ascent+descent) — так SwiftUI центрирует Text; глифы при этом встают как в макете.
        let lineCY: Double
        let size: Double
        let font: String
        let weight: Double?
        let maxWidth: Double?
        let squeezeX: Double?
        let rotation: Double?
        let text: String?
    }

    struct Halo: Decodable {
        let cx: Double
        let cy: Double
        let r: Double
        let opacity: Double
    }

    /// Картинка часов (с ниткой и запечённой тенью) + где на ней тексты.
    struct WatchState: Decodable {
        let image: String
        let x: Double
        let y: Double
        let width: Double
        let height: Double
        /// [x, y, w, h] — корпус часов: зона тапа.
        let body: [Double]
        let halo: Halo
        let today: TextSpec
        let todayLabel: TextSpec?
        let total: TextSpec?
        let totalLabel: TextSpec?
    }

    struct Rect: Decodable {
        let x: Double
        let y: Double
        let width: Double
        let height: Double
    }

    struct RightAnchored: Decodable {
        let right: Double
        let y: Double
        let width: Double
        let height: Double
    }

    struct Telegram: Decodable {
        let collapsed: RightAnchored
        let expanded: RightAnchored
    }

    struct Dim: Decodable {
        let brightness: Double
        let saturation: Double
        let hangingLayer: Double
    }

    let frame: [Double]
    let collapsed: WatchState
    let expanded: WatchState
    let distanceTag: Rect
    let telegram: Telegram

    /// Приглушение мира и «висящего» слоя при раскрытых часах (ui-v3-notes.md).
    static let dim = Dim(brightness: 0.52, saturation: 0.45, hangingLayer: 0.78)

    static let shared: HUDLayout = {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("UI/hud_layout.json")
        do {
            return try JSONDecoder().decode(HUDLayout.self, from: Data(contentsOf: url))
        } catch {
            fatalError("Не удалось прочитать \(url.lastPathComponent): \(error)")
        }
    }()
}

/// Перевод координат макета в точки экрана — так же, как SKScene с .aspectFill
/// (масштаб по большей стороне, кадр по центру, лишнее обрезается).
struct FrameMapper {
    let size: CGSize
    let scale: CGFloat
    let origin: CGPoint

    init(size: CGSize, frame: CGSize = CGSize(width: 1170, height: 2532)) {
        self.size = size
        let s = max(size.width / frame.width, size.height / frame.height)
        scale = s
        origin = CGPoint(x: (size.width - frame.width * s) / 2, y: (size.height - frame.height * s) / 2)
    }

    func point(_ x: Double, _ y: Double) -> CGPoint {
        CGPoint(x: origin.x + CGFloat(x) * scale, y: origin.y + CGFloat(y) * scale)
    }

    func length(_ v: Double) -> CGFloat { CGFloat(v) * scale }

    /// Центр прямоугольника макета (для .position).
    func center(x: Double, y: Double, width: Double, height: Double) -> CGPoint {
        point(x + width / 2, y + height / 2)
    }
}

/// Картинки HUD из GameAssets (PNG с альфой), с кэшем.
enum HUDImages {
    private static var cache: [String: UIImage] = [:]

    static func image(_ relativePath: String) -> UIImage {
        if let cached = cache[relativePath] { return cached }
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent(relativePath + ".png")
        let image = UIImage(contentsOfFile: url.path) ?? UIImage()
        cache[relativePath] = image
        return image
    }
}

/// Шрифты макета (OFL): Oswald (окошко свёрнутых часов), Yeseva One (цифры), Kurale (подписи).
/// Лежат в GameAssets/Fonts, регистрируются при запуске — Info.plist (UIAppFonts) не нужен.
enum HUDFonts {
    private static var descriptors: [String: CTFontDescriptor] = [:]
    private static var registered = false

    static func registerAll() {
        guard !registered else { return }
        registered = true
        let dir = WorldConfigLoader.assetsRoot.appendingPathComponent("Fonts")
        let files = (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? []
        for url in files where ["ttf", "otf"].contains(url.pathExtension.lowercased()) {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            if let list = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as? [CTFontDescriptor],
               let first = list.first {
                descriptors[url.deletingPathExtension().lastPathComponent] = first
            }
        }
    }

    /// key — имя файла без расширения (Oswald, YesevaOne, Kurale); weight — ось wght вариативного шрифта.
    static func font(_ key: String, size: CGFloat, weight: Double? = nil) -> Font {
        registerAll()
        guard let base = descriptors[key] else {
            return .system(size: size, weight: .bold, design: .serif)
        }
        var descriptor = base
        if let weight {
            let wghtTag = 0x7767_6874 // 'wght'
            let attrs = [kCTFontVariationAttribute as String: [wghtTag: weight]] as CFDictionary
            descriptor = CTFontDescriptorCreateCopyWithAttributes(base, attrs)
        }
        return Font(CTFontCreateWithFontDescriptor(descriptor, size, nil))
    }
}
