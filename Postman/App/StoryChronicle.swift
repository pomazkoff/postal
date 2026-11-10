import Foundation

/// Абзац уже узнанной основной истории. Текст — связный пересказ, не письмо и не журнал.
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

/// Основная линия по `docs/canon/story-bible.md` §§5 и 5б и по `docs/canon/ideas.md`
/// (акт I: быт, адресаты, первые странные письма и замеченные противоречия).
/// Авторская правда §§1–2 в свиток не попадает: ни мотива, ни виновных, ни глав 3–5.
/// Каждый абзац ждёт своё событие и состояние сейва. Это не перебор doneEvents и не цитатник писем.
enum StoryChronicle {
    struct Progress {
        var done: Set<String> = []
        var choices: [String: String] = [:]
        var items: [String: ItemStatus] = [:]
        var opened: Set<String> = []
        var carried: Set<String> = []
        var reached: Int = 0
    }

    private struct Beat {
        let id: String
        let chapterID: Int
        let step: Int
        let eventID: String
        let residentID: String?
        let placeID: String?
    }

    /// Порядок — порядок узнавания на ленте, не порядок всех событий.
    private static let beats: [Beat] = [
        Beat(id: "road", chapterID: 1, step: 0, eventID: "sort", residentID: nil, placeID: "pochta"),
        Beat(id: "stilts", chapterID: 1, step: 2900, eventID: "d_l1", residentID: "kuzma", placeID: "svai"),
        Beat(id: "belfry", chapterID: 1, step: 6000, eventID: "d_l2", residentID: "pimen", placeID: "zvonarnya"),
        Beat(id: "ask", chapterID: 1, step: 8900, eventID: "s_nina", residentID: "nina", placeID: "kadushki"),
        Beat(id: "strange", chapterID: 1, step: 9100, eventID: "d_l6", residentID: "nina", placeID: "kadushki"),
        Beat(id: "nii", chapterID: 1, step: 13200, eventID: "d_vera", residentID: "vera", placeID: "nii"),
        Beat(id: "wind", chapterID: 1, step: 15500, eventID: "e_wind", residentID: nil, placeID: "sedlo"),
        Beat(id: "saddle", chapterID: 1, step: 20000, eventID: "finale", residentID: nil, placeID: "sedlo"),
        Beat(id: "two", chapterID: 2, step: 50, eventID: "p_l1", residentID: "nina", placeID: "sedlo"),
        Beat(id: "fuse", chapterID: 2, step: 7200, eventID: "p_l3", residentID: "mitya", placeID: "penki"),
        Beat(id: "roosters", chapterID: 2, step: 7400, eventID: "p_l4", residentID: "kuzma", placeID: "penki"),
        Beat(id: "thursday", chapterID: 2, step: 7600, eventID: "p_l5", residentID: "pimen", placeID: "penki"),
        Beat(id: "hum", chapterID: 2, step: 14000, eventID: "p_l6", residentID: "mitya", placeID: "repka"),
        Beat(id: "station", chapterID: 2, step: 14200, eventID: "p_l7", residentID: "nina", placeID: "repka"),
        Beat(id: "mark", chapterID: 2, step: 16800, eventID: "p_l8", residentID: "kuzma", placeID: "krivulya"),
        Beat(id: "lamp", chapterID: 2, step: 20000, eventID: "p_l9", residentID: "pimen", placeID: "krivulya"),
        Beat(id: "bell", chapterID: 2, step: 20050, eventID: "s_bell", residentID: "pimen", placeID: "krivulya"),
        Beat(id: "gorge", chapterID: 2, step: 25000, eventID: "finale", residentID: nil, placeID: "gorlovina"),
    ]

    static func facts(world: WorldConfig, activeIndex: Int, activeSteps: Int,
                      active: Progress, saved: (Int) -> Progress?) -> [HistoryFact] {
        var pages: [HistoryFact] = []
        for (index, chapter) in world.chapters.enumerated() where index <= activeIndex {
            let progress = index == activeIndex ? active : (saved(chapter.id) ?? Progress())
            let reached = MetPeople.reached(index: index, active: activeIndex,
                                            activeSteps: activeSteps, length: chapter.lengthSteps)
            let gate = min(progress.reached, reached)
            let valleyID = world.chapters.first?.id ?? chapter.id
            let valley = chapter.id == valleyID ? progress : (saved(valleyID) ?? Progress())
            for beat in beats where beat.chapterID == chapter.id && beat.step <= gate && progress.done.contains(beat.eventID) {
                guard let text = prose(beat.id, here: progress, valley: valley), !text.isEmpty else { continue }
                let place = chapter.settlements.first { $0.id == beat.placeID }?.name ?? ""
                pages.append(HistoryFact(
                    id: "\(chapter.id):\(beat.id)",
                    worldStep: chapter.startStep + beat.step,
                    chapterID: chapter.id,
                    chapterTitle: chapter.title,
                    place: place,
                    heading: L10n.text(titleKey(beat.id)),
                    text: text,
                    residentID: beat.residentID,
                    assetsFolder: chapter.assetsFolder,
                    placeID: beat.placeID))
            }
        }
        return pages.sorted { ($0.worldStep, $0.id) < ($1.worldStep, $1.id) }
    }

    private static func titleKey(_ id: String) -> String {
        switch id {
        case "road": return "history.main.road.title"
        case "stilts": return "history.main.stilts.title"
        case "belfry": return "history.main.belfry.title"
        case "ask": return "history.main.ask.title"
        case "strange": return "history.main.strange.title"
        case "nii": return "history.main.nii.title"
        case "wind": return "history.main.wind.title"
        case "saddle": return "history.main.saddle.title"
        case "two": return "history.main.two.title"
        case "fuse": return "history.main.fuse.title"
        case "roosters": return "history.main.roosters.title"
        case "thursday": return "history.main.thursday.title"
        case "hum": return "history.main.hum.title"
        case "station": return "history.main.station.title"
        case "mark": return "history.main.mark.title"
        case "lamp": return "history.main.lamp.title"
        case "bell": return "history.main.bell.title"
        case "gorge": return "history.main.gorge.title"
        default: return "history.title"
        }
    }

    /// Письмо уже было в руках: унесено, вручено, прочитано или ещё лежит в сумке.
    private static func carried(_ id: String, _ items: [String: ItemStatus]) -> Bool {
        switch items[id] {
        case .inBag, .inPocket, .delivered, .sent, .read, .lostWind: return true
        default: return false
        }
    }

    private static func prose(_ id: String, here: Progress, valley: Progress) -> String? {
        switch id {
        case "road":
            var lines = [L10n.text("history.main.road.out")]
            if carried("l3", here.items) { lines.append(L10n.text("history.main.road.nina")) }
            if carried("l2", here.items) { lines.append(L10n.text("history.main.road.mitya")) }
            if here.items["l4"] == .inPocket || carried("l4", here.items) {
                lines.append(L10n.text("history.main.road.vera"))
            }
            return lines.joined(separator: " ")
        case "stilts":
            guard here.items["l1"] == .delivered else { return nil }
            return L10n.text("history.main.stilts.body")
        case "belfry":
            guard here.items["l2"] == .delivered else { return nil }
            var lines = [L10n.text("history.main.belfry.body")]
            if carried("l5", here.items) {
                lines.append(L10n.text("history.main.belfry.fortyone"))
            }
            if here.opened.contains("l5") {
                lines.append(L10n.text("history.main.belfry.opened"))
            }
            return lines.joined(separator: " ")
        case "ask":
            if here.items["l3"] == .inBag { return L10n.text("history.main.ask.bag") }
            if here.items["l3"] == .atPost { return L10n.text("history.main.ask.post") }
            return L10n.text("history.main.ask.body")
        case "strange":
            guard here.items["l6"] == .delivered else { return nil }
            return L10n.text("history.main.strange.body")
        case "nii":
            guard here.items["batteries"] == .delivered else { return nil }
            return L10n.text("history.main.nii.body")
        case "wind":
            guard let picked = here.choices["e_wind"] else { return nil }
            if picked == "let" { return L10n.text("history.main.wind.let") }
            if picked == "chase" { return L10n.text("history.main.wind.chase") }
            return nil
        case "saddle":
            var lines: [String] = []
            if here.items["l3"] == .sent { lines.append(L10n.text("history.main.saddle.sent")) }
            if here.items["l7"] == .read { lines.append(L10n.text("history.main.saddle.ksenia")) }
            return lines.isEmpty ? nil : lines.joined(separator: " ")
        case "two":
            guard valley.items["l6"] == .delivered, carried("l1", here.items) else { return nil }
            return L10n.text("history.main.two.body")
        case "fuse":
            guard carried("l3", here.items) else { return nil }
            return L10n.text("history.main.fuse.body")
        case "roosters":
            guard carried("l4", here.items) else { return nil }
            return L10n.text("history.main.roosters.body")
        case "thursday":
            guard carried("l5", here.items) else { return nil }
            return L10n.text("history.main.thursday.body")
        case "hum":
            guard carried("l6", here.items) else { return nil }
            return L10n.text("history.main.hum.body")
        case "station":
            guard carried("l7", here.items) else { return nil }
            if carried("l1", here.items) { return L10n.text("history.main.station.body") }
            if valley.items["l6"] == .delivered { return L10n.text("history.main.station.box") }
            return L10n.text("history.main.station.only")
        case "mark":
            guard carried("l8", here.items) else { return nil }
            return L10n.text("history.main.mark.body")
        case "lamp":
            guard carried("l9", here.items) else { return nil }
            if here.done.contains("p_l4") {
                return L10n.text("history.main.lamp.compared")
            }
            return L10n.text("history.main.lamp.body")
        case "bell":
            return L10n.text("history.main.bell.body")
        case "gorge":
            return L10n.text("history.main.gorge.body")
        default:
            return nil
        }
    }
}
