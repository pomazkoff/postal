import Foundation
import CoreGraphics
import CoreImage
import CoreImage.CIFilterBuiltins
import UIKit

/// Данные карты «Пергамент» (GameAssets/UI/map/map.json, tools/build_map_assets.py).
/// Координаты — кадр 1170×2532. Дорога — полилиния Почта→Седло с параметризацией по длине дуги:
/// шаг s главы ↔ доля дороги s / lengthSteps (реальные пропорции, а не «как удобно художнику»).
struct ParchmentMap: Decodable {
    struct Field: Decodable {
        let image: String
        let decodeScale: Double
        let decodeBias: Double
    }
    struct Puffs: Decodable {
        let levels: Int
        let maxT: Double
        let image: String
        let aspect: Double
        /// points[уровень] = [[x, y, ширина, flip]]
        let points: [[[Double]]]
    }
    struct Place: Decodable {
        let id: String
        let name: String
        let step: Int
        let road: [Double]
        let icon: String
        /// Низ-центр иконки.
        let x: Double
        let y: Double
        let w: Double
        let h: Double
        var iconRect: CGRect { CGRect(x: x - w / 2, y: y - h, width: w, height: h) }
        var roadPoint: CGPoint { CGPoint(x: road[0], y: road[1]) }
    }
    struct Sprite: Decodable {
        let image: String
        let w: Double
        let h: Double
    }

    let size: [Double]
    let lengthSteps: Int
    let roadLength: Double
    let road: [[Double]]
    let aheadPx: Double
    let softPx: Double
    let field: Field
    let puffs: Puffs
    let settlements: [Place]
    let postman: Sprite
    let compass: Sprite
    let chrome: [[Double]]

    private static var cached: ParchmentMap?
    private static var loaded = false

    static var shared: ParchmentMap? {
        if !loaded {
            loaded = true
            cached = load()
        }
        return cached
    }

    static func invalidate() {
        loaded = false
        cached = nil
    }

    private static func load() -> ParchmentMap? {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("UI/map/map.json")
        let data = ContentLocalizer.data(at: url, kind: .map)
        guard !data.isEmpty else { return nil }
        return try? JSONDecoder().decode(ParchmentMap.self, from: data)
    }

    var points: [CGPoint] { road.map { CGPoint(x: $0[0], y: $0[1]) } }
    var chromeRects: [CGRect] { chrome.map { CGRect(x: $0[0], y: $0[1], width: $0[2] - $0[0], height: $0[3] - $0[1]) } }

    func fraction(step: Int) -> Double {
        guard lengthSteps > 0 else { return 0 }
        return min(1, max(0, Double(step) / Double(lengthSteps)))
    }

    /// Порог «открытости» T0 (доля дороги): цвет там, где поле ≤ T0, карандаш — где ≥ T0 + soft.
    func revealThreshold(step: Int) -> Double {
        let f = fraction(step: step)
        return f >= 1 ? 2 : f + aheadPx / max(1, roadLength)
    }
    var softFraction: Double { softPx / max(1, roadLength) }

    func puffPoints(threshold t0: Double) -> [[Double]] {
        guard t0 < puffs.maxT, puffs.levels > 0, !puffs.points.isEmpty else { return [] }
        let i = Int((t0 / puffs.maxT * Double(puffs.levels)).rounded())
        return puffs.points[min(max(0, i), puffs.points.count - 1)]
    }
}

/// Дорога с длиной дуги: точка по доле и префикс-полилиния (пройденное).
struct RoadGeometry {
    let points: [CGPoint]
    let cumulative: [Double]
    var length: Double { cumulative.last ?? 0 }

    init(_ points: [CGPoint]) {
        self.points = points
        var cum: [Double] = [0]
        for i in 1..<max(1, points.count) {
            let a = points[i - 1], b = points[i]
            cum.append(cum[i - 1] + Double(hypot(b.x - a.x, b.y - a.y)))
        }
        self.cumulative = cum
    }

    private func locate(_ fraction: Double) -> (Int, Double) {
        guard points.count > 1, length > 0 else { return (0, 0) }
        let s = min(1, max(0, fraction)) * length
        var lo = 0, hi = cumulative.count - 1
        while hi - lo > 1 {
            let mid = (lo + hi) / 2
            if cumulative[mid] <= s { lo = mid } else { hi = mid }
        }
        let seg = max(1e-6, cumulative[lo + 1] - cumulative[lo])
        return (lo, (s - cumulative[lo]) / seg)
    }

    func point(at fraction: Double) -> CGPoint {
        guard points.count > 1 else { return points.first ?? .zero }
        let (i, t) = locate(fraction)
        let a = points[i], b = points[i + 1]
        return CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t)
    }

    /// Полилиния от начала до доли fraction.
    func prefix(to fraction: Double) -> [CGPoint] {
        guard points.count > 1, fraction > 0 else { return [] }
        let (i, _) = locate(fraction)
        return Array(points[0...i]) + [point(at: fraction)]
    }
}

/// Раскладка бирок без наложений при любом прогрессе: жадно, по приоритету
/// (сначала «Вы здесь», потом следующая остановка, пройденные, дальние), из нескольких мест вокруг иконки.
enum ParchmentLayout {
    static let tagScale: CGFloat = 300.0 / 287.0
    /// Прямоугольник «тела» маленькой бирки (без тени) — 208×110 при tagScale.
    static var tagSize: CGSize {
        let e = UIArt.entry("tag_small")
        return CGSize(width: e.body.width * tagScale, height: e.body.height * tagScale)
    }

    struct Result {
        /// Центр тела бирки для каждого поселения (по id) и для «Вы здесь».
        var tags: [String: CGPoint] = [:]
        var postmanTag: CGPoint = .zero
    }

    static func layout(map: ParchmentMap, postmanFeet: CGPoint, frame: CGSize, nextID: String?,
                       reachedStep: Int) -> Result {
        let ts = tagSize
        var obstacles = map.chromeRects
        obstacles += map.settlements.map { $0.iconRect.insetBy(dx: $0.w * 0.12, dy: $0.h * 0.1) }
        let fig = CGRect(x: postmanFeet.x - map.postman.w * 0.4, y: postmanFeet.y - map.postman.h,
                         width: map.postman.w * 0.8, height: map.postman.h)
        obstacles.append(fig)
        let bounds = CGRect(origin: .zero, size: frame).insetBy(dx: 12, dy: 12)

        func rect(_ c: CGPoint) -> CGRect {
            CGRect(x: c.x - ts.width / 2, y: c.y - ts.height / 2, width: ts.width, height: ts.height)
        }
        func cost(_ c: CGPoint) -> CGFloat {
            let r = rect(c)
            var s: CGFloat = 0
            for o in obstacles {
                let i = r.intersection(o)
                if !i.isNull { s += i.width * i.height }
            }
            let inside = r.intersection(bounds)
            s += (r.width * r.height - (inside.isNull ? 0 : inside.width * inside.height)) * 4
            return s
        }
        func pick(_ candidates: [CGPoint]) -> CGPoint {
            var best = candidates[0], bestCost = CGFloat.greatestFiniteMagnitude
            for (i, c) in candidates.enumerated() {
                let v = cost(c) + CGFloat(i) * 0.5     // при равенстве — раньше в списке
                if v < bestCost { best = c; bestCost = v }
                if v < 1 { break }
            }
            obstacles.append(rect(best).insetBy(dx: -6, dy: -6))
            return best
        }

        var result = Result()
        let p = postmanFeet
        let dx = map.postman.w * 0.4 + ts.width / 2 + 8
        result.postmanTag = pick([
            CGPoint(x: p.x - dx, y: p.y - map.postman.h * 0.45),
            CGPoint(x: p.x + dx, y: p.y - map.postman.h * 0.45),
            CGPoint(x: p.x - dx, y: p.y - map.postman.h * 0.05),
            CGPoint(x: p.x + dx, y: p.y - map.postman.h * 0.05),
            CGPoint(x: p.x - dx, y: p.y - map.postman.h * 0.85),
            CGPoint(x: p.x + dx, y: p.y - map.postman.h * 0.85),
            CGPoint(x: p.x, y: p.y + ts.height / 2 + 10),
            CGPoint(x: p.x, y: p.y - map.postman.h - ts.height / 2 - 6),
        ])

        let order = map.settlements.sorted { a, b in
            func rank(_ s: ParchmentMap.Place) -> Int {
                if s.id == nextID { return 0 }
                return s.step <= reachedStep ? 1 : 2
            }
            return (rank(a), a.step) < (rank(b), b.step)
        }
        for s in order {
            let r = s.iconRect
            let side: CGFloat = r.midX > frame.width / 2 ? 1 : -1      // наружу от дороги
            let below = r.maxY + ts.height / 2 - 4
            result.tags[s.id] = pick([
                CGPoint(x: r.midX - side * 10, y: below),
                CGPoint(x: r.midX + side * (r.width / 2 + ts.width / 2 - 10), y: r.midY + r.height * 0.15),
                CGPoint(x: r.midX - side * (r.width / 2 + ts.width / 2 - 10), y: r.midY + r.height * 0.15),
                CGPoint(x: r.midX, y: r.minY - ts.height / 2 + 6),
                CGPoint(x: r.midX + side * 60, y: below + ts.height * 0.7),
                CGPoint(x: r.midX - side * 60, y: below + ts.height * 0.7),
                CGPoint(x: r.midX + side * (r.width / 2 + ts.width / 2 - 10), y: r.minY + 10),
                CGPoint(x: r.midX - side * (r.width / 2 + ts.width / 2 - 10), y: r.minY + 10),
            ])
        }
        return result
    }
}

/// Открытая часть карты: цвет vs карандаш по маске длины дуги (CoreImage, без шейдеров).
enum ParchmentReveal {
    private static let raw: [CIImageOption: Any] = [.colorSpace: NSNull()]
    private static let context = CIContext(options: [.workingColorSpace: NSNull(), .cacheIntermediates: false])
    private static let images: (color: CIImage, pencil: CIImage, field: CIImage)? = {
        let root = WorldConfigLoader.assetsRoot.appendingPathComponent("UI/map")
        guard let c = CIImage(contentsOf: root.appendingPathComponent("map_color.jpg"), options: raw),
              let p = CIImage(contentsOf: root.appendingPathComponent("map_pencil.jpg"), options: raw),
              let f = CIImage(contentsOf: root.appendingPathComponent("map_field.png"), options: raw) else { return nil }
        return (c, p, f)
    }()

    static func colorImage() -> UIImage? {
        UIImage(contentsOfFile: WorldConfigLoader.assetsRoot.appendingPathComponent("UI/map/map_color.jpg").path)
    }

    /// Синхронно; звать не с главного потока.
    static func render(map: ParchmentMap, threshold t0: Double) -> UIImage? {
        guard let images else { return nil }
        let extent = images.color.extent
        if t0 > 1.5 { return colorImage() }
        let fe = images.field.extent
        let field = images.field.clampedToExtent()
            .transformed(by: CGAffineTransform(scaleX: extent.width / fe.width, y: extent.height / fe.height))
            .cropped(to: extent)
        // mask = clamp((T0 + soft − (S·r + B)) / soft)
        let soft = max(1e-4, map.softFraction)
        let a = CGFloat(-map.field.decodeScale / soft)
        let b = CGFloat((t0 + soft - map.field.decodeBias) / soft)
        let matrix = CIFilter.colorMatrix()
        matrix.inputImage = field
        matrix.rVector = CIVector(x: a, y: 0, z: 0, w: 0)
        matrix.gVector = CIVector(x: a, y: 0, z: 0, w: 0)
        matrix.bVector = CIVector(x: a, y: 0, z: 0, w: 0)
        matrix.aVector = CIVector(x: 0, y: 0, z: 0, w: 0)
        matrix.biasVector = CIVector(x: b, y: b, z: b, w: 1)
        let clamp = CIFilter.colorClamp()
        clamp.inputImage = matrix.outputImage
        clamp.minComponents = CIVector(x: 0, y: 0, z: 0, w: 0)
        clamp.maxComponents = CIVector(x: 1, y: 1, z: 1, w: 1)
        let blend = CIFilter.blendWithMask()
        blend.inputImage = images.color
        blend.backgroundImage = images.pencil
        blend.maskImage = clamp.outputImage
        guard let out = blend.outputImage,
              let cg = context.createCGImage(out, from: extent, format: .RGBA8,
                                             colorSpace: CGColorSpace(name: CGColorSpace.sRGB)) else { return nil }
        return UIImage(cgImage: cg)
    }
}
