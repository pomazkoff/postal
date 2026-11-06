import Foundation
import Combine

/// Логика главы 1: разбор сумки, события по шагам, состояние писем, доверие, финал.
///
/// История идёт БЕЗ игрока: все шаги засчитываются, маршрут не останавливается.
/// Остановки (прибытие в поселение, вручение, конверт на палке, событие) обрабатываются по порядку шагов —
/// и в приложении, и при фоновом пробуждении (HealthKit / BGAppRefresh, см. AppCore). О каждой остановке
/// движок сообщает через onBeat (локальный пуш). Выбор не блокирует сюжет: см. ChoiceMode.
@MainActor
final class ChapterEngine: ObservableObject {
    let story: StoryConfig
    @Published private(set) var state: ChapterState

    /// Шаги главы, до которых обработаны события (не убывает).
    private(set) var currentStep = 0

    /// Как решаются выборы без игрока. Источник — story json `choicePolicy` (переключается в DEBUG).
    enum ChoiceMode: String, CaseIterable {
        /// Пуш с кнопками; нет ответа до следующей остановки или timeoutSteps — выбирает почтальон (default).
        case notifyThenAuto
        /// Почтальон сразу выбирает default (пуш сообщает итог).
        case auto
        /// Сюжет ждёт ответа игрока (старое поведение).
        case wait

        var title: String {
            switch self {
            case .notifyThenAuto: return "пуш, потом сам"
            case .auto: return "почтальон сам"
            case .wait: return "ждать игрока"
            }
        }
    }
    var choiceMode: ChoiceMode
    var choiceTimeoutSteps: Int

    enum Chooser: String { case player, postman }

    /// Остановка для пуша: заголовок — место, тело — одна строка. choiceEventID — пуш с кнопками выбора.
    struct Beat {
        let id: String
        let title: String
        let body: String
        let choiceEventID: String?
    }
    /// Вызывается на каждой остановке (AppCore → Notifier).
    var onBeat: ((Beat) -> Void)?

    /// Игрок сейчас смотрит на мир: новые записи журнала сразу считаются увиденными.
    var liveViewing = false

    private struct Stop {
        enum Kind {
            case event(StoryConfig.Event)
            case arrival(id: String, name: String, text: String)
        }
        let step: Int
        let kind: Kind
        var key: String {
            switch kind {
            case .event(let e): return e.id
            case .arrival(let id, _, _): return "arrive:" + id
            }
        }
    }

    private let store: ChapterStateStore
    private let settlementName: (String) -> String
    private let gameStartDate: () -> Date?
    private let orderedEvents: [StoryConfig.Event]
    private let timeline: [Stop]

    /// settlements — (id, имя, шаг) из world.json: прибытия стоят перед событиями того же шага.
    init(story: StoryConfig, store: ChapterStateStore = ChapterStateStore(),
         settlements: [(id: String, name: String, step: Int)] = [],
         settlementName: @escaping (String) -> String, gameStartDate: @escaping () -> Date?) {
        self.story = story
        self.store = store
        self.settlementName = settlementName
        self.gameStartDate = gameStartDate
        let ordered = story.events.enumerated()
            .sorted { ($0.element.step, $0.offset) < ($1.element.step, $1.offset) }
            .map(\.element)
        self.orderedEvents = ordered
        var stops: [(Stop, Int)] = []
        for s in settlements where s.step > 0 {
            guard let a = story.arrivals?.first(where: { $0.settlement == s.id }) else { continue }
            stops.append((Stop(step: s.step, kind: .arrival(id: s.id, name: s.name, text: a.text)), 0))
        }
        for (i, e) in ordered.enumerated() { stops.append((Stop(step: e.step, kind: .event(e)), i + 1)) }
        let timeline = stops.sorted { ($0.0.step, $0.1) < ($1.0.step, $1.1) }.map(\.0)
        self.timeline = timeline
        let policy = story.choicePolicy
        self.choiceMode = ChoiceMode(rawValue: policy?.mode ?? "") ?? .notifyThenAuto
        self.choiceTimeoutSteps = max(1, policy?.timeoutSteps ?? 400)

        var loaded = store.load() ?? ChapterState()
        for item in story.items where loaded.items[item.id] == nil {
            loaded.items[item.id] = item.initial
        }
        if loaded.version < 2 {
            // Сохранение до «истории без игрока»: прошлые прибытия не пушим, старый лог журналом не показываем.
            let reached = ordered.filter { loaded.doneEvents.contains($0.id) }.map(\.step).max() ?? -1
            for stop in timeline where stop.step <= reached {
                if case .arrival = stop.kind { loaded.doneEvents.insert(stop.key) }
            }
            if loaded.journalSeenCount == nil { loaded.journalSeenCount = loaded.log.count }
            loaded.version = 2
        }
        self.state = loaded
    }

    func choiceBy(_ eventID: String) -> Chooser? {
        state.choiceBy?[eventID].flatMap(Chooser.init(rawValue:))
    }

    // MARK: - Чтение состояния

    func status(_ id: String) -> ItemStatus {
        state.items[id] ?? story.item(id)?.initial ?? .atPost
    }

    func isOpened(_ id: String) -> Bool { state.opened.contains(id) }

    /// Письма в сумке (занимают отделения), в порядке сюжета.
    var bagItems: [StoryConfig.Item] {
        story.items.filter { status($0.id) == .inBag && $0.takesSlot }
    }

    /// Что носится в сумке/кармане без отделения (бланк Веры, и т.п.).
    var pocketItems: [StoryConfig.Item] {
        story.items.filter {
            (status($0.id) == .inPocket) || (status($0.id) == .inBag && !$0.takesSlot)
        }
    }

    var freeSlots: Int { max(0, story.slots - bagItems.count) }

    var needsSorting: Bool { !state.sortingDone }

    /// Кандидаты утреннего разбора (письма на полке Почты).
    var sortCandidates: [StoryConfig.Item] {
        let ids = story.events.first { $0.type == .sort }?.candidates ?? []
        return ids.compactMap { story.item($0) }
    }

    var nextCard: StoryCard? { state.pendingCards.first }

    var isFinished: Bool { state.finished }

    /// Текущее задание (телеграмма).
    var questText: String? {
        if state.finished { return nil }
        return story.quests.first { !state.doneEvents.contains($0.event) && check($0.if) }?.telegram
    }

    func trust(_ settlement: String) -> Int { state.trust[settlement] ?? 0 }

    /// Записка к письму с учётом условий (вариант А.Л., если письмо Нины унёс ветер).
    func note(for item: StoryConfig.Item) -> String? {
        if let n = (item.notes ?? []).first(where: { check($0.if) }) { return resolve(n.text) }
        return item.note.map(resolve)
    }

    /// Спутник (Рамка) на этом шаге главы: id фигуры или nil.
    func companion(atStep step: Double) -> String? {
        for e in story.events {
            guard let c = e.companion, Double(c.from) <= step, step <= Double(c.to), check(c.if) else { continue }
            return c.id
        }
        return nil
    }

    /// Судьбы писем для итоговой карточки.
    var fates: [StoryConfig.Fate] { story.fates.filter { check($0.if) } }

    // MARK: - Условия

    /// "inBag:l3,!flag:ramka" — все атомы через запятую должны выполняться.
    func check(_ condition: String?) -> Bool {
        guard let condition, !condition.trimmingCharacters(in: .whitespaces).isEmpty else { return true }
        for raw in condition.split(separator: ",") {
            var atom = raw.trimmingCharacters(in: .whitespaces)
            var negate = false
            if atom.hasPrefix("!") { negate = true; atom.removeFirst() }
            let parts = atom.split(separator: ":", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { continue }
            let value = evaluate(kind: parts[0], id: parts[1])
            if value == negate { return false }
        }
        return true
    }

    private func evaluate(kind: String, id: String) -> Bool {
        let s = status(id)
        switch kind {
        case "inBag": return s == .inBag
        case "inPocket": return s == .inPocket
        case "delivered": return s == .delivered
        case "missed": return s != .delivered
        case "opened": return state.opened.contains(id)
        case "sealed": return s == .delivered && !state.opened.contains(id)
        case "sent": return s == .sent
        case "lost": return s == .lostWind
        case "atPost": return s == .atPost
        case "left": return s == .leftBehind
        case "flag": return state.flags.contains(id)
        case "carried": return state.carried.contains(id)
        // "choice:e_wind=chase" — в событии выбран этот вариант (игроком или почтальоном).
        case "choice":
            let p = id.split(separator: "=", maxSplits: 1).map(String.init)
            return p.count == 2 && state.choices[p[0]] == p[1]
        // "trust:kadushki" — доверие поселения > 0, "distrust:kadushki" — < 0.
        case "trust": return (state.trust[id] ?? 0) > 0
        case "distrust": return (state.trust[id] ?? 0) < 0
        default: return false
        }
    }

    // MARK: - Подстановки в тексты ({postmark}, {labelDate})

    func resolve(_ text: String) -> String {
        guard text.contains("{") else { return text }
        return text
            .replacingOccurrences(of: "{postmark}", with: Self.dateFormatter.string(from: postmarkDate))
            .replacingOccurrences(of: "{labelDate}", with: Self.dateFormatter.string(from: labelDate))
    }

    /// Подделки Агнии: штемпель = дата чтения + 2 дня (story-bible §1.3).
    private var postmarkDate: Date {
        let base = state.kseniaReadDate ?? Date()
        return Calendar.current.date(byAdding: .day, value: 2, to: base) ?? base
    }

    /// Этикетка в письме 7 = дата Тишины − ~20 дней; Тишина = начало игры − ~6 месяцев (предв.).
    private var labelDate: Date {
        let start = gameStartDate() ?? Date()
        let cal = Calendar.current
        let silence = cal.date(byAdding: .month, value: -6, to: start) ?? start
        return cal.date(byAdding: .day, value: -20, to: silence) ?? silence
    }

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ru_RU")
        f.dateFormat = "dd.MM.yy"
        return f
    }()

    // MARK: - Шаги

    func update(chapterSteps: Int) {
        currentStep = max(currentStep, chapterSteps)
        process()
    }

    private func isDone(_ stop: Stop) -> Bool { state.doneEvents.contains(stop.key) }

    /// Пора ли почтальону решить самому: следующая остановка уже наступила или прошло timeoutSteps.
    private func shouldAutoResolve(after index: Int, step: Int) -> Bool {
        switch choiceMode {
        case .wait: return false
        case .auto: return true
        case .notifyThenAuto:
            if currentStep >= step + choiceTimeoutSteps { return true }
            let next = timeline[(index + 1)...].first { !isDone($0) }
            return (next?.step ?? Int.max) <= currentStep
        }
    }

    private func process() {
        var changed = false
        // Старые сохранения: выбор, который стал сценой (гроза), не должен висеть карточкой с кнопками.
        let staleChoices = state.pendingCards.filter { $0.kind == .choice && story.event($0.id)?.type != .choice }
        if !staleChoices.isEmpty {
            state.pendingCards.removeAll { c in staleChoices.contains { $0.id == c.id } }
            changed = true
        }
        loop: for (index, stop) in timeline.enumerated() where !isDone(stop) {
            guard stop.step <= currentStep else { break }
            switch stop.kind {
            case .arrival(_, let name, let text):
                state.doneEvents.insert(stop.key)
                log(LogEntry(step: stop.step, text: text, kind: "arrival", place: name))
                beat(id: stop.key, title: name, body: text)
                changed = true
            case .event(let event):
                if event.type == .sort {
                    if !state.sortingDone {
                        guard shouldAutoResolve(after: index, step: event.step) else { break loop }
                        performSort(selected: story.sortDefault ?? event.candidates ?? [], by: .postman)
                    }
                    state.doneEvents.insert(event.id)
                    changed = true
                    continue loop
                }
                if event.type == .choice {
                    let place = settlementName(event.settlement)
                    if let req = event.requires, !check(req) {
                        // Условие не выполнено (например, ветру нечего уносить) — короткая сцена без выбора.
                        state.doneEvents.insert(event.id)
                        state.pendingCards.removeAll { $0.id == event.id }
                        if let fallback = event.fallback {
                            enqueue(StoryCard(id: event.id, kind: .scene, step: event.step, settlement: event.settlement,
                                              resident: nil, title: event.title, text: fallback,
                                              lines: [], items: [], missed: []))
                            log(LogEntry(step: event.step, text: fallback, kind: "scene", place: place, title: event.title))
                            beat(id: event.id, title: place, body: pushLine(event) ?? fallback)
                        }
                        changed = true
                        continue loop
                    }
                    if !state.pendingCards.contains(where: { $0.id == event.id }) {
                        enqueue(StoryCard(id: event.id, kind: .choice, step: event.step, settlement: event.settlement,
                                          resident: event.resident, title: event.title, text: event.text,
                                          lines: [], items: [], missed: []))
                        changed = true
                        if choiceMode != .auto {
                            beat(id: event.id, title: event.title ?? place,
                                 body: pushLine(event) ?? event.text ?? "", choiceEventID: event.id)
                        }
                    }
                    guard shouldAutoResolve(after: index, step: event.step),
                          let option = defaultOption(event) else { break loop }
                    applyChoice(event, option, by: .postman)
                    changed = true
                    continue loop
                }
                apply(event)
                changed = true
            }
        }
        if changed { commit() }
    }

    private func defaultOption(_ event: StoryConfig.Event) -> StoryConfig.Option? {
        let options = event.options ?? []
        return options.first { $0.id == event.default } ?? options.first
    }

    /// Первая строка пуша, чьё условие выполняется сейчас.
    private func pushLine(_ event: StoryConfig.Event) -> String? {
        (event.push ?? []).first { check($0.if) }.map { resolve($0.text) }
    }

    private func beat(id: String, title: String, body: String, choiceEventID: String? = nil) {
        guard !body.isEmpty else { return }
        onBeat?(Beat(id: id, title: title, body: body, choiceEventID: choiceEventID))
    }

    private func apply(_ event: StoryConfig.Event) {
        state.doneEvents.insert(event.id)
        let place = settlementName(event.settlement)
        switch event.type {
        case .deliver:
            var given: [String] = [], missed: [String] = []
            for id in event.items ?? [] {
                let s = status(id)
                if s == .inBag || s == .inPocket {
                    state.items[id] = .delivered
                    addTrust(event.settlement, 1)
                    given.append(id)
                } else {
                    // Нести было нечего (осталось на Почте / не влезло) — житель ждал зря.
                    addTrust(event.settlement, -1)
                    missed.append(id)
                }
            }
            let names = given.compactMap { story.item($0) }.map(describe)
            let text = names.isEmpty ? "Вручать было нечего." : "Вручено — \(names.joined(separator: ", "))."
            log(LogEntry(step: event.step, text: text, kind: "delivery", place: place,
                         title: story.resident(event.resident)?.name))
            enqueue(card(for: event, kind: .delivery, items: given, missed: missed))
            beat(id: event.id, title: place, body: pushLine(event) ?? "\(place). \(text)")

        case .pickup:
            guard let id = event.item, let item = story.item(id) else { break }
            var got: [String] = [], left: [String] = []
            if status(id) == .onRoad {
                if !item.takesSlot || freeSlots > 0 {
                    state.items[id] = .inBag
                    state.carried.insert(id)
                    got.append(id)
                    log(LogEntry(step: event.step, text: "Взято — \(describe(item)).", kind: "pickup", place: place))
                } else {
                    state.items[id] = .leftBehind
                    left.append(id)
                    log(LogEntry(step: event.step, text: "Сумка полна, \(describe(item)) осталось.", kind: "pickup", place: place))
                }
            }
            enqueue(card(for: event, kind: .pickup, items: got, missed: left))
            beat(id: event.id, title: place, body: pushLine(event) ?? "\(place). Конверт на палке у дороги.")

        case .scene:
            for flag in event.flags ?? [] { state.flags.insert(flag) }
            var said: String?
            if let first = (event.lines ?? []).first(where: { check($0.if) }) {
                said = first.who.isEmpty ? first.text : "\(first.who): «\(first.text)»"
                log(LogEntry(step: event.step, text: said ?? "", kind: "scene", place: place,
                             title: story.resident(event.resident)?.name))
            } else if let text = event.text {
                log(LogEntry(step: event.step, text: text, kind: "scene", place: place, title: event.title))
            }
            enqueue(card(for: event, kind: .scene, items: [], missed: []))
            beat(id: event.id, title: place, body: pushLine(event) ?? said.map { "\(place). \($0)" } ?? place)

        case .finale:
            var sent: [String] = []
            if let id = event.send {
                if status(id) == .inBag {
                    state.items[id] = .sent
                    sent.append(id)
                } else if status(id) == .atPost {
                    addTrust(story.item(id)?.senderSettlement ?? "", -1)
                }
            }
            if let id = event.receive {
                state.items[id] = .read
                state.kseniaReadDate = Date()
            }
            state.finished = true
            log(LogEntry(step: event.step, text: "Выемка. Письмо «Почтальону».", kind: "finale", place: place))
            enqueue(card(for: event, kind: .finale, items: sent, missed: []))
            beat(id: event.id, title: place, body: pushLine(event) ?? "\(place). В ящике письмо «Почтальону».")

        case .sort, .choice:
            break
        }
    }

    private func card(for event: StoryConfig.Event, kind: StoryCard.Kind, items: [String], missed: [String]) -> StoryCard {
        StoryCard(id: event.id, kind: kind, step: event.step, settlement: event.settlement,
                  resident: event.resident, title: event.title, text: event.text.map(resolve),
                  lines: (event.lines ?? []).filter { check($0.if) },
                  items: items, missed: missed)
    }

    private func describe(_ item: StoryConfig.Item) -> String {
        switch item.kind {
        case "parcel": return "батарейки (\(item.place))"
        case "form": return "бланк Веры"
        default: return "письмо \(item.to)"
        }
    }

    private func addTrust(_ settlement: String, _ delta: Int) {
        guard !settlement.isEmpty else { return }
        state.trust[settlement, default: 0] += delta
    }

    private func enqueue(_ card: StoryCard) {
        state.pendingCards.removeAll { $0.id == card.id }
        state.pendingCards.append(card)
    }

    private func log(_ entry: LogEntry) {
        var e = entry
        if e.date == nil { e.date = Date() }
        state.log.append(e)
        if liveViewing { state.journalSeenCount = state.log.count }
    }

    private func commit() {
        store.save(state)
    }

    // MARK: - Действия игрока

    /// Разбор на Почте (игрок): выбранное — в сумку, остальное остаётся на полке.
    func confirmSort(selected: [String]) {
        guard !state.sortingDone else { return }
        performSort(selected: selected, by: .player)
        commit()
        process()
    }

    private func performSort(selected: [String], by chooser: Chooser) {
        var room = story.slots
        for item in sortCandidates {
            if selected.contains(item.id) && room > 0 && item.takesSlot {
                state.items[item.id] = .inBag
                state.carried.insert(item.id)
                room -= 1
            } else if item.takesSlot {
                state.items[item.id] = .atPost
            }
        }
        state.sortingDone = true
        setChooser("sort", chooser)
        let taken = bagItems.map(describe)
        let text = taken.isEmpty ? "Сумка ушла пустой." : "В сумке — \(taken.joined(separator: ", "))."
        let place = settlementName("pochta")
        log(LogEntry(step: 0, text: text, kind: "sort", place: place, title: "Утренний разбор", by: chooser.rawValue))
        if chooser == .postman {
            beat(id: "sort", title: place, body: story.sortAuto ?? "Почтальон сам собрал сумку и вышел.")
        }
    }

    private func setChooser(_ id: String, _ chooser: Chooser) {
        var map = state.choiceBy ?? [:]
        map[id] = chooser.rawValue
        state.choiceBy = map
    }

    /// Тап всегда начинает с безопасного досье; доступный choice даёт свои обычные опции.
    /// Только ответ меняет сюжет. Повторный визит показывает тот же лор, не будущую реплику.
    @discardableResult
    func interactWithResident(_ residentID: String) -> StoryCard? {
        let resident = story.resident(residentID)
        // Рамка может быть только спутником из rig/parts: не добавляем стоящую фигуру в residents.
        guard resident != nil || orderedEvents.contains(where: { $0.companion?.id == residentID }) else { return nil }
        let lore = ResidentLore.entry(for: residentID, fallbackTitle: resident?.name ?? residentID)
        let events = orderedEvents.filter { $0.resident == residentID }
        let choices = events.filter { $0.type == .choice }
        for event in choices where state.doneEvents.contains(event.id) || !check(event.requires) {
            state.pendingCards.removeAll { $0.id == event.id && $0.kind == .choice }
        }
        let interaction: StoryCard
        if let event = choices.first(where: {
            !state.doneEvents.contains($0.id) && check($0.requires) && !($0.options ?? []).isEmpty
        }) {
            // Лор идёт первым на той же бумаге, ниже — исходная ситуация и опции события.
            let text = [lore.text, event.text.map(resolve)].compactMap { $0 }.joined(separator: "\n\n")
            interaction = StoryCard(id: event.id, kind: .choice, step: event.step,
                                    settlement: event.settlement, resident: residentID,
                                    title: lore.title, text: text,
                                    lines: (event.lines ?? []).filter { check($0.if) },
                                    items: [], missed: [])
        } else {
            interaction = StoryCard(id: "resident:" + residentID, kind: .scene, step: currentStep,
                                    settlement: events.first?.settlement ?? "", resident: residentID,
                                    title: lore.title, text: lore.text, lines: [], items: [], missed: [])
        }
        // Поднимаем уже ожидающий выбор, а не создаём второй. Остальная очередь остаётся на месте.
        state.pendingCards.removeAll { $0.id == interaction.id }
        state.pendingCards.insert(interaction, at: 0)
        commit()
        return interaction
    }

    /// Ответ на выбор (кнопка в карточке или в пуше). Возвращает текст результата;
    /// nil — выбор уже сделан (например, почтальон решил сам, пока игрок думал).
    @discardableResult
    func resolveChoice(_ eventID: String, option optionID: String, by chooser: Chooser = .player) -> String? {
        guard let event = story.event(eventID), event.type == .choice,
              !state.doneEvents.contains(eventID),
              (event.step <= currentStep || state.pendingCards.contains { $0.id == eventID && $0.kind == .choice }),
              let option = event.options?.first(where: { $0.id == optionID }) else { return nil }
        guard check(event.requires) else {
            state.pendingCards.removeAll { $0.id == eventID }
            commit()
            process()
            return nil
        }
        applyChoice(event, option, by: chooser)
        commit()
        process()
        return option.result
    }

    private func applyChoice(_ event: StoryConfig.Event, _ option: StoryConfig.Option, by chooser: Chooser) {
        for (settlement, delta) in option.trust ?? [:] { addTrust(settlement, delta) }
        for flag in option.flags ?? [] { state.flags.insert(flag) }
        for effect in option.effects ?? [] { state.items[effect.item] = effect.status }
        state.choices[event.id] = option.id
        setChooser(event.id, chooser)
        state.doneEvents.insert(event.id)
        state.pendingCards.removeAll { $0.id == event.id }
        let place = settlementName(event.settlement)
        log(LogEntry(step: event.step, text: option.result, kind: "choice", place: place,
                     title: event.title, by: chooser.rawValue))
        if chooser == .postman {
            // Игрок не ответил: показываем, как решил почтальон (карточка-сцена) и сообщаем пушем.
            let line = option.auto ?? "Почтальон решил сам: \(option.label.lowercased())."
            enqueue(StoryCard(id: event.id, kind: .scene, step: event.step, settlement: event.settlement,
                              resident: event.resident, title: event.title,
                              text: line + " " + option.result, lines: [], items: [], missed: []))
            beat(id: event.id + ".auto", title: event.title ?? place, body: line)
        }
    }

    func dismissCard(_ id: String) {
        guard let index = state.pendingCards.firstIndex(where: { $0.id == id }) else { return }
        // Выбор убирается только через resolveChoice.
        guard state.pendingCards[index].kind != .choice else { return }
        state.pendingCards.remove(at: index)
        commit()
    }

    /// Вскрыть секретное письмо (Пимен → Вера). Вера заметит второй отпечаток.
    func open(_ id: String) {
        guard let item = story.item(id), item.kind == "secret", !state.opened.contains(id),
              status(id) == .inBag else { return }
        state.opened.insert(id)
        addTrust(item.settlement, -1)
        log(LogEntry(step: currentStep, text: "Вскрыто: \(describe(item)). На печати — второй отпечаток.",
                     kind: "opened", by: Chooser.player.rawValue))
        commit()
    }

    func markEndCardSeen() {
        state.endCardSeen = true
        commit()
    }

    // MARK: - «Вот как развивалась история»

    struct Journal: Identifiable {
        let id = UUID()
        let fromStep: Int
        let toStep: Int
        let entries: [LogEntry]
        /// state.log.count на момент сборки: всё, что случится позже, попадёт в следующий журнал.
        let logEnd: Int
        var walked: Int { max(0, toStep - fromStep) }
    }

    /// Журнал событий с прошлого визита (nil — нового нет).
    func journal(chapterSteps: Int) -> Journal? {
        let seen = min(state.journalSeenCount ?? 0, state.log.count)
        guard state.log.count > seen else { return nil }
        let entries = state.log[seen...].enumerated()
            .sorted { ($0.element.step, $0.offset) < ($1.element.step, $1.offset) }
            .map(\.element)
        let from = state.lastSeenSteps ?? entries.first?.step ?? 0
        return Journal(fromStep: min(from, chapterSteps), toStep: chapterSteps, entries: entries,
                       logEnd: state.log.count)
    }

    /// Журнал прочитан: пассивные карточки (вручение, подбор, сцены) до его конца уже рассказаны
    /// в нём — убираем; открытый выбор и финал остаются.
    func markJournalSeen(_ journal: Journal) {
        state.journalSeenCount = max(state.journalSeenCount ?? 0, min(journal.logEnd, state.log.count))
        state.pendingCards.removeAll { $0.kind != .choice && $0.kind != .finale && $0.step <= journal.toStep }
        state.lastSeenSteps = journal.toStep
        commit()
    }

    func markSeen(_ chapterSteps: Int) {
        guard state.lastSeenSteps != chapterSteps else { return }
        state.lastSeenSteps = chapterSteps
        commit()
    }

    /// «Сбросить историю» (DEBUG-панель и скрытый жест в Release): письма, выборы, события, журнал — с нуля.
    /// Новое состояние сразу текущей версии, поэтому миграция старых сохранений его не трогает.
    func resetStory() {
        store.reset()
        var fresh = ChapterState()
        fresh.version = 2
        for item in story.items { fresh.items[item.id] = item.initial }
        state = fresh
        currentStep = 0
        liveViewing = false
        commit()
    }
}
