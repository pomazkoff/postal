import Foundation

/// Сюжет главы 1: GameAssets/Data/chapter1_story.json (генерирует tools/build_chapter1_story.py
/// из walking-sim/letters-ch1.md — тексты писем дословно).
struct StoryConfig: Decodable {
    struct Line: Codable, Hashable {
        let who: String
        let text: String
        /// Условие показа (см. StoryCondition), nil или "" — всегда.
        let `if`: String?
    }

    struct Reader: Decodable {
        let paper: String
        /// hand (Neucha) · draft (Oswald) · tape (лента телеграфа) · violet (Kurale, фиолетовый)
        let font: String
        let envelope: String?
        let envelopeOpened: String?
        let address: [String]
        let stamp: [String]?
        let attachment: String?
        let attachment2: String?
        let attachmentDate: String?
        let attachmentCaption: String?
    }

    struct Item: Decodable, Identifiable {
        let id: String
        /// letter · form · parcel · secret
        let kind: String
        let takesSlot: Bool
        let to: String
        let place: String
        let settlement: String
        let from: String
        let senderSettlement: String
        let art: String
        let artOpened: String?
        let stick: String
        let initial: ItemStatus
        let road: String?
        let reader: Reader?
        let text: String
        /// Секретное письмо: что написано снаружи (читается без вскрытия).
        let outside: String?
        /// Записка, лежащая вместе с письмом (А.Л.).
        let note: String?
        /// Условные варианты записки: первая, чьё условие выполняется; иначе — note.
        let notes: [Line]?
    }

    struct Option: Decodable, Identifiable {
        struct Effect: Decodable {
            let item: String
            let status: ItemStatus
        }
        let id: String
        let label: String
        let result: String
        let trust: [String: Int]?
        let flags: [String]?
        let effects: [Effect]?
        /// Строка, когда вариант выбрал сам почтальон (игрок не ответил) — для пуша и журнала.
        let auto: String?
    }

    enum EventType: String, Decodable {
        case sort, choice, deliver, pickup, scene, finale
    }

    struct Event: Decodable, Identifiable {
        let id: String
        let step: Int
        let type: EventType
        let settlement: String
        let resident: String?
        let title: String?
        let text: String?
        let fallback: String?
        let requires: String?
        let candidates: [String]?
        let items: [String]?
        let item: String?
        let send: String?
        let receive: String?
        let note: String?
        let options: [Option]?
        let lines: [Line]?
        /// Вариант «в характере» почтальона, если игрок не ответил (choicePolicy).
        let `default`: String?
        /// Строки пуш-уведомления: первая, чьё условие выполняется в момент события.
        let push: [Line]?
        /// Флаги, которые ставит событие-сцена (например, hum у грозы).
        let flags: [String]?
        /// Спутник, который идёт рядом с почтальоном на шагах from…to главы, если выполнено if.
        let companion: Companion?
    }

    struct Companion: Decodable {
        let id: String
        let from: Int
        let to: Int
        let `if`: String?
    }

    /// Как решаются выборы, пока игрок не в приложении (story json → choicePolicy; переключается в DEBUG).
    struct ChoicePolicy: Decodable {
        /// notifyThenAuto — пуш с кнопками, без ответа до следующей остановки или timeoutSteps шагов
        /// почтальон выбирает default сам; auto — сразу default; wait — старое поведение (сюжет ждёт игрока).
        let mode: String
        let timeoutSteps: Int
    }

    /// Прибытие в поселение — тоже остановка (пуш + запись в журнал). Шаг — из world.json.
    struct Arrival: Decodable {
        let settlement: String
        let text: String
    }

    struct Quest: Decodable {
        let telegram: String
        let event: String
        let `if`: String?
    }

    struct Resident: Decodable, Identifiable {
        let id: String
        let name: String
        let aliases: [String]
        let step: Int
        let dx: Double
        let height: Double
    }

    struct Fate: Decodable {
        let settlement: String
        let `if`: String
        let text: String
    }

    struct Day: Decodable {
        let day: Int
        let from: Int
        let to: Int
    }

    let chapter: Int
    let slots: Int
    let days: [Day]
    let items: [Item]
    let events: [Event]
    let quests: [Quest]
    let residents: [Resident]
    let fates: [Fate]
    let finaleTitle: String
    let finaleSubtitle: String
    let nextChapter: String
    let trustSettlements: [String]
    let choicePolicy: ChoicePolicy?
    let arrivals: [Arrival]?
    /// Что почтальон берёт на разборе сам (по умолчанию — все кандидаты, сколько влезет).
    let sortDefault: [String]?
    /// Пуш, когда разбор сделал почтальон.
    let sortAuto: String?

    func item(_ id: String) -> Item? { items.first { $0.id == id } }
    func event(_ id: String) -> Event? { events.first { $0.id == id } }
    func resident(_ id: String?) -> Resident? {
        guard let id else { return nil }
        return residents.first { $0.id == id }
    }

    static func load() -> StoryConfig { load(chapter: 1) }

    /// chapter 1 → chapter1_story.json, 2 → chapter2_story.json. Нет файла — fatal для 1, для >1 пробуем 1.
    static func load(chapter: Int) -> StoryConfig {
        let name = "chapter\(chapter)_story.json"
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/\(name)")
        if FileManager.default.fileExists(atPath: url.path) {
            do {
                return try JSONDecoder().decode(StoryConfig.self, from: ContentLocalizer.data(at: url, kind: .story))
            } catch {
                fatalError("Не удалось загрузить \(name): \(error)")
            }
        }
        if chapter != 1 {
            return load(chapter: 1)
        }
        fatalError("Нет Data/chapter1_story.json")
    }
}

/// Только открытые бытовые сведения: без авторских тайн и будущих сюжетных реплик.
/// Отдельный JSON копируется в бандл вместе с папкой GameAssets.
struct ResidentLore: Decodable {
    let title: String
    let lines: [String]

    var text: String { lines.joined(separator: "\n") }

    private static var cached: [String: ResidentLore]?

    private static func loadEntries() -> [String: ResidentLore] {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Data/resident_lore.json")
        do {
            return try JSONDecoder().decode([String: ResidentLore].self, from: ContentLocalizer.data(at: url, kind: .lore))
        } catch {
            #if DEBUG
            print("ResidentLore: не удалось загрузить resident_lore.json: \(error)")
            #endif
            return [:]
        }
    }

    static func invalidate() { cached = nil }

    static func entry(for id: String, fallbackTitle: String) -> ResidentLore {
        if cached == nil { cached = loadEntries() }
        return cached?[id] ?? ResidentLore(title: fallbackTitle, lines: [L10n.text("lore.empty")])
    }
}

/// Состояние письма/посылки.
enum ItemStatus: String, Codable {
    case atPost        // осталось на Почте (не взято при разборе)
    case onRoad        // ещё не подобрано (ждёт на дороге / в ящике / у жителя)
    case inBag
    case inPocket      // бланк Веры: в кармане, слот не занимает
    case delivered
    case sent          // опущено в ящик на Седле
    case lostWind      // унёс ветер (найдётся в гл. 2)
    case leftBehind    // не влезло в сумку при подборе
    case read          // прочитано на месте (письмо 7)
}
