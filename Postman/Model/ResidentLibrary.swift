import UIKit

/// Жители из GameAssets/<ChapterN>/residents/<id>/. Папка главы — chapterAssetsFolder (ставит AppCore/GameModel).
///
/// Терпимый загрузчик — понимает:
///  1. rig.json как у почтальона: `offsets {part: [x, y]}` (левый верх PNG в координатах исходника),
///     картинки в `parts/<part>.png` или `<part>.png`; порядок — `order`/`draw_order` или эвристика;
///  2. rig.json с массивом `parts: [{name|file|image, x, y, z?}]`;
///  3. готовая картинка `full.png` / `preview.png` / `<id>.png` в папке жителя или `residents/<id>.png`.
/// Необязательные поля: `facing` ("left"/"right" — куда смотрит исходник, по умолчанию "right"),
/// `ground_y` (или `pivots_src.ground_y`) — линия земли в координатах исходника.
/// Нет папки/файлов — житель просто не рисуется (nil), игра работает без него.
enum ResidentLibrary {
    struct Figure {
        let image: UIImage
        /// Доля высоты картинки от верха до линии земли (обычно ≈1).
        let groundFraction: CGFloat
        /// Дыхание (idle 12 fps) из rig.json → idle + spritesheet.png; nil — житель статичен.
        var idle: Idle? = nil
    }

    /// Горизонтальный лист кадров. Кадр покрывает всю ширину исходника (×game_scale),
    /// линия земли кадра — frame_ground_y. figureUnitsPerFramePx переводит пиксели кадра в пиксели Figure.image.
    struct Idle {
        let sheet: UIImage
        let frames: Int
        let fps: Double
        let frameSize: CGSize
        let anchor: CGPoint
        let figureUnitsPerFramePx: CGFloat

        /// Один кадр отдельным битмапом. Весь лист (у Пимена 8256 px) нельзя отдавать в SKTexture:
        /// симулятор обрывает Metal, если сторона больше 8192.
        func frameImage(at index: Int) -> UIImage? {
            guard (0..<frames).contains(index), let cg = sheet.cgImage else { return nil }
            let scale = sheet.scale
            let frameW = Int((frameSize.width * scale).rounded())
            let frameH = Int((frameSize.height * scale).rounded())
            let originX = Int((frameSize.width * CGFloat(index) * scale).rounded())
            guard frameW >= 1, frameH >= 1, originX >= 0,
                  originX + frameW <= cg.width, frameH <= cg.height else { return nil }
            let rect = CGRect(x: originX, y: 0, width: frameW, height: frameH)
            // cropping иногда отдаёт тот же широкий буфер. Нужен ровно один кадр,
            // иначе SKTexture снова получит лист шире лимита Metal.
            guard let cropped = cg.cropping(to: rect),
                  cropped.width == frameW, cropped.height == frameH else { return nil }
            return UIImage(cgImage: cropped, scale: scale, orientation: .up)
        }
    }

    private static var cache: [String: Figure?] = [:]

    /// "Chapter1" / "Chapter2" — откуда грузить жителей текущей главы.
    static var chapterAssetsFolder: String = "Chapter1" {
        didSet { if oldValue != chapterAssetsFolder { cache.removeAll() } }
    }

    static var root: URL {
        WorldConfigLoader.assetsRoot.appendingPathComponent("\(chapterAssetsFolder)/residents", isDirectory: true)
    }

    /// Фигура жителя, повёрнутая лицом влево (к почтальону, который подходит слева).
    static func figure(for resident: StoryConfig.Resident, assetsFolder: String? = nil) -> Figure? {
        let folder = assetsFolder ?? chapterAssetsFolder
        let key = "\(folder)/\(resident.id)"
        if let cached = cache[key] { return cached }
        let residentsRoot = WorldConfigLoader.assetsRoot.appendingPathComponent("\(folder)/residents", isDirectory: true)
        var result = load(resident, in: residentsRoot)
        if result == nil, folder != "Chapter1" {
            let ch1 = WorldConfigLoader.assetsRoot.appendingPathComponent("Chapter1/residents", isDirectory: true)
            result = load(resident, in: ch1)
        }
        cache[key] = result
        return result
    }

    private static func load(_ resident: StoryConfig.Resident) -> Figure? { load(resident, in: root) }

    private static func load(_ resident: StoryConfig.Resident, in root: URL) -> Figure? {
        let fm = FileManager.default
        guard fm.fileExists(atPath: root.path) else { return nil }
        let names = ([resident.id] + resident.aliases).reduce(into: [String]()) { acc, n in
            if !acc.contains(n) { acc.append(n) }
        }
        let entries = (try? fm.contentsOfDirectory(atPath: root.path)) ?? []
        for name in names {
            // Папка (без учёта регистра).
            if let dirName = entries.first(where: { $0.lowercased() == name.lowercased() }) {
                let dir = root.appendingPathComponent(dirName, isDirectory: true)
                var isDir: ObjCBool = false
                if fm.fileExists(atPath: dir.path, isDirectory: &isDir), isDir.boolValue,
                   let figure = loadFolder(dir, id: resident.id) {
                    return figure
                }
            }
            // Одиночная картинка residents/<name>.png
            if let file = entries.first(where: { $0.lowercased() == name.lowercased() + ".png" }),
               let image = UIImage(contentsOfFile: root.appendingPathComponent(file).path) {
                return Figure(image: flipped(image), groundFraction: 1)
            }
        }
        return nil
    }

    private static func loadFolder(_ dir: URL, id: String) -> Figure? {
        let fm = FileManager.default
        let rigURL = dir.appendingPathComponent("rig.json")
        var json: [String: Any] = [:]
        if let data = try? Data(contentsOf: rigURL),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            json = obj
        }
        let facesRight = (json["facing"] as? String)?.lowercased() != "left"

        if let composed = compose(json: json, dir: dir) {
            let image = facesRight ? flipped(composed.image) : composed.image
            // Idle-лист нарисован в ориентации исходника; для «правых» исходников не используем.
            let idle = facesRight ? nil : composed.idle
            return Figure(image: image, groundFraction: composed.groundFraction, idle: idle)
        }
        for name in ["full.png", "preview.png", "\(id).png", "figure.png", "idle.png"] {
            let url = dir.appendingPathComponent(name)
            if fm.fileExists(atPath: url.path), let image = UIImage(contentsOfFile: url.path) {
                return Figure(image: facesRight ? flipped(image) : image, groundFraction: 1)
            }
        }
        return nil
    }

    private struct Part {
        let name: String
        let image: UIImage
        let origin: CGPoint
        let z: Double
    }

    private static func compose(json: [String: Any], dir: URL) -> Figure? {
        var parts: [Part] = []
        let order = (json["order"] as? [String]) ?? (json["draw_order"] as? [String]) ?? []

        func image(named name: String) -> UIImage? {
            let candidates = [name, name + ".png", "parts/" + name, "parts/" + name + ".png"]
            for c in candidates {
                let url = dir.appendingPathComponent(c)
                if FileManager.default.fileExists(atPath: url.path), let img = UIImage(contentsOfFile: url.path) {
                    return img
                }
            }
            return nil
        }

        if let offsets = json["offsets"] as? [String: Any] {
            for (name, value) in offsets {
                guard let xy = value as? [Any], xy.count >= 2,
                      let x = number(xy[0]), let y = number(xy[1]),
                      let img = image(named: name) else { continue }
                let z = order.firstIndex(of: name).map(Double.init) ?? heuristicZ(name)
                parts.append(Part(name: name, image: img, origin: CGPoint(x: x, y: y), z: z))
            }
        } else if let list = json["parts"] as? [[String: Any]] {
            for (i, p) in list.enumerated() {
                let name = (p["name"] as? String) ?? (p["file"] as? String) ?? (p["image"] as? String) ?? "part\(i)"
                let file = (p["file"] as? String) ?? (p["image"] as? String) ?? name
                guard let img = image(named: file) else { continue }
                var x = number(p["x"]) ?? 0, y = number(p["y"]) ?? 0
                if let off = p["offset"] as? [Any], off.count >= 2 {
                    x = number(off[0]) ?? x; y = number(off[1]) ?? y
                }
                let z = number(p["z"]) ?? order.firstIndex(of: name).map(Double.init) ?? Double(i)
                parts.append(Part(name: name, image: img, origin: CGPoint(x: x, y: y), z: z))
            }
        }
        guard !parts.isEmpty else { return nil }
        parts.sort { $0.z < $1.z }

        var bounds = CGRect.null
        for p in parts { bounds = bounds.union(CGRect(origin: p.origin, size: p.image.size)) }
        guard bounds.width > 1, bounds.height > 1, bounds.width < 8000, bounds.height < 8000 else { return nil }

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: bounds.size, format: format)
        let image = renderer.image { _ in
            for p in parts {
                p.image.draw(in: CGRect(x: p.origin.x - bounds.minX, y: p.origin.y - bounds.minY,
                                        width: p.image.size.width, height: p.image.size.height))
            }
        }
        var groundY = number(json["ground_y"])
        if groundY == nil, let piv = json["pivots_src"] as? [String: Any] { groundY = number(piv["ground_y"]) }
        let fraction = groundY.map { CGFloat(($0 - bounds.minY) / bounds.height) } ?? 1
        return Figure(image: image, groundFraction: max(0.5, min(1.2, fraction)),
                      idle: loadIdle(json: json, dir: dir, bounds: bounds))
    }

    private static func loadIdle(json: [String: Any], dir: URL, bounds: CGRect) -> Idle? {
        guard let idle = json["idle"] as? [String: Any],
              let sc = number(json["game_scale"]), sc > 0,
              let fs = idle["frame_size"] as? [Any], fs.count >= 2,
              let fw = number(fs[0]), let fh = number(fs[1]), fw > 0, fh > 0,
              let groundY = number(idle["frame_ground_y"]),
              let count = number(idle["frames"]), count >= 2 else { return nil }
        let file = (idle["spritesheet"] as? String) ?? "spritesheet.png"
        guard let sheet = UIImage(contentsOfFile: dir.appendingPathComponent(file).path),
              sheet.size.width >= CGFloat(fw * count) - 1 else { return nil }
        let fps = number(idle["fps"]) ?? 12
        return Idle(sheet: sheet, frames: Int(count), fps: fps,
                    frameSize: CGSize(width: fw, height: fh),
                    anchor: CGPoint(x: bounds.midX * CGFloat(sc) / CGFloat(fw), y: 1 - CGFloat(groundY / fh)),
                    figureUnitsPerFramePx: 1 / CGFloat(sc))
    }

    /// Порядок частей, если в rig.json его нет: дальние конечности → ноги → тело → голова → ближние руки.
    private static func heuristicZ(_ name: String) -> Double {
        let n = name.lowercased()
        let far = n.contains("far") || n.contains("back") || n.hasSuffix("_l") || n.contains("left")
        if n.contains("shadow") { return -10 }
        if n.contains("arm") || n.contains("hand") || n.contains("forearm") { return far ? 0 : 8 }
        if n.contains("leg") || n.contains("thigh") || n.contains("shin") || n.contains("foot") || n.contains("boot") {
            return far ? 1 : 3
        }
        if n.contains("torso") || n.contains("body") || n.contains("coat") || n.contains("skirt") { return 4 }
        if n.contains("head") || n.contains("face") { return 6 }
        if n.contains("hat") || n.contains("cap") || n.contains("scarf") || n.contains("kerchief") { return 7 }
        if n.contains("prop") || n.contains("staff") || n.contains("stick") || n.contains("bag") { return 7.5 }
        return 5
    }

    private static func number(_ any: Any?) -> Double? {
        if let d = any as? Double { return d }
        if let i = any as? Int { return Double(i) }
        if let n = any as? NSNumber { return n.doubleValue }
        return nil
    }

    private static func flipped(_ image: UIImage) -> UIImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = image.scale
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: image.size, format: format)
        return renderer.image { ctx in
            ctx.cgContext.translateBy(x: image.size.width, y: 0)
            ctx.cgContext.scaleBy(x: -1, y: 1)
            image.draw(at: .zero)
        }
    }
}
