import Foundation

/// Сумка без лимита мест и без выбора «что оставить».
/// Почта уходит в уже существующей точке сюжета. Находки остаются, их только смотрят.
/// Старый сейв не переигрывается: доверие, выборы и уже закрытые письма не трогаются.
enum BagPolicy {
    enum Role: String { case mail, personal }

    struct Snapshot {
        var items: [String: String]
        var done: Set<String>
        var sortingDone: Bool
        var settled: Set<String>
        var opened: Set<String>
        var choices: [String: String]
    }

    struct Change {
        var items: [String: String]
        var sortingDone: Bool
        var settled: Set<String>
        var logs: [String]
    }

    static func role(id: String, kind: String) -> Role {
        if kind == "letter" || kind == "parcel" || kind == "secret" { return .mail }
        // Бланки без kind «письмо»: требование, записка лесника, телеграмма. Их несут и сдают или читают.
        if id == "l4" || id == "note_gar" || id == "l9" { return .mail }
        return .personal
    }

    struct Drop: Equatable {
        var event: String
        var step: Int
    }

    /// Куда письмо можно сдать, от ближней точки к дальней. Первая точка всегда строго после подбора.
    /// Если её уже прошли, годится следующая, которая ещё впереди. Находки сюда не входят.
    static func drops(chapter: Int, id: String) -> [Drop] {
        switch (chapter, id) {
        case (1, "l1"): return [Drop(event: "d_l1", step: 2900)]
        case (1, "l2"): return [Drop(event: "d_l2", step: 6000)]
        case (1, "l3"), (1, "l7"): return [Drop(event: "finale", step: 20000)]
        case (1, "l4"), (1, "l5"), (1, "batteries"): return [Drop(event: "d_vera", step: 13200)]
        case (1, "l6"): return [Drop(event: "d_l6", step: 9100)]
        case (2, "l1"), (2, "l2"):
            return [Drop(event: "s_nii_drop", step: 400),
                    Drop(event: "e_khomut", step: 11000),
                    Drop(event: "finale", step: 25000)]
        case (2, "note_gar"), (2, "l3"), (2, "l4"), (2, "l5"):
            return [Drop(event: "e_khomut", step: 11000),
                    Drop(event: "finale", step: 25000)]
        case (2, "l6"), (2, "l7"), (2, "l8"):
            return [Drop(event: "finale", step: 25000)]
        case (3, "l1"): return [Drop(event: "d_gat", step: 4000)]
        case (3, "l4"), (3, "note_fedya"): return [Drop(event: "d_top", step: 9000)]
        case (3, "l2"): return [Drop(event: "d_torf", step: 12500)]
        case (3, "l3"): return [Drop(event: "d_barge", step: 16500)]
        case (3, "l5"), (3, "l7"): return [Drop(event: "d_reeds", step: 20000)]
        case (3, "l9"): return [Drop(event: "d_otstoy", step: 28000)]
        case (3, "find_edge"): return [Drop(event: "d_gat", step: 4000)]
        case (3, "find_tag"): return [Drop(event: "d_top", step: 9000)]
        case (3, "find_card"): return [Drop(event: "d_top", step: 9000)]
        case (3, "find_pole"): return [Drop(event: "d_torf", step: 12500)]
        case (3, "find_graph"): return [Drop(event: "d_torf", step: 12500)]
        case (3, "find_pass"): return [Drop(event: "d_barge", step: 16500)]
        default:
            return []
        }
    }

    /// Ближняя сдача. nil — находка или письмо, которое читают на месте.
    static func handoff(chapter: Int, id: String) -> String? {
        drops(chapter: chapter, id: id).first?.event
    }

    /// Сдача, которая ещё впереди игрока. Пройденную точку не называем.
    static func ahead(chapter: Int, id: String, playerStep: Int) -> Drop? {
        drops(chapter: chapter, id: id).first { $0.step > playerStep }
    }

    static func pickupEvent(chapter: Int, id: String) -> String? {
        switch (chapter, id) {
        case (1, "l5"): return "p_l5"
        case (1, "l6"): return "p_l6"
        case (1, "batteries"): return "p_bat"
        case (1, "animal_cat_stamp"): return "e_animal_cat"
        case (2, "l1"): return "p_l1"
        case (2, "l2"): return "p_l2"
        case (2, "l3"): return "p_l3"
        case (2, "l4"): return "p_l4"
        case (2, "l5"): return "p_l5"
        case (2, "l6"): return "p_l6"
        case (2, "l7"): return "p_l7"
        case (2, "l8"): return "p_l8"
        case (2, "l9"): return "p_l9"
        case (2, "note_gar"): return "p_note_gar"
        case (2, "animal_raven_scrap"): return "e_animal_raven"
        case (2, "animal_dog_horn"): return "p_animal_dog_find"
        case (3, "l1"): return "p_l1"
        case (3, "l2"): return "p_l2"
        case (3, "l3"): return "p_l3"
        case (3, "l4"): return "p_l4"
        case (3, "l5"): return "p_l5"
        case (3, "l6"): return "p_l6"
        case (3, "l7"): return "p_l7"
        case (3, "l8"): return "p_l8"
        case (3, "l9"): return "p_l9"
        case (3, "l10"): return "p_l10"
        case (3, "note_fedya"): return "e_fedya_help"
        case (3, "find_edge"): return "p_edge"
        case (3, "find_tag"): return "e_fedya_help"
        case (3, "find_card"): return "p_card"
        case (3, "find_pole"): return "p_pole"
        case (3, "find_graph"): return "p_graph"
        case (3, "find_pass"): return "p_pass"
        default: return nil
        }
    }

    static func actionKey(chapter: Int, id: String) -> String {
        actionKey(chapter: chapter, id: id, playerStep: -1)
    }

    /// Бирка называет ту сдачу, которая ещё впереди. Если ближнюю уже прошли, берётся следующая.
    static func actionKey(chapter: Int, id: String, playerStep: Int) -> String {
        let list = drops(chapter: chapter, id: id)
        if let active = list.first(where: { $0.step > playerStep }), active.event != list.first?.event {
            return "bag.act.drop.\(chapter).\(active.event)"
        }
        return "bag.act.\(chapter).\(id)"
    }

    /// Ключ одной строки в журнал, когда уже пройденная точка наконец забирает почту из старого сейва.
    /// У «finale» в ключе остаётся имя события: по нему журнал находит шаг. Текст зависит от главы.
    static func passedNoteKey(trigger: String) -> String { "bag.handoff.\(trigger)" }

    static func passedNoteTextKey(chapter: Int, trigger: String) -> String {
        trigger == "finale" ? "bag.handoff.\(chapter).finale" : passedNoteKey(trigger: trigger)
    }

    private static let carried: Set<String> = ["inBag", "inPocket"]
    private static let closed: Set<String> = ["delivered", "sent", "read", "lostWind"]

    /// Идемпотентно. Не возвращает уже закрытые письма и не повторяет доверие.
    static func migrate(chapter: Int, candidates: [String], snap: Snapshot) -> Change {
        var items = snap.items
        var sorting = snap.sortingDone
        var settled = snap.settled
        var logs: [String] = []

        if !sorting {
            var took = false
            for id in candidates where items[id] == "atPost" || items[id] == nil {
                items[id] = "inBag"
                took = true
            }
            sorting = true
            if took { logs.append("bag.took.all") }
        } else {
            var recovered = false
            for id in candidates where items[id] == "atPost" {
                if !handoffPassed(chapter: chapter, id: id, done: snap.done) {
                    items[id] = "inBag"
                    recovered = true
                }
            }
            for (id, status) in items where status == "leftBehind" {
                guard let pickup = pickupEvent(chapter: chapter, id: id), snap.done.contains(pickup) else { continue }
                if !handoffPassed(chapter: chapter, id: id, done: snap.done) {
                    items[id] = "inBag"
                    recovered = true
                }
            }
            if recovered { logs.append("bag.recovered") }
        }

        var movedAt: Set<String> = []
        for (id, status) in items where carried.contains(status) {
            guard let hit = drops(chapter: chapter, id: id).first(where: { snap.done.contains($0.event) }) else { continue }
            guard !settled.contains(hit.event) else { continue }
            items[id] = closeStatus(chapter: chapter, id: id)
            movedAt.insert(hit.event)
        }
        for trigger in snap.done.sorted() where !settled.contains(trigger) {
            settled.insert(trigger)
            if movedAt.contains(trigger) { logs.append(passedNoteKey(trigger: trigger)) }
        }

        return Change(items: items, sortingDone: sorting, settled: settled, logs: logs)
    }

    static func handoffPassed(chapter: Int, id: String, done: Set<String>) -> Bool {
        guard let event = handoff(chapter: chapter, id: id) else { return false }
        return done.contains(event)
    }

    static func readOnHandoff(chapter: Int, id: String) -> Bool {
        (chapter == 1 && id == "l7") || (chapter == 2 && id == "l9")
    }

    /// Письмо Нины сыну на Седле уходит как «отправлено». Телеграмму и письмо Ксении читают. Остальное — вручено.
    static func closeStatus(chapter: Int, id: String) -> String {
        if readOnHandoff(chapter: chapter, id: id) { return "read" }
        if chapter == 1 && id == "l3" { return "sent" }
        return "delivered"
    }

    static func isClosed(_ status: String) -> Bool { closed.contains(status) }
}
