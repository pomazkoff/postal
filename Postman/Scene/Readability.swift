import SpriteKit
import UIKit

/// Читаемость героев на фоне поселений — все ручки в одном месте.
/// Фон (дальний/средний план и постройки «places» основного плана) мягко уходит в дымку,
/// герои (почтальон, жители, коза) получают тёплый «ключевой свет», край-подсветку и контактную тень.
/// Днём дорога, передний план и небо не трогаются.
/// Ночь светлеет общим тоном суток в ambient.json, одним и тем же для героя, домов и земли.
/// Отдельный множитель героя выключен: иначе он читается вырезом на уже более светлом мире.
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
    // MARK: Вечер/ночь — только яркость фигур

    /// 1 — фигура в том же свете, что и мир. Больше 1 снова включит отдельный шейдер.
    static let nightFigureGain: CGFloat = 1
    /// Luma тона, при которой ночь считается полной. Совпадает с ночным тинтом #C6CDDF.
    static let nightLuma: CGFloat = 0.80

    /// 0 днём (тон белый) … 1 ночью. Закат (#F0C6A0) ≈ 0.45.
    static func nightAmount(tint: RGB) -> CGFloat {
        let l = 0.299 * tint.r + 0.587 * tint.g + 0.114 * tint.b
        return max(0, min(1, (1 - l) / max(0.05, 1 - nightLuma)))
    }

    private static let gainUniform = SKUniform(name: "u_gain", float: 1)

    /// Пиксели фигуры × u_gain. Если пик выше альфы, все каналы сжимаются вместе — оттенок не уезжает.
    /// Дальше кадр как и весь мир умножается на тон суток.
    static let nightShader: SKShader = {
        let src = """
        void main() {
            vec4 c = texture2D(u_texture, v_tex_coord);
            vec3 rgb = c.rgb * u_gain;
            float peak = max(rgb.r, max(rgb.g, rgb.b));
            float limit = max(c.a, 0.0001);
            rgb *= min(1.0, limit / max(peak, 0.0001));
            gl_FragColor = vec4(rgb, c.a) * v_color_mix.a;
        }
        """
        let sh = SKShader(source: src)
        sh.uniforms = [gainUniform]
        return sh
    }()

    /// 0 — шейдер не вешается, фигура остаётся в общем тоне (дневной вид при белом тинте тоже).
    @discardableResult
    static func updateNight(tint: RGB) -> CGFloat {
        let n = nightAmount(tint: tint)
        let extra = (nightFigureGain - 1) * n
        gainUniform.floatValue = Float(1 + extra)
        return extra > 0.01 ? n : 0
    }
}
