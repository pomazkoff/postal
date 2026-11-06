import SpriteKit
import UIKit

// MARK: - Lazy sprite (места и подземные модули грузятся, только когда рядом с камерой)

final class LazySpriteNode: SKSpriteNode {
    let imagePath: String
    private enum LoadState { case unloaded, loading, loaded }
    private var state: LoadState = .unloaded
    /// Дымка фона (Readability): цвет и сила смешивания, применяются при загрузке текстуры.
    var gradeColor: UIColor = .white
    var gradeLayer: LayerKind = .main
    var gradeFactor: CGFloat = 0 {
        didSet {
            guard state == .loaded else { return }
            color = gradeFactor > 0 ? gradeColor : .white
            colorBlendFactor = gradeFactor
        }
    }

    init(imagePath: String, size: CGSize) {
        self.imagePath = imagePath
        super.init(texture: nil, color: .clear, size: size)
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) не используется") }

    func setNeeded(_ needed: Bool) {
        if needed {
            guard state == .unloaded else { return }
            state = .loading
            alpha = 0
            TextureStore.shared.loadAsync(imagePath) { [weak self] tex in
                guard let self, self.state == .loading else { return }
                self.texture = tex
                self.color = self.gradeFactor > 0 ? self.gradeColor : .white
                self.colorBlendFactor = self.gradeFactor
                self.state = .loaded
                self.run(.fadeIn(withDuration: 0.15))
            }
        } else {
            guard state == .loaded else { return }
            texture = nil
            color = .clear
            state = .unloaded
            TextureStore.shared.evict(imagePath)
        }
    }
}

// MARK: - Бесконечный тайл для параллакс-слоёв (дальний/средний план)

final class TiledStripNode: SKNode {
    private let texture: SKTexture
    private let tileSize: CGSize
    private let bottomY: CGFloat
    private let darken: CGFloat
    private var pool: [SKSpriteNode] = []
    /// Дымка фона (Readability), задаётся до первого layout.
    var hazeColor: UIColor = .white
    var hazeFactor: CGFloat = 0 {
        didSet { for t in pool { styleTile(t) } }
    }

    private func styleTile(_ s: SKSpriteNode) {
        let total = min(1, darken + hazeFactor)
        guard total > 0 else { s.colorBlendFactor = 0; return }
        // Затемнение (к чёрному) и дымка (к hazeColor) одним смешиванием.
        let c = RGB(r: 0, g: 0, b: 0).mix(RGB(hazeColor), hazeFactor / max(0.001, darken + hazeFactor))
        s.color = c.color
        s.colorBlendFactor = total
    }

    init(texture: SKTexture, tileHeight: CGFloat, aspect: CGFloat, bottomY: CGFloat, brightness: CGFloat) {
        self.texture = texture
        self.tileSize = CGSize(width: (tileHeight * aspect).rounded(), height: tileHeight)
        self.bottomY = bottomY
        self.darken = max(0, min(1, 1 - brightness))
        super.init()
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) не используется") }

    /// Разложить тайлы на видимый участок в локальных координатах слоя.
    func layout(localMinX: CGFloat, localMaxX: CGFloat) {
        let w = tileSize.width
        let first = Int(floor(localMinX / w))
        let last = Int(floor(localMaxX / w))
        let needed = max(0, last - first + 1)
        while pool.count < needed {
            let s = SKSpriteNode(texture: texture)
            s.anchorPoint = .zero
            s.size = CGSize(width: w + 1, height: tileSize.height) // +1 px против швов
            styleTile(s)
            addChild(s)
            pool.append(s)
        }
        for (i, s) in pool.enumerated() {
            if i < needed {
                s.isHidden = false
                s.position = CGPoint(x: CGFloat(first + i) * w, y: bottomY)
            } else {
                s.isHidden = true
            }
        }
    }
}

// MARK: - Метка поселения (заглушка: столбик с табличкой)

final class SettlementMarkerNode: SKNode {
    init(title: String) {
        super.init()
        let post = SKShapeNode(rectOf: CGSize(width: 14, height: 190), cornerRadius: 4)
        post.fillColor = UIColor(red: 0.37, green: 0.24, blue: 0.14, alpha: 1)
        post.strokeColor = UIColor(red: 0.11, green: 0.06, blue: 0.04, alpha: 0.8)
        post.lineWidth = 3
        post.position = CGPoint(x: 0, y: 95)
        addChild(post)

        let label = SKLabelNode(text: title)
        label.fontName = "Georgia-Bold"
        label.fontSize = 40
        label.fontColor = UIColor(red: 0.20, green: 0.16, blue: 0.11, alpha: 1)
        label.verticalAlignmentMode = .center
        label.horizontalAlignmentMode = .center

        let w = max(160, label.frame.width + 48)
        let board = SKShapeNode(rectOf: CGSize(width: w, height: 70), cornerRadius: 10)
        board.fillColor = UIColor(red: 0.78, green: 0.65, blue: 0.41, alpha: 1)
        board.strokeColor = UIColor(red: 0.37, green: 0.24, blue: 0.14, alpha: 1)
        board.lineWidth = 4
        board.position = CGPoint(x: 0, y: 200)
        board.zPosition = 1
        label.zPosition = 1
        board.addChild(label)
        addChild(board)
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) не используется") }
}

// MARK: - Текстуры, создаваемые кодом

enum ProceduralTextures {
    /// Вертикальный градиент неба: topColor вверху → bottomColor на линии дороги и ниже.
    static func sky(top: UIColor, bottom: UIColor, roadFraction: CGFloat) -> SKTexture {
        let size = CGSize(width: 8, height: 512)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let img = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            let colors = [top.cgColor, bottom.cgColor, bottom.cgColor] as CFArray
            let locations: [CGFloat] = [0, max(0.01, min(0.99, roadFraction)), 1]
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: locations) {
                ctx.cgContext.drawLinearGradient(g, start: .zero, end: CGPoint(x: 0, y: size.height), options: [])
            }
        }
        return SKTexture(image: img)
    }

    /// Тайл с альфа-рампой сверху (переход дальнего плана в небо, как в compose_places.py).
    static func fadedTop(_ relativePath: String, fraction: CGFloat) -> SKTexture {
        guard fraction > 0, let image = UIImage(contentsOfFile: TextureStore.url(for: relativePath).path) else {
            return TextureStore.shared.texture(relativePath)
        }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let size = image.size
        let img = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            image.draw(at: .zero)
            let colors = [UIColor(white: 0, alpha: 0).cgColor, UIColor(white: 0, alpha: 1).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                ctx.cgContext.setBlendMode(.destinationIn)
                ctx.cgContext.drawLinearGradient(g, start: .zero, end: CGPoint(x: 0, y: size.height * fraction),
                                                 options: [.drawsAfterEndLocation])
            }
        }
        return SKTexture(image: img)
    }
}

extension UIColor {
    /// "#RRGGBB"
    convenience init(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.hasPrefix("#") { s.removeFirst() }
        var v: UInt64 = 0
        Scanner(string: s).scanHexInt64(&v)
        self.init(red: CGFloat((v >> 16) & 0xFF) / 255,
                  green: CGFloat((v >> 8) & 0xFF) / 255,
                  blue: CGFloat(v & 0xFF) / 255,
                  alpha: 1)
    }
}
