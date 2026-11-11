import CoreGraphics
import Foundation
import UIKit

/// Два листа одной дороги. Долина уже нарисована. Горы подключаются только файлами
/// `UI/map/mountains.json` + `mountains_color.jpg` + `mountains_pencil.jpg`.
/// Пока их нет, герой второй главы остаётся на Седле этого листа, без запасной картинки.
enum MapJoin {
    /// Последняя точка дороги в `map.json`: шаг 20000, Седло.
    static let valley = CGPoint(x: 705.8, y: 480)
    /// Та же точка на листе гор. Низ листа — продолжение верха Долины.
    static let mountain = CGPoint(x: 705.8, y: 2452)
    static let mountainSize = CGSize(width: 1170, height: 2532)
    /// Сколько верхних строк Долины накрывает низ листа гор (включая ящик Седла).
    static var overlap: CGFloat { mountainSize.height - (mountain.y - valley.y) }

    static var valleyOrigin: CGPoint {
        CGPoint(x: mountain.x - valley.x, y: mountain.y - valley.y)
    }
}

/// Подпись на общем свитке. Долина в JSON уже от Почты (0). Горы в JSON — от Седла,
/// поэтому на бирке к ним один раз прибавляется globalStart. Седло остаётся 20 000, не 40 000.
enum WorldSteps {
    static func shown(local: Int, origin: Int) -> Int { origin + local }
}

/// Шаги мест главы 2. Других поселений на этом листе нет.
enum MountainPlaces {
    static let steps: [String: Int] = [
        "sedlo": 0,
        "gar": 2800,
        "penki": 6500,
        "khomut": 11000,
        "repka": 15500,
        "krivulya": 16500,
        "gorlovina": 24000,
    ]
    static let lengthSteps = 25000
    static let globalStart = 20000
}

struct MapAtlas {
    let valley: ParchmentMap
    let mountains: MountainSheet?
    let swamps: MountainSheet?
    /// Верхний левый угол листа Долины на общем холсте. Ноль, пока гор нет.
    let valleyOrigin: CGPoint
    /// Сдвиг вниз, чтобы лист болот (его низ стыкуется с верхом гор) начинался с нуля.
    let lift: CGFloat
    /// Нижние 560 px листа болот полупрозрачны: шов с горами не читается, вершины остаются.
    let swampOverlap: CGFloat
    let contentSize: CGSize

    static func make(valley: ParchmentMap, mountains: MountainSheet? = MountainSheet.load(),
                     swamps: MountainSheet? = MountainSheet.loadSwamps()) -> MapAtlas {
        guard let mountains else {
            return MapAtlas(valley: valley, mountains: nil, swamps: nil, valleyOrigin: .zero,
                            lift: 0, swampOverlap: 0,
                            contentSize: CGSize(width: valley.size[0], height: valley.size[1]))
        }
        let origin = MapJoin.valleyOrigin
        var lift: CGFloat = 0
        var overlap: CGFloat = 0
        var swampSheet = swamps
        if let swamps, let end = mountains.road.last {
            let rawY = end.y - SwampJoin.point.y
            lift = -rawY
            overlap = swamps.size.height - (SwampJoin.point.y - end.y)
            if overlap < 1 { swampSheet = nil; lift = 0; overlap = 0 }
        } else {
            swampSheet = nil
        }
        // Верх холста — y=0, верх листа болот. Низ — низ Долины после сдвига lift.
        // Высота без lift обрезает прокрутку ровно по верху гор.
        let height = origin.y + valley.size[1] + lift
        let width = max(valley.size[0], max(mountains.size.width, swampSheet?.size.width ?? 0))
        return MapAtlas(valley: valley, mountains: mountains, swamps: swampSheet, valleyOrigin: origin,
                        lift: lift, swampOverlap: overlap,
                        contentSize: CGSize(width: width, height: height))
    }

    /// Глобальный шаг: `chapter.startStep + chapterSteps`.
    func point(globalStep: Int) -> CGPoint {
        if let swamps, globalStep >= swamps.globalStart {
            let local = min(swamps.lengthSteps, globalStep - swamps.globalStart)
            let p = RoadGeometry(swamps.road).point(at: swamps.fraction(localStep: local))
            return CGPoint(x: p.x, y: p.y + lift + swampOriginY)
        }
        if let mountains, globalStep >= mountains.globalStart {
            let local = min(mountains.lengthSteps, globalStep - mountains.globalStart)
            let p = RoadGeometry(mountains.road).point(at: mountains.fraction(localStep: local))
            return CGPoint(x: p.x, y: p.y + lift)
        }
        let local = min(valley.lengthSteps, max(0, globalStep))
        let p = RoadGeometry(valley.points).point(at: valley.fraction(step: local))
        return CGPoint(x: p.x + valleyOrigin.x, y: p.y + valleyOrigin.y + lift)
    }

    /// Низ листа болот в координатах, где горы ещё стоят в нуле. Отрицательный.
    private var swampOriginY: CGFloat { swamps == nil ? 0 : -lift }

    /// Лист Долины и так на весь кадр. К герою едем только когда сверху есть продолжение.
    func centersHero(viewSize: CGSize, scale: CGFloat) -> Bool {
        guard mountains != nil || swamps != nil else { return false }
        return contentSize.height * scale > viewSize.height + 2
    }
}

enum SwampJoin {
    static let point = CGPoint(x: 619.9, y: 2373.7)
}

/// Стык листа болот с горами. Низ листа растворяется в вершины.
/// Дорога на шве сдвигается на ось пути гор, сужается до его ширины и меняет цвет,
/// без круглой заглушки поверх.
enum MarshSeam {
    /// 420 px кадра 2532 — около 140 pt на телефоне, внутри запрошенных 100–150.
    static let fadeDesignPx: CGFloat = 420

    static func apply(_ image: UIImage, road: [CGPoint], mountain: UIImage,
                      mountainRoad: [CGPoint], lift: CGFloat) -> UIImage {
        guard let cg = image.cgImage, let mountainCG = mountain.cgImage, !road.isEmpty else { return image }
        let w = cg.width, h = cg.height
        let color = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        func buffer(_ source: CGImage, width: Int, height: Int) -> (CGContext, UnsafeMutablePointer<UInt8>)? {
            guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                                      bytesPerRow: width * 4, space: color, bitmapInfo: info),
                  let data = ctx.data else { return nil }
            ctx.draw(source, in: CGRect(x: 0, y: 0, width: width, height: height))
            return (ctx, data.bindMemory(to: UInt8.self, capacity: width * height * 4))
        }
        guard let (ctx, pixels) = buffer(cg, width: w, height: h) else { return image }
        let mh = mountainCG.height
        guard let (mountainCtx, mount) = buffer(mountainCG, width: w, height: mh), mountainCG.width == w else { return image }
        _ = mountainCtx
        var original = [UInt8](repeating: 0, count: w * h * 4)
        for i in 0..<(w * h * 4) { original[i] = pixels[i] }
        func index(_ x: Int, _ imageY: Int, _ width: Int, _ height: Int) -> Int {
            ((height - 1 - imageY) * width + x) * 4
        }
        let fadePx = max(1, Int((Self.fadeDesignPx * CGFloat(h) / 2532).rounded()))
        let yStart = max(0, h - fadePx)
        let liftY = Int((lift * CGFloat(h) / 2532).rounded())
        func smooth(_ t: Float) -> Float {
            let c = min(1, max(0, t))
            return c * c * (3 - 2 * c)
        }
        func xAt(_ line: [CGPoint], _ y: CGFloat) -> CGFloat {
            guard let first = line.first else { return 620 }
            var best = first
            var bestD = abs(first.y - y)
            for i in 0..<(line.count - 1) {
                let a = line[i], b = line[i + 1]
                let span = b.y - a.y
                if abs(span) < 0.01 { continue }
                let t = (y - a.y) / span
                if t < 0 || t > 1 { continue }
                return a.x + (b.x - a.x) * t
            }
            for p in line where abs(p.y - y) < bestD {
                best = p
                bestD = abs(p.y - y)
            }
            return best.x
        }
        let scaleX = CGFloat(w) / 1170
        let scaleY = CGFloat(h) / 2532
        if yStart < h {
            for y in yStart..<h {
                let designY = CGFloat(y) / scaleY
                let swX = xAt(road, designY) * scaleX
                let mtX = xAt(mountainRoad, designY - lift) * scaleX
                let t = Float(y - yStart) / Float(max(1, fadePx - 1))
                let s = smooth(t)
                // Ось совмещается в первой половине полосы, цвет догоняет до самого края.
                let align = smooth(min(1, t / 0.55))
                let dest = swX + (mtX - swX) * CGFloat(align)
                let half = 19 + (21 - 19) * CGFloat(align)
                let roadPx = min(w - 1, max(0, Int(swX.rounded())))
                let keep = 24
                var strip = [UInt8](repeating: 0, count: (keep * 2 + 1) * 4)
                for dx in -keep...keep {
                    let x = min(w - 1, max(0, roadPx + dx))
                    let i = index(x, y, w, h)
                    let o = (dx + keep) * 4
                    strip[o] = original[i]
                    strip[o + 1] = original[i + 1]
                    strip[o + 2] = original[i + 2]
                    strip[o + 3] = original[i + 3]
                }
                // Старую, более широкую и левую дорогу затираем дымкой, потом кладём её пиксели на ось гор.
                let hazeX = min(w - 1, max(0, Int(swX.rounded()) - 48))
                let hi = index(hazeX, y, w, h)
                let erase = keep
                for dx in -erase...erase {
                    let x = Int(swX.rounded()) + dx
                    guard x >= 0, x < w else { continue }
                    let i = index(x, y, w, h)
                    original[i] = original[hi]
                    original[i + 1] = original[hi + 1]
                    original[i + 2] = original[hi + 2]
                    original[i + 3] = original[hi + 3]
                }
                let a = 1 - s
                let ab = UInt8((a * 255).rounded())
                for x in 0..<w {
                    let i = index(x, y, w, h)
                    pixels[i] = UInt8((Float(original[i]) * a).rounded())
                    pixels[i + 1] = UInt8((Float(original[i + 1]) * a).rounded())
                    pixels[i + 2] = UInt8((Float(original[i + 2]) * a).rounded())
                    pixels[i + 3] = ab
                }
                let my = y - liftY
                guard my >= 0, my < mh else { continue }
                let edge: CGFloat = 3
                let reach = Int((half + edge).rounded())
                for dx in -reach...reach {
                    let x = Int(dest.rounded()) + dx
                    guard x >= 0, x < w else { continue }
                    let along = half > 0.5 ? CGFloat(dx) / half : 0
                    let sampleX = min(w - 1, max(0, Int((mtX + along * 21).rounded())))
                    let sampleY = min(mh - 1, max(0, max(my, 401)))
                    let mi = index(sampleX, sampleY, w, mh)
                    let srcDx = max(-keep, min(keep, Int((along * 19).rounded())))
                    let so = (srcDx + keep) * 4
                    let dist = abs(CGFloat(dx))
                    let edgeA = dist <= half ? Float(1) : Float(max(0, 1 - (dist - half) / edge))
                    let i = index(x, y, w, h)
                    for c in 0..<3 {
                        let mixed = Float(strip[so + c]) * (1 - s) + Float(mount[mi + c]) * s
                        let under = Float(pixels[i + c])
                        pixels[i + c] = UInt8(min(255, (under * (1 - edgeA) + mixed * edgeA).rounded()))
                    }
                    let underA = Float(pixels[i + 3])
                    pixels[i + 3] = UInt8(min(255, (underA * (1 - edgeA) + 255 * edgeA).rounded()))
                }
            }
        }
        guard let out = ctx.makeImage() else { return image }
        return UIImage(cgImage: out, scale: image.scale, orientation: image.imageOrientation)
    }
}

enum SwampPlaces {
    static let steps: [String: Int] = [
        "gat": 4000,
        "top": 9000,
        "torfyanik": 12500,
        "staraya_protoka": 16500,
        "gorlo": 22500,
        "otstoy": 30000,
    ]
    static let lengthSteps = 30000
    static let globalStart = 45000
}

struct MountainSheet {
    let size: CGSize
    let lengthSteps: Int
    let globalStart: Int
    let road: [CGPoint]
    let roadLength: Double
    let aheadPx: Double
    let softPx: Double
    let field: ParchmentMap.Field
    let fieldPath: String
    let puffs: ParchmentMap.Puffs
    let colorPath: String
    let pencilPath: String
    let settlements: [ParchmentMap.Place]

    func fraction(localStep: Int) -> Double {
        guard lengthSteps > 0 else { return 0 }
        return min(1, max(0, Double(localStep) / Double(lengthSteps)))
    }

    /// Доля листа от мирового шага. До Седла доля отрицательная: aheadPx не
    /// открывает горы с нуля Долины. На Седле и дальше — тот же запас вперёд, что у Долины.
    func revealThreshold(worldStep: Int) -> Double {
        if worldStep >= globalStart + lengthSteps { return 2 }
        let f = Double(worldStep - globalStart) / Double(max(lengthSteps, 1))
        return f + aheadPx / max(1, roadLength)
    }

    var softFraction: Double { softPx / max(1, roadLength) }

    func puffPoints(threshold t0: Double) -> [[Double]] {
        guard t0 > 0, t0 < puffs.maxT, puffs.levels > 0, !puffs.points.isEmpty else { return [] }
        let i = Int((t0 / puffs.maxT * Double(puffs.levels)).rounded())
        return puffs.points[min(max(0, i), puffs.points.count - 1)]
    }

    /// nil, если файлов нет или они не сходятся со швом и списком мест.
    static func load(root: URL = WorldConfigLoader.assetsRoot) -> MountainSheet? {
        let mapRoot = root.appendingPathComponent("UI/map")
        let jsonURL = mapRoot.appendingPathComponent("mountains.json")
        let colorURL = mapRoot.appendingPathComponent("mountains_color.jpg")
        let pencilURL = mapRoot.appendingPathComponent("mountains_pencil.jpg")
        guard FileManager.default.fileExists(atPath: jsonURL.path),
              FileManager.default.fileExists(atPath: colorURL.path),
              FileManager.default.fileExists(atPath: pencilURL.path) else { return nil }
        let data = ContentLocalizer.data(at: jsonURL, kind: .map)
        guard let raw = try? JSONDecoder().decode(File.self, from: data) else { return nil }
        let fieldURL = root.appendingPathComponent(raw.field.image)
        guard FileManager.default.fileExists(atPath: fieldURL.path) else { return nil }
        return make(raw, colorPath: colorURL.path, pencilPath: pencilURL.path, fieldPath: fieldURL.path)
    }

    static func loadSwamps(root: URL = WorldConfigLoader.assetsRoot) -> MountainSheet? {
        let mapRoot = root.appendingPathComponent("UI/map")
        let jsonURL = mapRoot.appendingPathComponent("swamps.json")
        let colorURL = mapRoot.appendingPathComponent("swamps_color.jpg")
        let pencilURL = mapRoot.appendingPathComponent("swamps_pencil.jpg")
        guard FileManager.default.fileExists(atPath: jsonURL.path),
              FileManager.default.fileExists(atPath: colorURL.path),
              FileManager.default.fileExists(atPath: pencilURL.path) else { return nil }
        let data = ContentLocalizer.data(at: jsonURL, kind: .map)
        guard let raw = try? JSONDecoder().decode(File.self, from: data) else { return nil }
        let fieldURL = root.appendingPathComponent(raw.field.image)
        guard FileManager.default.fileExists(atPath: fieldURL.path) else { return nil }
        guard raw.lengthSteps == SwampPlaces.lengthSteps,
              raw.globalStart == SwampPlaces.globalStart,
              raw.join.count == 2,
              abs(raw.join[0] - SwampJoin.point.x) < 0.6,
              abs(raw.join[1] - SwampJoin.point.y) < 0.6,
              raw.road.count >= 2 else { return nil }
        let road = raw.road.map { CGPoint(x: $0[0], y: $0[1]) }
        guard let first = road.first,
              hypot(first.x - SwampJoin.point.x, first.y - SwampJoin.point.y) < 1 else { return nil }
        for place in raw.settlements {
            guard let expected = SwampPlaces.steps[place.id], place.step == expected else { return nil }
        }
        return MountainSheet(size: CGSize(width: raw.size[0], height: raw.size[1]),
                             lengthSteps: raw.lengthSteps,
                             globalStart: raw.globalStart,
                             road: road,
                             roadLength: raw.roadLength,
                             aheadPx: raw.aheadPx,
                             softPx: raw.softPx,
                             field: raw.field,
                             fieldPath: fieldURL.path,
                             puffs: raw.puffs,
                             colorPath: colorURL.path,
                             pencilPath: pencilURL.path,
                             settlements: raw.settlements)
    }

    static func make(_ raw: File, colorPath: String, pencilPath: String, fieldPath: String) -> MountainSheet? {
        guard raw.lengthSteps == MountainPlaces.lengthSteps,
              raw.globalStart == MountainPlaces.globalStart,
              raw.size.count == 2,
              abs(raw.size[0] - MapJoin.mountainSize.width) < 0.5,
              abs(raw.size[1] - MapJoin.mountainSize.height) < 0.5,
              raw.join.count == 2,
              abs(raw.join[0] - MapJoin.mountain.x) < 0.6,
              abs(raw.join[1] - MapJoin.mountain.y) < 0.6,
              raw.road.count >= 2 else { return nil }
        let road = raw.road.map { CGPoint(x: $0[0], y: $0[1]) }
        guard let first = road.first,
              hypot(first.x - MapJoin.mountain.x, first.y - MapJoin.mountain.y) < 1 else { return nil }
        for place in raw.settlements {
            guard let expected = MountainPlaces.steps[place.id], place.step == expected else { return nil }
        }
        return MountainSheet(size: CGSize(width: raw.size[0], height: raw.size[1]),
                             lengthSteps: raw.lengthSteps,
                             globalStart: raw.globalStart,
                             road: road,
                             roadLength: raw.roadLength,
                             aheadPx: raw.aheadPx,
                             softPx: raw.softPx,
                             field: raw.field,
                             fieldPath: fieldPath,
                             puffs: raw.puffs,
                             colorPath: colorPath,
                             pencilPath: pencilPath,
                             settlements: raw.settlements)
    }

    struct File: Decodable {
        let size: [Double]
        let lengthSteps: Int
        let globalStart: Int
        let join: [Double]
        let road: [[Double]]
        let roadLength: Double
        let aheadPx: Double
        let softPx: Double
        let field: ParchmentMap.Field
        let puffs: ParchmentMap.Puffs
        let settlements: [ParchmentMap.Place]
    }
}
