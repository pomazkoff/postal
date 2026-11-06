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
    /// Переход глав. Уже запаса контента за границей (ширина экрана × 4), поэтому дыр при скролле нет.
    private static let chapterBlend: CGFloat = 640
    private struct RoadSpan {
        let node: SKSpriteNode
        let chapterIndex: Int
        let worldLeft: CGFloat
        let width: CGFloat
        let z: CGFloat
    }
    private var roadSpans: [RoadSpan] = []
    private var lazyNodes: [(node: LazySpriteNode, layer: SKNode)] = []
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
    private var lastUpdateTime: TimeInterval = 0
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
        let sky = SKSpriteNode(texture: ProceduralTextures.sky(top: UIColor(hex: L.sky.topColor),
                                                              bottom: UIColor(hex: L.sky.bottomColor),
                                                              roadFraction: roadFraction))
        sky.size = CGSize(width: W * 2, height: H * 1.2) // запас на другие пропорции экрана
        sky.position = .zero
        sky.zPosition = -1000
        cam.addChild(sky)

        // Живой мир (облака, птицы, звёзды, время суток) — если есть Data/ambient.json и атлас.
        if let ac = AmbientConfig.load() {
            ambient = AmbientLayer(config: ac, sky: sky, camera: cam, designSize: CGSize(width: W, height: H),
                                   baseTop: UIColor(hex: L.sky.topColor), baseBottom: UIColor(hex: L.sky.bottomColor),
                                   roadFraction: roadFraction, maxCameraScale: maxCamScale,
                                   addLayer: { [unowned self] node, k in self.addLayer(node, parallax: k) })
        }

        // Погода (ясно/дождь/снег/туман) — поверх неба и планов, под тоном суток.
        weather = WeatherLayer(camera: cam, designSize: CGSize(width: W, height: H))

        // Одна сцена/камера/фигура героя на весь мир. Главы — соседние сегменты, а не сцены.
        let actorLayer = SKNode()
        actorLayer.zPosition = 200
        addLayer(actorLayer, parallax: L.mainParallax)
        actorLayerRef = actorLayer
        for (index, chapter) in config.chapters.enumerated() {
            buildChapter(chapter, index: index, actorLayer: actorLayer)
        }
        blendChapterRoads()

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
        postman = node

        updateCameraAndLayers()
        cullLazyNodes()
        applyReadability()
    }

    private var worldEndStep: Int { config.chapters.map(\.endStep).max() ?? 0 }

    /// Маска закреплена в мировых координатах; параллакс двигается ВНУТРИ неё.
    /// Соседние главы заходят друг на друга на chapterBlend: нижняя остаётся сплошной,
    /// верхняя (добавлена позже, тот же z) проявляется. Сумма покрытия 1, без дыры и без тёмной ямы.
    private func croppedLayer(chapter: ChapterConfig, index: Int, z: CGFloat, parallax: Double) -> SKNode {
        let margin = CGFloat(config.game.designWidth) * 4
        let half = Self.chapterBlend / 2
        let rawLeft = index == 0 ? -margin : geo.x(forStep: Double(chapter.startStep))
        let rawRight = index + 1 < config.chapters.count
            ? geo.x(forStep: Double(config.chapters[index + 1].startStep))
            : geo.x(forStep: Double(chapter.endStep)) + margin
        let fadeLeft = index > 0
        let fadeRight = false
        let left = fadeLeft ? rawLeft - half : rawLeft
        let right = index + 1 < config.chapters.count ? rawRight + half : rawRight
        let crop = SKCropNode()
        crop.zPosition = z
        let mask = chapterMaskSprite(left: left, right: right, fadeLeft: fadeLeft, fadeRight: fadeRight)
        crop.maskNode = mask
        addChild(crop)
        chapterCrops.append((crop, left...right))
        let layer = SKNode()
        crop.addChild(layer)
        addLayer(layer, parallax: parallax)
        return layer
    }

    /// Появление следующей главы слева направо. Предыдущая в этом же окне не гасится: она под низом.
    private func chapterMaskSprite(left: CGFloat, right: CGFloat, fadeLeft: Bool, fadeRight: Bool) -> SKSpriteNode {
        let span = max(1, right - left)
        let pixels = 1024
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let image = UIGraphicsImageRenderer(size: CGSize(width: pixels, height: 4), format: format).image { ctx in
            let cg = ctx.cgContext
            for i in 0..<pixels {
                let x = left + span * (CGFloat(i) + 0.5) / CGFloat(pixels)
                var alpha: CGFloat = 1
                if fadeLeft {
                    let t = min(1, max(0, (x - left) / Self.chapterBlend))
                    let s = t * t * (3 - 2 * t)
                    alpha = min(alpha, s)
                }
                if fadeRight {
                    let t = min(1, max(0, (x - (right - Self.chapterBlend)) / Self.chapterBlend))
                    let s = t * t * (3 - 2 * t)
                    alpha = min(alpha, 1 - s)
                }
                cg.setFillColor(UIColor(white: 1, alpha: alpha).cgColor)
                cg.fill(CGRect(x: i, y: 0, width: 1, height: 4))
            }
        }
        let mask = SKSpriteNode(texture: SKTexture(image: image), size: CGSize(width: span, height: 16000))
        mask.anchorPoint = .zero
        mask.position = CGPoint(x: left, y: worldBottomY - 4000)
        return mask
    }

    /// Дорога не в маске главы. Верхний тайл гаснет, нижний остаётся сплошным — поверхность не обрезается ступенькой.
    private func blendChapterRoads() {
        let half = Self.chapterBlend / 2
        for i in 0..<(config.chapters.count - 1) {
            let boundary = geo.x(forStep: Double(config.chapters[i + 1].startStep))
            let zone = (boundary - half)...(boundary + half)
            let lefts = roadSpans.filter { $0.chapterIndex == i && roadOverlaps($0, zone) }
            let rights = roadSpans.filter { $0.chapterIndex == i + 1 && roadOverlaps($0, zone) }
            guard !lefts.isEmpty, !rights.isEmpty else { continue }
            let leftZ = lefts.map(\.z).max() ?? 0
            let rightZ = rights.map(\.z).max() ?? 0
            let fadeLeftChapter = leftZ >= rightZ
            for road in fadeLeftChapter ? lefts : rights {
                applyRoadFade(road, boundary: boundary, half: half, fadeOutToTheRight: fadeLeftChapter)
            }
        }
    }

    private func roadOverlaps(_ road: RoadSpan, _ zone: ClosedRange<CGFloat>) -> Bool {
        road.worldLeft < zone.upperBound && road.worldLeft + road.width > zone.lowerBound
    }

    private func applyRoadFade(_ road: RoadSpan, boundary: CGFloat, half: CGFloat, fadeOutToTheRight: Bool) {
        let fade0 = Float((boundary - half - road.worldLeft) / road.width)
        let fade1 = Float((boundary + half - road.worldLeft) / road.width)
        let src = """
        void main() {
            vec4 c = texture2D(u_texture, v_tex_coord);
            float t = clamp((v_tex_coord.x - u_fade0) / max(0.0001, u_fade1 - u_fade0), 0.0, 1.0);
            float a = mix(u_a0, u_a1, t);
            gl_FragColor = c * a;
        }
        """
        let shader = SKShader(source: src)
        shader.uniforms = [
            SKUniform(name: "u_fade0", float: fade0),
            SKUniform(name: "u_fade1", float: fade1),
            SKUniform(name: "u_a0", float: fadeOutToTheRight ? 1 : 0),
            SKUniform(name: "u_a1", float: fadeOutToTheRight ? 0 : 1),
        ]
        road.node.shader = shader
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
            // Мировой X левого края: центр героя на шаге + dx; для слоёв с k≠1 — так, чтобы
            // пропс стоял на этом месте экрана, когда камера следит за героем на этом шаге.
            let worldLeft = geo.x(forStep: Double(chapter.startStep + p.step)) + CGFloat(p.dx)
            let camAtStep = geo.cameraX(forStep: Double(chapter.startStep + p.step))
            let localLeft = worldLeft - camAtStep * CGFloat(1 - k)
            node.position = CGPoint(x: localLeft, y: geo.roadY - CGFloat(p.sink ?? 0))
            node.zPosition = CGFloat(p.z ?? 0)
            target.addChild(node)
            lazyNodes.append((node, target))
            if p.layer == .main && p.image.contains("road/road_main") {
                roadSpans.append(RoadSpan(node: node, chapterIndex: index, worldLeft: worldLeft,
                                          width: w, z: node.zPosition))
            }
            ambient?.decorate(prop: node, image: p.image,
                              pixelSize: CGSize(width: p.pixelSize[0], height: p.pixelSize[1]),
                              seed: p.step &* 31 &+ Int(p.dx))
        }

        // Общая станция на границе двух глав получает только одну подпись.
        for settlement in chapter.settlements {
            let globalStep = chapter.startStep + settlement.step
            let duplicate = index > 0 && config.chapters[index - 1].settlements.contains {
                $0.id == settlement.id && config.chapters[index - 1].startStep + $0.step == globalStep
            }
            guard !duplicate else { continue }
            let marker = SettlementMarkerNode(title: settlement.name)
            marker.position = CGPoint(x: geo.x(forStep: Double(globalStep)), y: geo.roadY)
            marker.zPosition = 10
            actorLayer.addChild(marker)
        }
        // Заглушка только за ПОСЛЕДНЕЙ известной главой, не поверх следующей.
        if index == config.chapters.count - 1, let after = chapter.rawClayAfterStep {
            let clay = SKSpriteNode(color: UIColor(red: 0.55, green: 0.47, blue: 0.38, alpha: 1),
                                    size: CGSize(width: W * 4, height: CGFloat(config.game.designHeight)))
            clay.anchorPoint = .zero
            clay.position = CGPoint(x: geo.x(forStep: Double(chapter.startStep + after)) + 600, y: 0)
            clay.zPosition = 50
            actorLayer.addChild(clay)
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
                // Покадровое дыхание из листа убрано: в кадрах листа зашит сдвиг тела 1–3 px от кадра
                // к кадру (фазовая корреляция по листам) — это и было дрожание жителей. Статичный кадр +
                // плавное дыхание scaleY от стоп (якорь на линии земли), 60 fps.
                let period = Double.random(in: 3.0...3.8)
                let phase = Double.random(in: 0...(2 * Double.pi))
                let breath = SKAction.customAction(withDuration: period, actionBlock: { n, t in
                    let a = 2 * Double.pi * Double(t) / period + phase
                    n.yScale = CGFloat(1 + 0.006 * sin(a))
                })
                node.run(.repeatForever(breath), withKey: "breath")
            } else {
                node.size = CGSize(width: drawH * w / h, height: drawH)
                node.anchorPoint = CGPoint(x: 0.5, y: 1 - r.groundFraction)
            }
            node.position = CGPoint(x: geo.x(forStep: Double(r.step)) + r.dx, y: geo.roadY - 4)
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
        updateRoadItems()

        stepCamera(dt)
        updateCameraAndLayers()
        ambient?.update(dt: dt, now: Date(), cameraX: camX, cameraScale: camScale,
                        visibleSize: CGSize(width: visibleWidth, height: visibleHeight))
        weather?.update(dt: dt)
        updateCompanion(dt)
        updateNightFigures()
        updatePostmanVisibility()

        cullClock += dt
        if cullClock > 0.25 {
            cullClock = 0
            cullLazyNodes()
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

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        guard gestureRecognizer === residentTapRecognizer else { return true }
        guard isUserInteractionEnabled, let view else { return false }
        return residentKey(at: convertPoint(fromView: touch.location(in: view))) != nil
    }

    @objc private func handleResidentTap(_ g: UITapGestureRecognizer) {
        guard g.state == .ended, !isPanning, let view = g.view,
              let key = residentKey(at: convertPoint(fromView: g.location(in: view))) else { return }
        let parts = key.split(separator: "/", maxSplits: 1).map(String.init)
        guard parts.count == 2, let chapterID = Int(parts[0]) else { return }
        onResidentTap?(chapterID, parts[1])
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

private extension String {
    /// "places/x" → "Chapter1/places/x"
    func inChapter(_ chapter: ChapterConfig) -> String {
        chapter.assetsFolder + "/" + self
    }
}
