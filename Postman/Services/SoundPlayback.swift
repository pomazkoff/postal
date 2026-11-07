import AVFoundation
import UIKit

/// Короткий пул плееров. Категория ambient: тумблер беззвучности и чужая музыка остаются,
/// фоновый audio entitlement не нужен и не включён. Нет файла — тишина, без ошибки игроку.
final class SoundPlayback: NSObject {
    static let shared = SoundPlayback()

    private var effects: [AVAudioPlayer] = []
    private var slot = 0
    private var bed: AVAudioPlayer?
    private var bedID: String?
    private var bedLoop = false
    private var stepCursor: [String: Int] = [:]
    private var lastFoot: TimeInterval = 0
    private var lastEffect: (String, TimeInterval) = ("", 0)
    private var toldStories: Set<String> = []
    private var valleyBirdsAt: TimeInterval = 0
    private var breezeAt: TimeInterval = CACurrentMediaTime()
    private var sessionReady = false

    private override init() {
        super.init()
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(interrupted),
                           name: AVAudioSession.interruptionNotification, object: nil)
        center.addObserver(self, selector: #selector(resigned),
                           name: UIApplication.willResignActiveNotification, object: nil)
    }

    func effect(_ id: String, scale: Float = 1) {
        guard AudioMix.rejectedClips.contains(id) == false else { return }
        guard SoundPrefs.effects.gain > 0, scale > 0 else { return }
        let now = CACurrentMediaTime()
        if lastEffect.0 == id, now - lastEffect.1 < 0.3 { return }
        guard let player = takeEffectPlayer(id) else { return }
        lastEffect = (id, now)
        player.volume = SoundPrefs.effects.gain * scale
        player.numberOfLoops = 0
        player.currentTime = 0
        player.play()
    }

    /// Один удар на кадр стопы. Повтор того же клипа подряд не берём, и не наслаиваем шаг на шаг.
    func footfall(worldStep: Double, appActive: Bool, heroVisible: Bool, worldAudible: Bool) {
        let gain = SoundPrefs.effects.gain
        guard AudioMix.allowsFootstep(appActive: appActive, heroVisible: heroVisible,
                                      worldAudible: worldAudible, effectsGain: gain) else { return }
        let now = CACurrentMediaTime()
        guard now - lastFoot >= 0.28 else { return }
        let surface = AudioMix.surface(worldStep: worldStep)
        guard let clips = AudioMix.footstepClips[surface], !clips.isEmpty else { return }
        var index = stepCursor[surface.rawValue] ?? 0
        let id = clips[index % clips.count]
        index += 1
        stepCursor[surface.rawValue] = index
        lastFoot = now
        guard let player = takeEffectPlayer(id) else { return }
        player.volume = gain * 0.8
        player.numberOfLoops = 0
        player.currentTime = 0
        player.play()
    }

    func story(eventID: String, kind: String, residentID: String?, live: Bool) {
        let cues = AudioMix.storyCues(eventID: eventID, kind: kind, residentID: residentID, live: live)
        guard !cues.isEmpty, toldStories.insert(eventID).inserted else { return }
        for id in cues {
            let scale: Float = (id == "bell" && eventID == "s_bell") ? 0.4 : 1
            effect(id, scale: scale)
        }
    }

    /// Новый сюжет может снова позвонить в колокол. Громкость настроек не трогает.
    func forgetStories() {
        toldStories.removeAll()
    }

    func flock(worldStep: Double, audible: Bool) {
        guard audible, SoundPrefs.ambience.gain > 0 else { return }
        let weather = WeatherService.shared.current.rawValue
        let chapter = AudioMix.chapterID(worldStep: worldStep)
        guard AudioMix.allowsValleyBirds(chapterID: chapter, weather: weather) else { return }
        let now = CACurrentMediaTime()
        guard now - valleyBirdsAt > 20 else { return }
        if bedID == "valley_wind", bed?.isPlaying == true { return }
        valleyBirdsAt = now
        startBed("valley_birds", loop: false)
    }

    func tick(worldStep: Double, audible: Bool) {
        guard audible, SoundPrefs.ambience.gain > 0 else {
            stopBed(fade: 0.5)
            return
        }
        let weather = WeatherService.shared.current.rawValue
        let chapter = AudioMix.chapterID(worldStep: worldStep)
        guard let plan = AudioMix.bed(chapterID: chapter, weather: weather) else {
            if bedID != "valley_birds" { stopBed(fade: 0.8) }
            return
        }
        if plan.loop {
            startBed(plan.id, loop: true)
            return
        }
        let now = CACurrentMediaTime()
        if bedID == plan.id, bed?.isPlaying == true { return }
        if bedID == "valley_birds", bed?.isPlaying == true { return }
        if now - breezeAt < 50 { return }
        breezeAt = now
        startBed(plan.id, loop: false)
    }

    func stopAll() {
        effects.forEach { $0.stop() }
        stopBed(fade: 0.2)
    }

    func applyLevels() {
        let amb = SoundPrefs.ambience.gain * 0.45
        if amb <= 0 {
            stopBed(fade: 0.3)
        } else {
            bed?.volume = amb
        }
        if SoundPrefs.effects.gain <= 0 {
            effects.forEach { $0.stop() }
        }
    }

    // MARK: - Плееры

    private func takeEffectPlayer(_ id: String) -> AVAudioPlayer? {
        guard prepareSession() else { return nil }
        guard let url = clipURL(id) else { return nil }
        if effects.count < 2 {
            guard let player = try? AVAudioPlayer(contentsOf: url) else { return nil }
            player.prepareToPlay()
            effects.append(player)
            return player
        }
        slot = (slot + 1) % effects.count
        let player = effects[slot]
        if player.url != url {
            guard let fresh = try? AVAudioPlayer(contentsOf: url) else { return nil }
            fresh.prepareToPlay()
            effects[slot] = fresh
            return fresh
        }
        return player
    }

    private func startBed(_ id: String, loop: Bool) {
        guard SoundPrefs.ambience.gain > 0 else { return }
        if bedID == id, bed?.isPlaying == true, bedLoop == loop { return }
        guard prepareSession(), let url = clipURL(id) else { return }
        guard let player = try? AVAudioPlayer(contentsOf: url) else { return }
        bed?.setVolume(0, fadeDuration: 0.4)
        let old = bed
        bed = player
        bedID = id
        bedLoop = loop
        player.numberOfLoops = loop ? -1 : 0
        player.volume = 0
        player.play()
        player.setVolume(SoundPrefs.ambience.gain * 0.45, fadeDuration: 0.8)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { old?.stop() }
    }

    private func stopBed(fade: TimeInterval) {
        guard let player = bed else { return }
        player.setVolume(0, fadeDuration: fade)
        bed = nil
        bedID = nil
        bedLoop = false
        DispatchQueue.main.asyncAfter(deadline: .now() + fade + 0.05) { player.stop() }
    }

    private func clipURL(_ id: String) -> URL? {
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent("Audio/\(id).wav")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    private func prepareSession() -> Bool {
        if sessionReady { return true }
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.ambient, mode: .default, options: [])
            try session.setActive(true)
            sessionReady = true
            return true
        } catch {
            return false
        }
    }

    @objc private func interrupted(_ note: Notification) {
        let type = (note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt)
            .flatMap(AVAudioSession.InterruptionType.init(rawValue:))
        if type == .began { stopAll() }
    }

    @objc private func resigned() {
        stopAll()
    }
}
