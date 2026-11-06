import SpriteKit
import UIKit

/// Загрузка PNG из папки GameAssets (folder reference) в SKTexture.
/// Большие картинки мест декодируются в фоне и выгружаются, когда далеко от камеры.
final class TextureStore {
    static let shared = TextureStore()

    private var cache: [String: SKTexture] = [:]
    private var waiting: [String: [(SKTexture) -> Void]] = [:]
    private let queue = DispatchQueue(label: "postman.textures", qos: .userInitiated)

    /// Полный путь к PNG по относительному пути без расширения (относительно GameAssets).
    static func url(for relativePath: String) -> URL {
        WorldConfigLoader.assetsRoot.appendingPathComponent(relativePath + ".png")
    }

    /// Синхронная загрузка (для мелочи: части рига, тайлы).
    func texture(_ relativePath: String) -> SKTexture {
        if let t = cache[relativePath] { return t }
        let t: SKTexture
        if let image = UIImage(contentsOfFile: Self.url(for: relativePath).path) {
            t = SKTexture(image: image)
        } else {
            assertionFailure("Нет ассета: \(relativePath).png")
            t = SKTexture()
        }
        cache[relativePath] = t
        return t
    }

    /// Синхронная загрузка с заранее уменьшенным разрешением (качественный даунскейл вместо
    /// сэмплинга GPU) — для частей рига, которые рисуются в ~0.42 от исходника.
    func texture(_ relativePath: String, downscaledBy factor: CGFloat) -> SKTexture {
        let key = relativePath + "@\(factor)"
        if let t = cache[key] { return t }
        guard let image = UIImage(contentsOfFile: Self.url(for: relativePath).path) else {
            assertionFailure("Нет ассета: \(relativePath).png")
            return SKTexture()
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
        let t = SKTexture(image: scaled)
        cache[key] = t
        return t
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
            let decoded = UIImage(contentsOfFile: url.path)?.preparingForDisplay()
            DispatchQueue.main.async {
                guard let self else { return }
                let t: SKTexture
                if let decoded {
                    t = SKTexture(image: decoded)
                } else {
                    assertionFailure("Нет ассета: \(relativePath).png")
                    t = SKTexture()
                }
                self.cache[relativePath] = t
                let callbacks = self.waiting.removeValue(forKey: relativePath) ?? []
                callbacks.forEach { $0(t) }
            }
        }
    }

    func evict(_ relativePath: String) {
        cache.removeValue(forKey: relativePath)
    }
}
