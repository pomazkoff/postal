import SwiftUI

/// Карта главы — вариант A «Пергамент»: бумажная долина во весь экран.
/// Пройденное — цветной пластилин, непройденное — карандашный набросок за полосой облаков
/// (граница считается по длине дороги от текущего прогресса). Поселения стоят на дороге по реальным
/// долям шагов; пройденный путь — красный пунктир по оси дороги; фигурка почтальона — где он сейчас.
/// Пройденные места — в цвете, следующее — блёкло, дальние — призраки. Пан + пинч (1…3×).
struct MapScreen: View {
    @EnvironmentObject var game: GameModel
    @EnvironmentObject var engine: ChapterEngine
    let onShowEndCard: () -> Void
    let onClose: () -> Void

    @State private var revealed: UIImage?
    @State private var revealedFor: Double = -1
    @State private var zoom: CGFloat = 1
    @State private var pan: CGPoint = .zero
    @State private var pinchStart: (zoom: CGFloat, pan: CGPoint)?
    @State private var dragStart: (pan: CGPoint, translation: CGSize)?
    @State private var confirmReset = false

    static let maxZoom: CGFloat = 3

    private var map: ParchmentMap? { ParchmentMap.shared }
    private var step: Int { game.chapterSteps }

    var body: some View {
        FrameScreen(dim: 0.9) { m in
            GeometryReader { geo in
                ZStack {
                    if let map {
                        let road = RoadGeometry(map.points)
                        mapLayer(map, road: road, m: m)
                            .frame(width: geo.size.width, height: geo.size.height, alignment: .topLeading)
                            .scaleEffect(zoom, anchor: .topLeading)
                            .offset(x: pan.x, y: pan.y)
                            .contentShape(Rectangle())
                            .gesture(panGesture(m: m, size: geo.size).simultaneously(with: pinchGesture(m: m, size: geo.size)))
                            .onTapGesture(count: 2) { toggleZoom(map: map, road: road, m: m, size: geo.size) }
                        chrome(map, m: m)
                    } else {
                        Text("Карта не найдена").foregroundStyle(Ink.chalk)
                    }
                }
                .frame(width: geo.size.width, height: geo.size.height)
                .clipped()
            }
        }
        .transition(.opacity)
        .storyResetAlert(isPresented: $confirmReset)
        .task(id: map?.revealThreshold(step: step) ?? 0) { await refreshReveal() }
    }

    // MARK: Слой карты (в координатах кадра; масштабируется жестами)

    @ViewBuilder
    private func mapLayer(_ map: ParchmentMap, road: RoadGeometry, m: FrameMapper) -> some View {
        let s = m.scale
        let f = map.fraction(step: step)
        let feet = road.point(at: f)
        let t0 = map.revealThreshold(step: step)
        let next = map.settlements.first { $0.step > step }
        let layout = ParchmentLayout.layout(map: map, postmanFeet: feet,
                                            frame: CGSize(width: map.size[0], height: map.size[1]),
                                            nextID: next?.id, reachedStep: step)
        ZStack(alignment: .topLeading) {
            Group {
                if let revealed {
                    Image(uiImage: revealed).resizable()
                } else if let color = ParchmentReveal.colorImage() {
                    Image(uiImage: color).resizable()
                }
            }
            .frame(width: map.size[0] * s, height: map.size[1] * s)
            .position(m.point(map.size[0] / 2, map.size[1] / 2))

            // Полоса пластилиновых облаков по границе пройденного.
            let fog = HUDImages.image(map.puffs.image)
            ForEach(Array(map.puffPoints(threshold: t0).enumerated()), id: \.offset) { _, p in
                Image(uiImage: fog).resizable()
                    .frame(width: p[2] * s, height: p[2] * map.puffs.aspect * s)
                    .scaleEffect(x: p[3] > 0.5 ? -1 : 1, y: 1)
                    .shadow(color: Color(red: 0.12, green: 0.07, blue: 0.03).opacity(0.25), radius: 6 * s, x: 4 * s, y: 7 * s)
                    .position(m.point(p[0], p[1]))
            }

            WalkedDashes(points: road.prefix(to: f), m: m)

            ForEach(map.settlements, id: \.id) { place in
                let state = PlaceState(place.step <= step ? .visited : place.id == next?.id ? .next : .ghost)
                stake(place.roadPoint, state: state, m: m)
                placeIcon(place, state: state, m: m)
            }

            // Фигурка почтальона: ноги на дороге.
            Image(uiImage: HUDImages.image(map.postman.image)).resizable()
                .frame(width: map.postman.w * s, height: map.postman.h * s)
                .shadow(color: .black.opacity(0.35), radius: 5 * s, x: 8 * s, y: 6 * s)
                .position(m.point(feet.x + 4, feet.y + 14 - map.postman.h / 2))

            tag("Вы здесь", Format.steps(step) + " ш.", at: layout.postmanTag, dim: false, rotation: 5, m: m)
            ForEach(map.settlements, id: \.id) { place in
                if let c = layout.tags[place.id] {
                    tag(place.name, place.step == 0 ? "старт" : Format.steps(place.step) + " ш.", at: c,
                        dim: place.step > step && place.id != next?.id,
                        rotation: place.step / 100 % 2 == 0 ? -3 : 3, m: m)
                }
            }
        }
    }

    private struct PlaceState {
        enum Kind { case visited, next, ghost }
        let kind: Kind
        init(_ kind: Kind) { self.kind = kind }
    }

    private func stake(_ p: CGPoint, state: PlaceState, m: FrameMapper) -> some View {
        let lit = state.kind == .visited
        return ZStack {
            Circle().fill(lit ? Color(red: 0.35, green: 0.23, blue: 0.13) : Color(red: 0.67, green: 0.59, blue: 0.49))
                .frame(width: m.length(26), height: m.length(26))
            Circle().fill(lit ? Color(red: 0.84, green: 0.67, blue: 0.38) : Color(red: 0.88, green: 0.83, blue: 0.75))
                .frame(width: m.length(13), height: m.length(13))
                .offset(x: m.length(-2), y: m.length(-3))
        }
        .position(m.point(p.x, p.y))
    }

    @ViewBuilder
    private func placeIcon(_ place: ParchmentMap.Place, state: PlaceState, m: FrameMapper) -> some View {
        let s = m.scale
        let image = Image(uiImage: HUDImages.image(place.icon)).resizable()
            .frame(width: place.w * s, height: place.h * s)
        let at = m.point(place.x, place.y - place.h / 2)
        switch state.kind {
        case .visited:
            image
                .shadow(color: Color(red: 0.12, green: 0.07, blue: 0.03).opacity(0.4), radius: 8 * s, x: 12 * s, y: 12 * s)
                .position(at)
        case .next:
            image.saturation(0.45).brightness(0.06).opacity(0.78)
                .position(at)
        case .ghost:
            image.saturation(0).contrast(0.75).brightness(0.1).opacity(0.42)
                .blendMode(.multiply)
                .position(at)
        }
    }

    private func tag(_ line1: String, _ line2: String, at c: CGPoint, dim: Bool, rotation: Double, m: FrameMapper) -> some View {
        let e = UIArt.entry("tag_small")
        let k = m.scale
        let ts = ParchmentLayout.tagScale
        return TagArt(line1: line1, line2: line2, k: k, small: true, scale: ts)
            .saturation(dim ? 0.3 : 1)
            .opacity(dim ? 0.62 : 1)
            .pinned(size: CGSize(width: e.width * k * ts, height: e.height * k * ts),
                    anchor: CGPoint(x: e.bodyCenter.x * k * ts, y: e.bodyCenter.y * k * ts),
                    at: m.point(c.x, c.y), rotation: rotation)
    }

    // MARK: Рамка (не масштабируется)

    @ViewBuilder
    private func chrome(_ map: ParchmentMap, m: FrameMapper) -> some View {
        let k = m.scale
        PlacedArt(name: "plaque", m: m, at: CGPoint(x: 300, y: 250), scale: 520 / 660) { e, f in
            Text("Долина")
                .font(Ink.title(84 * f))
                .foregroundStyle(Ink.brown)
                .position(x: 310 * f, y: 150 * f)
            Text("глава \(game.chapter.id) · день \(dayNumber)")
                .font(Ink.label(40 * f))
                .foregroundStyle(Ink.brown.opacity(0.8))
                .lineLimit(1).minimumScaleFactor(0.6)
                .frame(width: 480 * f)
                .position(x: 310 * f, y: 228 * f)
        }
        .allowsHitTesting(false)

        // Скрытый жест для тестов (и в Release): 3 с на табличке «Долина» — «Сбросить историю».
        let plaque = UIArt.entry("plaque").body
        Color.clear
            .contentShape(Rectangle())
            .frame(width: plaque.width * k * 520 / 660, height: plaque.height * k * 520 / 660)
            .position(m.point(300, 250))
            .onLongPressGesture(minimumDuration: StoryReset.holdSeconds) { confirmReset = true }

        ZStack {
            Image(uiImage: HUDImages.image(map.compass.image)).resizable()
                .frame(width: map.compass.w * k, height: map.compass.h * k)
                .shadow(color: .black.opacity(0.3), radius: 6 * k, x: 8 * k, y: 10 * k)
            Text("С")
                .font(Ink.title(46 * k))
                .foregroundStyle(Ink.brown)
                .offset(y: -(map.compass.h / 2 + 26) * k)
        }
        .position(m.point(1010, 300))
        .allowsHitTesting(false)

        let total = game.chapter.lengthSteps
        PlacedArt(name: "tag", m: m, at: CGPoint(x: 300, y: 2380), scale: 420 / 437, rotation: 3) { e, f in
            Text("\(Format.steps(min(step, total))) из \(Format.steps(total))")
                .font(Ink.title(46 * f))
                .foregroundStyle(Ink.brown)
                .lineLimit(1).minimumScaleFactor(0.5)
                .frame(width: 270 * f)
                .position(x: 225 * f, y: 80 * f)
            Text("шагов · день \(dayNumber)")
                .font(Ink.label(36 * f))
                .foregroundStyle(Ink.brown.opacity(0.8))
                .lineLimit(1).minimumScaleFactor(0.5)
                .frame(width: 270 * f)
                .position(x: 225 * f, y: 146 * f)
        }
        .allowsHitTesting(false)

        if engine.isFinished {
            ArrowButton(title: "Итоги", m: m, right: 600, bottom: 2250, flip: true, action: onShowEndCard)
        }
        ArrowButton(title: "Закрыть", m: m, bottom: 2470, action: onClose)
    }

    /// День пути: с полуночи дня старта игры.
    private var dayNumber: Int {
        guard let start = game.progress.gameStartDate else { return 1 }
        let cal = Calendar.current
        let d = cal.dateComponents([.day], from: cal.startOfDay(for: start), to: cal.startOfDay(for: Date())).day ?? 0
        return max(1, d + 1)
    }

    // MARK: Раскрытие

    @MainActor
    private func refreshReveal() async {
        guard let map else { return }
        let t0 = map.revealThreshold(step: step)
        guard abs(t0 - revealedFor) > 1e-4 else { return }
        let image = await Task.detached(priority: .userInitiated) {
            ParchmentReveal.render(map: map, threshold: t0)
        }.value
        revealed = image
        revealedFor = t0
    }

    // MARK: Жесты

    /// Карта в масштабе 1 — кадр 1170×2532 (aspectFill); при zoom её край не уходит внутрь экрана.
    private func clamped(_ p: CGPoint, zoom z: CGFloat, m: FrameMapper, size: CGSize) -> CGPoint {
        let origin = m.point(0, 0)
        let w = 1170 * m.scale, h = 2532 * m.scale
        let minX = size.width - z * (origin.x + w), maxX = -z * origin.x
        let minY = size.height - z * (origin.y + h), maxY = -z * origin.y
        return CGPoint(x: min(max(p.x, min(minX, maxX)), max(minX, maxX)),
                       y: min(max(p.y, min(minY, maxY)), max(minY, maxY)))
    }

    private func panGesture(m: FrameMapper, size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 4)
            .onChanged { v in
                guard pinchStart == nil else { dragStart = nil; return }
                if dragStart == nil { dragStart = (pan, v.translation) }
                guard let start = dragStart else { return }
                pan = clamped(CGPoint(x: start.pan.x + v.translation.width - start.translation.width,
                                      y: start.pan.y + v.translation.height - start.translation.height),
                              zoom: zoom, m: m, size: size)
            }
            .onEnded { v in
                let fling = CGSize(width: v.predictedEndTranslation.width - v.translation.width,
                                   height: v.predictedEndTranslation.height - v.translation.height)
                dragStart = nil
                guard pinchStart == nil else { return }
                withAnimation(.easeOut(duration: 0.45)) {
                    pan = clamped(CGPoint(x: pan.x + fling.width, y: pan.y + fling.height), zoom: zoom, m: m, size: size)
                }
            }
    }

    private func pinchGesture(m: FrameMapper, size: CGSize) -> some Gesture {
        MagnifyGesture()
            .onChanged { v in
                if pinchStart == nil { pinchStart = (zoom, pan); dragStart = nil }
                guard let start = pinchStart else { return }
                let z = min(Self.maxZoom, max(1, start.zoom * v.magnification))
                let loc = v.startLocation
                // Точка под пальцами остаётся на месте: screen = pan + zoom · content.
                let p = CGPoint(x: loc.x - (loc.x - start.pan.x) * z / start.zoom,
                                y: loc.y - (loc.y - start.pan.y) * z / start.zoom)
                zoom = z
                pan = clamped(p, zoom: z, m: m, size: size)
            }
            .onEnded { _ in pinchStart = nil }
    }

    /// Двойной тап: приблизить к почтальону / вернуть всю долину.
    private func toggleZoom(map: ParchmentMap, road: RoadGeometry, m: FrameMapper, size: CGSize) {
        withAnimation(.easeInOut(duration: 0.35)) {
            if zoom > 1.05 {
                zoom = 1
                pan = clamped(.zero, zoom: 1, m: m, size: size)
            } else {
                let z: CGFloat = 2.2
                let feet = m.point(road.point(at: map.fraction(step: step)).x, road.point(at: map.fraction(step: step)).y)
                zoom = z
                pan = clamped(CGPoint(x: size.width / 2 - z * feet.x, y: size.height / 2 - z * feet.y),
                              zoom: z, m: m, size: size)
            }
        }
    }
}

/// Пройденный путь: красный пластилиновый пунктир по оси дороги (тень, тёмный кант, цвет, блик).
private struct WalkedDashes: View {
    let points: [CGPoint]
    let m: FrameMapper

    var body: some View {
        let path = Path { p in
            guard let first = points.first else { return }
            p.move(to: m.point(first.x, first.y))
            for q in points.dropFirst() { p.addLine(to: m.point(q.x, q.y)) }
        }
        let w = m.length(16)
        let dash = [m.length(30), m.length(28)]
        ZStack {
            path.stroke(Color(red: 0.16, green: 0.08, blue: 0.04).opacity(0.45),
                        style: StrokeStyle(lineWidth: w + m.length(4), lineCap: .round, lineJoin: .round, dash: dash))
                .offset(x: m.length(4), y: m.length(6))
                .blur(radius: m.length(3))
            path.stroke(Color(red: 0.47, green: 0.12, blue: 0.07),
                        style: StrokeStyle(lineWidth: w + m.length(4), lineCap: .round, lineJoin: .round, dash: dash))
            path.stroke(Color(red: 0.80, green: 0.24, blue: 0.14),
                        style: StrokeStyle(lineWidth: w, lineCap: .round, lineJoin: .round, dash: dash))
            path.stroke(Color(red: 0.94, green: 0.51, blue: 0.37).opacity(0.75),
                        style: StrokeStyle(lineWidth: max(1, m.length(4)), lineCap: .round, lineJoin: .round, dash: dash))
                .offset(x: m.length(-2), y: m.length(-3))
        }
    }
}
