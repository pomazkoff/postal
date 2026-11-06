import SpriteKit
import UIKit

/// Читаемость героев на фоне поселений — все ручки в одном месте.
/// Фон (дальний/средний план и постройки «places» основного плана) мягко уходит в дымку,
/// герои (почтальон, жители, коза) получают тёплый «ключевой свет», край-подсветку и контактную тень.
/// Днём дорога, передний план и небо не трогаются.
/// Ночью холодный тон суток остаётся на небе и поселениях; герой и полоса дороги
/// получают отдельный мягкий тёплый свет уже после этого умножения.
enum Readability {
    /// DEBUG-переключатель «до/после» (DebugPanel, UserDefaults). Применяется сразу: WorldScene.applyReadability().
    static let debugOffKey = "postman.debug.readabilityOff"
    static var enabled: Bool {
        get {
            #if DEBUG
            return !UserDefaults.standard.bool(forKey: debugOffKey)
            #else
            return true
            #endif
        }
        set { UserDefaults.standard.set(!newValue, forKey: debugOffKey) }
    }

    // Фон: смешивание с цветом дымки (colorBlendFactor). Дымка нейтрально-холодная,
    // тон суток и погоды ложится сверху умножением, поэтому вечером/ночью она темнеет вместе с миром.
    static let hazeColor = UIColor(red: 0.60, green: 0.63, blue: 0.68, alpha: 1)
    static let farHaze: CGFloat = 0.34
    static let midHaze: CGFloat = 0.28
    static let placesHaze: CGFloat = 0.20

    // Герои: лёгкий подъём яркости тёплым светом.
    static let keyLightColor = UIColor(red: 1.0, green: 0.95, blue: 0.86, alpha: 1)
    static let keyLight: CGFloat = 0.15

    // Край-подсветка: светлая копия силуэта позади фигуры, сдвинутая к «солнцу» (вверх-влево).
    static let rimColor = UIColor(red: 1.0, green: 0.93, blue: 0.80, alpha: 1)
    static let rimAlpha: CGFloat = 0.18
    static let rimOffset = CGPoint(x: -2.0, y: 1.5)

    // Контактная тень под ногами: мягкий эллипс.
    static let shadowAlpha: CGFloat = 0.35
    /// Ширина тени относительно ширины фигуры / высота относительно ширины тени.
    static let shadowWidthFactor: CGFloat = 0.62
    static let shadowAspect: CGFloat = 0.16

    static func hazeFactor(for layer: LayerKind) -> CGFloat {
        switch layer {
        case .far: return farHaze
        case .mid: return midHaze
        case .main: return placesHaze
        default: return 0
        }
    }

    private static var shadowTexture: SKTexture = {
        let size = CGSize(width: 128, height: 32)
        let img = UIGraphicsImageRenderer(size: size).image { ctx in
            let cg = ctx.cgContext
            cg.translateBy(x: 64, y: 16)
            cg.scaleBy(x: 4, y: 1)
            let colors = [UIColor(red: 0.12, green: 0.08, blue: 0.05, alpha: 1).cgColor,
                          UIColor(red: 0.12, green: 0.08, blue: 0.05, alpha: 0).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                cg.drawRadialGradient(g, startCenter: .zero, startRadius: 0, endCenter: .zero, endRadius: 16, options: [])
            }
        }
        return SKTexture(image: img)
    }()

    /// Контактная тень (дочерний узел фигуры, y = 0 — линия земли фигуры).
    static func contactShadow(width: CGFloat) -> SKSpriteNode {
        let w = width * shadowWidthFactor
        let n = SKSpriteNode(texture: shadowTexture, size: CGSize(width: w, height: max(8, w * shadowAspect)))
        n.alpha = shadowAlpha
        n.zPosition = -2
        n.name = "contactShadow"
        return n
    }

    /// Тёплый свет на спрайте героя.
    static func light(_ sprite: SKSpriteNode, on: Bool = true) {
        sprite.color = keyLightColor
        sprite.colorBlendFactor = on ? keyLight : 0
    }

    /// Край-подсветка для спрайта-фигуры (копия той же текстуры, светлая, позади).
    static func rim(for sprite: SKSpriteNode) -> SKSpriteNode {
        let r = SKSpriteNode(texture: sprite.texture, size: sprite.size)
        r.anchorPoint = sprite.anchorPoint
        r.color = rimColor
        r.colorBlendFactor = 1
        r.alpha = rimAlpha
        r.position = rimOffset
        r.zPosition = -1
        r.name = "rim"
        return r
    }
    // MARK: Вечер/ночь — герои светлее фона

    /// Доля тёмного тона суток, которая ложится на героев (фон получает 100%).
    static let nightTintShare: CGFloat = 0.42
    /// Подъём яркости и насыщенности героев на полной ночи (плавно от 0 днём).
    static let nightBrightness: CGFloat = 0.10
    static let nightSaturation: CGFloat = 0.30
    /// Тёплый «фонарь»: доля смешивания с тёплым цветом в усилении.
    static let lanternColor = (r: CGFloat(1.0), g: CGFloat(0.86), b: CGFloat(0.64))
    static let lanternAmount: CGFloat = 0.22
    /// Яркость (luma) тона, при которой считается «полная ночь» (ночной тон #8090B8 ≈ 0.57).
    static let nightLuma: CGFloat = 0.57
    static let maxGain: CGFloat = 2.4

    /// 0 днём (тон белый) … 1 ночью. Закат (#F0C6A0) ≈ 0.45.
    static func nightAmount(tint: RGB) -> CGFloat {
        let l = 0.299 * tint.r + 0.587 * tint.g + 0.114 * tint.b
        return max(0, min(1, (1 - l) / max(0.05, 1 - nightLuma)))
    }

    private static let gainUniform = SKUniform(name: "u_gain", vectorFloat3: SIMD3<Float>(1, 1, 1))
    private static let satUniform = SKUniform(name: "u_sat", float: 1)

    /// Общий шейдер героев: насыщенность + усиление, компенсирующее часть умножения тоном суток.
    /// Один объект на всех — униформы обновляются раз в кадр.
    static let nightShader: SKShader = {
        let src = """
        void main() {
            vec4 c = texture2D(u_texture, v_tex_coord);
            vec3 rgb = c.rgb;
            float l = dot(rgb, vec3(0.299, 0.587, 0.114));
            rgb = mix(vec3(l), rgb, u_sat);
            rgb = clamp(rgb * u_gain, vec3(0.0), vec3(c.a));
            gl_FragColor = vec4(rgb, c.a) * v_color_mix.a;
        }
        """
        let sh = SKShader(source: src)
        sh.uniforms = [gainUniform, satUniform]
        return sh
    }()

    /// Обновить униформы под текущий тон. Возвращает силу эффекта (0 — шейдер не нужен).
    @discardableResult
    static func updateNight(tint: RGB) -> CGFloat {
        let n = nightAmount(tint: tint)
        let keep = 1 - nightTintShare       // какую долю затемнения снимаем
        let boost = 1 + nightBrightness * n
        func ch(_ t: CGFloat, _ warm: CGFloat) -> Float {
            let undo = pow(max(0.05, t), -keep)
            let lantern = 1 + (warm - 1) * lanternAmount * n
            return Float(min(maxGain, undo * boost * lantern))
        }
        gainUniform.vectorFloat3Value = SIMD3<Float>(ch(tint.r, lanternColor.r),
                                                     ch(tint.g, lanternColor.g),
                                                     ch(tint.b, lanternColor.b))
        satUniform.floatValue = Float(1 + nightSaturation * n)
        return n
    }

    // MARK: Ночной тёплый свет (герой и дорога, не всё небо)

    /// Цвет фонаря. Альфа спрайта отдельно режет силу: здесь сам цвет, без затемнения.
    static let nightFillRed: CGFloat = 1.0
    static let nightFillGreen: CGFloat = 0.66
    static let nightFillBlue: CGFloat = 0.36
    static let nightFillColor = UIColor(red: nightFillRed, green: nightFillGreen, blue: nightFillBlue, alpha: 1)
    /// Пиковая добавка в центре героя в полную ночь (до кривой силы). Мягко, без выбеливания глины.
    static let heroNightFillAlpha: CGFloat = 0.28
    /// Пиковая добавка на полосе дороги — слабее героя, чтобы тропа читалась, но не стала дневной.
    static let roadNightFillAlpha: CGFloat = 0.18
    /// Размер пятна героя в пикселях дизайна (мир), центр — на груди/лице, не на небе.
    static let heroNightFillSize = CGSize(width: 640, height: 860)
    /// На сколько поднять центр пятна над стопами (рост героя 430).
    static let heroNightFillLift: CGFloat = 300
    /// Полоса дороги: высота в пикселях дизайна и подъём центра над линией дороги.
    /// Центр чуть выше линии стоп — там плотная глина тропы, не небо и не верх домов.
    static let roadNightFillHeight: CGFloat = 300
    static let roadNightFillLift: CGFloat = 50
    /// Выше слоя-умножения суток (AmbientLayer, z 900), иначе фонарь снова остынет и упрётся в тинт.
    static let nightFillZ: CGFloat = 920

    /// 0 днём и почти 0 на рассвете; к полной ночи дорастает до 1. Квадрат бережёт закат и день.
    static func nightFillStrength(for amount: CGFloat) -> CGFloat {
        let x = min(1, max(0, amount))
        return x * x
    }

    /// 0 на краю пятна, 1 в центре. `tools/check_night_readability.py` повторяет эту формулу.
    static func nightFillFalloff(_ distance: CGFloat) -> CGFloat {
        let x = min(1, max(0, distance))
        let inv = 1 - x * x
        return inv * inv
    }

    /// Маленькая текстура: на экране она растягивается в мягкое пятно, линейная фильтрация сглаживает край.
    static let heroNightFillTexture: SKTexture = SKTexture(image: makeNightFillImage(width: 96, height: 96, round: true))
    static let roadNightFillTexture: SKTexture = SKTexture(image: makeNightFillImage(width: 32, height: 96, round: false))

    /// Мягкое пятно одним градиентом. Остановки считают nightFillFalloff, без покадровой заливки.
    private static func makeNightFillImage(width: Int, height: Int, round: Bool) -> UIImage {
        let size = CGSize(width: width, height: height)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            let cg = ctx.cgContext
            let space = CGColorSpaceCreateDeviceRGB()
            if round {
                let stops: [CGFloat] = [0, 0.2, 0.45, 0.7, 0.85, 1]
                let colors = stops.map { nightFillColor.withAlphaComponent(nightFillFalloff($0)).cgColor } as CFArray
                guard let gradient = CGGradient(colorsSpace: space, colors: colors, locations: stops) else { return }
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                cg.drawRadialGradient(gradient, startCenter: center, startRadius: 0,
                                      endCenter: center, endRadius: min(size.width, size.height) / 2,
                                      options: [])
            } else {
                // От центра полосы вверх и вниз — к небу и к разрезу. Края по X гаснут, чтобы не было кромки.
                let stops: [CGFloat] = [0, 0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92, 1]
                let colors = stops.map { t -> CGColor in
                    let distance = min(1, abs(t - 0.5) * 2)
                    return nightFillColor.withAlphaComponent(nightFillFalloff(distance)).cgColor
                } as CFArray
                guard let gradient = CGGradient(colorsSpace: space, colors: colors, locations: stops) else { return }
                cg.drawLinearGradient(gradient, start: CGPoint(x: 0, y: size.height), end: CGPoint(x: 0, y: 0), options: [])
                let fade = [UIColor(white: 1, alpha: 0).cgColor, UIColor(white: 1, alpha: 1).cgColor,
                            UIColor(white: 1, alpha: 1).cgColor, UIColor(white: 1, alpha: 0).cgColor] as CFArray
                let fadeAt: [CGFloat] = [0, 0.06, 0.94, 1]
                if let mask = CGGradient(colorsSpace: space, colors: fade, locations: fadeAt) {
                    cg.setBlendMode(.destinationIn)
                    cg.drawLinearGradient(mask, start: .zero, end: CGPoint(x: size.width, y: 0), options: [])
                }
            }
        }
    }
}
