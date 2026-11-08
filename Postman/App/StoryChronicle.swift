import Foundation

/// Один уже рассказанный абзац основной линии. Текст только из письма или из
/// уже выбранного последствия этого письма. Служебные шаги и журнальные строки сюда не входят.
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

/// Основная история, как она разложена в docs/design/chapter1-timeline.md §2
/// («Письма главы 1: 7»). Тела писем — те же строки, что в chapter1_story.json
/// (дословно из letters-ch1.md). Это не перебор doneEvents.
///
/// Главы 2 в таблице нет: chapter2-timeline.md и story-bible.md §5б в репозитории
/// отсутствуют, события главы 2 в JSON помечены как черновик. Пока их нет,
/// вход в горы не дописывает абзацы.
enum StoryChronicle {
    struct Progress {
        var done: Set<String> = []
        var choices: [String: String] = [:]
        var items: [String: ItemStatus] = [:]
        var opened: Set<String> = []
        var carried: Set<String> = []
        /// Шаги этой главы, до которых почтальон дошёл. Чужой главе — 0.
        var reached: Int = 0
    }

    /// Явное соответствие абзаца и раскрывающего события. Не эвристика «всё, что случилось».
    private struct Beat {
        let id: String
        let chapterID: Int
        let step: Int
        let eventID: String
        let itemID: String
        /// Внутренний текст секретного письма — только после вскрытия.
        let secret: Bool
        let residentID: String?
        let placeID: String?
        /// Выбор, чьё выбранное последствие относится к этому письму.
        let choiceID: String?
    }

    /// Источник порядка и состава: docs/design/chapter1-timeline.md, таблица §2.
    /// Придорожные события той же схемы (тачка, коза, гроза, звери) в таблицу не входят.
    /// Ветер входит только как последствие письма Нины Тимофею.
    private static let beats: [Beat] = [
        Beat(id: "l1", chapterID: 1, step: 2900, eventID: "d_l1", itemID: "l1",
             secret: false, residentID: "kuzma", placeID: "svai", choiceID: nil),
        Beat(id: "l2", chapterID: 1, step: 6000, eventID: "d_l2", itemID: "l2",
             secret: false, residentID: "pimen", placeID: "zvonarnya", choiceID: nil),
        Beat(id: "l6", chapterID: 1, step: 9100, eventID: "d_l6", itemID: "l6",
             secret: false, residentID: "nina", placeID: "kadushki", choiceID: nil),
        Beat(id: "l4", chapterID: 1, step: 13200, eventID: "d_vera", itemID: "l4",
             secret: false, residentID: "vera", placeID: "nii", choiceID: nil),
        Beat(id: "l5", chapterID: 1, step: 13200, eventID: "d_vera", itemID: "l5",
             secret: true, residentID: "vera", placeID: "nii", choiceID: nil),
        Beat(id: "l3", chapterID: 1, step: 20000, eventID: "finale", itemID: "l3",
             secret: false, residentID: "nina", placeID: "sedlo", choiceID: "e_wind"),
        Beat(id: "l7", chapterID: 1, step: 20000, eventID: "finale", itemID: "l7",
             secret: false, residentID: nil, placeID: "sedlo", choiceID: nil),
    ]

    static func facts(world: WorldConfig, activeIndex: Int, activeSteps: Int,
                      active: Progress, saved: (Int) -> Progress?) -> [HistoryFact] {
        var pages: [HistoryFact] = []
        for (index, chapter) in world.chapters.enumerated() where index <= activeIndex {
            let story = StoryConfig.load(chapter: chapter.id)
            let progress = index == activeIndex ? active : (saved(chapter.id) ?? Progress())
            let reached = MetPeople.reached(index: index, active: activeIndex,
                                            activeSteps: activeSteps, length: chapter.lengthSteps)
            let gate = min(progress.reached, reached)
            pages += beats.compactMap { beat in
                paragraph(beat, chapter: chapter, story: story, progress: progress, reached: gate)
            }
        }
        return pages.sorted { ($0.worldStep, $0.id) < ($1.worldStep, $1.id) }
    }

    private static func paragraph(_ beat: Beat, chapter: ChapterConfig, story: StoryConfig,
                                  progress: Progress, reached: Int) -> HistoryFact? {
        guard beat.chapterID == chapter.id else { return nil }
        guard beat.step <= reached, progress.done.contains(beat.eventID) else { return nil }
        guard let item = story.item(beat.itemID) else { return nil }
        let status = progress.items[beat.itemID]
        let consequence = choiceResult(beat, story: story, progress: progress, reached: reached)
        // Требование Веры остаётся в кармане. Абзац — когда двенадцать батареек сданы.
        let body: String?
        if beat.id == "l4" {
            guard progress.items["batteries"] == .delivered else { return nil }
            body = item.text
        } else {
            body = letterBody(beat, item: item, status: status, opened: progress.opened)
        }
        // Письмо Нины Тимофею: либо опущено, либо ветер его уже унёс.
        // До этого абзац не открывается, даже если конверт лежит в сумке.
        if beat.id == "l3" {
            let sent = status == .sent
            let lost = status == .lostWind && progress.done.contains("e_wind")
            guard sent || lost else { return nil }
        }
        if beat.id == "l7", status != .read { return nil }
        var lines: [String] = []
        if let body, !body.isEmpty { lines.append(body) }
        if let consequence, !consequence.isEmpty, !lines.contains(consequence) {
            lines.append(consequence)
        }
        guard !lines.isEmpty else { return nil }
        let place = chapter.settlements.first { $0.id == beat.placeID }?.name ?? ""
        let heading = [item.from, item.to].filter { !$0.isEmpty }.joined(separator: " — ")
        return HistoryFact(id: "\(chapter.id):\(beat.id)",
                           worldStep: chapter.startStep + beat.step,
                           chapterID: chapter.id,
                           chapterTitle: chapter.title,
                           place: place,
                           heading: heading.isEmpty ? chapter.title : heading,
                           text: lines.joined(separator: "\n\n"),
                           residentID: beat.residentID,
                           assetsFolder: chapter.assetsFolder,
                           placeID: beat.placeID)
    }

    /// Тело — текст письма. У секретного до вскрытия видна только наружная строка.
    private static func letterBody(_ beat: Beat, item: StoryConfig.Item,
                                   status: ItemStatus?, opened: Set<String>) -> String? {
        if beat.secret {
            if opened.contains(beat.itemID) { return item.text }
            if status == .delivered || status == .sent || status == .read { return item.outside }
            return nil
        }
        switch status {
        case .delivered, .sent, .read, .lostWind:
            return item.text
        default:
            return opened.contains(beat.itemID) ? item.text : nil
        }
    }

    /// Только записанный вариант. Чужой result в абзац не попадает.
    private static func choiceResult(_ beat: Beat, story: StoryConfig,
                                     progress: Progress, reached: Int) -> String? {
        guard let choiceID = beat.choiceID, progress.done.contains(choiceID) else { return nil }
        guard let event = story.events.first(where: { $0.id == choiceID }), event.step <= reached else { return nil }
        guard let picked = progress.choices[choiceID] else { return nil }
        return event.options?.first { $0.id == picked }?.result
    }
}
