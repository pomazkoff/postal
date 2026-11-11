import SpriteKit
import UIKit

/// Единая лента мира (все главы в глобальных шагах): параллакс-слои, почтальон, камера, прокрутка назад по пройденному.
///
/// Слои (сзади вперёд) и коэффициенты параллакса — из world.json:
///   небо (за камерой) → дальний 0.1 → средний 0.4 → основной 1.0 → разрез 1.0 → [метки, герой] → передний 1.3.
/// Позиция слоя: layer.x = camera.x · (1 − k) — содержимое смещается со скоростью k относительно камеры.
final class WorldScene: SKScene, UIGestureRecognizerDelegate {
    private let config: WorldConfig
    private let geo: WorldGeometry
    private let rig: RigConfig

    private let cam = SKCameraNode()
    private var layerNodes: [(node: SKNode, parallax: CGFloat)] = []
    private var tiledStrips: [(node: TiledStripNode, parallax: CGFloat, kind: LayerKind)] = []
    private var chapterCrops: [(node: SKCropNode, range: ClosedRange<CGFloat>)] = []
    private var lazyNodes: [(node: LazySpriteNode, layer: SKNode)] = []
    /// Живые сценки болот. Мало, паузятся за кадром, текстуры не выгружаются.
    private var lifeNodes: [SKNode] = []
    private var postman: PostmanRigNode!
    private var actorLayerRef: SKNode?

    // Сюжет главы: предметы на дороге и жители (см. installStory)
    private struct RoadItem {
        let id: String
        let chapterID: Int
        let step: Double
        let node: SKSpriteNode
        var leftBehind: Bool
        var pickedUp = false
    }
    private var roadItems: [RoadItem] = []
    private var residentNodes: [String: SKSpriteNode] = [:]
    /// Ключ содержит главу: жители всех глав остаются на единой ленте.
    var onResidentTap: ((_ chapterID: Int, _ residentID: String) -> Void)?
    /// Короткий тап по вещи на болотах: id из chapter3_taps.json.
    var onMarshTap: ((String) -> Void)?
    var onPostmanTap: (() -> Void)?
    /// Видимый шаг героя: мировой шаг, только когда стопа ставится и он в кадре.
    var onFootfall: ((Double) -> Void)?
    /// Стая пролетела. Звук решает вызывающий, здесь только факт.
    var onFlock: (() -> Void)?
    var onAmbienceTick: ((Double) -> Void)?

    // Спутник (коза Рамка): идёт рядом с почтальоном, пока companionProvider(шаг) возвращает его id.
    /// Какой спутник должен идти рядом на этом шаге главы (nil — никто). Задаёт GameModel.
    var companionProvider: ((Double) -> String?)?
    private var companionFigures: [String: (image: UIImage, groundFraction: CGFloat, height: CGFloat)] = [:]
    private var companionNode: SKSpriteNode?
    private var companionID: String?
    private var companionClock: Double = 0
    private var companionAnim: Double = 0
    private var walkIdleClock: Double = 0
    private var companionSway: Double = 0
    private static let walkStartGapPx: Double = 40
    private static let walkStopHold: Double = 0.12

    // Прогресс в глобальных шагах мира. Сюжет по-прежнему получает шаги внутри главы.
    private(set) var displayedStep: Double
    private var targetStep: Double

    // Камера: свободный обзор пройденного, инерция, отзум (см. MARK: Camera)
    private var camX: CGFloat = 0
    /// Масштаб камеры: 1 — как в макете, больше — отзум (видно больше дороги).
    private var camScale: CGFloat = 1
    /// Камера следит за почтальоном. Выключается панорамой, включается только кнопкой «к почтальону».
    private(set) var isFollowing = true
    private var velocityX: CGFloat = 0
    private var isPanning = false
    private var isReturning = false
    private var panRecognizer: UIPanGestureRecognizer?
    private var pinchRecognizer: UIPinchGestureRecognizer?
    private var residentTapRecognizer: UITapGestureRecognizer?
    /// Почтальон за краем экрана: .left/.right — где он; nil — виден.
    enum Offscreen: Equatable { case left, right }
    private(set) var postmanOffscreen: Offscreen?
    /// Вызывается при смене видимости почтальона (кнопка «к почтальону» в HUD).
    var onPostmanOffscreenChange: ((Offscreen?) -> Void)?
    /// Наименьший зум (1 / наибольший масштаб камеры).
    static let minZoom: CGFloat = 0.35
    /// Наибольшее приближение (зум 2.5× → масштаб камеры 0.4).
    static let maxZoom: CGFloat = 2.5
    private var maxCamScale: CGFloat { 1 / Self.minZoom }
    private var minCamScale: CGFloat { 1 / Self.maxZoom }
    /// Вертикальный сдвиг камеры при приближении (точка под пальцами остаётся на месте); при масштабе ≥ 1 — 0.
    private var camShiftY: CGFloat = 0
    /// Нижняя граница мира по Y: под разрезом — «толща» земли, чтобы при отзуме не было пустоты.
    private let worldBottomY: CGFloat = -1800
    private(set) var ambient: AmbientLayer?
    private(set) var weather: WeatherLayer?
    private var skySprite: SKSpriteNode?
    private var skyRoadFraction: CGFloat = 0
    private var appliedSkyChapter: Int = -1
    private var lastUpdateTime: TimeInterval = 0
    private var ambienceClock: TimeInterval = 0
    private var cullClock: TimeInterval = 0

    init(config: WorldConfig, rig: RigConfig, initialStep: Double) {
        self.config = config
        self.geo = WorldGeometry(game: config.game)
        self.rig = rig
        let start = max(0, min(Double(config.chapters.map(\.endStep).max() ?? 0), initialStep))
        self.displayedStep = start
        self.targetStep = start
        super.init(size: geo.sceneSize)
        scaleMode = .aspectFill
        anchorPoint = .zero
        backgroundColor = UIColor(hex: config.layers.sky.topColor)
        isUserInteractionEnabled = true
        buildWorld()
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) не используется") }

    // MARK: Build

    private func buildWorld() {
        let L = config.layers
        let W = CGFloat(config.game.designWidth)
        let H = CGFloat(config.game.designHeight)

        // Камера + небо (неподвижно относительно экрана)
        camX = geo.cameraX(forStep: displayedStep)
        cam.position = CGPoint(x: camX, y: H / 2)
        addChild(cam)
        camera = cam
        let roadFraction = CGFloat(config.game.roadLineY / config.game.designHeight)
        skyRoadFraction = roadFraction
        let sky = SKSpriteNode(texture: ProceduralTextures.sky(top: UIColor(hex: L.sky.topColor),
                                                              bottom: UIColor(hex: L.sky.bottomColor),
                                                              roadFraction: roadFraction))
        sky.size = CGSize(width: W * 2, height: H * 1.2) // запас на другие пропорции экрана
        sky.position = .zero
        sky.zPosition = -1000
        cam.addChild(sky)
        skySprite = sky

        // Живой мир (облака, птицы, звёзды, время суток) — если есть Data/ambient.json и атлас.
        if let ac = AmbientConfig.load() {
            ambient = AmbientLayer(config: ac, sky: sky, camera: cam, designSize: CGSize(width: W, height: H),
                                   baseTop: UIColor(hex: L.sky.topColor), baseBottom: UIColor(hex: L.sky.bottomColor),
                                   roadFraction: roadFraction, maxCameraScale: maxCamScale,
                                   addLayer: { [unowned self] node, k in self.addLayer(node, parallax: k) })
            ambient?.onFlock = { [weak self] in self?.onFlock?() }
        }

        // Погода (ясно/дождь/снег/туман) — поверх неба и планов, под тоном суток.
        // Полный белый слой на камеру здесь не вешается: он мыл весь кадр, включая
        // жителей и разрез, и не снимался, когда камеру уводили назад в горы.
        weather = WeatherLayer(camera: cam, designSize: CGSize(width: W, height: H))
        applyChapterSky()

        // Одна сцена/камера/фигура героя на весь мир. Главы — соседние сегменты, а не сцены.
        let actorLayer = SKNode()
        actorLayer.zPosition = 200
        addLayer(actorLayer, parallax: L.mainParallax)
        actorLayerRef = actorLayer
        for (index, chapter) in config.chapters.enumerated() {
            buildChapter(chapter, index: index, actorLayer: actorLayer)
        }
        // Почтальон
        let pc = config.game.postman
        let node = PostmanRigNode(rig: rig,
                                  height: CGFloat(pc.height),
                                  sourceHeight: CGFloat(pc.rigSourceHeight),
                                  centerX: CGFloat(pc.rigCenterX),
                                  idleFrame: pc.idleFrame,
                                  randomJitter: pc.jitter == "random")
        node.position = CGPoint(x: geo.x(forStep: displayedStep), y: geo.roadY - CGFloat(pc.feetBelowRoad))
        node.zPosition = 100
        let shadow = Readability.contactShadow(width: CGFloat(pc.height) * 0.62)
        shadow.position = CGPoint(x: 0, y: CGFloat(pc.feetBelowRoad) * 0.5)
        node.addChild(shadow)
        actorLayer.addChild(node)
        node.onFootfall = { [weak self] in
            guard let self, self.postmanOffscreen == nil else { return }
            self.onFootfall?(self.displayedStep)
        }
        postman = node

        installMarshSky()
        updateCameraAndLayers()
        cullLazyNodes()
        applyReadability()
    }

    private struct MarshDrift {
        let node: SKSpriteNode
        let speed: CGFloat
        var base: CGFloat
        let parallax: CGFloat
    }

    private var marshDrift: [MarshDrift] = []
    private var marshSkyNodes: [SKNode] = []
    private var marshBirdTextures: [SKTexture] = []
    private var marshBirdLayer: SKNode?
    private var marshBirdClock: Double = 6
    private var marshSkyTime: Double = 0
    private var marshSkySpan: CGFloat = 0
    private var shimmerTime: Double = 0

    /// Небо главы 3: Chapter3/sky. Облака висят в открытой полосе над грядами,
    /// клочья тумана — ниже, над полями. Птиц и puff пока нет: файл с префиксом bird_ подхватится сам.
    private func installMarshSky() {
        let H = CGFloat(config.game.designHeight)
        // y — низ сцены. fromTop: верёвка у верхнего края кадра. Иначе y — центр.
        let pieces: [(file: String, height: CGFloat, y: CGFloat, parallax: CGFloat, speed: CGFloat,
                      alpha: CGFloat, z: CGFloat, fromTop: Bool, flip: Bool)] = [
            ("cloud_stratus", 120, H - 250, 0.04, 7, 1, -760, false, false),
            ("cloud_moon", 520, H + 16, 0.07, 10, 1, -740, true, false),
            ("cloud_torn", 250, H - 24, 0.06, 12, 1, -730, true, false),
            ("fog_wisp", 96, H - 1120, 0.16, 6, 0.72, -450, false, false),
            ("cloud_rain", 310, H - 12, 0.08, 9, 1, -735, true, false),
            ("cloud_stratus", 88, H - 150, 0.05, 8, 1, -755, false, true),
            ("cloud_moon", 390, H - 8, 0.07, 11, 1, -738, true, true),
            ("fog_wisp", 112, H - 1200, 0.18, 5, 0.62, -450, false, true),
            ("cloud_torn", 200, H - 70, 0.06, 13, 1, -728, true, true),
            ("cloud_rain", 250, H - 40, 0.08, 10, 1, -732, true, true),
            ("fog_wisp", 80, H - 1040, 0.15, 7, 0.7, -450, false, false),
        ]
        let span = CGFloat(config.game.designWidth) * 6
        marshSkySpan = span
        var layers: [CGFloat: SKNode] = [:]
        for (i, piece) in pieces.enumerated() {
            let path = "Chapter3/sky/\(piece.file)"
            guard FileManager.default.fileExists(atPath: TextureStore.url(for: path).path) else { continue }
            let layer: SKNode
            if let existing = layers[piece.z] {
                layer = existing
            } else {
                let node = SKNode()
                node.zPosition = piece.z
                // Слой едет с камерой. Сдвиг каждого спрайта считается отдельно.
                addLayer(node, parallax: 0)
                marshSkyNodes.append(node)
                layers[piece.z] = node
                layer = node
            }
            let tex = TextureStore.shared.texture(path)
            let node = SKSpriteNode(texture: tex)
            let aspect = tex.size().width / max(1, tex.size().height)
            node.size = CGSize(width: piece.height * aspect, height: piece.height)
            node.anchorPoint = piece.fromTop ? CGPoint(x: 0.5, y: 1) : CGPoint(x: 0.5, y: 0.5)
            node.alpha = piece.alpha
            node.position.y = piece.y
            if piece.flip { node.xScale = -1 }
            layer.addChild(node)
            marshDrift.append(MarshDrift(node: node, speed: piece.speed,
                                         base: span * CGFloat(i) / CGFloat(pieces.count),
                                         parallax: piece.parallax))
        }
        let birdNames = ((try? FileManager.default.contentsOfDirectory(
            atPath: WorldConfigLoader.assetsRoot.appendingPathComponent("Chapter3/sky", isDirectory: true).path
        )) ?? []).filter { $0.lowercased().hasPrefix("bird") && $0.lowercased().hasSuffix(".png") }.sorted()
        let birds = birdNames.map { "Chapter3/sky/\(($0 as NSString).deletingPathExtension)" }
        if !birds.isEmpty {
            let layer = SKNode()
            layer.zPosition = -660
            addLayer(layer, parallax: 0.2)
            marshBirdLayer = layer
            marshSkyNodes.append(layer)
            marshBirdTextures = birds.filter {
                FileManager.default.fileExists(atPath: TextureStore.url(for: $0).path)
            }.map { TextureStore.shared.texture($0) }
        }
    }

    private func updateMarshSky(dt: TimeInterval) {
        guard !marshSkyNodes.isEmpty || marshBirdLayer != nil else { return }
        // Небо болот привязано к камере. Пока почтальон в главе 3, взгляд назад
        // в горы не должен тащить за собой луну и клочья тумана.
        let inMarsh = chapter(containing: stepUnderCamera)?.id == 3
        for node in marshSkyNodes { node.isHidden = !inMarsh }
        guard inMarsh else { return }
        marshSkyTime += dt
        let span = max(marshSkySpan, 1)
        for item in marshDrift {
            let base = item.base + item.speed * CGFloat(marshSkyTime)
            let localCam = camX * item.parallax
            let u = base - localCam + span / 2
            let rel = u - span * floor(u / span) - span / 2
            // Родитель уже едет с камерой (параллакс 0), поэтому здесь только сдвиг по экрану.
            item.node.position.x = rel.rounded()
        }
        guard let layer = marshBirdLayer, !marshBirdTextures.isEmpty else { return }
        marshBirdClock -= dt
        guard marshBirdClock <= 0 else { return }
        marshBirdClock = 16
        let tex = marshBirdTextures[Int(displayedStep) % marshBirdTextures.count]
        let bird = SKSpriteNode(texture: tex)
        let h: CGFloat = 48
        let aspect = tex.size().width / max(1, tex.size().height)
        bird.size = CGSize(width: h * aspect, height: h)
        let k: CGFloat = 0.2
        bird.position = CGPoint(x: camX * k - CGFloat(config.game.designWidth), y: CGFloat(config.game.designHeight) * 0.72)
        layer.addChild(bird)
        let travel = CGFloat(config.game.designWidth) * 2.4
        bird.run(.sequence([
            .moveBy(x: travel, y: 30, duration: 18),
            .removeFromParent(),
        ]))
    }

    private var worldEndStep: Int { config.chapters.map(\.endStep).max() ?? 0 }

    /// Маска сплошная и ровно по границе главы. Альфа тайлов здесь не трогается:
    /// на Release 17746c5 она открывала пустую заливку вместо соседней земли.
    private func croppedLayer(chapter: ChapterConfig, index: Int, z: CGFloat, parallax: Double) -> SKNode {
        let margin = CGFloat(config.game.designWidth) * 4
        let left = index == 0 ? -margin : geo.x(forStep: Double(chapter.startStep))
        let right = index + 1 < config.chapters.count
            ? geo.x(forStep: Double(config.chapters[index + 1].startStep))
            : geo.x(forStep: Double(chapter.endStep)) + margin
        let crop = SKCropNode()
        crop.zPosition = z
        let mask = SKSpriteNode(color: .white, size: CGSize(width: max(1, right - left), height: 16000))
        mask.anchorPoint = .zero
        mask.position = CGPoint(x: left, y: worldBottomY - 4000)
        crop.maskNode = mask
        addChild(crop)
        chapterCrops.append((crop, left...right))
        let layer = SKNode()
        crop.addChild(layer)
        addLayer(layer, parallax: parallax)
        return layer
    }

    private func buildChapter(_ chapter: ChapterConfig, index: Int, actorLayer: SKNode) {
        let L = config.layers
        let W = CGFloat(config.game.designWidth)
        let farLayer = croppedLayer(chapter: chapter, index: index, z: -500, parallax: L.far.parallax)
        let midLayer = croppedLayer(chapter: chapter, index: index, z: -400, parallax: L.mid.parallax)
        for (kind, spec, layer) in [(LayerKind.far, L.far, farLayer), (.mid, L.mid, midLayer)] {
            let tex = ProceduralTextures.fadedTop(spec.image.inChapter(chapter), fraction: CGFloat(spec.fadeTopFraction ?? 0))
            let strip = TiledStripNode(texture: tex, tileHeight: CGFloat(spec.height),
                                      aspect: CGFloat(spec.pixelSize[0] / spec.pixelSize[1]),
                                      bottomY: geo.sceneY(fromTop: spec.top + spec.height),
                                      brightness: CGFloat(spec.brightness ?? 1))
            strip.hazeColor = Readability.hazeColor
            strip.hazeFactor = Readability.hazeFactor(for: kind)
            layer.addChild(strip)
            tiledStrips.append((strip, CGFloat(spec.parallax), kind))
        }
        // Постройки могут пересекать границу главы: не режем дом/дерево пополам маской.
        let mainLayer = SKNode()
        mainLayer.zPosition = 0
        addLayer(mainLayer, parallax: L.mainParallax)
        let ugLayer = croppedLayer(chapter: chapter, index: index, z: 100, parallax: L.undergroundParallax)
        buildUnderground(in: ugLayer, chapter: chapter)
        let fgLayer = SKNode()
        fgLayer.zPosition = 500
        fgLayer.alpha = 0.9
        addLayer(fgLayer, parallax: L.foregroundParallax)

        // Толща под разрезом — только заливка отзума, не замена движущимся UG-тайлам.
        let ugBottom = geo.sceneY(fromTop: chapter.underground.top)
            - CGFloat(chapter.underground.tilePixelSize[1] * chapter.underground.scale)
        let left = geo.x(forStep: Double(chapter.startStep)) - W * 4
        let width = CGFloat(chapter.lengthSteps) * CGFloat(config.game.pixelsPerStep) + W * 8
        let soil = SKSpriteNode(color: UIColor(hex: ambient?.config.deepSoilColor ?? "#2A1D16"),
                                size: CGSize(width: width, height: max(10, ugBottom - worldBottomY + 200)))
        soil.anchorPoint = CGPoint(x: 0, y: 1)
        soil.position = CGPoint(x: left, y: ugBottom + 4)
        soil.zPosition = -1
        ugLayer.addChild(soil)

        // Пропсы из JSON по слоям
        for p in chapter.props {
            if index + 1 < config.chapters.count {
                let next = config.chapters[index + 1]
                let atBoundary = chapter.startStep + p.step == next.startStep
                if atBoundary && (p.image.contains("raw_clay") || next.props.contains(where: {
                    $0.step == 0 && $0.image == p.image
                })) { continue } // общая станция берёт один арт, из следующей главы
            }
            let target: SKNode
            let k: Double
            switch p.layer {
            case .far: target = farLayer; k = L.far.parallax
            case .mid: target = midLayer; k = L.mid.parallax
            case .main: target = mainLayer; k = L.mainParallax
            case .underground: target = ugLayer; k = L.undergroundParallax
            case .foreground: target = fgLayer; k = L.foregroundParallax
            }
            let h = CGFloat(p.height)
            let w = h * CGFloat(p.pixelSize[0] / max(1, p.pixelSize[1]))
            let worldLeft = geo.x(forStep: Double(chapter.startStep + p.step)) + CGFloat(p.dx)
            let camAtStep = geo.cameraX(forStep: Double(chapter.startStep + p.step))
            let localLeft = worldLeft - camAtStep * CGFloat(1 - k)
            if chapter.id == 3, p.image.hasPrefix("ambient/"),
               let life = marshLifeNode(prop: p, chapter: chapter, size: CGSize(width: w, height: h)) {
                life.position = CGPoint(x: localLeft, y: geo.roadY - CGFloat(p.sink ?? 0))
                life.zPosition = CGFloat(p.z ?? 0)
                pinLifeBottom(life)
                animateMarshLife(life, image: p.image, chapter: chapter,
                                 pixelHeight: CGFloat(p.pixelSize[1]))
                target.addChild(life)
                lifeNodes.append(life)
                continue
            }
            var imagePath = p.image.inChapter(chapter)
            if let alt = ambient?.substituteImage(for: p.image)?.inChapter(chapter),
               FileManager.default.fileExists(atPath: TextureStore.url(for: alt).path) {
                imagePath = alt
            }
            let node = LazySpriteNode(imagePath: imagePath, size: CGSize(width: w, height: h))
            node.anchorPoint = .zero
            // Дымка: дальний/средний план и постройки основного плана (не дорога, не передний план).
            if p.layer == .far || p.layer == .mid || (p.layer == .main && p.image.contains("places/")) {
                node.gradeColor = Readability.hazeColor
                node.gradeLayer = p.layer
                node.gradeFactor = Readability.hazeFactor(for: p.layer)
            }
            node.position = CGPoint(x: localLeft, y: geo.roadY - CGFloat(p.sink ?? 0))
            node.zPosition = CGFloat(p.z ?? 0)
            target.addChild(node)
            lazyNodes.append((node, target))
            ambient?.decorate(prop: node, image: p.image,
                              pixelSize: CGSize(width: p.pixelSize[0], height: p.pixelSize[1]),
                              seed: p.step &* 31 &+ Int(p.dx))
        }
        if chapter.id == 3 {
            addMarshReeds(to: mainLayer, chapter: chapter)
        }

        // Общая станция на границе двух глав получает только одну подпись.
        for settlement in chapter.settlements {
            let globalStep = chapter.startStep + settlement.step
            let duplicate = index > 0 && config.chapters[index - 1].settlements.contains {
                $0.id == settlement.id && config.chapters[index - 1].startStep + $0.step == globalStep
            }
            guard !duplicate else { continue }
            let marker = SettlementMarkerNode(title: settlement.name)
            marker.name = "settle.\(chapter.id).\(settlement.id)"
            marker.position = CGPoint(x: geo.x(forStep: Double(globalStep)), y: geo.roadY)
            marker.zPosition = 10
            actorLayer.addChild(marker)
        }
        // Заглушка только за ПОСЛЕДНЕЙ известной главой, не поверх следующей.
        if chapter.id == 3 {
            installMarshTaps(in: actorLayer, chapter: chapter)
        }
        if index == config.chapters.count - 1, let after = chapter.rawClayAfterStep {
            let clay = SKSpriteNode(color: UIColor(red: 0.55, green: 0.47, blue: 0.38, alpha: 1),
                                    size: CGSize(width: W * 4, height: CGFloat(config.game.designHeight)))
            clay.anchorPoint = .zero
            clay.position = CGPoint(x: geo.x(forStep: Double(chapter.startStep + after)) + 600, y: 0)
            clay.zPosition = 50
            actorLayer.addChild(clay)
        }
    }

    private struct MarshTap: Decodable {
        let id: String
        let step: Int
        let dx: Double
        let sprite: String
        let flag: String?
    }

    /// Вещи §10.3. Каждая — отдельная цель, не житель и не письмо.
    private func installMarshTaps(in layer: SKNode, chapter: ChapterConfig) {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/chapter3_taps.json")
        guard let data = try? Data(contentsOf: url),
              let taps = try? JSONDecoder().decode([MarshTap].self, from: data) else { return }
        for tap in taps {
            let path = TextureStore.url(for: tap.sprite).path
            guard FileManager.default.fileExists(atPath: path) else { continue }
            let tex = TextureStore.shared.texture(tap.sprite)
            let node = SKSpriteNode(texture: tex)
            let h: CGFloat = 150
            let w = tex.size().width > 0 ? h * tex.size().width / tex.size().height : h
            node.size = CGSize(width: w, height: h)
            node.anchorPoint = CGPoint(x: 0.5, y: 0)
            node.position = CGPoint(x: geo.x(forStep: Double(chapter.startStep + tap.step)) + CGFloat(tap.dx),
                                    y: geo.roadY - 8)
            node.zPosition = 60
            node.name = "marsh:" + tap.id
            node.isUserInteractionEnabled = false
            layer.addChild(node)
        }
    }

    /// Подписи поселений после смены языка. Геометрия дороги и стык глав не трогаются.
    func retitleSettlements(_ config: WorldConfig) {
        for chapter in config.chapters {
            for settlement in chapter.settlements {
                let name = "settle.\(chapter.id).\(settlement.id)"
                guard let node = childNode(withName: "//\(name)") as? SettlementMarkerNode else { continue }
                node.setTitle(settlement.name)
            }
        }
    }

    private func addLayer(_ node: SKNode, parallax: Double) {
        if node.parent == nil { addChild(node) }
        layerNodes.append((node, CGFloat(parallax)))
    }

    /// Разрез: тематические модули в своих местах, промежутки — нейтральный тайл N
    /// (все модули имеют общие края с N, поэтому стыки бесшовны). N растягивается по X,
    /// чтобы промежуток заполнялся целым числом тайлов.
    private func buildUnderground(in layer: SKNode, chapter: ChapterConfig) {
        let ug = chapter.underground
        let tileW = CGFloat(ug.tilePixelSize[0] * ug.scale)
        let tileH = CGFloat(ug.tilePixelSize[1] * ug.scale)
        let topY = geo.sceneY(fromTop: ug.top)
        let bottomY = topY - tileH
        let neutralPath = ug.neutralTile.inChapter(chapter)
        let neutral = TextureStore.shared.texture(neutralPath)
        let W = CGFloat(config.game.designWidth)
        let stripStart = geo.x(forStep: Double(chapter.startStep)) - W * 4
        let stripEnd = geo.x(forStep: Double(chapter.endStep)) + W * 4

        func addNeutral(left: CGFloat, width: CGFloat) {
            let s = SKSpriteNode(texture: neutral)
            s.anchorPoint = .zero
            s.size = CGSize(width: width + 1, height: tileH)
            s.position = CGPoint(x: left, y: bottomY)
            if chapter.id == 3 { s.shader = MarshSurface.shader }
            layer.addChild(s)
        }

        let placed = ug.modules
            .map { m -> (path: String, left: CGFloat) in
                (m.image.inChapter(chapter), geo.x(forStep: Double(chapter.startStep + m.step)) + CGFloat(m.dx) - tileW / 2)
            }
            .sorted { $0.left < $1.left }

        var baseX = stripStart
        while baseX < stripEnd { addNeutral(left: baseX, width: tileW); baseX += tileW }
        guard let first = placed.first else { return }

        var cursor = first.left
        for (i, m) in placed.enumerated() {
            var left = m.left
            if i > 0 {
                let gap = left - cursor
                if gap < tileW * CGFloat(ug.minGapFraction) {
                    left = cursor // вплотную (сдвиг модуля не больше minGapFraction тайла)
                } else {
                    let n = max(1, Int((gap / tileW).rounded()))
                    let w = gap / CGFloat(n)
                    for j in 0..<n { addNeutral(left: cursor + CGFloat(j) * w, width: w) }
                }
            }
            let node = LazySpriteNode(imagePath: m.path, size: CGSize(width: tileW, height: tileH))
            node.anchorPoint = .zero
            node.position = CGPoint(x: left, y: bottomY)
            node.zPosition = 1
            if chapter.id == 3 { node.shader = MarshSurface.shader }
            layer.addChild(node)
            lazyNodes.append((node, layer))
            cursor = left + tileW
        }
    }

    // MARK: Progress API

    /// Новое целевое значение в ГЛОБАЛЬНЫХ шагах (сюжетные шаги главы сюда не передавать).
    func setTargetSteps(_ steps: Int) {
        let t = max(0, min(Double(worldEndStep), Double(steps)))
        targetStep = t
        if t < displayedStep {
            displayedStep = t // сброс прогресса (debug) — сразу
        } else if t - displayedStep > Double(config.game.walking.teleportGapSteps) {
            displayedStep = max(displayedStep, t - Double(config.game.walking.teleportLandBeforeSteps))
        }
    }

    /// DEBUG/сброс форса: меняется виртуальная позиция, но не total и не сама сцена.
    func jumpToSteps(_ steps: Int) {
        displayedStep = max(0, min(Double(worldEndStep), Double(steps)))
        targetStep = displayedStep
        postman.position.x = geo.x(forStep: displayedStep)
        velocityX = 0
        isReturning = false
        isFollowing = true
        camScale = 1
        camShiftY = 0
        camX = cameraRange(scale: camScale).upperBound
        updateRoadItems()
        updateCameraAndLayers()
        cullLazyNodes()
        updatePostmanVisibility()
    }

    /// Сброс истории: герой на старте, камера следит за ним, зум 1.
    func resetForNewStory() {
        jumpToSteps(0)
    }

    var isPostmanWalking: Bool { postman?.isWalking ?? false }

    // MARK: Story nodes

    struct RoadItemSpec {
        let id: String
        let step: Int
        /// Путь PNG относительно GameAssets без расширения (UI/ch1/road_envstake).
        let image: String
        /// Точка «ноги» в пикселях картинки (Y вниз): ставится на линию дороги.
        let foot: CGPoint
        let leftBehind: Bool
    }

    struct ResidentSpec {
        let id: String
        let step: Int
        let dx: CGFloat
        let height: CGFloat
        let image: UIImage
        let groundFraction: CGFloat
        var idle: ResidentLibrary.Idle? = nil
        /// Низ спрайта ниже линии дороги. nil — прежние 4 px (Федя и главы 1–2).
        var sink: CGFloat? = nil
    }

    /// Зарегистрировать фигуру спутника (картинка смотрит влево, как у жителей).
    func registerCompanion(id: String, image: UIImage, groundFraction: CGFloat, height: CGFloat) {
        companionFigures[id] = (image, groundFraction, height)
    }

    private func updateCompanion(_ dt: Double) {
        companionClock += dt
        if companionClock >= 0.25 {
            companionClock = 0
            let want = companionProvider?(displayedStep)
            if want != companionID { setCompanion(want) }
        }
        guard let node = companionNode, let postman else { return }
        // Во время реакции SKAction владеет transform; иначе follow/sway затрут прыжок каждый кадр.
        guard node.action(forKey: "residentReact") == nil else { return }
        // Отстаёт на ~40 px за спиной героя (герой идёт вправо), на той же линии земли.
        let targetX = postman.position.x - 40 - node.size.width * 0.5
        node.position = CGPoint(x: targetX, y: geo.roadY - 4)
        // Покачивание плавное (60 fps), затухает при остановке — без ступенек 12 fps.
        let target: Double = postman.isWalking ? 1 : 0
        companionSway += (target - companionSway) * min(1, dt * 6)
        companionAnim += dt
        node.zRotation = CGFloat(sin(companionAnim * 2 * .pi * 1.5) * 0.012 * companionSway)
    }

    private func setCompanion(_ id: String?) {
        nightFiguresDirty = true
        companionID = id
        if let old = companionNode {
            companionNode = nil
            old.run(.sequence([.fadeOut(withDuration: 0.4), .removeFromParent()]))
        }
        guard let id, let fig = companionFigures[id], let layer = actorLayerRef else { return }
        let w = fig.image.size.width, h = fig.image.size.height
        guard w > 0, h > 0, fig.image.cgImage != nil else { return }
        let node = SKSpriteNode(texture: TextureStore.shared.spriteTexture(fig.image, name: "companion/\(id)"))
        let drawH = fig.height / max(0.5, fig.groundFraction)
        node.size = CGSize(width: drawH * w / h, height: drawH)
        node.anchorPoint = CGPoint(x: 0.5, y: 1 - fig.groundFraction)
        node.name = "resident:" + id
        node.xScale = -1 // идёт вправо, вместе с почтальоном
        node.zPosition = 95
        Readability.light(node, on: Readability.enabled)
        let rim = Readability.rim(for: node)
        rim.isHidden = !Readability.enabled
        node.addChild(rim)
        let shadow = Readability.contactShadow(width: fig.height * w / h)
        shadow.isHidden = !Readability.enabled
        node.addChild(shadow)
        node.alpha = 0
        layer.addChild(node)
        node.run(.fadeIn(withDuration: 0.4))
        companionNode = node
    }

    /// Конверты на палке и посылки на дороге + жители у своих домов. Вызывается один раз после загрузки сюжета.
    func installStory(roadItems specs: [RoadItemSpec], residents: [ResidentSpec], chapterID: Int) {
        guard let layer = actorLayerRef else { return }
        for r in roadItems where r.chapterID == chapterID { r.node.removeFromParent() }
        roadItems.removeAll { $0.chapterID == chapterID }
        for spec in specs {
            let path = TextureStore.url(for: spec.image).path
            guard FileManager.default.fileExists(atPath: path) else { continue }
            let tex = TextureStore.shared.texture(spec.image)
            let node = SKSpriteNode(texture: tex)
            let size = tex.size()
            node.size = size
            node.anchorPoint = CGPoint(x: size.width > 0 ? spec.foot.x / size.width : 0.5,
                                       y: size.height > 0 ? 1 - spec.foot.y / size.height : 0)
            // Чуть впереди точки события — почтальон «подходит» к палке.
            node.position = CGPoint(x: geo.x(forStep: Double(spec.step)) + 70, y: geo.roadY - 6)
            node.zPosition = 90
            layer.addChild(node)
            roadItems.append(RoadItem(id: spec.id, chapterID: chapterID, step: Double(spec.step), node: node, leftBehind: spec.leftBehind))
        }
        let prefix = "\(chapterID)/"
        for key in residentNodes.keys.filter({ $0.hasPrefix(prefix) }) {
            residentNodes.removeValue(forKey: key)?.removeFromParent()
        }
        for r in residents {
            let w = r.image.size.width, h = r.image.size.height
            guard w > 0, h > 0, r.image.cgImage != nil else { continue }
            let drawH = r.height / max(0.5, r.groundFraction)
            // Кадр листа — отдельная картинка, не подтекстура всего листа.
            // Лист Пимена 8256×443 шире лимита Metal в симуляторе (8192): SKTexture всего листа
            // обрывает процесс в validateWithDevice, даже если на экране один кадр.
            let idleFrame = r.idle?.frameImage(at: 0)
            let tex = TextureStore.shared.spriteTexture(idleFrame ?? r.image, name: "\(prefix)\(r.id)")
            let node = SKSpriteNode(texture: tex)
            if let idle = r.idle, idleFrame != nil {
                let unit = drawH / h * idle.figureUnitsPerFramePx
                node.size = CGSize(width: idle.frameSize.width * unit, height: idle.frameSize.height * unit)
                node.anchorPoint = idle.anchor
                // Покадровый лист не крутим: в кадрах зашит сдвиг тела на 1–3 px, и житель дрожал.
            } else {
                node.size = CGSize(width: drawH * w / h, height: drawH)
                node.anchorPoint = CGPoint(x: 0.5, y: 1 - r.groundFraction)
            }
            node.position = CGPoint(x: geo.x(forStep: Double(r.step)) + r.dx,
                                    y: geo.roadY - (r.sink ?? 4))
            breathe(node)
            swayLiving(node, id: r.id)
            node.zPosition = 80
            node.name = "resident:" + prefix + r.id
            // Касания распознаёт SKView; узел не перехватывает touches у панорамы.
            node.isUserInteractionEnabled = false
            do {
                Readability.light(node)
                let rim = Readability.rim(for: node)
                node.addChild(rim)
                let figureW = r.height * w / h
                node.addChild(Readability.contactShadow(width: figureW))
            }
            layer.addChild(node)
            residentNodes[prefix + r.id] = node
            nightFiguresDirty = true
        }
        updateRoadItems()
        applyReadability()
    }

    /// Дыхание от стоп: и у листа idle, и у одиночного full.png (Федя и глава без листа).
    /// Покадровый spritesheet не крутим — там зашит дрожащий сдвиг тела.
    private func breathe(_ node: SKNode) {
        let period = Double.random(in: 3.1...3.9)
        let phase = Double.random(in: 0...(2 * Double.pi))
        let base = node.position.y
        let action = SKAction.customAction(withDuration: period) { n, t in
            let a = 2 * Double.pi * Double(t) / period + phase
            let s = sin(a)
            n.yScale = CGFloat(1 + 0.012 * s)
            n.position.y = base + CGFloat(2.4 * s)
        }
        node.run(.repeatForever(action), withKey: "breath")
    }

    /// Лёгкое покачивание full.png. Лист idle не трогаем: в кадрах уже есть сдвиг тела.
    /// Федя остаётся только на дыхании. У Петьки период короче — так дрожит удочка.
    private func swayLiving(_ node: SKNode, id: String) {
        let amp: Double
        let period: Double
        switch id {
        case "nyura": amp = 0.7; period = 5.4
        case "semyon": amp = 0.45; period = 4.8
        case "grisha": amp = 0.3; period = 6.2
        case "petka": amp = 0.85; period = 2.6
        default: return
        }
        let phase = Double.random(in: 0...(2 * Double.pi))
        let sway = SKAction.customAction(withDuration: period) { n, t in
            let a = 2 * Double.pi * Double(t) / period + phase
            n.zRotation = CGFloat(sin(a) * amp * Double.pi / 180)
        }
        node.run(.repeatForever(sway), withKey: "sway")
        guard id == "semyon" else { return }
        let shift = SKAction.sequence([
            .wait(forDuration: 7.5),
            .moveBy(x: 5, y: 0, duration: 0.35),
            .wait(forDuration: 0.45),
            .moveBy(x: -5, y: 0, duration: 0.35),
        ])
        node.run(.repeatForever(shift), withKey: "step")
    }

    /// Камыши главы 3 отдельными спрайтами: в картинке места они нарисованы мёртво.
    private func addMarshReeds(to layer: SKNode, chapter: ChapterConfig) {
        let image = "taps/reeds"
        let path = image.inChapter(chapter)
        guard FileManager.default.fileExists(atPath: TextureStore.url(for: path).path) else { return }
        let steps = [1200, 3600, 6200, 9800, 12800, 16400, 19800, 23200, 26800]
        for (i, step) in steps.enumerated() {
            let h: CGFloat = i % 2 == 0 ? 230 : 180
            let node = LazySpriteNode(imagePath: path, size: CGSize(width: h * 0.7, height: h))
            node.anchorPoint = .zero
            let dx: CGFloat = i % 2 == 0 ? -460 : 260
            node.position = CGPoint(x: geo.x(forStep: Double(chapter.startStep + step)) + dx, y: geo.roadY - 20)
            node.zPosition = 8
            layer.addChild(node)
            lazyNodes.append((node, layer))
            ambient?.decorate(prop: node, image: image,
                              pixelSize: CGSize(width: 175, height: 250), seed: step &* 17)
        }
    }

    /// Короткая реакция на самом спрайте, без смены текстуры/покадрового spritesheet.
    /// Длительность нужна GameModel: бумага появится ПОСЛЕ прыжка, не закроет его.
    @discardableResult
    func playResidentReact(chapterID: Int, id: String) -> TimeInterval {
        let animals: Set<String> = ["matrena", "goat_kid", "ramka", "cat_barrel",
                                    "rooster", "dog_penki", "raven_saddle"]
        guard animals.contains(id) else { return 0 }
        let key = "\(chapterID)/\(id)"
        var figures: [SKSpriteNode] = []
        if let resident = residentNodes[key] { figures.append(resident) }
        if companionID == key, let companion = companionNode { figures.append(companion) }
        guard !figures.isEmpty else { return 0 }
        let duration: TimeInterval = 0.6
        for node in figures {
            // Быстрые повторные тапы не суммируют смещение и не сбивают дыхание scaleY.
            guard node.action(forKey: "residentReact") == nil else { continue }
            let origin = node.position
            let rotation = node.zRotation
            let hop: CGFloat = id == "raven_saddle" || id == "rooster" ? 28 : 36
            let shadow = node.childNode(withName: "contactShadow")
            let shadowOrigin = shadow?.position ?? .zero
            let react = SKAction.customAction(withDuration: duration) { sprite, elapsed in
                let t = min(1, Double(elapsed) / duration)
                let lift = hop * CGFloat(sin(.pi * t))
                let shake = CGFloat(sin(6 * .pi * t) * (1 - t))
                sprite.position = CGPoint(x: origin.x + 7 * shake, y: origin.y + lift)
                sprite.zRotation = rotation + 0.06 * shake
                // Контактная тень остаётся у земли, край-подсветка движется вместе с фигурой.
                shadow?.position = CGPoint(x: shadowOrigin.x, y: shadowOrigin.y - lift)
            }
            node.run(.sequence([react, .run { [weak node, weak shadow] in
                node?.position = origin
                node?.zRotation = rotation
                shadow?.position = shadowOrigin
            }]), withKey: "residentReact")
        }
        return duration
    }

    private var nightShaderOn = false

    /// Вечер/ночь: отдельный шейдер только если nightFigureGain > 1.
    /// Сейчас герой темнеет общим тоном, как дома и земля. Днём шейдер снят.
    private func updateNightFigures() {
        let tint = ambient?.currentTint ?? RGB(r: 1, g: 1, b: 1)
        let n = Readability.enabled ? Readability.updateNight(tint: tint) : 0
        let want = n > 0.01
        if want == nightShaderOn && !(want && nightFiguresDirty) { return }
        nightShaderOn = want
        nightFiguresDirty = false
        let shader: SKShader? = want ? Readability.nightShader : nil
        var list: [SKSpriteNode] = postman?.partSprites ?? []
        var roots: [SKNode] = residentNodes.values.map { $0 as SKNode }
        if let c = companionNode { roots.append(c) }
        for r in roots {
            if let s = r as? SKSpriteNode, s.name != "rim" { list.append(s) }
            r.enumerateChildNodes(withName: ".//*") { node, _ in
                if let s = node as? SKSpriteNode, s.name != "rim", s.name != "contactShadow" { list.append(s) }
            }
        }
        for s in list { s.shader = shader }
    }

    /// Новые фигуры (смена козы и т.п.) — переназначить шейдер.
    private var nightFiguresDirty = true

    /// Читаемость героев вкл/выкл (Readability.enabled) — применяется на лету, без пересборки сцены.
    func applyReadability() {
        let on = Readability.enabled
        for (strip, _, kind) in tiledStrips {
            strip.hazeFactor = on ? Readability.hazeFactor(for: kind) : 0
        }
        for (node, _) in lazyNodes where node.gradeColor != .white {
            node.gradeFactor = on ? Readability.hazeFactor(for: node.gradeLayer) : 0
        }
        postman?.setReadability(on)
        var figures = Array(residentNodes.values)
        if let c = companionNode { figures.append(c) }
        for n in figures {
            Readability.light(n, on: on)
            n.childNode(withName: "rim")?.isHidden = !on
            n.childNode(withName: "contactShadow")?.isHidden = !on
        }
        postman?.childNode(withName: "contactShadow")?.isHidden = !on
    }

    /// Предмет не влез в сумку — остаётся стоять на дороге.
    func setRoadItemLeftBehind(_ ids: Set<String>, chapterID: Int) {
        for i in roadItems.indices where roadItems[i].chapterID == chapterID {
            roadItems[i].leftBehind = ids.contains(roadItems[i].id)
        }
        updateRoadItems()
    }

    private func updateRoadItems() {
        for i in roadItems.indices {
            let item = roadItems[i]
            let reached = displayedStep >= item.step
            if reached && !item.leftBehind {
                if !item.pickedUp {
                    roadItems[i].pickedUp = true
                    let lift = SKAction.group([.moveBy(x: -40, y: 160, duration: 0.35),
                                               .fadeOut(withDuration: 0.35),
                                               .scale(to: 0.6, duration: 0.35)])
                    lift.timingMode = .easeIn
                    item.node.run(lift, withKey: "pick")
                }
            } else if item.pickedUp {
                // Прокрутили назад / сброс: палка снова на дороге.
                roadItems[i].pickedUp = false
                item.node.removeAction(forKey: "pick")
                item.node.position.x = geo.x(forStep: item.step) + 70
                item.node.position.y = geo.roadY - 6
                item.node.alpha = 1
                item.node.setScale(1)
            }
        }
    }

    // MARK: Frame loop

    override func update(_ currentTime: TimeInterval) {
        let dt = lastUpdateTime == 0 ? 0 : min(currentTime - lastUpdateTime, 0.1)
        lastUpdateTime = currentTime

        // Ходьба: догоняем targetStep
        let pps = config.game.pixelsPerStep
        let gap = targetStep - displayedStep
        let gapPx = gap * pps
        // Причина дрожи: шагомер присылает шаги по 1–3 (1–4 px). Раньше каждый такой хвост включал ходьбу
        // на 1 кадр (поза walk[0] с другим уровнем тела) и сразу idle — герой «дёргался» при каждом апдейте.
        // Теперь маленький разрыв доезжает плавно без смены позы, ходьба — только с гистерезисом.
        if postman.isWalking ? gap > 0.01 : gapPx >= Self.walkStartGapPx {
            var speed = config.game.walking.speed // px/с
            if gapPx / speed > config.game.walking.maxCatchUpSeconds {
                speed = gapPx / config.game.walking.maxCatchUpSeconds
            }
            displayedStep = min(targetStep, displayedStep + speed * dt / pps)
            walkIdleClock = 0
            postman.setWalking(true)
        } else if gap > 0.0001 {
            // Плавный доезд (экспонента, без смены позы).
            displayedStep += gap * min(1, dt * 4)
            if targetStep - displayedStep < 0.01 { displayedStep = targetStep }
            walkIdleClock += dt
            if walkIdleClock > Self.walkStopHold { postman.setWalking(false) }
        } else {
            displayedStep = targetStep
            walkIdleClock += dt
            if walkIdleClock > Self.walkStopHold { postman.setWalking(false) }
        }
        postman.position.x = geo.x(forStep: displayedStep)
        postman.update(deltaTime: dt)
        ambienceClock += dt
        if ambienceClock >= 1 {
            ambienceClock = 0
            onAmbienceTick?(displayedStep)
        }
        updateRoadItems()

        stepCamera(dt)
        updateCameraAndLayers()
        ambient?.update(dt: dt, now: Date(), cameraX: camX, cameraScale: camScale,
                        visibleSize: CGSize(width: visibleWidth, height: visibleHeight))
        weather?.update(dt: dt)
        shimmerTime += dt
        MarshSurface.time.floatValue = Float(shimmerTime)
        applyChapterSky()
        updateMarshSky(dt: dt)
        updateCompanion(dt)
        updateNightFigures()
        updatePostmanVisibility()

        cullClock += dt
        if cullClock > 0.25 {
            cullClock = 0
            cullLazyNodes()
        }
    }

    /// Шаг под центром камеры, не шаг почтальона. Взгляд назад не перекрашивает небо.
    private var stepUnderCamera: Double {
        geo.step(forX: camX - geo.cameraLead)
    }

    private func chapter(containing step: Double) -> ChapterConfig? {
        config.chapters.last { Double($0.startStep) <= step }
    }

    /// Днём глава 3 красится своим небом. Долина и горы остаются на общем градиенте.
    private func applyChapterSky() {
        let chapter = chapter(containing: stepUnderCamera)
        let id = chapter?.id ?? 0
        guard id != appliedSkyChapter else { return }
        appliedSkyChapter = id
        let top = chapter?.sky?.topColor ?? config.layers.sky.topColor
        let bottom = chapter?.sky?.bottomColor ?? config.layers.sky.bottomColor
        let topColor = UIColor(hex: top)
        let bottomColor = UIColor(hex: bottom)
        backgroundColor = topColor
        if let ambient {
            ambient.setBaseSky(top: topColor, bottom: bottomColor)
        } else {
            skySprite?.texture = ProceduralTextures.sky(top: topColor, bottom: bottomColor, roadFraction: skyRoadFraction)
        }
    }

    // MARK: Camera

    private var followCameraX: CGFloat { geo.cameraX(forStep: displayedStep) }

    private var minCameraX: CGFloat { geo.cameraX(forStep: -config.game.camera.leftMarginSteps) }

    /// Пунктов экрана на единицу сцены (aspectFill, без учёта зума).
    private var pointsPerUnit: CGFloat {
        guard let v = view, v.bounds.width > 0, v.bounds.height > 0 else { return 1 }
        return max(v.bounds.width / size.width, v.bounds.height / size.height)
    }

    /// Видимая ширина в единицах сцены при масштабе 1 (aspectFill).
    private var visibleWidth: CGFloat {
        guard let v = view, v.bounds.width > 0 else { return size.width }
        return v.bounds.width / pointsPerUnit
    }

    /// Видимая высота в единицах сцены при масштабе 1.
    private var visibleHeight: CGFloat {
        guard let v = view, v.bounds.height > 0 else { return size.height }
        return v.bounds.height / pointsPerUnit
    }

    /// Обзор ограничен пройденным: слева — начало МИРА (с запасом leftMarginSteps),
    /// справа — то, что видно, когда камера следит за почтальоном. Вперёд не заглянуть.
    private var viewLeftLimit: CGFloat { minCameraX - visibleWidth / 2 }
    private var viewRightLimit: CGFloat { followCameraX + visibleWidth / 2 }

    /// Наибольший отзум сейчас: пройденный участок должен закрывать экран по ширине.
    private var allowedMaxScale: CGFloat {
        let byWidth = (viewRightLimit - viewLeftLimit) / max(1, visibleWidth)
        return max(1, min(maxCamScale, byWidth))
    }

    private func cameraRange(scale: CGFloat) -> ClosedRange<CGFloat> {
        let half = visibleWidth * scale / 2
        let lo = viewLeftLimit + half
        let hi = viewRightLimit - half
        return lo <= hi ? lo...hi : hi...hi
    }

    /// Y камеры: линия дороги остаётся на своей доле экрана; при отзуме сверху открывается небо,
    /// снизу — толща земли, но не ниже worldBottomY.
    private func cameraY(scale: CGFloat) -> CGFloat {
        let road = geo.roadY
        let y = road + (size.height / 2 - road) * scale
        return max(y, worldBottomY + visibleHeight * scale / 2)
    }

    private func stepCamera(_ dt: Double) {
        camScale = min(camScale, allowedMaxScale)
        let range = cameraRange(scale: camScale)
        if isFollowing {
            camX = followTargetX(scale: camScale)
        } else if isReturning {
            // «К почтальону»: зум плавно возвращается к 1.
            let k = CGFloat(1 - exp(-7 * dt))
            camScale += (1 - camScale) * k
            camShiftY += (0 - camShiftY) * k
            if abs(camScale - 1) < 0.003 { camScale = 1 }
            let target = followTargetX(scale: camScale)
            camX += (target - camX) * k
            if abs(target - camX) < 2 && camScale == 1 {
                camX = target
                isReturning = false
                isFollowing = true
            }
        } else if !isPanning && velocityX != 0 {
            camX += velocityX * CGFloat(dt)
            velocityX *= CGFloat(exp(-3.2 * dt))
            if abs(velocityX) < 8 { velocityX = 0 }
        }
        let clamped = min(max(camX, range.lowerBound), range.upperBound)
        if clamped != camX {
            camX = clamped
            velocityX = 0
        }
    }

    /// Сдвиг по Y, при котором приближенный кадр не выходит за кадр масштаба 1.
    private func clampShiftY(_ shift: CGFloat, scale: CGFloat) -> CGFloat {
        guard scale < 1 else { return 0 }
        let base = cameraY(scale: scale), y1 = cameraY(scale: 1)
        let room = visibleHeight * (1 - scale) / 2
        let lo = y1 - room - base, hi = y1 + room - base
        return lo <= hi ? min(max(shift, lo), hi) : 0
    }

    /// Куда смотрит следящая камера: при масштабе ≥ 1 — как раньше; при приближении герой
    /// плавно уходит к центру кадра, чтобы не выпасть за левый край.
    private func followTargetX(scale: CGFloat) -> CGFloat {
        let r = cameraRange(scale: scale)
        guard scale < 1, let postman else { return r.upperBound }
        let px = postman.position.x
        let x = px + (r.upperBound - px) * scale
        return min(max(x, r.lowerBound), r.upperBound)
    }

    private func updateCameraAndLayers() {
        camShiftY = clampShiftY(camShiftY, scale: camScale)
        cam.position = CGPoint(x: camX, y: cameraY(scale: camScale) + camShiftY)
        cam.setScale(camScale)
        for (node, k) in layerNodes {
            node.position.x = camX * (1 - k)
        }
        let half = visibleWidth * camScale / 2 + 64
        for (strip, k, _) in tiledStrips {
            strip.layout(localMinX: k * camX - half, localMaxX: k * camX + half)
        }
        for (crop, range) in chapterCrops {
            crop.isHidden = range.upperBound < camX - half || range.lowerBound > camX + half
        }
    }

    private func updatePostmanVisibility() {
        guard let postman else { return }
        let px = postman.position.x
        let half = visibleWidth * camScale / 2
        let margin: CGFloat = 60
        var now: Offscreen?
        if px - margin > camX + half {
            now = .right
        } else if px + margin < camX - half {
            now = .left
        }
        if now != postmanOffscreen {
            postmanOffscreen = now
            onPostmanOffscreenChange?(now)
        }
    }

    /// Кнопка «к почтальону»: камера плавно возвращается и снова следит за героем (зум сохраняется).
    func returnToPostman(animated: Bool = true) {
        velocityX = 0
        guard !isFollowing || camScale != 1 else { return }
        if animated {
            isFollowing = false
            isReturning = true
        } else {
            isReturning = false
            isFollowing = true
            camScale = 1
            camShiftY = 0
            camX = cameraRange(scale: camScale).upperBound
            updateCameraAndLayers()
            updatePostmanVisibility()
        }
    }

    /// Загрузка/выгрузка текстур по расстоянию от камеры; анимации (дым, качание, жители) — только на экране.
    private func cullLazyNodes() {
        let cx = cam.position.x
        let half = visibleWidth * camScale / 2
        let W = size.width
        for (node, layer) in lazyNodes {
            let f = node.frame
            let minX = layer.position.x + f.minX
            let maxX = layer.position.x + f.maxX
            let dist = max(0, max(minX - cx, cx - maxX))
            if dist < half + W * 0.9 {
                node.setNeeded(true)
            } else if dist > half + W * 2.5 {
                node.setNeeded(false)
            }
            node.isPaused = dist > half + 120
        }
        for node in residentNodes.values {
            let f = node.frame
            let dist = max(0, max(f.minX - cx, cx - f.maxX))
            node.isPaused = dist > half + 120
        }
        for node in lifeNodes {
            let f = node.frame
            let dist = max(0, max(f.minX - cx, cx - f.maxX))
            node.isPaused = dist > half + 120
        }
    }

    // MARK: Gestures (панорама с инерцией + пинч-зум)

    override func didMove(to view: SKView) {
        super.didMove(to: view)
        view.isMultipleTouchEnabled = true
        if panRecognizer == nil {
            let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan(_:)))
            pan.maximumNumberOfTouches = 2
            pan.cancelsTouchesInView = false
            pan.delegate = self
            panRecognizer = pan
            let pinch = UIPinchGestureRecognizer(target: self, action: #selector(handlePinch(_:)))
            pinch.cancelsTouchesInView = false
            pinch.delegate = self
            pinchRecognizer = pinch
            let tap = UITapGestureRecognizer(target: self, action: #selector(handleResidentTap(_:)))
            tap.cancelsTouchesInView = false
            tap.delegate = self
            // Свайп/пинч, начатый на фигуре, всегда остаётся жестом камеры, а не тапом.
            tap.require(toFail: pan)
            tap.require(toFail: pinch)
            residentTapRecognizer = tap
        }
        if let pan = panRecognizer, pan.view !== view { view.addGestureRecognizer(pan) }
        if let pinch = pinchRecognizer, pinch.view !== view { view.addGestureRecognizer(pinch) }
        if let tap = residentTapRecognizer, tap.view !== view { view.addGestureRecognizer(tap) }
    }

    override func willMove(from view: SKView) {
        if let pan = panRecognizer { view.removeGestureRecognizer(pan) }
        if let pinch = pinchRecognizer { view.removeGestureRecognizer(pinch) }
        if let tap = residentTapRecognizer { view.removeGestureRecognizer(tap) }
        super.willMove(from: view)
    }

    /// Hit-test в координатах сцены учитывает камеру, зум, якорь и дыхание спрайта.
    /// Дочерние rim/тень сами по себе не расширяют область тапа на пустую дорогу.
    private func residentKey(at point: CGPoint) -> String? {
        for hit in nodes(at: point) {
            var candidate: SKNode? = hit
            while let node = candidate, node !== self {
                if let name = node.name, name.hasPrefix("resident:"),
                   !node.isHidden, node.alpha > 0.01, let parent = node.parent,
                   node.contains(convert(point, to: parent)) {
                    let key = String(name.dropFirst("resident:".count))
                    if residentNodes[key] === node || companionNode === node { return key }
                }
                candidate = node.parent
            }
        }
        return nil
    }

    private func marshKey(at point: CGPoint) -> String? {
        for hit in nodes(at: point) {
            var candidate: SKNode? = hit
            while let node = candidate, node !== self {
                if let name = node.name, name.hasPrefix("marsh:"),
                   !node.isHidden, node.alpha > 0.01, let parent = node.parent,
                   node.contains(convert(point, to: parent)) {
                    return String(name.dropFirst("marsh:".count))
                }
                candidate = node.parent
            }
        }
        return nil
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        guard gestureRecognizer === residentTapRecognizer else { return true }
        guard isUserInteractionEnabled, let view else { return false }
        let point = convertPoint(fromView: touch.location(in: view))
        return residentKey(at: point) != nil || marshKey(at: point) != nil || hitsPostman(at: point)
    }

    private func hitsPostman(at point: CGPoint) -> Bool {
        guard let postman, !postman.isHidden, postman.alpha > 0.01 else { return false }
        for hit in nodes(at: point) {
            var node: SKNode? = hit
            while let current = node {
                if current === postman { return true }
                node = current.parent
            }
        }
        return false
    }

    @objc private func handleResidentTap(_ g: UITapGestureRecognizer) {
        guard g.state == .ended, !isPanning, let view = g.view else { return }
        let point = convertPoint(fromView: g.location(in: view))
        if let key = marshKey(at: point) {
            onMarshTap?(key)
            return
        }
        if let key = residentKey(at: point) {
            let parts = key.split(separator: "/", maxSplits: 1).map(String.init)
            guard parts.count == 2, let chapterID = Int(parts[0]) else { return }
            onResidentTap?(chapterID, parts[1])
            return
        }
        guard hitsPostman(at: point) else { return }
        postman.playNod(reduceMotion: UIAccessibility.isReduceMotionEnabled)
        onPostmanTap?()
    }

    @objc private func handlePan(_ g: UIPanGestureRecognizer) {
        guard let v = g.view else { return }
        let unitsPerPoint = camScale / pointsPerUnit
        switch g.state {
        case .began:
            isPanning = true
            isReturning = false
            isFollowing = false
            velocityX = 0
        case .changed:
            let t = g.translation(in: v)
            camX -= t.x * unitsPerPoint   // палец вправо → смотрим назад
            g.setTranslation(.zero, in: v)
            let r = cameraRange(scale: camScale)
            camX = min(max(camX, r.lowerBound), r.upperBound)
        case .ended, .cancelled, .failed:
            isPanning = false
            if g.state == .ended {
                let vx = -g.velocity(in: v).x * unitsPerPoint
                velocityX = max(-9000, min(9000, vx))
            }
        default:
            break
        }
    }

    @objc private func handlePinch(_ g: UIPinchGestureRecognizer) {
        guard let v = g.view else { return }
        switch g.state {
        case .began:
            isReturning = false
            velocityX = 0
        case .changed:
            guard g.scale > 0 else { return }
            let old = camScale
            let new = min(max(old / g.scale, minCamScale), allowedMaxScale)
            g.scale = 1
            guard new != old else { return }
            let loc = g.location(in: v)
            let ppu = pointsPerUnit
            if !isFollowing {
                // Точка под пальцами остаётся на месте.
                let fx = loc.x - v.bounds.width / 2
                let worldX = camX + fx * old / ppu
                camX = worldX - fx * new / ppu
            }
            // По вертикали — тоже (только в приближении; отзум держит дорогу на своей доле экрана).
            let fy = v.bounds.height / 2 - loc.y
            let oldY = cameraY(scale: old) + camShiftY
            let worldY = oldY + fy * old / ppu
            camShiftY = clampShiftY(worldY - fy * new / ppu - cameraY(scale: new), scale: new)
            camScale = new
            let r = cameraRange(scale: camScale)
            camX = min(max(camX, r.lowerBound), r.upperBound)
            updateCameraAndLayers()
        default:
            break
        }
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                           shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
        let mine: [UIGestureRecognizer?] = [panRecognizer, pinchRecognizer]
        return mine.contains { $0 === gestureRecognizer } && mine.contains { $0 === otherGestureRecognizer }
    }
}

// MARK: - Живые сценки болот

extension WorldScene {
    /// Спрайт с якорем в левом нижнем углу. Нет файла — сценку не ставим.
    fileprivate func marshLifeNode(prop: PropConfig, chapter: ChapterConfig, size: CGSize) -> SKSpriteNode? {
        let path = prop.image.inChapter(chapter)
        guard FileManager.default.fileExists(atPath: TextureStore.url(for: path).path) else { return nil }
        let node = SKSpriteNode(texture: TextureStore.shared.texture(path))
        node.size = size
        node.anchorPoint = .zero
        node.name = "life:\(prop.image):\(prop.step)"
        return node
    }

    /// После постановки левым нижним углом переносим якорь в низ по центру, картинку не сдвигая.
    fileprivate func pinLifeBottom(_ node: SKSpriteNode) {
        let dx = (0.5 - node.anchorPoint.x) * node.size.width
        node.anchorPoint = CGPoint(x: 0.5, y: 0)
        node.position.x += dx
    }

    fileprivate func animateMarshLife(_ node: SKSpriteNode, image: String,
                                     chapter: ChapterConfig, pixelHeight: CGFloat) {
        let scale = node.size.height / max(1, pixelHeight)
        func frame(_ name: String) -> String { name.inChapter(chapter) }
        switch image {
        case "ambient/dragonflies":
            swapLife(node, frames: [frame("ambient/dragonflies"), frame("ambient/dragonflies_b")],
                     scale: scale, hold: 0.32)
            flitDragonflies(on: node, part: frame("ambient/dragonfly_one"))
        case "ambient/boat_trestles":
            rockLife(node, degrees: 1.15, period: 3.4)
        case "ambient/smoke_chimney":
            swapLife(node, frames: [frame("ambient/smoke_chimney"), frame("ambient/smoke_chimney_b")],
                     scale: scale, hold: 0.85)
            pulseLife(node, low: 0.62, high: 1, period: 2.4)
            emitPuffs(on: node, frames: [frame("ambient/smoke_puff_a"), frame("ambient/smoke_puff_b")],
                      every: 1.7, rise: 80...140, height: 26, at: 0.92)
        case "ambient/frog":
            hopFrog(node, scale: scale, chapter: chapter)
        case "ambient/heron_stand":
            herdHeron(node, scale: scale, chapter: chapter, flies: true)
        case "ambient/smoke_peat":
            driftLife(node, distance: 18, period: 7.5, alphaLow: 0.45, alphaHigh: 0.9)
            emitPuffs(on: node, frames: [frame("ambient/smoke_puff_b"), frame("ambient/smoke_puff_a")],
                      every: 2.8, rise: 8...22, height: 16, at: 0.55)
        case "ambient/punt":
            driftLife(node, distance: 34, period: 11, alphaLow: 1, alphaHigh: 1)
            rockLife(node, degrees: 1.4, period: 5.5)
        case "ambient/ducks":
            diveDucks(node, scale: scale, chapter: chapter)
        case "ambient/mist_low":
            driftLife(node, distance: 48, period: 16, alphaLow: 0.38, alphaHigh: 0.82)
        case "ambient/boat_moored":
            rockLife(node, degrees: 0.8, period: 4.8)
        default:
            break
        }
    }

    private func showLife(_ node: SKSpriteNode, path: String, scale: CGFloat) {
        let tex = TextureStore.shared.texture(path)
        let s = tex.size()
        guard s.height > 1 else { return }
        node.texture = tex
        node.size = CGSize(width: s.width * scale, height: s.height * scale)
    }

    private func swapLife(_ node: SKSpriteNode, frames: [String], scale: CGFloat, hold: Double) {
        guard frames.count > 1 else { return }
        var steps: [SKAction] = []
        for path in frames {
            steps.append(.run { [weak self, weak node] in
                guard let self, let node else { return }
                self.showLife(node, path: path, scale: scale)
            })
            steps.append(.wait(forDuration: hold))
        }
        node.run(.repeatForever(.sequence(steps)), withKey: "frames")
    }

    private func rockLife(_ node: SKSpriteNode, degrees: Double, period: Double) {
        let phase = Double.random(in: 0...(2 * Double.pi))
        let rock = SKAction.customAction(withDuration: period) { n, t in
            let a = 2 * Double.pi * Double(t) / period + phase
            n.zRotation = CGFloat(sin(a) * degrees * Double.pi / 180)
        }
        node.run(.repeatForever(rock), withKey: "rock")
    }

    private func pulseLife(_ node: SKSpriteNode, low: CGFloat, high: CGFloat, period: Double) {
        let phase = Double.random(in: 0...(2 * Double.pi))
        let pulse = SKAction.customAction(withDuration: period) { n, t in
            let a = 2 * Double.pi * Double(t) / period + phase
            n.alpha = low + (high - low) * CGFloat(0.5 + 0.5 * sin(a))
        }
        node.run(.repeatForever(pulse), withKey: "pulse")
    }

    /// Синус по X от домашней точки. Альфа не трогается, если low == high.
    private func driftLife(_ node: SKSpriteNode, distance: CGFloat, period: Double,
                           alphaLow: CGFloat, alphaHigh: CGFloat) {
        let homeX = node.position.x
        let phase = Double.random(in: 0...(2 * Double.pi))
        let drift = SKAction.customAction(withDuration: period) { n, t in
            let a = 2 * Double.pi * Double(t) / period + phase
            let s = sin(a)
            n.position.x = homeX + distance * CGFloat(s)
            if alphaLow != alphaHigh {
                n.alpha = alphaLow + (alphaHigh - alphaLow) * CGFloat(0.5 + 0.5 * s)
            }
        }
        node.run(.repeatForever(drift), withKey: "drift")
    }

    private func flitDragonflies(on node: SKSpriteNode, part: String) {
        let tex = TextureStore.shared.texture(part)
        let aspect = tex.size().width / max(1, tex.size().height)
        for i in 0..<3 {
            let one = SKSpriteNode(texture: tex)
            let h: CGFloat = 20
            one.size = CGSize(width: h * aspect, height: h)
            one.position = CGPoint(x: CGFloat(i - 1) * 26, y: node.size.height * 0.62)
            one.zPosition = 1
            node.addChild(one)
            let home = one.position
            let phase = Double(i) * 2.2
            let period = 0.9 + Double(i) * 0.28
            let flap = SKAction.customAction(withDuration: period) { n, t in
                let a = 2 * Double.pi * Double(t) / period + phase
                n.position = CGPoint(x: home.x + CGFloat(sin(a) * 24),
                                     y: home.y + CGFloat(cos(a * 1.4) * 12))
                n.zRotation = CGFloat(sin(a) * 0.45)
            }
            one.run(.repeatForever(flap), withKey: "flit")
        }
    }

    private func emitPuffs(on node: SKSpriteNode, frames: [String], every: Double,
                           rise: ClosedRange<CGFloat>, height: CGFloat, at: CGFloat) {
        let spawn = SKAction.run { [weak node] in
            guard let node, node.children.count < 4, let path = frames.randomElement() else { return }
            let tex = TextureStore.shared.texture(path)
            let puff = SKSpriteNode(texture: tex)
            let aspect = tex.size().width / max(1, tex.size().height)
            puff.size = CGSize(width: height * aspect, height: height)
            puff.alpha = 0
            puff.setScale(0.65)
            puff.position = CGPoint(x: 0, y: node.size.height * at)
            puff.zPosition = 2
            node.addChild(puff)
            let up = CGFloat.random(in: rise)
            let drift = CGFloat.random(in: -16...22)
            puff.run(.sequence([
                .group([
                    .fadeAlpha(to: 0.75, duration: 0.3),
                    .moveBy(x: drift, y: up, duration: 2.4),
                    .scale(to: 1.2, duration: 2.4),
                ]),
                .fadeOut(withDuration: 0.45),
                .removeFromParent(),
            ]))
        }
        node.run(.repeatForever(.sequence([spawn, .wait(forDuration: every)])), withKey: "puffs")
    }

    private func hopFrog(_ node: SKSpriteNode, scale: CGFloat, chapter: ChapterConfig) {
        func show(_ name: String) -> SKAction {
            let path = name.inChapter(chapter)
            return .run { [weak self, weak node] in
                guard let self, let node else { return }
                self.showLife(node, path: path, scale: scale)
            }
        }
        let sit = SKAction.sequence([
            show("ambient/frog"), .wait(forDuration: 1.8),
            show("ambient/frog_throat"), .wait(forDuration: 0.55),
            show("ambient/frog"), .wait(forDuration: 1.4),
        ])
        let hop = SKAction.sequence([
            show("ambient/frog_jump"),
            .moveBy(x: 16, y: 22, duration: 0.26),
            .moveBy(x: -16, y: -22, duration: 0.2),
            show("ambient/frog"),
            .wait(forDuration: 0.35),
        ])
        node.run(.repeatForever(.sequence([.repeat(sit, count: 2), hop])), withKey: "hop")
    }

    private func herdHeron(_ node: SKSpriteNode, scale: CGFloat, chapter: ChapterConfig, flies: Bool) {
        func show(_ name: String) -> SKAction {
            let path = name.inChapter(chapter)
            return .run { [weak self, weak node] in
                guard let self, let node else { return }
                self.showLife(node, path: path, scale: scale)
            }
        }
        let preen = SKAction.sequence([
            show("ambient/heron_stand"), .wait(forDuration: 3.6),
            show("ambient/heron_preen"), .wait(forDuration: 2.1),
        ])
        guard flies else {
            node.run(.repeatForever(preen), withKey: "heron")
            return
        }
        let fly = SKAction.sequence([
            show("ambient/heron_fly"),
            .moveBy(x: 10, y: 78, duration: 0.45),
            show("ambient/heron_fly_b"),
            .wait(forDuration: 0.35),
            .moveBy(x: -10, y: -78, duration: 0.4),
            show("ambient/heron_stand"),
            .wait(forDuration: 0.3),
        ])
        node.run(.repeatForever(.sequence([.repeat(preen, count: 3), fly])), withKey: "heron")
    }

    private func diveDucks(_ node: SKSpriteNode, scale: CGFloat, chapter: ChapterConfig) {
        func show(_ name: String) -> SKAction {
            let path = name.inChapter(chapter)
            return .run { [weak self, weak node] in
                guard let self, let node else { return }
                self.showLife(node, path: path, scale: scale)
            }
        }
        let homeX = node.position.x
        let bob = SKAction.customAction(withDuration: 5.5) { n, t in
            let a = 2 * Double.pi * Double(t) / 5.5
            n.position.x = homeX + CGFloat(sin(a) * 14)
        }
        node.run(.repeatForever(bob), withKey: "bob")
        let dive = SKAction.sequence([
            show("ambient/ducks"), .wait(forDuration: 4.2),
            show("ambient/ducks_dive"), .wait(forDuration: 0.7),
        ])
        node.run(.repeatForever(dive), withKey: "dive")
    }
}

/// Лёгкий блик по верхней кромке разреза болот. Не вуаль на камеру: только пиксели тайла.
enum MarshSurface {
    static let time = SKUniform(name: "u_time", float: 0)
    static let shader: SKShader = {
        let src = """
        void main() {
            vec4 c = texture2D(u_texture, v_tex_coord);
            float y = v_tex_coord.y;
            float band = smoothstep(0.62, 0.74, y) * (1.0 - smoothstep(0.74, 0.86, y));
            float wave = sin(v_tex_coord.x * 46.0 + u_time * 1.2);
            c.rgb += vec3(0.025, 0.04, 0.03) * wave * band;
            gl_FragColor = c * v_color_mix;
        }
        """
        let sh = SKShader(source: src)
        sh.uniforms = [time]
        return sh
    }()
}

private extension String {
    /// "places/x" → "Chapter1/places/x"
    func inChapter(_ chapter: ChapterConfig) -> String {
        chapter.assetsFolder + "/" + self
    }
}
