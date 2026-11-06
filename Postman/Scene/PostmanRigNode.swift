import SpriteKit

/// Почтальон-перекладка: 13 спрайтов частей, позы из RigWalk, 12 fps, ступенчато (без интерполяции).
/// Начало координат узла — точка между стопами на линии земли рига; масштаб уже применён.
final class PostmanRigNode: SKNode {
    private let walk: RigWalk
    private let rig: RigConfig
    private let rigRoot = SKNode()
    private var sprites: [RigPart: SKSpriteNode] = [:]
    private var walkFrames: [[RigPart: Affine2D]] = []
    private var idlePose: [RigPart: Affine2D] = [:]
    private let idleFrame: Int
    private let randomJitter: Bool

    private(set) var isWalking = false
    private var frameIndex = 0
    private var frameClock: TimeInterval = 0

    /// - Parameters:
    ///   - height: высота героя в px дизайна (430).
    ///   - sourceHeight: высота силуэта в px исходника рига (1028).
    ///   - centerX: X центра героя в исходнике (≈ бедро, 395).
    init(rig: RigConfig, height: CGFloat, sourceHeight: CGFloat, centerX: CGFloat,
         idleFrame: Int, randomJitter: Bool) {
        self.rig = rig
        self.walk = RigWalk(rig: rig)
        self.idleFrame = max(0, min(RigWalk.frameCount - 1, idleFrame))
        self.randomJitter = randomJitter
        super.init()

        let scale = height / sourceHeight
        rigRoot.setScale(scale)
        // Локальные координаты rigRoot = координаты исходника с перевёрнутой осью Y.
        // Линия земли рига (ground_y) → y = 0 узла; центр героя → x = 0.
        rigRoot.position = CGPoint(x: -centerX * scale, y: CGFloat(rig.groundY) * scale)
        addChild(rigRoot)

        for (i, part) in RigPart.allCases.enumerated() {
            let tex = TextureStore.shared.texture("Rig/parts/\(part.imageName)", downscaledBy: scale)
            let s = SKSpriteNode(texture: tex)
            // Спрайт рисуется в размере исходника (текстура уменьшена заранее, rigRoot масштабирует обратно 1:1).
            s.size = tex.size().applying(CGAffineTransform(scaleX: 1 / scale, y: 1 / scale))
            s.anchorPoint = CGPoint(x: 0, y: 1) // левый верхний угол PNG, как offsets в rig.json
            s.zPosition = CGFloat(i)
            if part.isDark {
                s.color = .black
                s.colorBlendFactor = 0.38 // ≈ rgb × 0.62
            }
            rigRoot.addChild(s)
            sprites[part] = s
            if !part.isDark {
                Readability.light(s)
                let rim = Readability.rim(for: s)
                // Сдвиг подсветки задан в px дизайна; rigRoot уменьшен в scale раз.
                rim.position = CGPoint(x: Readability.rimOffset.x / scale, y: Readability.rimOffset.y / scale)
                rim.alpha = Readability.rimAlpha * 0.8
                rim.zPosition = -0.5
                s.addChild(rim)
            }
        }

        rebuildFrames(jitterSeed: nil)
        idlePose = walk.pose(frame: self.idleFrame, jitter: (0, 0))
        apply(idlePose)
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) не используется") }

    private func rebuildFrames(jitterSeed: Int?) {
        walkFrames = (0..<RigWalk.frameCount).map { f in
            // Без джиттера торса/головы: сдвиг всего тела на ±1 ед. каждые 1/12 с читался на устройстве
            // как дрожание героя относительно плавно едущей земли. Стоп-моушн остаётся в позах частей.
            let j: (Double, Double) = (0, 0)
            _ = jitterSeed
            return walk.pose(frame: f, jitter: j)
        }
    }

    /// Раскладка аффинной матрицы части (Y вниз) на позицию/поворот спрайта (Y вверх).
    private func apply(_ pose: [RigPart: Affine2D]) {
        for (part, m) in pose {
            guard let s = sprites[part] else { continue }
            let topLeft = m.apply(rig.offset(part.imageName))
            s.position = CGPoint(x: topLeft.x, y: -topLeft.y)
            s.zRotation = CGFloat(-m.angle)
        }
    }

    /// Читаемость (DEBUG-переключатель): тёплый свет и кромка на частях.
    /// Спрайты частей (для вечернего шейдера).
    var partSprites: [SKSpriteNode] { Array(sprites.values) }

    func setReadability(_ on: Bool) {
        for (part, s) in sprites where !part.isDark {
            Readability.light(s, on: on)
            s.childNode(withName: "rim")?.isHidden = !on
        }
    }

    func setWalking(_ walking: Bool) {
        guard walking != isWalking else { return }
        isWalking = walking
        if walking {
            frameIndex = 0
            frameClock = 0
            apply(walkFrames[0])
        } else {
            apply(idlePose)
        }
    }

    /// Вызывать каждый кадр сцены.
    func update(deltaTime dt: TimeInterval) {
        guard isWalking else { return }
        frameClock += dt
        let frameDuration = 1.0 / RigWalk.fps
        var advanced = false
        while frameClock >= frameDuration {
            frameClock -= frameDuration
            frameIndex += 1
            if frameIndex >= RigWalk.frameCount {
                frameIndex = 0
                if randomJitter { rebuildFrames(jitterSeed: 1) }
            }
            advanced = true
        }
        if advanced { apply(walkFrames[frameIndex]) }
    }
}
