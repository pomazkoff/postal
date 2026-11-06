import SpriteKit
import UIKit

/// Погода поверх мира: дождь (косые «пластилиновые» штрихи + серое небо), снег (медленные хлопья),
/// туман (мягкие полосы над средним планом, ниже контраст). Ясно — ничего не добавляется.
/// Всё — дети камеры (экранные координаты), смена состояния — плавный кроссфейд.
/// Ночной/закатный тон AmbientLayer (умножение, z 900) ложится поверх — погода темнеет вместе с миром.
final class WeatherLayer {
    private let designSize: CGSize
    private let rain: SKEmitterNode
    private let snow: SKEmitterNode
    private let fogRoot = SKNode()
    private var fogBands: [(node: SKSpriteNode, phase: Double, speed: Double, alpha: CGFloat)] = []
    private let fogVeil: SKSpriteNode
    private let skyTint: SKSpriteNode

    private let rainRate: CGFloat = 150
    private let snowRate: CGFloat = 22

    private var level: [Weather: CGFloat] = [.clear: 1, .rain: 0, .snow: 0, .fog: 0]
    private(set) var target: Weather = .clear
    private var pollClock: Double = 100
    private var time: Double = 0
    private var lastTintKey: Int = -1

    /// Скорость кроссфейда: полный переход примерно за 3 с.
    private let fadeRate: CGFloat = 1.0 / 3.0

    init(camera: SKCameraNode, designSize: CGSize) {
        self.designSize = designSize
        let W = designSize.width, H = designSize.height

        // Серое небо/мир при дожде: ещё одно умножение под тоном суток.
        skyTint = SKSpriteNode(color: .white, size: CGSize(width: W * 3, height: H * 3))
        skyTint.blendMode = .multiply
        skyTint.zPosition = 899
        skyTint.isHidden = true
        camera.addChild(skyTint)

        // Дождь: косые глиняные штрихи, падают влево-вниз.
        rain = SKEmitterNode()
        rain.particleTexture = SKTexture(image: WeatherLayer.streakImage())
        rain.particleBirthRate = 0
        rain.particleLifetime = 2.2
        rain.particleLifetimeRange = 0.4
        rain.position = CGPoint(x: W * 0.15, y: H * 0.62)
        rain.particlePositionRange = CGVector(dx: W * 1.8, dy: 0)
        let slant: CGFloat = 0.22
        rain.emissionAngle = -.pi / 2 - slant
        rain.emissionAngleRange = 0.03
        rain.particleSpeed = 1500
        rain.particleSpeedRange = 250
        rain.particleRotation = -slant
        rain.particleScale = 1
        rain.particleScaleRange = 0.35
        rain.particleAlpha = 0.5
        rain.particleAlphaRange = 0.2
        rain.particleColor = UIColor(red: 0.80, green: 0.84, blue: 0.88, alpha: 1)
        rain.particleColorBlendFactor = 1
        rain.particleBlendMode = .alpha
        rain.zPosition = 600
        rain.alpha = 0
        rain.isHidden = true
        camera.addChild(rain)

        // Снег: медленные комочки, лёгкий снос и вращение.
        snow = SKEmitterNode()
        snow.particleTexture = SKTexture(image: WeatherLayer.flakeImage())
        snow.particleBirthRate = 0
        snow.particleLifetime = 18
        snow.particleLifetimeRange = 3
        snow.position = CGPoint(x: 0, y: H * 0.62)
        snow.particlePositionRange = CGVector(dx: W * 1.6, dy: 0)
        snow.emissionAngle = -.pi / 2
        snow.emissionAngleRange = 0.5
        snow.particleSpeed = 150
        snow.particleSpeedRange = 60
        snow.xAcceleration = -6
        snow.particleScale = 0.7
        snow.particleScaleRange = 0.5
        snow.particleRotationRange = .pi * 2
        snow.particleRotationSpeed = 0.4
        snow.particleAlpha = 0.92
        snow.particleAlphaRange = 0.08
        snow.zPosition = 600
        snow.alpha = 0
        snow.isHidden = true
        camera.addChild(snow)

        // Туман: вуаль (ниже контраст) + дрейфующие полосы над средним планом и одна тонкая — над основным.
        let haze = UIColor(red: 0.90, green: 0.88, blue: 0.85, alpha: 1)
        fogVeil = SKSpriteNode(color: haze, size: CGSize(width: W * 3, height: H * 3))
        fogVeil.zPosition = -390
        fogVeil.alpha = 0
        fogRoot.addChild(fogVeil)
        let band = SKTexture(image: WeatherLayer.bandImage())
        let specs: [(y: CGFloat, h: CGFloat, z: CGFloat, a: CGFloat, speed: Double)] = [
            (-0.02, 0.22, -380, 0.55, 0.05),
            (-0.14, 0.18, -370, 0.50, -0.035),
            (0.08, 0.26, -385, 0.40, 0.025),
            (-0.22, 0.14, 450, 0.22, 0.045),
        ]
        for (i, s) in specs.enumerated() {
            let n = SKSpriteNode(texture: band)
            n.size = CGSize(width: W * 2.6, height: H * s.h)
            n.color = haze
            n.colorBlendFactor = 1
            n.position = CGPoint(x: 0, y: H * s.y)
            n.zPosition = s.z
            n.alpha = 0
            fogRoot.addChild(n)
            fogBands.append((n, Double(i) * 1.7, s.speed, s.a))
        }
        fogRoot.isHidden = true
        camera.addChild(fogRoot)
    }

    // MARK: Frame

    func update(dt: Double) {
        time += dt
        pollClock += dt
        if pollClock >= 2 {
            pollClock = 0
            target = WeatherService.shared.current
        }
        let step = fadeRate * CGFloat(dt)
        for w in Weather.allCases {
            let goal: CGFloat = w == target ? 1 : 0
            let v = level[w] ?? 0
            level[w] = v < goal ? min(goal, v + step) : max(goal, v - step)
        }
        let r = level[.rain] ?? 0, s = level[.snow] ?? 0, f = level[.fog] ?? 0

        apply(emitter: rain, level: r, rate: rainRate)
        apply(emitter: snow, level: s, rate: snowRate)

        fogRoot.isHidden = f < 0.005
        if !fogRoot.isHidden {
            fogVeil.alpha = 0.28 * f
            let W = designSize.width
            for b in fogBands {
                b.node.alpha = b.alpha * f
                b.node.position.x = CGFloat(sin(time * b.speed + b.phase)) * W * 0.28
            }
        }

        // Тон неба/мира: дождь — серее и темнее, туман — чуть белесее (через вуаль), снег — немного серее.
        let k = r * 1.0 + s * 0.45 + f * 0.35
        let key = Int(k * 200)
        if key != lastTintKey {
            lastTintKey = key
            let grey = RGB(r: 0.74, g: 0.77, b: 0.82)
            let c = RGB(r: 1, g: 1, b: 1).mix(grey, min(1, k))
            skyTint.color = c.color
            skyTint.isHidden = k < 0.01
        }
    }

    /// Мгновенно применить текущую погоду (первый кадр, DEBUG-переключение без ожидания опроса).
    func refresh() { pollClock = 100 }

    private func apply(emitter e: SKEmitterNode, level v: CGFloat, rate: CGFloat) {
        if v <= 0.001 {
            if !e.isHidden {
                e.particleBirthRate = 0
                e.isHidden = true
                e.resetSimulation()
            }
            return
        }
        if e.isHidden {
            e.isHidden = false
        }
        e.particleBirthRate = rate * v
        e.alpha = min(1, v * 1.4)
    }

    // MARK: Процедурные текстуры (мягкие, «лепные»)

    private static func streakImage() -> UIImage {
        let size = CGSize(width: 7, height: 46)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            let path = UIBezierPath(roundedRect: CGRect(x: 1, y: 1, width: 5, height: 44), cornerRadius: 2.5)
            UIColor(white: 1, alpha: 0.85).setFill()
            path.fill()
            // Чуть плотнее «капля» внизу — как вылепленный штрих.
            UIColor(white: 1, alpha: 1).setFill()
            UIBezierPath(ovalIn: CGRect(x: 0.5, y: 34, width: 6, height: 11)).fill()
            _ = ctx
        }
    }

    private static func flakeImage() -> UIImage {
        let size = CGSize(width: 18, height: 18)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            let cg = ctx.cgContext
            let colors = [UIColor(white: 1, alpha: 1).cgColor, UIColor(white: 0.96, alpha: 0).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0.55, 1]) {
                cg.drawRadialGradient(g, startCenter: CGPoint(x: 8.5, y: 9.5), startRadius: 0,
                                      endCenter: CGPoint(x: 9, y: 9), endRadius: 9, options: [])
            }
            // Тень снизу — объём комочка.
            UIColor(red: 0.80, green: 0.84, blue: 0.90, alpha: 0.5).setFill()
            UIBezierPath(ovalIn: CGRect(x: 6, y: 10, width: 7, height: 4)).fill()
        }
    }

    private static func bandImage() -> UIImage {
        let size = CGSize(width: 64, height: 64)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            let colors = [UIColor(white: 1, alpha: 0).cgColor, UIColor(white: 1, alpha: 1).cgColor,
                          UIColor(white: 1, alpha: 0).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 0.5, 1]) {
                ctx.cgContext.drawLinearGradient(g, start: CGPoint(x: 0, y: 0), end: CGPoint(x: 0, y: 64), options: [])
            }
        }
    }
}
