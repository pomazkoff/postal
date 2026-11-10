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
