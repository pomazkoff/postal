import Foundation

/// Язык интерфейса и сюжета.
///
/// Штатный выбор iOS: `Bundle.preferredLocalizations` учитывает язык приложения
/// (Настройки → приложение) и язык системы. Регион разработки — `en`, поэтому
/// русский даёт ru.lproj, английский — en, любой другой язык падает в английский.
/// Своего переключателя в игре нет.
enum AppLanguage {
    static var code: String {
        if Bundle.main.preferredLocalizations.first?.hasPrefix("ru") == true {
            return "ru"
        }
        return "en"
    }

    static var isRussian: Bool { code == "ru" }

    /// ru_RU сохраняет прежнюю группировку шагов и русские названия месяцев.
    /// Остальные языки читают числа и даты по-английски.
    static var locale: Locale {
        Locale(identifier: isRussian ? "ru_RU" : "en_US")
    }
}

enum L10n {
    static func text(_ key: String) -> String {
        NSLocalizedString(key, tableName: "Localizable", comment: "")
    }

    static func format(_ key: String, _ args: Any...) -> String {
        let cargs: [CVarArg] = args.map { value -> CVarArg in
            switch value {
            case let n as Int: return Int64(n)
            case let n as Int64: return n
            case let s as String: return s
            case let d as Double: return d
            default: return String(describing: value)
            }
        }
        return String(format: text(key), locale: AppLanguage.locale, arguments: cargs)
    }

    /// Ключ из Localizable.stringsdict: формат — только слово (число нужно правилу, в строку не входит).
    static func plural(_ key: String, _ n: Int) -> String {
        String(format: text(key), locale: AppLanguage.locale, n)
    }
}

/// Английские строки поверх русских JSON. Файлы сюжета, мира и лора не переписываются:
/// при русской локали в декодер уходят исходные байты. Id, флаги, условия и числа не трогаем.
/// Уже записанные карточки и журнал в сейве остаются как были — в них лежит текст момента события.
enum ContentLocalizer {
    enum Kind {
        case world, story, lore, map
    }

    static func data(at url: URL, kind: Kind) -> Data {
        guard let raw = try? Data(contentsOf: url) else { return Data() }
        guard !AppLanguage.isRussian, var root = jsonObject(raw) else { return raw }
        apply(&root, kind: kind)
        guard JSONSerialization.isValidJSONObject(root),
              let out = try? JSONSerialization.data(withJSONObject: root) else { return raw }
        return out
    }

    private static let table: [String: Any] = {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("L10n/en.json")
        guard let data = try? Data(contentsOf: url),
              let obj = jsonObject(data) as? [String: Any] else { return [:] }
        return obj
    }()

    private static func jsonObject(_ data: Data) -> Any? {
        try? JSONSerialization.jsonObject(with: data)
    }

    private static func apply(_ root: inout Any, kind: Kind) {
        switch kind {
        case .world: applyWorld(&root)
        case .story: applyStory(&root)
        case .lore: applyLore(&root)
        case .map: applyMap(&root)
        }
    }

    private static func applyWorld(_ root: inout Any) {
        guard var doc = root as? [String: Any],
              var chapters = doc["chapters"] as? [[String: Any]] else { return }
        let specs = (table["world"] as? [String: Any])?["chapters"] as? [String: Any] ?? [:]
        for i in chapters.indices {
            let id = stringID(chapters[i]["id"])
            guard let spec = specs[id] as? [String: Any] else { continue }
            if let title = spec["title"] as? String { chapters[i]["title"] = title }
            if var sets = chapters[i]["settlements"] as? [[String: Any]],
               let names = spec["settlements"] as? [String: Any] {
                for j in sets.indices {
                    let sid = sets[j]["id"] as? String ?? ""
                    guard let n = names[sid] as? [String: Any] else { continue }
                    copyStrings(n, into: &sets[j], keys: ["name", "nameGenitive", "fullName"])
                }
                chapters[i]["settlements"] = sets
            }
            if var quests = chapters[i]["quests"] as? [[String: Any]],
               let qmap = spec["quests"] as? [String: String] {
                for j in quests.indices {
                    let until = stringID(quests[j]["untilStep"])
                    if let text = qmap[until] { quests[j]["telegram"] = text }
                }
                chapters[i]["quests"] = quests
            }
        }
        doc["chapters"] = chapters
        root = doc
    }

    private static func applyMap(_ root: inout Any) {
        guard var doc = root as? [String: Any],
              var sets = doc["settlements"] as? [[String: Any]] else { return }
        let names = (table["map"] as? [String: Any])?["settlements"] as? [String: String] ?? [:]
        for i in sets.indices {
            let id = sets[i]["id"] as? String ?? ""
            if let name = names[id] { sets[i]["name"] = name }
        }
        doc["settlements"] = sets
        root = doc
    }

    private static func applyLore(_ root: inout Any) {
        guard var doc = root as? [String: Any] else { return }
        let lore = table["lore"] as? [String: Any] ?? [:]
        for (id, specAny) in lore {
            guard var entry = doc[id] as? [String: Any],
                  let spec = specAny as? [String: Any] else { continue }
            if let title = spec["title"] as? String { entry["title"] = title }
            if let lines = spec["lines"] as? [String] { entry["lines"] = lines }
            doc[id] = entry
        }
        root = doc
    }

    private static func applyStory(_ root: inout Any) {
        guard var doc = root as? [String: Any] else { return }
        let chapter = stringID(doc["chapter"])
        guard let spec = (table["stories"] as? [String: Any])?[chapter] as? [String: Any] else { return }
        copyStrings(spec, into: &doc, keys: ["finaleTitle", "finaleSubtitle", "nextChapter", "sortAuto"])
        if var items = doc["items"] as? [[String: Any]],
           let itemSpecs = spec["items"] as? [String: Any] {
            for i in items.indices {
                let id = items[i]["id"] as? String ?? ""
                guard let itemSpec = itemSpecs[id] as? [String: Any] else { continue }
                copyStrings(itemSpec, into: &items[i], keys: ["to", "place", "from", "text", "outside", "note"])
                if var reader = items[i]["reader"] as? [String: Any] {
                    if let caption = itemSpec["attachmentCaption"] as? String {
                        reader["attachmentCaption"] = caption
                    }
                    if let address = itemSpec["address"] as? [String] { reader["address"] = address }
                    if let stamp = itemSpec["stamp"] as? [String] { reader["stamp"] = stamp }
                    items[i]["reader"] = reader
                }
                if var notes = items[i]["notes"] as? [[String: Any]],
                   let noteSpecs = itemSpec["notes"] as? [[String: Any]] {
                    let n = min(notes.count, noteSpecs.count)
                    for j in 0..<n {
                        copyStrings(noteSpecs[j], into: &notes[j], keys: ["who", "text"])
                    }
                    items[i]["notes"] = notes
                }
            }
            doc["items"] = items
        }
        if var events = doc["events"] as? [[String: Any]],
           let eventSpecs = spec["events"] as? [String: Any] {
            for i in events.indices {
                let id = events[i]["id"] as? String ?? ""
                guard let eventSpec = eventSpecs[id] as? [String: Any] else { continue }
                copyStrings(eventSpec, into: &events[i], keys: ["title", "text", "fallback", "note"])
                replaceLines(&events[i], key: "lines", specs: eventSpec["lines"])
                replaceLines(&events[i], key: "push", specs: eventSpec["push"])
                if var options = events[i]["options"] as? [[String: Any]],
                   let optionSpecs = eventSpec["options"] as? [String: Any] {
                    for j in options.indices {
                        let oid = options[j]["id"] as? String ?? ""
                        guard let optionSpec = optionSpecs[oid] as? [String: Any] else { continue }
                        copyStrings(optionSpec, into: &options[j], keys: ["label", "result", "auto"])
                    }
                    events[i]["options"] = options
                }
            }
            doc["events"] = events
        }
        if var quests = doc["quests"] as? [[String: Any]],
           let qmap = spec["quests"] as? [String: String] {
            for i in quests.indices {
                let key = questKey(quests[i]["event"], quests[i]["if"])
                if let text = qmap[key] { quests[i]["telegram"] = text }
            }
            doc["quests"] = quests
        }
        if var residents = doc["residents"] as? [[String: Any]],
           let names = spec["residents"] as? [String: String] {
            for i in residents.indices {
                let id = residents[i]["id"] as? String ?? ""
                if let name = names[id] { residents[i]["name"] = name }
            }
            doc["residents"] = residents
        }
        if var fates = doc["fates"] as? [[String: Any]],
           let fmap = spec["fates"] as? [String: String] {
            for i in fates.indices {
                let key = questKey(fates[i]["settlement"], fates[i]["if"])
                if let text = fmap[key] { fates[i]["text"] = text }
            }
            doc["fates"] = fates
        }
        if var arrivals = doc["arrivals"] as? [[String: Any]],
           let amap = spec["arrivals"] as? [String: String] {
            for i in arrivals.indices {
                let id = arrivals[i]["settlement"] as? String ?? ""
                if let text = amap[id] { arrivals[i]["text"] = text }
            }
            doc["arrivals"] = arrivals
        }
        root = doc
    }

    private static func replaceLines(_ event: inout [String: Any], key: String, specs: Any?) {
        guard let specs = specs as? [[String: Any]],
              var lines = event[key] as? [[String: Any]] else { return }
        let n = min(lines.count, specs.count)
        for i in 0..<n {
            copyStrings(specs[i], into: &lines[i], keys: ["who", "text"])
        }
        event[key] = lines
    }

    private static func copyStrings(_ from: [String: Any], into: inout [String: Any], keys: [String]) {
        for key in keys {
            if let value = from[key] as? String { into[key] = value }
        }
    }

    private static func questKey(_ id: Any?, _ condition: Any?) -> String {
        let left = id as? String ?? ""
        let right = (condition as? String) ?? ""
        return left + "|" + right
    }

    private static func stringID(_ value: Any?) -> String {
        if let s = value as? String { return s }
        if let n = value as? Int { return String(n) }
        if let n = value as? NSNumber { return n.stringValue }
        return ""
    }
}

/// Русские имена из исходных JSON. Нужны, чтобы старый журнал (текст уже в сейве)
/// находил место и жителя, даже если игра теперь на английском. На русскую локаль
/// не влияет: там совпадает текущее имя, как и раньше.
enum SaveNames {
    static func settlementID(matching folded: String, among settlements: [Settlement]) -> Settlement? {
        if let hit = settlements.first(where: {
            $0.name.lowercased() == folded || $0.fullName.lowercased() == folded || $0.id == folded
        }) { return hit }
        guard let id = settlementIndex[folded] else { return nil }
        return settlements.first { $0.id == id }
    }

    static func resident(matching raw: String, in residents: [StoryConfig.Resident]) -> StoryConfig.Resident? {
        func match(_ s: String) -> StoryConfig.Resident? {
            let t = s.lowercased()
            if let hit = residents.first(where: {
                $0.name.lowercased() == t || $0.id == t || $0.aliases.contains(t)
            }) { return hit }
            guard let id = residentIndex[t] else { return nil }
            return residents.first { $0.id == id }
        }
        if let hit = match(raw) { return hit }
        for part in raw.components(separatedBy: "·") {
            if let hit = match(part.trimmingCharacters(in: .whitespaces)) { return hit }
        }
        return nil
    }

    /// Та же основа, что в журнале: «Кузьме» всё ещё находит «Кузьма» в старом сейве.
    static func residentByStem(in words: [String], residents: [StoryConfig.Resident]) -> StoryConfig.Resident? {
        if let hit = stem(words, names: residents.map { ($0.id, $0.name) }, residents: residents) {
            return hit
        }
        let canonical = residentIndex.map { ($0.value, $0.key) }
        return stem(words, names: canonical, residents: residents)
    }

    private static func stem(_ words: [String], names: [(String, String)],
                             residents: [StoryConfig.Resident]) -> StoryConfig.Resident? {
        for (id, name) in names {
            let folded = name.lowercased()
            guard folded.count >= 3, folded.allSatisfy({ $0.isLetter }) else { continue }
            let stem = String(folded.dropLast())
            let hit = words.contains { word in
                word == folded || (word.hasPrefix(stem) && word.count <= folded.count + 2)
            }
            if hit, let resident = residents.first(where: { $0.id == id }) { return resident }
        }
        return nil
    }

    private static let settlementIndex: [String: String] = loadSettlements()
    private static let residentIndex: [String: String] = loadResidents()

    private static func loadSettlements() -> [String: String] {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/world.json")
        guard let data = try? Data(contentsOf: url),
              let doc = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let chapters = doc["chapters"] as? [[String: Any]] else { return [:] }
        var index: [String: String] = [:]
        for chapter in chapters {
            for set in chapter["settlements"] as? [[String: Any]] ?? [] {
                guard let id = set["id"] as? String else { continue }
                for key in ["name", "fullName", "nameGenitive"] {
                    if let name = set[key] as? String { index[name.lowercased()] = id }
                }
            }
        }
        return index
    }

    private static func loadResidents() -> [String: String] {
        var index: [String: String] = [:]
        for name in ["chapter1_story.json", "chapter2_story.json"] {
            let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/\(name)")
            guard let data = try? Data(contentsOf: url),
                  let doc = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let residents = doc["residents"] as? [[String: Any]] else { continue }
            for resident in residents {
                guard let id = resident["id"] as? String, let display = resident["name"] as? String else { continue }
                index[display.lowercased()] = id
            }
        }
        let loreURL = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/resident_lore.json")
        if let data = try? Data(contentsOf: loreURL),
           let lore = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            for (id, value) in lore {
                if let entry = value as? [String: Any], let title = entry["title"] as? String {
                    index[title.lowercased()] = id
                }
            }
        }
        return index
    }
}

/// Подпись к рисунку, в пикселях которого ещё виден русский. На русской локали не показывается.
enum BakedArt {
    static func caption(for asset: String?) -> String? {
        guard AppLanguage.isRussian == false, let asset else { return nil }
        switch asset {
        case "att_label": return L10n.text("baked.att_label")
        case "att_drawing": return L10n.text("baked.att_drawing")
        case "sheet_telegram": return L10n.text("baked.sheet_telegram")
        default: return nil
        }
    }
}
