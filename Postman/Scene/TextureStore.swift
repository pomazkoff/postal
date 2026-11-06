import SpriteKit
import UIKit

/// Загрузка PNG из папки GameAssets (folder reference) в SKTexture.
/// Большие картинки мест декодируются в фоне и выгружаются, когда далеко от камеры.
final class TextureStore {
    static let shared = TextureStore()

    /// Симулятор (MTLSimDevice) часто отвергает текстуру шире или выше 8192
    /// и обрывает процесс в `validateWithDevice`, если ширина или высота равна 0.
    static let metalMaxDimension = 8192

    private var cache: [String: SKTexture] = [:]
    private var waiting: [String: [(SKTexture) -> Void]] = [:]
    private let queue = DispatchQueue(label: "postman.textures", qos: .userInitiated)

    /// 1×1 прозрачный пиксель. Пустой `SKTexture()` даёт дескриптор 0×0 и SIGABRT в Metal.
    private static let fallback: SKTexture = {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let img = UIGraphicsImageRenderer(size: CGSize(width: 1, height: 1), format: format).image { ctx in
            UIColor.clear.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 1, height: 1))
        }
        return SKTexture(image: img)
    }()

    /// Полный путь к PNG по относительному пути без расширения (относительно GameAssets).
    static func url(for relativePath: String) -> URL {
        WorldConfigLoader.assetsRoot.appendingPathComponent(relativePath + ".png")
    }

    /// Синхронная загрузка (для мелочи: части рига, тайлы).
    func texture(_ relativePath: String) -> SKTexture {
        if let t = cache[relativePath] { return t }
        let t = Self.makeTexture(UIImage(contentsOfFile: Self.url(for: relativePath).path), name: relativePath)
        cache[relativePath] = t
        return t
    }

    /// Синхронная загрузка с заранее уменьшенным разрешением (качественный даунскейл вместо
    /// сэмплинга GPU) — для частей рига, которые рисуются в ~0.42 от исходника.
    func texture(_ relativePath: String, downscaledBy factor: CGFloat) -> SKTexture {
        let key = relativePath + "@\(factor)"
        if let t = cache[key] { return t }
        guard let image = UIImage(contentsOfFile: Self.url(for: relativePath).path) else {
            Self.logSkip(relativePath)
            return Self.fallback
        }
        let target = CGSize(width: max(1, (image.size.width * factor).rounded()),
                            height: max(1, (image.size.height * factor).rounded()))
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let scaled = UIGraphicsImageRenderer(size: target, format: format).image { ctx in
            ctx.cgContext.interpolationQuality = .high
            image.draw(in: CGRect(origin: .zero, size: target))
        }
        let t = Self.makeTexture(scaled, name: key)
        cache[key] = t
        return t
    }

    /// Уже декодированная картинка (житель, атлас, кадр листа). Не подменяет пиксели,
    /// если сторона не больше `metalMaxDimension`.
    func spriteTexture(_ image: UIImage, name: String) -> SKTexture {
        Self.makeTexture(image, name: name)
    }

    /// Асинхронная загрузка: декодирование в фоне, completion — на главном потоке.
    func loadAsync(_ relativePath: String, completion: @escaping (SKTexture) -> Void) {
        dispatchPrecondition(condition: .onQueue(.main))
        if let t = cache[relativePath] {
            completion(t)
            return
        }
        if waiting[relativePath] != nil {
            waiting[relativePath]?.append(completion)
            return
        }
        waiting[relativePath] = [completion]
        let url = Self.url(for: relativePath)
        queue.async { [weak self] in
            // Не вызывать preparingForDisplay: этот API только для JPEG/HEIC.
            // На PNG UIKit пишет «Error -17102 decompressing image -- possibly corrupt»
            // и отдаёт nil или картинку без годного CGImage. SKTexture из неё
            // падает в симуляторе: MTLTextureDescriptor validateWithDevice.
            let loaded = UIImage(contentsOfFile: url.path)
            let pixels = loaded?.cgImage
            let readable = (pixels?.width ?? 0) > 0 && (pixels?.height ?? 0) > 0
            DispatchQueue.main.async {
                guard let self else { return }
                let t = readable ? Self.makeTexture(loaded, name: relativePath) : Self.fallback
                if !readable { Self.logSkip(relativePath) }
                self.cache[relativePath] = t
                let callbacks = self.waiting.removeValue(forKey: relativePath) ?? []
                callbacks.forEach { $0(t) }
            }
        }
    }

    func evict(_ relativePath: String) {
        cache.removeValue(forKey: relativePath)
    }

    /// Текстура, которую Metal симулятора согласится создать. nil-картинка и 0×0 не проходят.
    private static func makeTexture(_ image: UIImage?, name: String) -> SKTexture {
        guard let image, let cg = image.cgImage else {
            logSkip(name)
            return fallback
        }
        let width = cg.width
        let height = cg.height
        guard width > 0, height > 0 else {
            logSkip(name, detail: "размер \(width)×\(height)")
            return fallback
        }
        guard width <= metalMaxDimension, height <= metalMaxDimension else {
            guard let fitted = downscale(image, pixelWidth: width, pixelHeight: height) else {
                logSkip(name, detail: "размер \(width)×\(height) больше \(metalMaxDimension)")
                return fallback
            }
            print("Postman: текстура \(name) \(width)×\(height) уменьшена до лимита Metal \(metalMaxDimension)")
            return SKTexture(image: fitted)
        }
        return SKTexture(image: image)
    }

    private static func downscale(_ image: UIImage, pixelWidth: Int, pixelHeight: Int) -> UIImage? {
        let limit = CGFloat(metalMaxDimension)
        let fit = limit / CGFloat(max(pixelWidth, pixelHeight))
        let size = CGSize(width: max(1, floor(CGFloat(pixelWidth) * fit)),
                          height: max(1, floor(CGFloat(pixelHeight) * fit)))
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        format.preferredRange = .standard
        let rendered = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            ctx.cgContext.interpolationQuality = .high
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        guard let cg = rendered.cgImage, cg.width > 0, cg.height > 0,
              cg.width <= metalMaxDimension, cg.height <= metalMaxDimension else { return nil }
        return rendered
    }

    private static func logSkip(_ name: String, detail: String? = nil) {
        if let detail {
            print("Postman: пропуск текстуры \(name) (\(detail))")
        } else {
            print("Postman: пропуск текстуры \(name)")
        }
    }
}
