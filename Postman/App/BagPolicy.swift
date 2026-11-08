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

    /// Событие, на котором вещь уже должна покинуть сумку. nil — находка, её не вручают.
    static func handoff(chapter: Int, id: String) -> String? {
        switch (chapter, id) {
        case (1, "l1"): return "d_l1"
        case (1, "l2"): return "d_l2"
        case (1, "l3"), (1, "l7"): return "finale"
        case (1, "l4"), (1, "l5"), (1, "batteries"): return "d_vera"
        case (1, "l6"): return "d_l6"
        case (2, "l1"), (2, "l2"): return "s_nii_drop"
        case (2, "l3"), (2, "l4"), (2, "l5"), (2, "l6"), (2, "l7"), (2, "l8"), (2, "note_gar"): return "finale"
        default: return nil
        }
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
        default: return nil
        }
    }

    static func actionKey(chapter: Int, id: String) -> String {
        "bag.act.\(chapter).\(id)"
    }

    /// Ключ одной строки в журнал, когда уже пройденная точка наконец забирает почту из старого сейва.
    static func passedNoteKey(trigger: String) -> String { "bag.handoff.\(trigger)" }

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

        for trigger in snap.done where !settled.contains(trigger) {
            var moved = false
            for (id, status) in items where handoff(chapter: chapter, id: id) == trigger && carried.contains(status) {
                items[id] = closeStatus(chapter: chapter, id: id)
                moved = true
            }
            settled.insert(trigger)
            if moved { logs.append(passedNoteKey(trigger: trigger)) }
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
