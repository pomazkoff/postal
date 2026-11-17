import Foundation

/// Уровни громкости. Тишина — ноль, и она сохраняется отдельно от сюжета.
enum SoundLevel: String, CaseIterable {
    case silent, quiet, mid, full

    var gain: Float {
        switch self {
        case .silent: return 0
        case .quiet: return 0.28
        case .mid: return 0.62
        case .full: return 1
        }
    }

    static func stored(_ key: String, fallback: SoundLevel) -> SoundLevel {
        guard let raw = UserDefaults.standard.string(forKey: key),
              let level = SoundLevel(rawValue: raw) else { return fallback }
        return level
    }

    static func store(_ level: SoundLevel, key: String) {
        UserDefaults.standard.set(level.rawValue, forKey: key)
    }
}

enum SoundPrefs {
    static let effectsKey = "postman.sound.effects"
    static let ambienceKey = "postman.sound.ambience"

    static var effects: SoundLevel {
        get { SoundLevel.stored(effectsKey, fallback: .mid) }
        set { SoundLevel.store(newValue, key: effectsKey) }
    }

    static var ambience: SoundLevel {
        get { SoundLevel.stored(ambienceKey, fallback: .quiet) }
        set { SoundLevel.store(newValue, key: ambienceKey) }
    }
}

/// Покрытие дороги и ворота звука. Без AVFoundation, чтобы правила можно было сверить.
enum AudioMix {
    enum Surface: String { case earth, grass, stone, wood }

    /// Одноударные нарезки, у которых огибающая даёт один удар и край не обрезан.
    /// earth_2, grass_2, stone_4 и wood_2 в набор не входят: у них второй пик.
    static let footstepClips: [Surface: [String]] = [
        .earth: ["steps_earth_one_shot_1", "steps_earth_one_shot_3", "steps_earth_one_shot_4"],
        .grass: ["steps_grass_one_shot_1", "steps_grass_one_shot_3", "steps_grass_one_shot_4"],
        .stone: ["steps_stone_one_shot_1", "steps_stone_one_shot_2", "steps_stone_one_shot_3"],
        .wood: ["steps_wood_one_shot_1", "steps_wood_one_shot_3", "steps_wood_one_shot_4"],
    ]

    /// Родители с четырьмя шагами подряд и кривые нарезки. Их проигрывать нельзя.
    static let rejectedClips: Set<String> = [
        "steps_earth", "steps_grass", "steps_stone", "steps_wood",
        "steps_earth_one_shot_2", "steps_grass_one_shot_2",
        "steps_stone_one_shot_4", "steps_wood_one_shot_2",
    ]

    /// Кадры цикла ходьбы (8 кадров, 12 fps), на которых стопа ставится.
    static let footfallFrames: Set<Int> = [0, 4]

    /// Доски только у Свай: «под ногами доски» и мостки, где стоят петух и Кузьма.
    /// Это не отдельная плитка дороги, а короткий участок вокруг шага 2500.
    static func surface(worldStep: Double) -> Surface {
        let s = worldStep
        if s >= 2300 && s < 3100 { return .wood }
        if s >= 5600 && s < 8700 { return .grass }
        if (s >= 8700 && s < 20000) || (s >= 24000 && s < 34000) || (s >= 38000 && s < 42000) {
            return .stone
        }
        return .earth
    }

    static func chapterID(worldStep: Double) -> Int {
        worldStep < 20000 ? 1 : 2
    }

    /// Шаг звучит только вместе с видимой ходьбой, не от каждого шага HealthKit и не в фоне.
    static func allowsFootstep(appActive: Bool, heroVisible: Bool, worldAudible: Bool,
                               effectsGain: Float) -> Bool {
        appActive && heroVisible && worldAudible && effectsGain > 0
    }

    /// Постоянный слой только у дождя и снега. Ясно в горах — редкий проход ветра, не петля.
    /// Туман без файла: тишина. Долина в ясную погоду молчит, пока не пролетит стая.
    static func bed(chapterID: Int, weather: String) -> (id: String, loop: Bool)? {
        switch weather {
        case "rain": return ("rain", true)
        case "snow": return ("snow_wind", true)
        case "fog": return nil
        case "clear":
            // Один проход и пауза. Долина — мягкий луг, горы — воздух у камней.
            return (chapterID == 2 ? "mountain_wind" : "valley_wind", false)
        default: return nil
        }
    }

    /// Стая в долине при ясной погоде. В дождь, снег, туман и в горах этот файл не играет.
    static func allowsValleyBirds(chapterID: Int, weather: String) -> Bool {
        chapterID == 1 && weather == "clear"
    }

    /// Животные, которые стоят на дороге или идут рядом. Чужих видов нет.
    /// Взрослые козы Рамка и Матрёна делят один звук: это один вид.
    static func animalCue(_ residentID: String) -> String? {
        switch residentID {
        case "rooster": return "animal_rooster"
        case "cat_barrel": return "animal_cat"
        case "goat_kid": return "animal_goat_kid"
        case "ramka", "matrena": return "animal_goat"
        case "raven_saddle": return "animal_raven"
        case "dog_penki": return "animal_dog"
        default: return nil
        }
    }

    /// Два варианта на каждый cue. Курсор снаружи чередует их, как шаги.
    static let animalClips: [String: [String]] = [
        "animal_rooster": ["animal_rooster_1", "animal_rooster_2"],
        "animal_cat": ["animal_cat_1", "animal_cat_2"],
        "animal_goat_kid": ["animal_goat_kid_1", "animal_goat_kid_2"],
        "animal_goat": ["animal_goat_1", "animal_goat_2"],
        "animal_raven": ["animal_raven_1", "animal_raven_2"],
        "animal_dog": ["animal_dog_1", "animal_dog_2"],
    ]

    static func nextAnimalClip(cue: String, cursor: Int) -> (id: String, next: Int)? {
        guard let clips = animalClips[cue], !clips.isEmpty else { return nil }
        let index = cursor % clips.count
        return (clips[index], cursor + 1)
    }

    /// Только видимый тап. Прогресс, журнал и фон сюда не входят.
    static func allowsAnimalTap(appActive: Bool, worldVisible: Bool, effectsGain: Float) -> Bool {
        appActive && worldVisible && effectsGain > 0
    }

    /// Звук карточки, только когда игрок смотрит сейчас. Журнал догона сюда не попадает.
    /// Звери сюда не входят: их голос только от тапа по фигуре.
    static func storyCues(eventID: String, kind: String, residentID: String?, live: Bool) -> [String] {
        guard live else { return [] }
        // residentID не выбирает клип: человек молчит, зверь звучит только от тапа по фигуре.
        _ = residentID
        if eventID == "s_bell" || eventID == "d_l2" { return ["bell"] }
        switch kind {
        case "delivery", "finale": return ["mail_handover"]
        case "pickup": return ["mail_bag"]
        default: return []
        }
    }
}
