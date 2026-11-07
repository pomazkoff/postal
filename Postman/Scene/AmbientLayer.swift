import SpriteKit
import UIKit

/// Цвет для интерполяции неба и тона мира.
struct RGB: Equatable {
    var r: CGFloat
    var g: CGFloat
    var b: CGFloat

    init(r: CGFloat, g: CGFloat, b: CGFloat) {
        self.r = r
        self.g = g
        self.b = b
    }

    init(_ color: UIColor) {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        color.getRed(&r, green: &g, blue: &b, alpha: &a)
        self.init(r: r, g: g, b: b)
    }

    init(hex: String) { self.init(UIColor(hex: hex)) }

    func mix(_ o: RGB, _ t: CGFloat) -> RGB {
        RGB(r: r + (o.r - r) * t, g: g + (o.g - g) * t, b: b + (o.b - b) * t)
    }

    /// Компенсация тона: небо рисуется под слоем-умножением, поэтому заранее делим на тон.
    func divided(by o: RGB) -> RGB {
        RGB(r: min(1, r / max(0.05, o.r)), g: min(1, g / max(0.05, o.g)), b: min(1, b / max(0.05, o.b)))
    }

    func distance(_ o: RGB) -> CGFloat { abs(r - o.r) + abs(g - o.g) + abs(b - o.b) }

    var color: UIColor { UIColor(red: r, green: g, blue: b, alpha: 1) }
}

/// Детерминированный ГПСЧ (одинаковый «джиттер» при каждом запуске).
struct SeededRandom: RandomNumberGenerator {
    private var state: UInt64
    init(seed: Int) { state = UInt64(truncatingIfNeeded: seed) &* 0x9E3779B97F4A7C15 | 1 }
    mutating func next() -> UInt64 {
        state ^= state << 13
        state ^= state >> 7
        state ^= state << 17
        return state
    }
}

/// Атлас мелкого арта: один PNG + JSON {"frames": {"name": [x, y, w, h]}} (пиксели, Y вниз).
final class AmbientAtlas {
    private var textures: [String: SKTexture] = [:]
    private var sizes: [String: CGSize] = [:]

    init?(path: String) {
        let pngURL = TextureStore.url(for: path)
        let jsonURL = WorldConfigLoader.assetsRoot.appendingPathComponent(path + ".json")
        guard let image = UIImage(contentsOfFile: pngURL.path),
              let data = try? Data(contentsOf: jsonURL),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let frames = obj["frames"] as? [String: [Double]] else { return nil }
        let W = Double(image.size.width), H = Double(image.size.height)
        guard W > 0, H > 0 else { return nil }
        let sheet = TextureStore.shared.spriteTexture(image, name: path)
        for (name, r) in frames where r.count == 4 {
            let rect = CGRect(x: r[0] / W, y: 1 - (r[1] + r[3]) / H, width: r[2] / W, height: r[3] / H)
            textures[name] = SKTexture(rect: rect, in: sheet)
            sizes[name] = CGSize(width: r[2], height: r[3])
        }
    }

    func texture(_ name: String) -> SKTexture? { textures[name] }

    func size(_ name: String) -> CGSize { sizes[name] ?? CGSize(width: 1, height: 1) }

    /// Все кадры с префиксом, по имени (cloud_0, cloud_1, …).
    func names(prefix: String) -> [String] {
        textures.keys.filter { $0.hasPrefix(prefix) }.sorted()
    }
}

/// Живой мир поверх WorldScene: небо по местному времени (утро/день/закат/ночь), тон мира,
/// звёзды, облака в нескольких планах, птицы, дым из труб, качание травы, колокол Звонарни.
/// Вся «покадровая» анимация — 12 fps с лёгким джиттером (стоп-моушн, как риг почтальона).
final class AmbientLayer {
    let config: AmbientConfig
    private let atlas: AmbientAtlas?
    private let sky: SKSpriteNode
    private let baseTop: RGB
    private let baseBottom: RGB
    private let roadFraction: CGFloat
    private let designSize: CGSize
    private let tintNode: SKSpriteNode
    /// Текущий тон суток (умножение поверх мира) — для «вечерних» героев (Readability.updateNight).
    private(set) var currentTint = RGB(r: 1, g: 1, b: 1)
    private let starField = SKNode()

    private struct Cloud {
        let sprite: SKSpriteNode
        let base: CGFloat
    }
    private struct CloudPlane {
        let node: SKNode
        let parallax: CGFloat
        let speed: CGFloat
        var drift: CGFloat
        let clouds: [Cloud]
    }
    private var planes: [CloudPlane] = []
    /// Ширина «петли» облаков: больше видимой ширины при наибольшем отзуме + облако.
    private let cloudSpan: CGFloat

    private var birdsLayer: SKNode?
    /// Стая появилась на экране. Звук сюда не входит.
    var onFlock: (() -> Void)?
    private var birdTimer: Double = 6
    private var tick: Double = 0
    private var skyClock: Double = 0
    private var shownTop = RGB(r: -1, g: 0, b: 0)
    private var shownBottom = RGB(r: -1, g: 0, b: 0)
    private var rng = SystemRandomNumberGenerator()

    /// DEBUG: сдвиг часов суток (кнопка в DebugPanel), чтобы посмотреть закат/ночь днём.
    static var debugHourOffset: Double = 0

    /// addLayer — регистрирует узел как слой с параллаксом в сцене (layer.x = camera.x · (1 − k)).
    init(config: AmbientConfig, sky: SKSpriteNode, camera: SKCameraNode, designSize: CGSize,
         baseTop: UIColor, baseBottom: UIColor, roadFraction: CGFloat, maxCameraScale: CGFloat,
         addLayer: (SKNode, Double) -> Void) {
        self.config = config
        self.atlas = AmbientAtlas(path: config.atlas)
        self.sky = sky
        self.baseTop = RGB(baseTop)
        self.baseBottom = RGB(baseBottom)
        self.roadFraction = roadFraction
        self.designSize = designSize
        self.cloudSpan = designSize.width * (maxCameraScale + 1.0)

        // Тон мира: слой-умножение поверх всего (HUD — SwiftUI, его не касается).
        tintNode = SKSpriteNode(color: .white, size: CGSize(width: designSize.width * 3, height: designSize.height * 3))
        tintNode.blendMode = .multiply
        tintNode.zPosition = 900
        tintNode.isHidden = true
        camera.addChild(tintNode)

        // Звёзды — «бесконечно далеко»: привязаны к камере, за дальним планом.
        starField.zPosition = -900
        camera.addChild(starField)
        buildStars()

        buildClouds(addLayer: addLayer)

        if let birds = config.birds, atlas?.names(prefix: "bird_").isEmpty == false {
            let layer = SKNode()
            layer.zPosition = CGFloat(birds.z)
            addLayer(layer, birds.parallax)
            birdsLayer = layer
            birdTimer = Double.random(in: 3...8)
        }
        applyTimeOfDay(Date())
    }

    // MARK: Frame

    func update(dt: Double, now: Date, cameraX: CGFloat, cameraScale: CGFloat, visibleSize: CGSize) {
        skyClock += dt
        if skyClock >= 10 {
            skyClock = 0
            applyTimeOfDay(now)
        }
        for i in planes.indices { planes[i].drift += planes[i].speed * CGFloat(dt) }
        tick += dt
        let frame = 1 / max(1, config.fps)
        if tick >= frame {
            tick = tick.truncatingRemainder(dividingBy: frame)
            layoutClouds(cameraX: cameraX)
        }
        if let birds = config.birds, birdsLayer != nil {
            birdTimer -= dt
            if birdTimer <= 0 {
                birdTimer = Double.random(in: birds.interval[0]...max(birds.interval[0], birds.interval[1]))
                spawnFlock(cameraX: cameraX, halfWidth: visibleSize.width * cameraScale / 2)
            }
        }
    }

    /// Пересчитать небо сразу (после смены debugHourOffset).
    func refreshTimeOfDay() { skyClock = 100 }

    // MARK: Время суток

    private struct SkyState {
        var top: RGB
        var bottom: RGB
        var tint: RGB
        var stars: CGFloat
    }

    private func state(of key: AmbientConfig.SkyKey) -> SkyState {
        SkyState(top: key.skyTop.map(RGB.init(hex:)) ?? baseTop,
                 bottom: key.skyBottom.map(RGB.init(hex:)) ?? baseBottom,
                 tint: RGB(hex: key.tint),
                 stars: CGFloat(key.stars))
    }

    private func skyState(at date: Date) -> SkyState? {
        let keys = config.timeOfDay.sorted { $0.hour < $1.hour }
        guard let first = keys.first, let last = keys.last else { return nil }
        let c = Calendar.current.dateComponents([.hour, .minute, .second], from: date)
        var hour = Double(c.hour ?? 12) + Double(c.minute ?? 0) / 60 + Double(c.second ?? 0) / 3600
        hour = (hour + Self.debugHourOffset).truncatingRemainder(dividingBy: 24)
        if hour < 0 { hour += 24 }
        var a = last, b = first
        var ha = last.hour - 24, hb = first.hour
        for i in 0..<keys.count {
            let k0 = keys[i]
            let k1 = i + 1 < keys.count ? keys[i + 1] : first
            let h1 = i + 1 < keys.count ? k1.hour : first.hour + 24
            if hour >= k0.hour && hour < h1 {
                a = k0; b = k1; ha = k0.hour; hb = h1
                break
            }
        }
        if hour < first.hour { ha = last.hour - 24; hb = first.hour; a = last; b = first }
        let raw = hb > ha ? (hour - ha) / (hb - ha) : 0
        let t = CGFloat(raw * raw * (3 - 2 * raw)) // плавный переход
        let sa = state(of: a), sb = state(of: b)
        return SkyState(top: sa.top.mix(sb.top, t), bottom: sa.bottom.mix(sb.bottom, t),
                        tint: sa.tint.mix(sb.tint, t), stars: sa.stars + (sb.stars - sa.stars) * t)
    }

    private func applyTimeOfDay(_ date: Date) {
        guard let s = skyState(at: date) else { return }
        let top = s.top.divided(by: s.tint)
        let bottom = s.bottom.divided(by: s.tint)
        if top.distance(shownTop) > 0.004 || bottom.distance(shownBottom) > 0.004 {
            sky.texture = ProceduralTextures.sky(top: top.color, bottom: bottom.color, roadFraction: roadFraction)
            shownTop = top
            shownBottom = bottom
        }
        let white = RGB(r: 1, g: 1, b: 1)
        currentTint = s.tint
        tintNode.color = s.tint.color
        tintNode.isHidden = s.tint.distance(white) < 0.01
        starField.alpha = max(0, min(1, s.stars))
        starField.isHidden = s.stars < 0.02
        starField.isPaused = starField.isHidden
    }

    // MARK: Звёзды

    private func buildStars() {
        guard let cfg = config.stars, let atlas else { return }
        let names = atlas.names(prefix: "star_")
        guard !names.isEmpty else { return }
        var gen = SeededRandom(seed: 11)
        let W = designSize.width, H = designSize.height
        let fps = max(1, config.fps)
        for i in 0..<cfg.count {
            let name = names[i % names.count]
            guard let tex = atlas.texture(name) else { continue }
            let star = SKSpriteNode(texture: tex)
            let px = CGFloat(Double.random(in: cfg.size[0]...max(cfg.size[0], cfg.size[1]), using: &gen))
            let sz = atlas.size(name)
            star.size = CGSize(width: px, height: px * sz.height / max(1, sz.width))
            // Экранные координаты относительно центра камеры: верхняя часть кадра (+ запас для отзума).
            let x = CGFloat.random(in: -W * 0.6...W * 0.6, using: &gen)
            let y = CGFloat.random(in: H * (0.5 - CGFloat(cfg.topFraction))...H * 0.62, using: &gen)
            star.position = CGPoint(x: x, y: y)
            star.zRotation = CGFloat.random(in: -0.4...0.4, using: &gen)
            starField.addChild(star)
            // Мерцание: изредка «моргает» на пару кадров (стоп-моушн).
            let low = CGFloat.random(in: 0.25...0.6, using: &gen)
            let blink = SKAction.sequence([
                .wait(forDuration: Double.random(in: 1.5...6, using: &gen), withRange: 2),
                .fadeAlpha(to: low, duration: 0),
                .wait(forDuration: 2 / fps),
                .fadeAlpha(to: 0.8, duration: 0),
                .wait(forDuration: 1 / fps),
                .fadeAlpha(to: 1, duration: 0),
            ])
            star.run(.repeatForever(blink))
        }
    }

    // MARK: Облака

    private func buildClouds(addLayer: (SKNode, Double) -> Void) {
        guard let atlas else { return }
        let names = atlas.names(prefix: "cloud_")
        guard !names.isEmpty else { return }
        var gen = SeededRandom(seed: 5)
        for (li, cfg) in config.clouds.enumerated() {
            let node = SKNode()
            node.zPosition = CGFloat(cfg.z)
            addLayer(node, cfg.parallax)
            var clouds: [Cloud] = []
            for i in 0..<cfg.count {
                let name = names[(i + li) % names.count]
                guard let tex = atlas.texture(name) else { continue }
                let s = SKSpriteNode(texture: tex)
                let h = CGFloat(Double.random(in: cfg.height[0]...max(cfg.height[0], cfg.height[1]), using: &gen))
                let sz = atlas.size(name)
                s.size = CGSize(width: h * sz.width / max(1, sz.height), height: h)
                s.anchorPoint = CGPoint(x: 0.5, y: 0)
                s.alpha = CGFloat(cfg.alpha)
                s.position.y = CGFloat(Double.random(in: cfg.y[0]...max(cfg.y[0], cfg.y[1]), using: &gen))
                if Bool.random(using: &gen) { s.xScale = -1 }
                node.addChild(s)
                // Равномерно по петле + случайный сдвиг, чтобы не было «строя».
                let base = cloudSpan * (CGFloat(i) + CGFloat.random(in: 0...0.6, using: &gen)) / CGFloat(max(1, cfg.count))
                clouds.append(Cloud(sprite: s, base: base))
            }
            planes.append(CloudPlane(node: node, parallax: CGFloat(cfg.parallax), speed: CGFloat(cfg.speed),
                                     drift: 0, clouds: clouds))
        }
    }

    private func layoutClouds(cameraX: CGFloat) {
        let span = cloudSpan
        for plane in planes {
            // Центр экрана в локальных координатах слоя: camera.x − layer.x = camera.x · k.
            let localCam = cameraX * plane.parallax
            for c in plane.clouds {
                let u = c.base + plane.drift - localCam + span / 2
                let rel = u - span * floor(u / span) - span / 2
                c.sprite.position.x = (localCam + rel).rounded()
            }
        }
    }

    // MARK: Птицы

    private func spawnFlock(cameraX: CGFloat, halfWidth: CGFloat) {
        guard let cfg = config.birds, let layer = birdsLayer, let atlas else { return }
        let frames = atlas.names(prefix: "bird_").compactMap { atlas.texture($0) }
        guard let firstName = atlas.names(prefix: "bird_").first, !frames.isEmpty else { return }
        let k = CGFloat(cfg.parallax)
        let localCam = cameraX * k
        let half = halfWidth + 200
        let dir: CGFloat = Bool.random() ? 1 : -1
        let count = Int.random(in: cfg.flock[0]...max(cfg.flock[0], cfg.flock[1]))
        let baseY = CGFloat(Double.random(in: cfg.y[0]...max(cfg.y[0], cfg.y[1])))
        let speed = CGFloat(Double.random(in: cfg.speed[0]...max(cfg.speed[0], cfg.speed[1])))
        let distance = half * 2
        let duration = Double(distance / max(1, speed))
        let fps = max(1, config.fps)
        let sz = atlas.size(firstName)
        let h = CGFloat(cfg.height)
        for i in 0..<count {
            let bird = SKSpriteNode(texture: frames[0])
            let scale = CGFloat.random(in: 0.8...1.1)
            bird.size = CGSize(width: h * scale * sz.width / max(1, sz.height), height: h * scale)
            bird.xScale = dir   // арт смотрит вправо
            let startX = localCam - dir * (half + CGFloat(i) * 110)
            let y0 = baseY + CGFloat.random(in: -50...50)
            bird.position = CGPoint(x: startX, y: y0)
            layer.addChild(bird)
            let phase = Double.random(in: 0...6)
            let flap = SKAction.repeatForever(.animate(with: frames, timePerFrame: 2 / fps))
            let fly = SKAction.customAction(withDuration: duration) { node, elapsed in
                // Квантуем движение до 12 fps — «покадрово».
                let t = (Double(elapsed) * fps).rounded(.down) / fps
                node.position.x = startX + dir * speed * CGFloat(t)
                node.position.y = y0 + CGFloat(sin(t * 2.2 + phase) * 14)
            }
            bird.run(.sequence([.wait(forDuration: Double.random(in: 0...0.4)), flap]))
            bird.run(.sequence([fly, .removeFromParent()]))
        }
        onFlock?()
    }

    // MARK: Декор пропсов (дым, качание, колокол)

    /// Пропс с колоколом рисуется из картинки без колокола (колокол — отдельный качающийся спрайт).
    func substituteImage(for image: String) -> String? {
        guard let atlas, let bell = config.bells.first(where: { $0.prop == image }),
              atlas.texture(bell.frame) != nil else { return nil }
        return bell.baseImage
    }

    /// Вызывается для каждого пропса при сборке мира. node — спрайт с якорем (0, 0) и размером в px сцены.
    func decorate(prop node: SKSpriteNode, image: String, pixelSize: CGSize, seed: Int) {
        let sx = node.size.width / max(1, pixelSize.width)
        let sy = node.size.height / max(1, pixelSize.height)
        let fps = max(1, config.fps)

        func local(_ ix: Double, _ iy: Double) -> CGPoint {
            CGPoint(x: CGFloat(ix) * sx - node.anchorPoint.x * node.size.width,
                    y: (pixelSize.height - CGFloat(iy)) * sy - node.anchorPoint.y * node.size.height)
        }

        if let sway = config.sway.first(where: { image.hasPrefix($0.match) }) {
            // Качаемся от низа по центру: переносим якорь, не сдвигая картинку.
            let dx = (0.5 - node.anchorPoint.x) * node.size.width
            node.anchorPoint = CGPoint(x: 0.5, y: node.anchorPoint.y)
            node.position.x += dx
            var gen = SeededRandom(seed: seed)
            let period = Double.random(in: sway.period[0]...max(sway.period[0], sway.period[1]), using: &gen)
            let action = Self.swayAction(amp: sway.amp, period: period, fps: fps, gen: &gen)
            let delay = Double.random(in: 0...period, using: &gen)
            node.run(.sequence([.wait(forDuration: delay), action]), withKey: "sway")
        }

        for smoke in config.smoke where smoke.prop == image {
            guard let atlas else { break }
            let puffs = atlas.names(prefix: "smoke_").compactMap { name -> (SKTexture, CGSize)? in
                atlas.texture(name).map { ($0, atlas.size(name)) }
            }
            guard !puffs.isEmpty, smoke.at.count >= 2 else { continue }
            let emitter = SKNode()
            emitter.position = local(smoke.at[0], smoke.at[1])
            emitter.zPosition = 3
            node.addChild(emitter)
            let scale = CGFloat(smoke.scale)
            let wind = CGFloat(smoke.wind)
            let spawn = SKAction.run { [weak emitter] in
                guard let emitter, let pick = puffs.randomElement() else { return }
                Self.puff(in: emitter, texture: pick.0, pixelSize: pick.1, scale: scale, wind: wind, fps: fps)
            }
            emitter.run(.repeatForever(.sequence([spawn, .wait(forDuration: smoke.interval, withRange: smoke.interval * 0.5)])))
        }

        for bell in config.bells where bell.prop == image {
            guard let atlas, let tex = atlas.texture(bell.frame), bell.pivot.count >= 2, bell.hang.count >= 2 else { continue }
            let px = atlas.size(bell.frame)
            let sprite = SKSpriteNode(texture: tex)
            sprite.size = CGSize(width: px.width * sx, height: px.height * sy)
            sprite.anchorPoint = CGPoint(x: CGFloat(bell.hang[0]) / max(1, px.width),
                                         y: 1 - CGFloat(bell.hang[1]) / max(1, px.height))
            sprite.position = local(bell.pivot[0], bell.pivot[1])
            sprite.zPosition = CGFloat(bell.z)
            node.addChild(sprite)
            var gen = SeededRandom(seed: seed &+ 7)
            sprite.run(Self.swayAction(amp: bell.amp, period: bell.period, fps: fps, gen: &gen), withKey: "bell")
        }
    }

    /// Покачивание по синусу, покадрово (fps), с джиттером «на двойках».
    static func swayAction(amp: Double, period: Double, fps: Double, gen: inout SeededRandom) -> SKAction {
        let n = max(4, Int((period * fps).rounded()))
        var steps: [SKAction] = []
        steps.reserveCapacity(n * 2)
        for i in 0..<n {
            var deg = sin(2 * Double.pi * Double(i) / Double(n)) * amp
            if i % 2 == 0 { deg += Double.random(in: -0.18...0.18, using: &gen) * amp }
            steps.append(.rotate(toAngle: CGFloat(deg * Double.pi / 180), duration: 0))
            steps.append(.wait(forDuration: 1 / fps))
        }
        return .repeatForever(.sequence(steps))
    }

    /// Клуб дыма: растёт, поднимается, сносится ветром и тает. Движение квантуется до fps.
    private static func puff(in emitter: SKNode, texture: SKTexture, pixelSize: CGSize,
                             scale: CGFloat, wind: CGFloat, fps: Double) {
        let p = SKSpriteNode(texture: texture)
        let h = 70 * scale
        p.size = CGSize(width: h * pixelSize.width / max(1, pixelSize.height), height: h)
        p.alpha = 0
        p.setScale(0.4)
        p.zRotation = CGFloat.random(in: -0.5...0.5)
        emitter.addChild(p)
        let life = Double.random(in: 3.0...4.2)
        let rise = CGFloat.random(in: 220...300) * scale
        let drift = wind * CGFloat.random(in: 70...120) * scale
        let spin = CGFloat.random(in: -0.6...0.6)
        let a0 = p.zRotation
        let seed = Double.random(in: 0...100)
        let action = SKAction.customAction(withDuration: life) { node, elapsed in
            let frame = (Double(elapsed) * fps).rounded(.down)
            let q = CGFloat(min(1, frame / fps / life))
            let jitter = CGFloat(sin((frame + seed) * 12.9898)) * 1.5
            node.position = CGPoint(x: drift * q * q + jitter, y: rise * q)
            node.setScale(0.4 + 0.9 * q)
            node.zRotation = a0 + spin * q
            node.alpha = q < 0.12 ? q / 0.12 * 0.9 : 0.9 * (1 - (q - 0.12) / 0.88)
        }
        p.run(.sequence([action, .removeFromParent()]))
    }
}
