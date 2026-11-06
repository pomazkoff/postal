import Foundation
import CoreGraphics

/// Живой мир: небо по времени суток, облака, птицы, звёзды, дым, качание травы, колокол.
/// GameAssets/Data/ambient.json (генерирует tools/build_ambient_assets.py). Нет файла — мир статичный, как раньше.
struct AmbientConfig: Decodable {
    /// Частота «покадровой» анимации (стоп-моушн), обычно 12.
    let fps: Double
    /// Атлас мелкого арта (PNG + JSON с прямоугольниками кадров), путь от GameAssets без расширения.
    let atlas: String
    let timeOfDay: [SkyKey]
    let deepSoilColor: String
    let clouds: [CloudLayer]
    let birds: Birds?
    let stars: Stars?
    let smoke: [Smoke]
    let sway: [Sway]
    let bells: [Bell]

    /// Опорная точка суток (час 0…24). Между точками цвета интерполируются.
    struct SkyKey: Decodable {
        let hour: Double
        /// nil — цвета неба из world.json (дневное небо макета).
        let skyTop: String?
        let skyBottom: String?
        /// Мягкий тон мира (умножение), "#FFFFFF" — без изменений.
        let tint: String
        /// Видимость звёзд 0…1.
        let stars: Double
    }

    struct CloudLayer: Decodable {
        let parallax: Double
        /// Мировой Y низа облаков (снизу), диапазон.
        let y: [Double]
        let height: [Double]
        let count: Int
        /// Дрейф, px сцены в секунду (знак — направление).
        let speed: Double
        let alpha: Double
        let z: Double
    }

    struct Birds: Decodable {
        /// Пауза между стайками, секунды (мин, макс).
        let interval: [Double]
        let parallax: Double
        let y: [Double]
        let speed: [Double]
        let height: Double
        let flock: [Int]
        let z: Double
    }

    struct Stars: Decodable {
        let count: Int
        /// Доля экрана сверху, где рассыпаны звёзды.
        let topFraction: Double
        let size: [Double]
    }

    /// Дым из трубы: prop — image пропса из world.json, at — точка в пикселях исходной картинки (Y вниз).
    struct Smoke: Decodable {
        let prop: String
        let at: [Double]
        let scale: Double
        let interval: Double
        let wind: Double
    }

    /// Качание: пропсы, чей image начинается с match; amp — градусы, period — секунды.
    struct Sway: Decodable {
        let match: String
        let amp: Double
        let period: [Double]
    }

    /// Колокол: отдельный спрайт поверх пропса, качается вокруг pivot (пиксели исходника пропса).
    struct Bell: Decodable {
        let prop: String
        /// Картинка пропса без колокола (дыра залита) — подменяет prop, когда живой мир включён.
        let baseImage: String?
        let frame: String
        let pivot: [Double]
        /// Точка подвеса в пикселях картинки колокола (Y вниз).
        let hang: [Double]
        let amp: Double
        let period: Double
        let z: Double
    }

    static func load() -> AmbientConfig? {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/ambient.json")
        guard let data = try? Data(contentsOf: url) else { return nil }
        do {
            return try JSONDecoder().decode(AmbientConfig.self, from: data)
        } catch {
            #if DEBUG
            print("ambient.json: \(error)")
            #endif
            return nil
        }
    }
}
