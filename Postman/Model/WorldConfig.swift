import Foundation
import CoreGraphics

// MARK: - world.json (GameAssets/Data/world.json)
// Все координаты — px дизайна кадра 1170×2532, ось Y сверху вниз (как в макетах и compose_places.py).
// Перевод в координаты SpriteKit (Y снизу вверх) делает WorldGeometry.

struct WorldConfig: Decodable {
    let game: GameConfig
    let layers: LayersConfig
    let chapters: [ChapterConfig]
}

struct GameConfig: Decodable {
    let totalSteps: Int
    let pixelsPerStep: Double
    let designWidth: Double
    let designHeight: Double
    let roadLineY: Double
    let postman: PostmanConfig
    let camera: CameraConfig
    let walking: WalkingConfig
}

struct PostmanConfig: Decodable {
    /// Высота героя в px дизайна (430 из 2532).
    let height: Double
    /// Насколько стопы ниже линии дороги (style-guide: GY−PH+30).
    let feetBelowRoad: Double
    /// Позиция героя по ширине экрана (0…1) при «следящей» камере.
    let screenX: Double
    /// Кадр цикла, который показывается в покое (0…7).
    let idleFrame: Int
    /// Высота силуэта в px исходника рига (для масштаба).
    let rigSourceHeight: Double
    /// X-координата центра героя в исходнике рига.
    let rigCenterX: Double
    /// "reference" — джиттер как в rig_walk.py (random.seed(4)), "random" — новый на каждом цикле.
    let jitter: String
}

struct CameraConfig: Decodable {
    let snapBackDelay: Double
    let snapBackRate: Double
    let leftMarginSteps: Double
}

struct WalkingConfig: Decodable {
    /// Скорость ходьбы, px дизайна в секунду.
    let speed: Double
    /// Если догонять дольше — скорость увеличивается, чтобы уложиться в это время.
    let maxCatchUpSeconds: Double
    /// Если отставание больше — герой «переносится» ближе к цели.
    let teleportGapSteps: Int
    let teleportLandBeforeSteps: Int
}

struct LayersConfig: Decodable {
    let sky: SkyConfig
    let far: TiledLayerConfig
    let mid: TiledLayerConfig
    let mainParallax: Double
    let undergroundParallax: Double
    let foregroundParallax: Double
}

struct SkyConfig: Decodable {
    let topColor: String
    let bottomColor: String
}

struct TiledLayerConfig: Decodable {
    let parallax: Double
    let image: String
    /// Верх слоя (Y сверху) в px дизайна.
    let top: Double
    let height: Double
    let brightness: Double?
    let fadeTopFraction: Double?
    let pixelSize: [Double]
}

enum LayerKind: String, Decodable {
    case far, mid, main, underground, foreground
}

struct ChapterConfig: Decodable {
    let id: Int
    let title: String
    let startStep: Int
    let lengthSteps: Int
    let assetsFolder: String
    let settlements: [Settlement]
    let props: [PropConfig]
    let underground: UndergroundConfig
    let quests: [QuestConfig]
    let rawClayAfterStep: Int?

    var endStep: Int { startStep + lengthSteps }
}

struct Settlement: Decodable, Identifiable, Hashable {
    let id: String
    let name: String
    let nameGenitive: String
    let fullName: String
    /// Шаг от начала главы.
    let step: Int
}

struct PropConfig: Decodable {
    /// Путь внутри папки главы без .png, напр. "places/place_pochta_main".
    let image: String
    let layer: LayerKind
    /// Шаг-якорь (обычно шаг поселения).
    let step: Int
    /// Смещение левого края от центра почтальона, стоящего на шаге `step`.
    let dx: Double
    /// Высота в px дизайна (ширина — по пропорции pixelSize).
    let height: Double
    /// На сколько px опустить основание ниже линии дороги (style-guide: +40).
    let sink: Double?
    let z: Double?
    let pixelSize: [Double]
}

struct UndergroundConfig: Decodable {
    let neutralTile: String
    /// Верх полосы разреза (Y сверху).
    let top: Double
    let scale: Double
    let tilePixelSize: [Double]
    /// Промежуток меньше этой доли тайла не заполняется — модуль придвигается вплотную.
    let minGapFraction: Double
    let modules: [UndergroundModule]
}

struct UndergroundModule: Decodable {
    let image: String
    let step: Int
    /// Смещение ЦЕНТРА модуля от центра почтальона на шаге `step`.
    let dx: Double
}

struct QuestConfig: Decodable {
    /// Квест активен, пока пройдено меньше этого числа шагов (в рамках главы).
    let untilStep: Int
    let telegram: String
    let lettersInBag: Int
}

// MARK: - Loading

enum WorldConfigLoader {
    static let assetsFolder = "GameAssets"

    static var assetsRoot: URL {
        (Bundle.main.resourceURL ?? Bundle.main.bundleURL).appendingPathComponent(assetsFolder, isDirectory: true)
    }

    static func load() -> WorldConfig {
        let url = assetsRoot.appendingPathComponent("Data/world.json")
        do {
            return try JSONDecoder().decode(WorldConfig.self, from: ContentLocalizer.data(at: url, kind: .world))
        } catch {
            fatalError("Не удалось загрузить \(url.lastPathComponent): \(error)")
        }
    }
}

// MARK: - Geometry helpers

/// Перевод шагов и координат дизайна в координаты сцены SpriteKit.
struct WorldGeometry {
    let game: GameConfig

    var sceneSize: CGSize { CGSize(width: game.designWidth, height: game.designHeight) }

    /// Y сверху (дизайн) → Y снизу (SpriteKit).
    func sceneY(fromTop y: Double) -> CGFloat { CGFloat(game.designHeight - y) }

    var roadY: CGFloat { sceneY(fromTop: game.roadLineY) }

    /// Центр почтальона по X для шага главы.
    func x(forStep step: Double) -> CGFloat { CGFloat(step * game.pixelsPerStep) }

    func step(forX x: CGFloat) -> Double { Double(x) / game.pixelsPerStep }

    /// Смещение камеры относительно героя, чтобы герой стоял на screenX ширины экрана.
    var cameraLead: CGFloat { CGFloat((0.5 - game.postman.screenX) * game.designWidth) }

    func cameraX(forStep step: Double) -> CGFloat { x(forStep: step) + cameraLead }
}
