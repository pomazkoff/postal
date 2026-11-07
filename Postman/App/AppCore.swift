import Foundation
import UIKit
import Combine
import BackgroundTasks

/// Ядро, живущее без экрана: iOS может запустить приложение в фоне (HealthKit background delivery,
/// BGAppRefresh) без SwiftUI-сцены. Здесь — единственные экземпляры прогресса, шагов и движка сюжета
/// (GameModel берёт их отсюда, чтобы два движка не писали один файл состояния).
///
/// Фоновый цикл: новые шаги → StepService.refresh → engine.update → остановки → onBeat → локальный пуш.
@MainActor
final class AppCore {
    static let shared = AppCore()

    let progress: ProgressStore
    private(set) var world: WorldConfig
    let steps: StepService
    private(set) var engine: ChapterEngine
    /// Активная глава (0-based). Меняется по шагам или DEBUG forceChapterIndex.
    private(set) var chapterIndex: Int = 0
    /// Колбэк после смены сюжета главы (единая WorldScene остаётся прежней).
    var onChapterChanged: ((Int) -> Void)?
    /// Смена языка: тот же прогресс и та же сцена, другие строки.
    var onLocalizationChanged: (() -> Void)?
    let notifier = Notifier()

    /// Совпадает с BGTaskSchedulerPermittedIdentifiers в Postman/Info.plist: $(PRODUCT_BUNDLE_IDENTIFIER).refresh
    static var refreshTaskID: String { (Bundle.main.bundleIdentifier ?? "app.postman") + ".refresh" }

    private var cancellables = Set<AnyCancellable>()
    private var backgroundObservationStarted = false
    private var tasksRegistered = false
    /// Биты, которые пришли, пока игра была на экране: карточка уже видна, пуш не дублировали.
    /// При уходе в фон досылаем только неотвеченные выборы (кнопки на локскрине).
    private var deferredBeats: [String: ChapterEngine.Beat] = [:]
    private var postedBeatIDs = Set<String>()

    private init() {
        let progress = ProgressStore()
        self.progress = progress
        let world = WorldConfigLoader.load()
        self.world = world
        self.steps = StepService(store: progress)
        let startIndex = Self.resolveChapterIndex(world: world, progress: progress, totalSteps: 0)
        self.chapterIndex = startIndex
        let chapter = world.chapters[startIndex]
        ResidentLibrary.chapterAssetsFolder = chapter.assetsFolder
        self.engine = Self.makeEngine(world: world, chapterIndex: startIndex, progress: progress)

        bindEngineNotifications()
        notifier.registerCategories(for: engine.story)
        steps.$totalSteps
            .sink { [weak self] total in self?.syncEngine(total: total) }
            .store(in: &cancellables)
    }

    private var engineCancellables = Set<AnyCancellable>()

    private func bindEngineNotifications() {
        engineCancellables.removeAll()
        engine.onBeat = { [weak self] beat in self?.deliver(beat) }
        // Выбор сделан — убрать устаревший пуш с кнопками.
        engine.$state
            .map { Set($0.choices.keys) }
            .removeDuplicates()
            .sink { [weak self] ids in ids.forEach { self?.notifier.withdraw(id: $0) } }
            .store(in: &engineCancellables)
    }

    var chapter: ChapterConfig { world.chapters[chapterIndex] }

    func chapterSteps(total: Int) -> Int {
        if progress.forceChapterIndex == chapterIndex, let base = progress.forceChapterBaseSteps {
            return max(0, min(chapter.lengthSteps, total - base))
        }
        return max(0, min(chapter.lengthSteps, min(total, world.game.totalSteps) - chapter.startStep))
    }

    /// Индекс главы: DEBUG force → иначе последняя, чей startStep уже достигнут.
    static func resolveChapterIndex(world: WorldConfig, progress: ProgressStore, totalSteps: Int) -> Int {
        if let force = progress.forceChapterIndex {
            return max(0, min(world.chapters.count - 1, force))
        }
        let capped = min(max(0, totalSteps), world.game.totalSteps)
        var idx = 0
        for (i, c) in world.chapters.enumerated() where capped >= c.startStep {
            idx = i
        }
        return idx
    }

    private static func makeEngine(world: WorldConfig, chapterIndex: Int, progress: ProgressStore) -> ChapterEngine {
        let chapter = world.chapters[chapterIndex]
        let story = StoryConfig.load(chapter: chapter.id)
        return ChapterEngine(
            story: story,
            store: ChapterStateStore(fileName: "chapter\(chapter.id)_state.json"),
            settlements: chapter.settlements.map { (id: $0.id, name: $0.name, step: $0.step) },
            settlementName: { id in chapter.settlements.first { $0.id == id }?.name ?? id },
            gameStartDate: { progress.gameStartDate })
    }

    /// Перечитать мир и сюжет на выбранном языке. Файл сейва тот же: сделанные события
    /// не проигрываются заново, уже записанный журнал не переписывается.
    func reloadLocalization() {
        let step = engine.currentStep
        let live = engine.liveViewing
        world = WorldConfigLoader.load()
        engine = Self.makeEngine(world: world, chapterIndex: chapterIndex, progress: progress)
        engine.adoptStep(step)
        engine.liveViewing = live
        bindEngineNotifications()
        notifier.registerCategories(for: engine.story)
        onLocalizationChanged?()
    }

    /// Сменить главу (сюжет + state-файл). GameModel перебиндит сюжет, не заменяя сцену.
    func switchToChapter(_ index: Int) {
        let idx = max(0, min(world.chapters.count - 1, index))
        guard idx != chapterIndex else { return }
        chapterIndex = idx
        let chapter = world.chapters[idx]
        ResidentLibrary.chapterAssetsFolder = chapter.assetsFolder
        engine = Self.makeEngine(world: world, chapterIndex: idx, progress: progress)
        bindEngineNotifications()
        notifier.registerCategories(for: engine.story)
        postedBeatIDs.removeAll()
        deferredBeats.removeAll()
        onChapterChanged?(idx)
    }

    /// DEBUG: форс главы 2 (Горы) без ожидания 20к шагов.
    /// Отдельная база шага: форс не меняет HealthKit/debug total и не сжигает Долину.
    func debugForceChapter2() {
        progress.forceChapterIndex = 1
        progress.forceChapterBaseSteps = steps.totalSteps
        switchToChapter(1)
        syncEngine(total: steps.totalSteps)
    }

    func debugClearChapterForce() {
        progress.forceChapterIndex = nil
        progress.forceChapterBaseSteps = nil
        let idx = Self.resolveChapterIndex(world: world, progress: progress, totalSteps: steps.totalSteps)
        switchToChapter(idx)
        syncEngine(total: steps.totalSteps)
    }

    /// Догнать сюжет до текущих шагов (идемпотентно). При переходе через startStep гл.2 — смена главы.
    func syncEngine(total: Int) {
        guard steps.hasLoaded, progress.onboardingDone else { return }
        let idx = Self.resolveChapterIndex(world: world, progress: progress, totalSteps: total)
        if progress.forceChapterIndex == nil, idx > chapterIndex {
            // Догоняем каждую пройденную главу до конца; лента при этом не меняется.
            while chapterIndex < idx {
                engine.update(chapterSteps: chapter.lengthSteps)
                switchToChapter(chapterIndex + 1)
            }
        } else if idx != chapterIndex {
            switchToChapter(idx)
        }
        engine.update(chapterSteps: chapterSteps(total: total))
    }

    // MARK: Пуши

    private func deliver(_ beat: ChapterEngine.Beat) {
        // Приложение открыто — остановку видно карточкой; запомним выбор, чтобы дослать пуш в фоне.
        if UIApplication.shared.applicationState == .active {
            if beat.choiceEventID != nil {
                deferredBeats[beat.id] = beat
            }
            return
        }
        postBeat(beat)
    }

    private func postBeat(_ beat: ChapterEngine.Beat) {
        // Выключенные и ещё не разрешённые напоминания не помечают остановку отправленной:
        // включение не ставит её второй раз, а ещё не отправленный выбор уйдёт один раз.
        guard ReminderPreference.allowsPosting(known: notifier.knownAuth) else { return }
        guard !postedBeatIDs.contains(beat.id) else { return }
        postedBeatIDs.insert(beat.id)
        deferredBeats.removeValue(forKey: beat.id)
        notifier.post(title: beat.title, body: beat.body, id: beat.id, choiceEventID: beat.choiceEventID)
    }

    /// DEBUG: баннер прямо сейчас, даже если игра открыта.
    func postTestNotification() {
        notifier.postTest()
    }

    func clearNotificationState() {
        deferredBeats.removeAll()
        postedBeatIDs.removeAll()
        notifier.removeAll()
    }

    /// Кнопка в пуше выбора. Если почтальон уже решил сам — ответ игнорируется.
    func answerChoice(_ eventID: String, option: String) {
        engine.resolveChoice(eventID, option: option, by: .player)
    }

    // MARK: Фон

    /// Регистрировать до конца запуска (AppDelegate).
    func registerBackgroundTasks() {
        guard !tasksRegistered else { return }
        tasksRegistered = true
        BGTaskScheduler.shared.register(forTaskWithIdentifier: Self.refreshTaskID, using: .main) { @Sendable task in
            task.expirationHandler = { task.setTaskCompleted(success: false) }
            Task { @MainActor in
                let core = AppCore.shared
                core.scheduleRefresh()
                await core.backgroundRefresh()
                task.setTaskCompleted(success: true)
            }
        }
    }

    /// Запасной путь к HealthKit-доставке: iOS сама решает, когда запустить (обычно раз в 15–60+ мин).
    func scheduleRefresh() {
        guard progress.onboardingDone, !engine.state.finished else { return }
        let request = BGAppRefreshTaskRequest(identifier: Self.refreshTaskID)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 5 * 60)
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            #if DEBUG
            print("BGTaskScheduler: \(error.localizedDescription)")
            #endif
        }
    }

    /// HKObserverQuery + enableBackgroundDelivery(.immediate). Вызывать при каждом запуске после онбординга.
    func startBackgroundObservation() {
        guard progress.onboardingDone, !backgroundObservationStarted else { return }
        backgroundObservationStarted = true
        steps.startBackgroundDelivery { @Sendable completion in
            Task { @MainActor in
                await AppCore.shared.backgroundRefresh()
                completion()
            }
        }
    }

    /// Прочитать шаги и обработать все наступившие остановки (пуши ставятся из engine.onBeat).
    func backgroundRefresh() async {
        guard progress.onboardingDone else { return }
        await steps.refresh()
        syncEngine(total: steps.totalSteps)
    }

    func appDidEnterBackground() {
        scheduleRefresh()
        flushDeferredChoicePushes()
        // На случай, если шаги уже накопились, а HealthKit ещё не разбудил: догоняем сюжет.
        Task { await backgroundRefresh() }
    }

    /// Неотвеченные выборы, которые игрок видел в приложении и ушёл — пуш с кнопками на локскрин.
    private func flushDeferredChoicePushes() {
        for beat in deferredBeats.values where beat.choiceEventID != nil {
            if engine.state.choices[beat.id] == nil {
                postBeat(beat)
            }
        }
        deferredBeats.removeAll()
        for card in engine.state.pendingCards where card.kind == .choice {
            guard engine.state.choices[card.id] == nil, !postedBeatIDs.contains(card.id) else { continue }
            let place = chapter.settlements.first { $0.id == card.settlement }?.name ?? card.settlement
            let title = card.title ?? place
            let body = card.text ?? title
            postBeat(ChapterEngine.Beat(id: card.id, title: title, body: body, choiceEventID: card.id))
        }
    }
}
