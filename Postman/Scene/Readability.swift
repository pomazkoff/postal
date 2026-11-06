import SpriteKit
import UIKit

/// Читаемость героев на фоне поселений — все ручки в одном месте.
/// Фон (дальний/средний план и постройки «places» основного плана) мягко уходит в дымку,
/// герои (почтальон, жители, коза) получают тёплый «ключевой свет», край-подсветку и контактную тень.
/// Днём дорога, передний план и небо не трогаются.
/// Ночью тон суток остаётся на небе, дороге и поселениях.
/// Герой читается только своим шейдером: тёмная глина светлеет без смены оттенка.
/// Экранных пятен нет — аддитивный квад даёт жёлтый прямоугольник с резким краем.
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
    /// Меньше прежних 0.42: глина лица и одежды не уходит в холодную тень.
    static let nightTintShare: CGFloat = 0.22
    /// Подъём яркости и насыщенности героев на полной ночи (плавно от 0 днём).
    static let nightBrightness: CGFloat = 0
    static let nightSaturation: CGFloat = 0.06
    /// Смещение к жёлтому выключено: оно красило силуэт, а не возвращало глину.
    static let lanternColor = (r: CGFloat(1.0), g: CGFloat(0.86), b: CGFloat(0.64))
    static let lanternAmount: CGFloat = 0
    /// Тени (luma ниже этого) поднимаются сильнее середины. Оттенок пикселя не меняется.
    static let nightShadowEnd: CGFloat = 0.50
    /// Сила подъёма теней в полную ночь. 0 на дневном белом тоне, шейдер тогда снят.
    static let nightShadowLift: CGFloat = 1.15
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
    private static let liftUniform = SKUniform(name: "u_lift", float: 0)

    /// Общий шейдер героев: подъём теней без смены оттенка и частичная компенсация тона суток.
    /// Красит только непрозрачные пиксели фигур. Один объект на всех — униформы раз в кадр.
    static let nightShader: SKShader = {
        let end = String(format: "%.4f", Double(nightShadowEnd))
        let src = """
        void main() {
            vec4 c = texture2D(u_texture, v_tex_coord);
            vec3 rgb = c.rgb;
            float l = dot(rgb, vec3(0.299, 0.587, 0.114));
            float shadow = clamp(1.0 - l / \(end), 0.0, 1.0);
            rgb *= 1.0 + u_lift * shadow;
            l = dot(rgb, vec3(0.299, 0.587, 0.114));
            rgb = mix(vec3(l), rgb, u_sat);
            rgb = clamp(rgb * u_gain, vec3(0.0), vec3(c.a));
            gl_FragColor = vec4(rgb, c.a) * v_color_mix.a;
        }
        """
        let sh = SKShader(source: src)
        sh.uniforms = [gainUniform, satUniform, liftUniform]
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
        liftUniform.floatValue = Float(nightShadowLift * n)
        return n
    }
}
