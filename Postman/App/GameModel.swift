import Foundation
import Combine
import SpriteKit
import UIKit

/// Связывает шаги, сохранённый прогресс, данные мира и сцену.
@MainActor
final class GameModel: ObservableObject {
    private(set) var world: WorldConfig
    let rig: RigConfig
    let progress: ProgressStore
    let steps: StepService
    private(set) var engine: ChapterEngine

    /// Журнал «Вот как развивалась история» — при открытии приложения, если без игрока что-то случилось.
    @Published var journal: ChapterEngine.Journal?
    /// Проверить журнал при первом чтении шагов после запуска/возврата из фона.
    private var pendingReturnCheck = true

    @Published var onboardingDone: Bool
    /// Почтальон за краем экрана (камеру увели панорамой) — показать кнопку «к почтальону».
    @Published private(set) var postmanOffscreen: WorldScene.Offscreen?
    /// Карточка почтальона по тапу в мире. Не сейв.
    @Published var showHeroCard = false
    /// Меню открыто: мир и HUD под ним размыты, бумага меню остаётся резкой.
    @Published var roadMenuOpen = false
    /// Где остановилась прокрутка «Истории». Не сейв: живёт, пока открыта игра.
    @Published var historyAnchor: String?
    /// Поверх мира лист, меню или карточка: шаги и окружение замолкают.
    @Published var worldCovered = false
    /// Карточка «Первый почтовый рейс». Не сейв и не сдвиг сюжета.
    @Published var firstMailPending = false
    @Published private(set) var chapterIndex = 0

    /// Визит к жителю не переключает главу/шаги. Для пройденной главы берём её собственное сохранение.
    struct ResidentVisit {
        let chapter: ChapterConfig
        let engine: ChapterEngine
        let cardID: String
    }
    @Published private(set) var residentVisit: ResidentVisit?
    private var residentVisitCancellable: AnyCancellable?
    /// Отменяет отложенную карточку при новом тапе, сбросе или смене главы.
    private var residentVisitRequestID: UUID?

    private var _sceneStorage: WorldScene?
    var scene: WorldScene {
        if let s = _sceneStorage { return s }
        let s = makeScene()
        _sceneStorage = s
        return s
    }
    private var cancellables = Set<AnyCancellable>()

    init() {
        let core = AppCore.shared
        self.progress = core.progress
        self.world = core.world
        self.rig = RigConfig.load()
        self.steps = core.steps
        self.onboardingDone = core.progress.onboardingDone
        self.engine = core.engine
        self.chapterIndex = core.chapterIndex

        // Пробрасываем изменения StepService наружу (SwiftUI видит один объект) и в сцену.
        steps.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
        bindEngine(core.engine)
        steps.$totalSteps
            .sink { [weak self] total in self?.applyTotal(total) }
            .store(in: &cancellables)
        core.onChapterChanged = { [weak self] idx in
            self?.handleChapterChanged(idx)
        }
        core.onLocalizationChanged = { [weak self] in
            self?.handleLocalizationChanged()
        }

        if onboardingDone { steps.start() }
        pullFirstMailInbox()
    }

    private var engineCancellables = Set<AnyCancellable>()

    private func bindEngine(_ engine: ChapterEngine) {
        engineCancellables.removeAll()
        engine.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &engineCancellables)
        let chapterID = chapter.id
        engine.$state
            .map { state in Set(state.items.filter { $0.value == .leftBehind }.keys) }
            .removeDuplicates()
            .sink { [weak self] left in self?.scene.setRoadItemLeftBehind(left, chapterID: chapterID) }
            .store(in: &engineCancellables)
    }

    /// Строки мира и сюжета заново. Сейв, шаги и сцена на месте; таблички только переписываются.
    private func handleLocalizationChanged() {
        world = AppCore.shared.world
        engine = AppCore.shared.engine
        bindEngine(engine)
        ResidentLore.invalidate()
        ParchmentMap.invalidate()
        PluralCatalog.invalidate()
        if _sceneStorage != nil {
            scene.retitleSettlements(world)
        }
        objectWillChange.send()
    }

    func setLanguage(_ choice: LanguageChoice) {
        guard choice != AppLanguage.choice else { return }
        AppLanguage.choice = choice
        AppCore.shared.reloadLocalization()
    }

    /// Уже рассказанное. Чтение чужих глав с диска ничего не записывает.
    func historyFacts() -> [HistoryFact] {
        let known = StoryChronicle.Progress(
            done: engine.state.doneEvents, choices: engine.state.choices,
            items: engine.state.items, opened: engine.state.opened,
            carried: engine.state.carried, reached: chapterSteps)
        return StoryChronicle.facts(world: world, activeIndex: chapterIndex, activeSteps: chapterSteps,
                                    active: known) { chapterID in
            guard let saved = ChapterStateStore(fileName: "chapter\(chapterID)_state.json").load() else { return nil }
            return StoryChronicle.Progress(done: saved.doneEvents, choices: saved.choices,
                                           items: saved.items, opened: saved.opened,
                                           carried: saved.carried, reached: Int.max)
        }
    }

    /// Кого показать в меню. Чужие главы читаются с диска и не создают сейв.
    func menuPeople() -> [MenuPerson] {
        var people: [MenuPerson] = []
        var seen = Set<String>()
        for (index, chapter) in world.chapters.enumerated() {
            let story = index == chapterIndex ? engine.story : StoryConfig.load(chapter: chapter.id)
            let done: Set<String>
            if index == chapterIndex {
                done = engine.state.doneEvents
            } else {
                done = ChapterStateStore(fileName: "chapter\(chapter.id)_state.json").load()?.doneEvents ?? []
            }
            let reached = MetPeople.reached(index: index, active: chapterIndex,
                                            activeSteps: chapterSteps, length: chapter.lengthSteps)
            let events = story.events.map {
                MetPeople.EventRef(id: $0.id, resident: $0.resident, companion: $0.companion?.id)
            }
            let residents = story.residents.map { (id: $0.id, step: $0.step) }
            for id in MetPeople.ids(events: events, done: done, residents: residents, reached: reached) {
                guard seen.insert(id).inserted else { continue }
                let resident = story.residents.first { $0.id == id }
                let lore = ResidentLore.entry(for: id, fallbackTitle: resident?.name ?? "")
                let name = resident?.name ?? lore.title
                guard !name.isEmpty else { continue }
                let figureResident = resident ?? StoryConfig.Resident(
                    id: id, name: name, aliases: [], step: 0, dx: 0, height: 200)
                let image = ResidentLibrary.figure(for: figureResident, assetsFolder: chapter.assetsFolder)?.image
                people.append(MenuPerson(id: id, name: name, text: lore.text, image: image))
            }
        }
        return people
    }

    /// Сюжет меняется, но единая сцена, камера и жители предыдущих глав остаются на месте.
    private func handleChapterChanged(_ idx: Int) {
        endResidentVisit()
        chapterIndex = idx
        engine = AppCore.shared.engine
        bindEngine(engine)
        journal = nil
        pendingReturnCheck = true
        // Не пересоздаём WorldScene: её displayedStep и камера уже в глобальных координатах.
        objectWillChange.send()
    }

    // MARK: Derived state

    var chapter: ChapterConfig { world.chapters[chapterIndex] }

    /// Всего шагов в игре с учётом лимита 150 000.
    var gameSteps: Int { min(steps.totalSteps, world.game.totalSteps) }

    /// Пройдено в рамках текущей главы.
    var chapterSteps: Int { chapterSteps(total: steps.totalSteps) }

    private func chapterSteps(total: Int) -> Int {
        if progress.forceChapterIndex == chapterIndex, let base = progress.forceChapterBaseSteps {
            return max(0, min(chapter.lengthSteps, total - base))
        }
        return max(0, min(chapter.lengthSteps, min(total, world.game.totalSteps) - chapter.startStep))
    }

    /// Форс сдвигает лишь виртуальную позицию на ленте, а не реальный счётчик шагов.
    private func worldSteps(total: Int) -> Int {
        if progress.forceChapterIndex == chapterIndex {
            return chapter.startStep + chapterSteps(total: total)
        }
        return max(0, min(total, world.game.totalSteps))
    }

    /// DEBUG-панель: total при форсе не публикуется заново, поэтому явно синхронизируем сцену.
    func refreshChapterProgress() {
        AppCore.shared.syncEngine(total: steps.totalSteps)
        scene.jumpToSteps(worldSteps(total: steps.totalSteps))
        objectWillChange.send()
    }

    var nextSettlement: Settlement? {
        chapter.settlements.first { $0.step > chapterSteps }
    }

    var stepsToNextSettlement: Int? {
        nextSettlement.map { $0.step - chapterSteps }
    }

    var currentQuest: QuestConfig? {
        chapter.quests.first { chapterSteps < $0.untilStep } ?? chapter.quests.last
    }

    // MARK: Actions

    func completeOnboarding() async {
        await steps.requestAuthorization()
        // Явная финальная кнопка онбординга. Повторно со старта и при возврате в игру не спрашиваем:
        // там только чтение статуса. Если iOS ещё не спрашивали, включение в меню спросит само.
        _ = await AppCore.shared.notifier.requestAuthorization()
        if progress.gameStartDate == nil { progress.gameStartDate = Date() }
        progress.onboardingDone = true
        onboardingDone = true
        steps.start()
        AppCore.shared.startBackgroundObservation()
        // Геопозиция для погоды — после онбординга, отдельным вопросом (грубая точность).
        WeatherService.shared.start(askPermission: true)
    }

    func appBecameActive() {
        guard onboardingDone else { return }
        pendingReturnCheck = true
        engine.liveViewing = false
        steps.start()
        WeatherService.shared.start(askPermission: true)
        Task { await AppCore.shared.notifier.refreshAuthorizationStatus() }
    }

    func appWentToBackground() {
        residentVisitRequestID = nil
        progress.displayedSteps = scene.displayedStep
        engine.liveViewing = false
        SoundPlayback.shared.stopAll()
        if steps.hasLoaded && journal == nil { engine.markSeen(chapterSteps) }
        // Таймер экрана гаснет. Фоновый наблюдатель HealthKit этим не снимается.
        steps.stop()
        AppCore.shared.appDidEnterBackground()
    }

    /// Верный адрес только поднимает карточку. Шаги, сумка, камера и диалоги не трогаются.
    func receiveFirstMail(_ url: URL) {
        guard FirstMailLink.route(from: url) else { return }
        firstMailPending = true
    }

    func pullFirstMailInbox() {
        guard FirstMailInbox.pending else { return }
        FirstMailInbox.pending = false
        firstMailPending = true
    }

    func dismissFirstMail() {
        firstMailPending = false
    }

    /// Чтение l1. Активная глава 1 — её движок. Иначе файл главы 1, без записи.
    func firstMailReading() -> FirstMailReading {
        if chapter.id == 1 {
            return FirstMailReading.classify(status: engine.status("l1"),
                                             deliveryDone: engine.state.doneEvents.contains("d_l1"))
        }
        guard let saved = ChapterStateStore(fileName: "chapter1_state.json").load() else {
            return .unreachable
        }
        let status = saved.items["l1"] ?? .atPost
        return FirstMailReading.classify(status: status,
                                         deliveryDone: saved.doneEvents.contains("d_l1"))
    }

    /// Кнопка «к почтальону»: камера плавно возвращается и снова следит за героем.
    func returnToPostman() {
        scene.returnToPostman(animated: true)
    }

    private func visitResident(chapterID: Int, residentID: String) {
        guard onboardingDone, let chapter = world.chapters.first(where: { $0.id == chapterID }) else { return }
        SoundPlayback.shared.animalTap(
            residentID: residentID,
            appActive: UIApplication.shared.applicationState == .active,
            worldVisible: !worldCovered && !roadMenuOpen && journal == nil && residentVisit == nil
        )
        endResidentVisit()
        let requestID = UUID()
        residentVisitRequestID = requestID
        let reactionDuration = scene.playResidentReact(chapterID: chapterID, id: residentID)
        // До окончания реакции не вставляем карточку даже в очередь активного engine:
        // HUD иначе покажет её сразу и полностью закроет прыжок.
        DispatchQueue.main.asyncAfter(deadline: .now() + reactionDuration) { [weak self] in
            guard let self, self.onboardingDone, self.residentVisitRequestID == requestID else { return }
            self.residentVisitRequestID = nil
            let visitEngine: ChapterEngine
            if chapterID == self.chapter.id {
                visitEngine = self.engine // Никогда не создаём второго писателя активного state-файла.
            } else {
                visitEngine = ChapterEngine(story: StoryConfig.load(chapter: chapterID),
                    store: ChapterStateStore(fileName: "chapter\(chapterID)_state.json"),
                    settlementName: { id in chapter.settlements.first { $0.id == id }?.name ?? id },
                    gameStartDate: { [weak self] in self?.progress.gameStartDate })
                visitEngine.liveViewing = true
            }
            guard let card = visitEngine.interactWithResident(residentID) else { return }
            self.residentVisitCancellable = visitEngine.objectWillChange
                .sink { [weak self] _ in self?.objectWillChange.send() }
            self.residentVisit = ResidentVisit(chapter: chapter, engine: visitEngine, cardID: card.id)
        }
    }

    func endResidentVisit() {
        residentVisitRequestID = nil
        residentVisit = nil
        residentVisitCancellable = nil
    }

    /// Игрок закрыл журнал: дальше — мир, камера у почтальона.
    func dismissJournal() {
        if let j = journal { engine.markJournalSeen(j) }
        journal = nil
        engine.liveViewing = true
        scene.returnToPostman(animated: false)
    }

    /// «Сбросить историю» (для тестов; DEBUG-панель и скрытый жест — долгое нажатие 3 с на часах
    /// или на табличке карты, работает и в Release/TestFlight). Состояние главы, старт (= сейчас,
    /// шаги с этой минуты), камера, пуши, онбординг — всё заново.
    func resetStory() {
        steps.stop()
        progress.resetStory() // очищает и индекс форса, и базу
        steps.resetForNewStart()
        // Новый старт — для ВСЕХ глав, иначе возврат из Гор поднимет старый сюжет Долины.
        for chapter in world.chapters {
            ChapterStateStore(fileName: "chapter\(chapter.id)_state.json").reset()
        }
        let core = AppCore.shared
        core.clearNotificationState()
        core.switchToChapter(0) // syncEngine до hasLoaded не переключает главу — делаем явно.
        engine.resetStory()
        journal = nil
        showHeroCard = false
        endResidentVisit()
        pendingReturnCheck = true
        onboardingDone = false
        SoundPlayback.shared.forgetStories()
        installWorldStory(in: scene)
        scene.resetForNewStory()
    }

    // MARK: Private

    /// Шаги и погода звучат, когда виден мир, а не журнал, меню или карточка.
    private var worldIsAudible: Bool {
        onboardingDone && !worldCovered && !roadMenuOpen && journal == nil && residentVisit == nil
    }

    private func makeScene() -> WorldScene {
        let initial = progress.forceChapterIndex != nil
            ? Double(worldSteps(total: steps.totalSteps)) : progress.displayedSteps
        let scene = WorldScene(config: world, rig: rig, initialStep: initial)
        scene.onPostmanOffscreenChange = { [weak self] off in
            DispatchQueue.main.async { self?.postmanOffscreen = off }
        }
        scene.onResidentTap = { [weak self] chapterID, residentID in
            DispatchQueue.main.async { self?.visitResident(chapterID: chapterID, residentID: residentID) }
        }
        scene.onPostmanTap = { [weak self] in
            DispatchQueue.main.async { self?.showHeroCard = true }
        }
        scene.onFootfall = { [weak self] step in
            guard let self else { return }
            SoundPlayback.shared.footfall(worldStep: step,
                                          appActive: UIApplication.shared.applicationState == .active,
                                          heroVisible: true,
                                          worldAudible: self.worldIsAudible)
        }
        scene.onFlock = { [weak self] in
            guard let self else { return }
            SoundPlayback.shared.flock(worldStep: self.scene.displayedStep, audible: self.worldIsAudible)
        }
        scene.onAmbienceTick = { [weak self] step in
            guard let self else { return }
            SoundPlayback.shared.tick(worldStep: step, audible: self.worldIsAudible)
        }
        installWorldStory(in: scene)
        installCompanions(in: scene)
        return scene
    }

    /// Сюжетные фигуры всех глав стоят на одном world strip, включая уже пройденные главы.
    private func installWorldStory(in scene: WorldScene) {
        for chapter in world.chapters {
            let story = chapter.id == self.chapter.id ? engine.story : StoryConfig.load(chapter: chapter.id)
            let state: ChapterState? = chapter.id == self.chapter.id ? engine.state
                : ChapterStateStore(fileName: "chapter\(chapter.id)_state.json").load()
            let left = Set((state?.items ?? [:]).filter { $0.value == .leftBehind }.keys)
            installStory(in: scene, chapter: chapter, story: story, leftBehind: left)
        }
    }

    private func installStory(in scene: WorldScene, chapter: ChapterConfig, story: StoryConfig,
                              leftBehind: Set<String>) {
        var road: [WorldScene.RoadItemSpec] = []
        for event in story.events where event.type == .pickup {
            guard let id = event.item, let item = story.item(id), let image = item.road else { continue }
            let entry = UIArt.entry(image)
            let foot = entry.anchor("foot")
            road.append(.init(id: id, step: chapter.startStep + event.step, image: entry.image, foot: foot,
                              leftBehind: leftBehind.contains(id)))
        }
        var residents: [WorldScene.ResidentSpec] = []
        for r in story.residents where r.step <= chapter.lengthSteps {
            guard let fig = ResidentLibrary.figure(for: r, assetsFolder: chapter.assetsFolder) else { continue }
            residents.append(.init(id: r.id, step: chapter.startStep + r.step, dx: CGFloat(r.dx), height: CGFloat(r.height),
                                   image: fig.image, groundFraction: fig.groundFraction, idle: fig.idle))
        }
        scene.installStory(roadItems: road, residents: residents, chapterID: chapter.id)
    }

    /// Спутники из событий (поле companion): фигура из Chapter1/residents/<id>, шаги — от начала главы.
    private func installCompanions(in scene: WorldScene) {
        for chapter in world.chapters {
            let story = StoryConfig.load(chapter: chapter.id)
            for event in story.events {
                guard let c = event.companion else { continue }
                let resident = StoryConfig.Resident(id: c.id, name: c.id, aliases: [], step: c.from, dx: 0, height: 200)
                guard let figure = ResidentLibrary.figure(for: resident, assetsFolder: chapter.assetsFolder) else { continue }
                scene.registerCompanion(id: "\(chapter.id)/\(c.id)", image: figure.image,
                                        groundFraction: figure.groundFraction, height: 200)
            }
        }
        scene.companionProvider = { [weak self] worldStep in
            guard let self, self.onboardingDone,
                  worldStep >= Double(self.chapter.startStep),
                  worldStep <= Double(self.chapter.endStep),
                  let id = self.engine.companion(atStep: worldStep - Double(self.chapter.startStep)) else { return nil }
            return "\(self.chapter.id)/\(id)"
        }
    }

    private func applyTotal(_ total: Int) {
        // До первого чтения шагов totalSteps = 0 — не сбрасываем сохранённую позицию героя.
        guard steps.hasLoaded else { return }
        guard onboardingDone else {
            scene.setTargetSteps(worldSteps(total: total))
            return
        }
        AppCore.shared.syncEngine(total: total)
        // После sync глава могла смениться — берём актуальные шаги главы.
        chapterIndex = AppCore.shared.chapterIndex
        let inChapter = chapterSteps(total: total)
        scene.setTargetSteps(worldSteps(total: total))
        if pendingReturnCheck {
            pendingReturnCheck = false
            if journal == nil {
                journal = engine.journal(chapterSteps: inChapter)
            }
            if journal == nil { engine.liveViewing = true }
        }
    }
}
