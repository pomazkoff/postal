import Foundation
import CoreLocation

/// Погода в мире игры: ясно / дождь / снег / туман.
enum Weather: String, CaseIterable {
    case clear, rain, snow, fog

    var title: String {
        switch self {
        case .clear: return "ясно"
        case .rain: return "дождь"
        case .snow: return "снег"
        case .fog: return "туман"
        }
    }

    /// WMO weather code (Open-Meteo) → одно из четырёх состояний.
    init(wmo code: Int) {
        switch code {
        case 45, 48: self = .fog
        case 51...67, 80...82, 95...99: self = .rain
        case 71...77, 85, 86: self = .snow
        default: self = .clear
        }
    }
}

/// Реальная погода у игрока (Open-Meteo, без ключа) по грубой геопозиции.
/// Кэш ~1 ч в UserDefaults. Нет разрешения/сети — сезонная псевдослучайная погода на день.
final class WeatherService: NSObject, CLLocationManagerDelegate {
    static let shared = WeatherService()

    /// DEBUG: ручная погода (nil — авто).
    static var debugOverride: Weather?

    private let defaults = UserDefaults.standard
    private var manager: CLLocationManager?
    private var fetching = false

    private enum Key {
        static let code = "postman.weather.code"
        static let date = "postman.weather.date"
    }
    private static let cacheLifetime: TimeInterval = 3600

    /// Погода, которую показывает сцена (с учётом DEBUG-оверрайда).
    var current: Weather {
        if let o = Self.debugOverride { return o }
        if let real = cachedReal { return real }
        return Self.seasonal(for: Date())
    }

    /// Источник для отладки: «сеть», «сезон».
    var sourceTitle: String { cachedReal != nil ? "Open-Meteo" : "по сезону" }

    private var cachedReal: Weather? {
        guard let d = defaults.object(forKey: Key.date) as? Date,
              Date().timeIntervalSince(d) < Self.cacheLifetime * 3,
              defaults.object(forKey: Key.code) != nil else { return nil }
        return Weather(wmo: defaults.integer(forKey: Key.code))
    }

    private var cacheFresh: Bool {
        guard let d = defaults.object(forKey: Key.date) as? Date else { return false }
        return Date().timeIntervalSince(d) < Self.cacheLifetime
    }

    /// Спросить разрешение (после онбординга) и обновить погоду, если кэш устарел.
    func start(askPermission: Bool) {
        DispatchQueue.main.async { self.startOnMain(askPermission: askPermission) }
    }

    private func startOnMain(askPermission: Bool) {
        let m = manager ?? CLLocationManager()
        if manager == nil {
            m.delegate = self
            m.desiredAccuracy = kCLLocationAccuracyReduced
            manager = m
        }
        switch m.authorizationStatus {
        case .notDetermined:
            if askPermission { m.requestWhenInUseAuthorization() }
        case .authorizedWhenInUse, .authorizedAlways:
            if !cacheFresh && !fetching { m.requestLocation() }
        default:
            break
        }
    }

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            if !cacheFresh && !fetching { manager.requestLocation() }
        default:
            break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        fetch(lat: loc.coordinate.latitude, lon: loc.coordinate.longitude)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: Open-Meteo

    private func fetch(lat: Double, lon: Double) {
        guard !fetching else { return }
        let s = String(format: "https://api.open-meteo.com/v1/forecast?latitude=%.2f&longitude=%.2f&current=weather_code", lat, lon)
        guard let url = URL(string: s) else { return }
        fetching = true
        var req = URLRequest(url: url)
        req.timeoutInterval = 15
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            var code: Int?
            if let data,
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let cur = obj["current"] as? [String: Any] {
                if let n = cur["weather_code"] as? NSNumber { code = n.intValue }
            }
            DispatchQueue.main.async {
                guard let self else { return }
                self.fetching = false
                if let code {
                    self.defaults.set(code, forKey: Key.code)
                    self.defaults.set(Date(), forKey: Key.date)
                }
            }
        }.resume()
    }

    // MARK: Запасной вариант

    /// Сезонная погода, одинаковая весь день: зимой чаще снег, осенью дождь/туман, летом ясно.
    static func seasonal(for date: Date) -> Weather {
        let cal = Calendar.current
        let month = cal.component(.month, from: date)
        let day = cal.ordinality(of: .day, in: .era, for: date) ?? 0
        var gen = SeededRandom(seed: day &* 7919 &+ 17)
        let r = Double(gen.next() % 1000) / 1000
        // Доли: [ясно, дождь, снег, туман]
        let p: [Double]
        switch month {
        case 12, 1, 2: p = [0.35, 0.05, 0.45, 0.15]
        case 3: p = [0.4, 0.2, 0.25, 0.15]
        case 4, 5: p = [0.6, 0.3, 0.0, 0.1]
        case 6, 7, 8: p = [0.75, 0.2, 0.0, 0.05]
        case 9, 10: p = [0.4, 0.35, 0.0, 0.25]
        default: p = [0.25, 0.35, 0.15, 0.25] // ноябрь
        }
        var acc = 0.0
        for (i, w) in Weather.allCases.enumerated() {
            acc += p[i]
            if r < acc { return w }
        }
        return .clear
    }
}
