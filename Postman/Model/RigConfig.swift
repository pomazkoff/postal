import Foundation

/// GameAssets/Rig/rig.json — без изменений из postman_fal/cutout.
/// offsets: левый верхний угол PNG части в координатах исходника (Y вниз).
/// pivots_src: шарниры в тех же координатах; ground_y — линия земли.
struct RigConfig: Decodable {
    let offsets: [String: [Double]]
    let pivots: [String: Double2]
    let groundY: Double

    enum CodingKeys: String, CodingKey {
        case offsets
        case pivots = "pivots_src"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        offsets = try c.decode([String: [Double]].self, forKey: .offsets)
        // pivots_src смешивает пары [x, y] и число ground_y — разбираем вручную.
        let raw = try c.decode([String: PivotValue].self, forKey: .pivots)
        var p: [String: Double2] = [:]
        var g: Double = 1108
        for (k, v) in raw {
            switch v {
            case .point(let pt): p[k] = pt
            case .scalar(let s): if k == "ground_y" { g = s }
            }
        }
        pivots = p
        groundY = g
    }

    func offset(_ part: String) -> Double2 {
        guard let o = offsets[part], o.count == 2 else { return Double2(0, 0) }
        return Double2(o[0], o[1])
    }

    func pivot(_ name: String) -> Double2 {
        pivots[name] ?? Double2(0, 0)
    }

    static func load() -> RigConfig {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Rig/rig.json")
        do {
            return try JSONDecoder().decode(RigConfig.self, from: Data(contentsOf: url))
        } catch {
            fatalError("Не удалось загрузить rig.json: \(error)")
        }
    }
}

private enum PivotValue: Decodable {
    case point(Double2)
    case scalar(Double)

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let arr = try? c.decode([Double].self), arr.count == 2 {
            self = .point(Double2(arr[0], arr[1]))
        } else {
            self = .scalar(try c.decode(Double.self))
        }
    }
}

/// Простая 2D-точка без зависимостей от CoreGraphics (чтобы математика рига проверялась где угодно).
struct Double2: Equatable {
    var x: Double
    var y: Double
    init(_ x: Double, _ y: Double) { self.x = x; self.y = y }
    static func - (a: Double2, b: Double2) -> Double2 { Double2(a.x - b.x, a.y - b.y) }
    static func + (a: Double2, b: Double2) -> Double2 { Double2(a.x + b.x, a.y + b.y) }
}
