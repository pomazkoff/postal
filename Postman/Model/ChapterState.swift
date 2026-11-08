import Foundation

/// Карточка, которую игрок должен увидеть (вручение, подбор, сцена, выбор, финал).
/// Реплики вычисляются в момент события и сохраняются — потом состояние писем меняется,
/// а показать нужно то, что было тогда.
struct StoryCard: Codable, Identifiable, Hashable {
    enum Kind: String, Codable { case delivery, pickup, scene, choice, finale }
    let id: String          // = id события
    let kind: Kind
    let step: Int
    let settlement: String
    let resident: String?
    let title: String?
    let text: String?
    let lines: [StoryConfig.Line]
    /// Что вручено / подобрано (для картинки в руке).
    let items: [String]
    /// Что не удалось вручить / подобрать.
    let missed: [String]
}

/// Запись журнала «Вот как развивалась история». Новые поля необязательны — старые сохранения читаются.
struct LogEntry: Codable, Hashable {
    let step: Int
    let text: String
    /// sort · arrival · delivery · pickup · scene · choice · finale · opened
    var kind: String? = nil
    var place: String? = nil
    var title: String? = nil
    /// Кто выбрал: player · postman (только для выборов и разбора).
    var by: String? = nil
    /// Когда событие обработано (в фоне — момент пробуждения приложения).
    var date: Date? = nil
}

/// Всё состояние главы 1 (Codable → Application Support/chapter1_state.json).
struct ChapterState: Codable {
    var version = 1
    var sortingDone = false
    var items: [String: ItemStatus] = [:]
    var opened: Set<String> = []
    var carried: Set<String> = []
    var doneEvents: Set<String> = []
    var choices: [String: String] = [:]
    var trust: [String: Int] = [:]
    var flags: Set<String> = []
    /// Очередь непоказанных карточек (по порядку событий).
    var pendingCards: [StoryCard] = []
    var log: [LogEntry] = []
    /// Шаги главы, которые игрок видел в прошлый раз (для экрана «пока вас не было»).
    var lastSeenSteps: Int?
    /// Дата чтения письма 7 (штемпель = дата чтения + 2 дня).
    var kseniaReadDate: Date?
    var finished = false
    var endCardSeen = false
    /// Карточка «путешествие продолжится» уже закрыта.
    /// Нет ключа в старом сохранении — ещё не показывали. На письма и шаги не влияет.
    var journeyCardSeen: Bool? = nil
    /// Кто сделал выбор: id события → "player" | "postman".
    var choiceBy: [String: String]?
    /// Сколько записей журнала игрок уже видел (журнал показывает log[journalSeenCount...]).
    var journalSeenCount: Int?
    /// Точки передачи, на которых почта уже снята с сумки. Повторная миграция ничего не добавляет.
    var settledHandoffs: [String]?
}

/// Чтение/запись ChapterState на диск. Пишет атомарно; битый файл → чистое состояние.
final class ChapterStateStore {
    private let url: URL

    init(fileName: String = "chapter1_state.json") {
        let fm = FileManager.default
        let dir = (try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask,
                               appropriateFor: nil, create: true))
            ?? fm.temporaryDirectory
        url = dir.appendingPathComponent(fileName)
    }

    func load() -> ChapterState? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(ChapterState.self, from: data)
    }

    func save(_ state: ChapterState) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        do {
            let data = try encoder.encode(state)
            try data.write(to: url, options: .atomic)
        } catch {
            #if DEBUG
            print("ChapterStateStore: не удалось сохранить: \(error)")
            #endif
        }
    }

    func reset() {
        try? FileManager.default.removeItem(at: url)
    }
}
