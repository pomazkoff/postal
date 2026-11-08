import Foundation
import UIKit

/// Один уже случившийся кусок пути. Текст только из сюжета и строк движка.
struct HistoryFact: Identifiable, Equatable {
    let id: String
    let worldStep: Int
    let chapterID: Int
    let chapterTitle: String
    let place: String
    let heading: String
    let text: String
    let residentID: String?
    let assetsFolder: String
    let placeID: String?
}

/// Хроника пройденного. Будущая глава и несделанное событие сюда не попадают,
/// даже если файл главы уже открыт.
enum StoryChronicle {
    struct Progress {
        var done: Set<String> = []
        var choices: [String: String] = [:]
        var items: [String: ItemStatus] = [:]
        var carried: Set<String> = []
        /// Шаги этой главы, до которых почтальон дошёл. Чужой главе — 0.
        var reached: Int = 0
    }

    static func facts(world: WorldConfig, activeIndex: Int, activeSteps: Int,
                      active: Progress, saved: (Int) -> Progress?) -> [HistoryFact] {
        var pages: [HistoryFact] = []
        for (index, chapter) in world.chapters.enumerated() where index <= activeIndex {
            let story = StoryConfig.load(chapter: chapter.id)
            let progress = index == activeIndex ? active : (saved(chapter.id) ?? Progress())
            let reached = MetPeople.reached(index: index, active: activeIndex,
                                            activeSteps: activeSteps, length: chapter.lengthSteps)
            let known = Progress(done: progress.done, choices: progress.choices,
                                 items: progress.items, carried: progress.carried,
                                 reached: min(progress.reached, reached))
            // Дошедший шаг главы режет спойлеры. doneEvents без этого шага не показываем.
            let gate = min(known.reached, reached)
            pages += chapterFacts(chapter: chapter, story: story, done: known.done,
                                  choices: known.choices, items: known.items,
                                  carried: known.carried, reached: gate)
        }
        return pages.sorted { ($0.worldStep, $0.id) < ($1.worldStep, $1.id) }
    }

    private static func chapterFacts(chapter: ChapterConfig, story: StoryConfig,
                                     done: Set<String>, choices: [String: String],
                                     items: [String: ItemStatus], carried: Set<String>,
                                     reached: Int) -> [HistoryFact] {
        var pages: [HistoryFact] = []
        for place in chapter.settlements where place.step <= reached && done.contains("arrive:" + place.id) {
            guard let line = story.arrivals?.first(where: { $0.settlement == place.id })?.text,
                  !line.isEmpty else { continue }
            pages.append(make(id: "arrive:\(chapter.id):\(place.id)", step: place.step, chapter: chapter,
                              place: place.name, heading: place.name, text: line,
                              resident: nil, placeID: place.id))
        }
        for event in story.events where event.step <= reached && done.contains(event.id) {
            let place = chapter.settlements.first { $0.id == event.settlement }?.name ?? event.settlement
            let text = sentences(event: event, choices: choices, items: items, carried: carried, story: story)
            guard !text.isEmpty else { continue }
            let heading = event.title?.isEmpty == false ? event.title! : place
            pages.append(make(id: "\(chapter.id):\(event.id)", step: event.step, chapter: chapter,
                              place: place, heading: heading, text: text,
                              resident: event.resident, placeID: event.settlement))
        }
        return pages
    }

    private static func make(id: String, step: Int, chapter: ChapterConfig, place: String,
                             heading: String, text: String, resident: String?, placeID: String?) -> HistoryFact {
        HistoryFact(id: id, worldStep: chapter.startStep + step, chapterID: chapter.id,
                    chapterTitle: chapter.title, place: place, heading: heading, text: text,
                    residentID: resident, assetsFolder: chapter.assetsFolder, placeID: placeID)
    }

    /// Уже показанные фразы. Чужие ветки выбора и условные реплики не включаются.
    static func sentences(event: StoryConfig.Event, choices: [String: String],
                          items: [String: ItemStatus], carried: Set<String>,
                          story: StoryConfig) -> String {
        var lines: [String] = []
        func add(_ line: String?) {
            guard let line, !line.isEmpty, !lines.contains(line) else { return }
            lines.append(line)
        }
        switch event.type {
        case .choice:
            add(event.text)
            if let picked = choices[event.id],
               let option = event.options?.first(where: { $0.id == picked }) {
                add(option.result)
            } else {
                add(event.fallback)
            }
        case .scene:
            add(event.text)
            for line in event.lines ?? [] where line.if == nil || line.if?.isEmpty == true {
                if line.who.isEmpty { add(line.text) }
                else { add("\(line.who): «\(line.text)»") }
            }
        case .deliver:
            let given = (event.items ?? []).filter { items[$0] == .delivered }
            if given.isEmpty {
                add(L10n.text("engine.deliver.none"))
            } else {
                let names = given.compactMap { story.item($0) }.map(describe)
                add(L10n.format("engine.deliver.some", names.joined(separator: ", ")))
            }
        case .pickup:
            if let id = event.item, let item = story.item(id) {
                switch items[id] {
                case .inBag, .inPocket, .delivered, .sent, .read:
                    add(L10n.format("engine.pickup.took", describe(item)))
                case .leftBehind, .lostWind:
                    add(L10n.format("engine.pickup.full", describe(item)))
                default:
                    break
                }
            }
            add(event.text)
        case .sort:
            let taken = (event.candidates ?? []).filter {
                carried.contains($0) || items[$0] == .inBag || items[$0] == .delivered || items[$0] == .sent
            }
            if taken.isEmpty {
                add(L10n.text("engine.sort.empty"))
            } else {
                let names = taken.compactMap { story.item($0) }.map(describe)
                add(L10n.format("engine.sort.some", names.joined(separator: ", ")))
            }
        case .finale:
            add(event.text)
            add(L10n.text("engine.finale.log"))
        }
        return lines.joined(separator: "\n")
    }

    private static func describe(_ item: StoryConfig.Item) -> String {
        switch item.kind {
        case "parcel": return L10n.format("engine.item.parcel", item.place)
        case "form": return L10n.text("engine.item.form")
        default: return L10n.format("engine.item.letter", item.to)
        }
    }
}
