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
    @State private var mountainPicture: UIImage?
    @State private var mountainPictureFor: Double = -1
    @State private var zoom: CGFloat = 1
    @State private var pan: CGPoint = .zero
    @State private var pinchStart: (zoom: CGFloat, pan: CGPoint)?
    @State private var dragStart: (pan: CGPoint, translation: CGSize)?
    @State private var confirmReset = false
    @State private var note: MapNote?
    @State private var didCenter = false

    static let maxZoom: CGFloat = 3

    private var map: ParchmentMap? { ParchmentMap.shared }
    private var step: Int { game.chapterSteps }
    /// Точка на нарисованном листе. Для главы 2 это конец Долины, не шаг 2419 у Свай.
    private var sheetStep: Int {
        map?.sheetStep(chapterID: game.chapter.id, chapterSteps: step) ?? 0
    }
    private var valleySheet: Bool { game.chapter.id == 1 }
    /// Порог цвета на листе гор. −1, пока файла нет.
    private var mountainRevealKey: Double {
        guard let map, let sheet = MapAtlas.make(valley: map).mountains else { return -1 }
        let global = game.chapter.startStep + step
        let local = min(sheet.lengthSteps, max(0, global - sheet.globalStart))
        return sheet.revealThreshold(localStep: global >= sheet.globalStart ? local : 0)
    }

    var body: some View {
        FrameScreen(dim: 0.9) { m in
            GeometryReader { geo in
                ZStack {
                    if let map {
                        let atlas = MapAtlas.make(valley: map)
                        let road = RoadGeometry(map.points)
                        let global = game.chapter.startStep + step
                        let heroOnMountain = atlas.mountains != nil && global >= MountainPlaces.globalStart
                        ZStack(alignment: .topLeading) {
                            // Долина снизу. Горы непрозрачным кадром сверху: в перекрытии нет смешения, иначе шов двоится.
                            mapLayer(map, road: road, m: m, drawHero: !heroOnMountain)
                                .offset(x: m.length(atlas.valleyOrigin.x), y: m.length(atlas.valleyOrigin.y))
                            if let mountains = atlas.mountains {
                                mountainLayer(mountains, global: global, m: m, drawHero: heroOnMountain,
                                              picture: mountainPicture, postman: map.postman)
                            }
                        }
                        .frame(width: geo.size.width, height: geo.size.height, alignment: .topLeading)
                        .scaleEffect(zoom, anchor: .topLeading)
                        .offset(x: pan.x, y: pan.y)
                        .contentShape(Rectangle())
                        .simultaneousGesture(panGesture(m: m, size: geo.size, content: atlas.contentSize))
                        .simultaneousGesture(pinchGesture(m: m, size: geo.size, content: atlas.contentSize))
                        .onTapGesture(count: 2) { toggleZoom(map: map, atlas: atlas, m: m, size: geo.size) }
                        .task(id: Int(geo.size.height)) {
                            guard !didCenter, geo.size.height > 1 else { return }
                            didCenter = true
                            guard atlas.centersHero(viewSize: geo.size, scale: m.scale) else { return }
                            let feet = atlas.point(globalStep: global)
                            pan = clamped(CGPoint(x: geo.size.width / 2 - m.point(feet.x, feet.y).x,
                                                  y: geo.size.height / 2 - m.point(feet.x, feet.y).y),
                                          zoom: 1, m: m, size: geo.size, content: atlas.contentSize)
                        }
                        if let note {
                            mapNote(note, m: m)
                        }
                        chrome(map, m: m, mountains: atlas.mountains != nil)
                    } else {
                        Text(L10n.text("map.missing")).foregroundStyle(Ink.chalk)
                    }
                }
                .frame(width: geo.size.width, height: geo.size.height)
                .clipped()
            }
        }
        .transition(.opacity)
        .storyResetAlert(isPresented: $confirmReset)
        .task(id: map?.revealThreshold(step: sheetStep) ?? 0) { await refreshReveal() }
        .task(id: mountainRevealKey) { await refreshMountain() }
        .onAppear { SoundPlayback.shared.effect("ui_paper_open") }
    }

    // MARK: Слой карты (в координатах кадра; масштабируется жестами)

    @ViewBuilder
    private func mapLayer(_ map: ParchmentMap, road: RoadGeometry, m: FrameMapper, drawHero: Bool) -> some View {
        let s = m.scale
        let f = map.fraction(step: sheetStep)
        let feet = road.point(at: f)
        let t0 = map.revealThreshold(step: sheetStep)
        let next = map.settlements.first { $0.step > sheetStep }
        let layout = ParchmentLayout.layout(map: map, postmanFeet: feet,
                                            frame: CGSize(width: map.size[0], height: map.size[1]),
                                            nextID: next?.id, reachedStep: sheetStep)
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
                let state = PlaceState(place.step <= sheetStep ? .visited : place.id == next?.id ? .next : .ghost)
                stake(place.roadPoint, name: place.name, state: state, m: m)
                    .onTapGesture { openPlace(place) }
                placeIcon(place, state: state, m: m)
                    .onTapGesture { openPlace(place) }
                    .accessibilityLabel(place.name)
                    .accessibilityAddTraits(.isButton)
            }

            if drawHero {
                Image(uiImage: HUDImages.image(map.postman.image)).resizable()
                    .frame(width: map.postman.w * s, height: map.postman.h * s)
                    .shadow(color: .black.opacity(0.35), radius: 5 * s, x: 8 * s, y: 6 * s)
                    .contentShape(Rectangle())
                    .position(m.point(feet.x + 4, feet.y + 14 - map.postman.h / 2))
                    .onTapGesture { openPostman() }
                    .accessibilityLabel(L10n.text("app.name"))
                    .accessibilityAddTraits(.isButton)
                tag(valleySheet ? L10n.text("map.you") : L10n.text("map.sheetEnd"),
                    valleySheet ? Format.steps(step) + " " + L10n.text("abbr.steps") : L10n.text("map.notDrawn"),
                    at: layout.postmanTag, dim: false, rotation: 5, m: m)
                    .onTapGesture { openPostman() }
            }
            ForEach(map.settlements, id: \.id) { place in
                if let c = layout.tags[place.id] {
                    // step Долины уже мировой: Седло 20 000. Второй раз globalStart не прибавляется.
                    tag(place.name, place.step == 0 ? L10n.text("map.start") : Format.steps(place.step) + " " + L10n.text("abbr.steps"), at: c,
                        dim: place.step > sheetStep && place.id != next?.id,
                        rotation: place.step / 100 % 2 == 0 ? -3 : 3, m: m)
                        .onTapGesture { openPlace(place) }
                        .accessibilityLabel(place.name)
                        .accessibilityAddTraits(.isButton)
                }
            }
        }
    }

    private struct PlaceState {
        enum Kind { case visited, next, ghost }
        let kind: Kind
        init(_ kind: Kind) { self.kind = kind }
    }

    private func stake(_ p: CGPoint, name: String, state: PlaceState, m: FrameMapper) -> some View {
        let lit = state.kind == .visited
        return ZStack {
            Circle().fill(lit ? Color(red: 0.35, green: 0.23, blue: 0.13) : Color(red: 0.67, green: 0.59, blue: 0.49))
                .frame(width: m.length(26), height: m.length(26))
            Circle().fill(lit ? Color(red: 0.84, green: 0.67, blue: 0.38) : Color(red: 0.88, green: 0.83, blue: 0.75))
                .frame(width: m.length(13), height: m.length(13))
                .offset(x: m.length(-2), y: m.length(-3))
        }
        .frame(width: m.length(120), height: m.length(120))
        .contentShape(Rectangle())
        .position(m.point(p.x, p.y))
        .accessibilityLabel(name)
        .accessibilityAddTraits(.isButton)
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
                .contentShape(Rectangle())
                .position(at)
        case .next:
            image.saturation(0.45).brightness(0.06).opacity(0.78)
                .contentShape(Rectangle())
                .position(at)
        case .ghost:
            image.saturation(0).contrast(0.75).brightness(0.1).opacity(0.42)
                .blendMode(.multiply)
                .contentShape(Rectangle())
                .position(at)
        }
    }

    /// Пройденное место — уже слышанная строка прибытия, если она есть. Дальше тумана — только «ещё впереди».
    private func openPlace(_ place: ParchmentMap.Place) {
        let reached = place.step <= sheetStep
        let body: String
        if reached, let line = arrivalText(place.id), !line.isEmpty {
            body = line
        } else if reached {
            body = L10n.text("map.place.been")
        } else {
            let left = max(0, place.step - sheetStep)
            body = L10n.format("map.place.ahead", Format.steps(left) + " " + L10n.text("abbr.steps"))
        }
        note = MapNote(title: place.name, body: body, image: reached ? place.icon : nil)
    }

    private func openPostman() {
        note = MapNote(title: L10n.text("app.name"), body: L10n.text("onboarding.card0.body"),
                       image: map?.postman.image)
    }

    /// Строка прибытия с листа долины, если активная глава уже другая.
    private func arrivalText(_ placeID: String) -> String? {
        if let line = engine.story.arrivals?.first(where: { $0.settlement == placeID })?.text, !line.isEmpty {
            return line
        }
        guard game.chapter.id != 1 else { return nil }
        return StoryConfig.load(chapter: 1).arrivals?.first { $0.settlement == placeID }?.text
    }

    private func mapNote(_ note: MapNote, m: FrameMapper) -> some View {
        ZStack {
            Color.black.opacity(0.28)
                .contentShape(Rectangle())
                .onTapGesture { self.note = nil }
            VStack(alignment: .leading, spacing: m.length(16)) {
                if let image = note.image {
                    Image(uiImage: HUDImages.image(image))
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: m.length(280), maxHeight: m.length(320))
                        .accessibilityHidden(true)
                }
                Text(note.title)
                    .font(Ink.title(m.length(48)))
                    .foregroundStyle(Ink.brown)
                    .accessibilityAddTraits(.isHeader)
                Text(note.body)
                    .font(Ink.font("hand", size: m.length(36)))
                    .foregroundStyle(Ink.pencil)
                    .fixedSize(horizontal: false, vertical: true)
                Button { self.note = nil } label: {
                    Text(L10n.text("map.close"))
                        .font(Ink.title(m.length(36)))
                        .foregroundStyle(Ink.chalk)
                        .frame(maxWidth: .infinity, minHeight: m.length(100))
                        .background(RoundedRectangle(cornerRadius: m.length(12), style: .continuous).fill(Theme.teal))
                }
                .buttonStyle(PressStyle())
                .accessibilityLabel(L10n.text("map.close"))
            }
            .padding(m.length(28))
            .frame(width: m.length(820))
            .background(
                RoundedRectangle(cornerRadius: m.length(22), style: .continuous)
                    .fill(Theme.paper)
                    .overlay(RoundedRectangle(cornerRadius: m.length(22), style: .continuous).stroke(Theme.paperEdge, lineWidth: max(1, m.length(3))))
            )
            .accessibilityElement(children: .contain)
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
    private func mountainLayer(_ sheet: MountainSheet, global: Int, m: FrameMapper, drawHero: Bool,
                               picture: UIImage?, postman: ParchmentMap.Sprite) -> some View {
        let s = m.scale
        let local = min(sheet.lengthSteps, max(0, global - sheet.globalStart))
        let onSheet = global >= sheet.globalStart
        let fraction = sheet.fraction(localStep: onSheet ? local : 0)
        let road = RoadGeometry(sheet.road)
        let feet = road.point(at: fraction)
        let t0 = sheet.revealThreshold(localStep: onSheet ? local : 0)
        let next = sheet.settlements.first { $0.step > (onSheet ? local : -1) }
        let reached = onSheet ? local : -1
        let tags = ParchmentLayout.layout(places: sheet.settlements,
                                          postman: CGSize(width: postman.w, height: postman.h),
                                          postmanFeet: feet, frame: sheet.size,
                                          nextID: next?.id, reachedStep: reached,
                                          includePostman: drawHero)
        let image = picture ?? UIImage(contentsOfFile: sheet.colorPath)
        if let image {
            Image(uiImage: image).resizable()
                .frame(width: sheet.size.width * s, height: sheet.size.height * s)
                .position(m.point(sheet.size.width / 2, sheet.size.height / 2))
                .allowsHitTesting(false)
        }
        let fog = HUDImages.image(sheet.puffs.image)
        ForEach(Array(sheet.puffPoints(threshold: t0).enumerated()), id: \.offset) { _, p in
            Image(uiImage: fog).resizable()
                .frame(width: p[2] * s, height: p[2] * sheet.puffs.aspect * s)
                .scaleEffect(x: p[3] > 0.5 ? -1 : 1, y: 1)
                .shadow(color: Color(red: 0.12, green: 0.07, blue: 0.03).opacity(0.25), radius: 6 * s, x: 4 * s, y: 7 * s)
                .position(m.point(p[0], p[1]))
                .allowsHitTesting(false)
        }
        if onSheet {
            WalkedDashes(points: road.prefix(to: fraction), m: m)
        }
        ForEach(sheet.settlements, id: \.id) { place in
            let been = onSheet && global >= sheet.globalStart + place.step
            let state = PlaceState(been ? .visited : place.id == next?.id ? .next : .ghost)
            stake(place.roadPoint, name: place.name, state: state, m: m)
                .onTapGesture { openMountain(place, sheet: sheet, global: global) }
            placeIcon(place, state: state, m: m)
                .onTapGesture { openMountain(place, sheet: sheet, global: global) }
                .accessibilityLabel(place.name)
                .accessibilityAddTraits(.isButton)
            if let c = tags.tags[place.id] {
                tag(place.name, Format.steps(WorldSteps.shown(local: place.step, origin: sheet.globalStart)) + " " + L10n.text("abbr.steps"), at: c,
                    dim: !been && place.id != next?.id, rotation: place.step / 100 % 2 == 0 ? -3 : 3, m: m)
                    .onTapGesture { openMountain(place, sheet: sheet, global: global) }
            }
        }
        if drawHero {
            Image(uiImage: HUDImages.image(postman.image)).resizable()
                .frame(width: postman.w * s, height: postman.h * s)
                .shadow(color: .black.opacity(0.35), radius: 5 * s, x: 8 * s, y: 6 * s)
                .contentShape(Rectangle())
                .position(m.point(feet.x + 4, feet.y + 14 - postman.h / 2))
                .onTapGesture { openPostman() }
                .accessibilityLabel(L10n.text("app.name"))
                .accessibilityAddTraits(.isButton)
            tag(L10n.text("map.you"), Format.steps(WorldSteps.shown(local: local, origin: sheet.globalStart)) + " " + L10n.text("abbr.steps"),
                at: tags.postmanTag, dim: false, rotation: 5, m: m)
                .onTapGesture { openPostman() }
        }
    }

    private func openMountain(_ place: ParchmentMap.Place, sheet: MountainSheet, global: Int) {
        let reached = global >= sheet.globalStart + place.step
        let body: String
        if reached, let line = arrivalText(place.id), !line.isEmpty {
            body = line
        } else if reached {
            body = L10n.text("map.place.been")
        } else {
            let left = max(0, sheet.globalStart + place.step - global)
            body = L10n.format("map.place.ahead", Format.steps(left) + " " + L10n.text("abbr.steps"))
        }
        note = MapNote(title: place.name, body: body, image: reached ? place.icon : nil)
    }

    private func chrome(_ map: ParchmentMap, m: FrameMapper, mountains: Bool) -> some View {
        let k = m.scale
        PlacedArt(name: "plaque", m: m, at: CGPoint(x: 300, y: 250), scale: 520 / 660) { e, f in
            Text(mountains && !valleySheet ? L10n.text("map.mountains") : L10n.text("map.region"))
                .font(Ink.title(84 * f))
                .foregroundStyle(Ink.brown)
                .position(x: 310 * f, y: 150 * f)
            Text(!mountains && !valleySheet
                 ? L10n.text("map.valleyOnly")
                 : L10n.format("map.chapterDay", game.chapter.id, dayNumber))
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
            Text(L10n.text("map.north"))
                .font(Ink.title(46 * k))
                .foregroundStyle(Ink.brown)
                .offset(y: -(map.compass.h / 2 + 26) * k)
        }
        .position(m.point(1010, 300))
        .allowsHitTesting(false)

        let total = valleySheet || mountains ? game.chapter.lengthSteps : map.lengthSteps
        let counted = valleySheet || mountains ? step : sheetStep
        PlacedArt(name: "tag", m: m, at: CGPoint(x: 300, y: 2380), scale: 420 / 437, rotation: 3) { e, f in
            Text(L10n.format("map.stepsOf", Format.steps(min(counted, total)), Format.steps(total)))
                .font(Ink.title(46 * f))
                .foregroundStyle(Ink.brown)
                .lineLimit(1).minimumScaleFactor(0.5)
                .frame(width: 270 * f)
                .position(x: 225 * f, y: 80 * f)
            Text(mountains && !valleySheet
                 ? L10n.format("map.chapterProgress", game.chapter.id, dayNumber)
                 : valleySheet
                    ? L10n.plural("map.stepWord", min(step, total)) + " · " + L10n.format("map.day", dayNumber)
                    : L10n.format("map.elsewhere", game.chapter.title, Format.steps(step)))
                .font(Ink.label(36 * f))
                .foregroundStyle(Ink.brown.opacity(0.8))
                .lineLimit(1).minimumScaleFactor(0.5)
                .frame(width: 270 * f)
                .position(x: 225 * f, y: 146 * f)
        }
        .allowsHitTesting(false)

        if engine.isFinished {
            ArrowButton(title: L10n.text("map.totals"), m: m, right: 600, bottom: 2250, flip: true, action: onShowEndCard)
        }
        ArrowButton(title: L10n.text("map.close"), m: m, bottom: 2470, action: onClose)
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
        let t0 = map.revealThreshold(step: sheetStep)
        guard abs(t0 - revealedFor) > 1e-4 else { return }
        let image = await Task.detached(priority: .userInitiated) {
            ParchmentReveal.render(map: map, threshold: t0)
        }.value
        revealed = image
        revealedFor = t0
    }

    @MainActor
    private func refreshMountain() async {
        guard let map, let sheet = MapAtlas.make(valley: map).mountains else { return }
        let t0 = mountainRevealKey
        guard t0 >= 0, abs(t0 - mountainPictureFor) > 1e-4 else { return }
        let color = URL(fileURLWithPath: sheet.colorPath)
        let pencil = URL(fileURLWithPath: sheet.pencilPath)
        let field = URL(fileURLWithPath: sheet.fieldPath)
        let scale = sheet.field.decodeScale
        let bias = sheet.field.decodeBias
        let soft = sheet.softFraction
        let image = await Task.detached(priority: .userInitiated) {
            ParchmentReveal.render(color: color, pencil: pencil, field: field,
                                   decodeScale: scale, decodeBias: bias,
                                   softFraction: soft, threshold: t0)
        }.value
        mountainPicture = image
        mountainPictureFor = t0
    }

    // MARK: Жесты

    /// Карта в масштабе 1 — кадр 1170×2532 (aspectFill); при zoom её край не уходит внутрь экрана.
    private func clamped(_ p: CGPoint, zoom z: CGFloat, m: FrameMapper, size: CGSize, content: CGSize) -> CGPoint {
        let origin = m.point(0, 0)
        let w = content.width * m.scale, h = content.height * m.scale
        let minX = size.width - z * (origin.x + w), maxX = -z * origin.x
        let minY = size.height - z * (origin.y + h), maxY = -z * origin.y
        return CGPoint(x: min(max(p.x, min(minX, maxX)), max(minX, maxX)),
                       y: min(max(p.y, min(minY, maxY)), max(minY, maxY)))
    }

    private func panGesture(m: FrameMapper, size: CGSize, content: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 14)
            .onChanged { v in
                guard pinchStart == nil else { dragStart = nil; return }
                if dragStart == nil { dragStart = (pan, v.translation) }
                guard let start = dragStart else { return }
                pan = clamped(CGPoint(x: start.pan.x + v.translation.width - start.translation.width,
                                      y: start.pan.y + v.translation.height - start.translation.height),
                              zoom: zoom, m: m, size: size, content: content)
            }
            .onEnded { v in
                let fling = CGSize(width: v.predictedEndTranslation.width - v.translation.width,
                                   height: v.predictedEndTranslation.height - v.translation.height)
                dragStart = nil
                guard pinchStart == nil else { return }
                withAnimation(.easeOut(duration: 0.45)) {
                    pan = clamped(CGPoint(x: pan.x + fling.width, y: pan.y + fling.height),
                                  zoom: zoom, m: m, size: size, content: content)
                }
            }
    }

    private func pinchGesture(m: FrameMapper, size: CGSize, content: CGSize) -> some Gesture {
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
                pan = clamped(p, zoom: z, m: m, size: size, content: content)
            }
            .onEnded { _ in pinchStart = nil }
    }

    /// Двойной тап: приблизить к почтальону / вернуть всю долину.
    private func toggleZoom(map: ParchmentMap, atlas: MapAtlas, m: FrameMapper, size: CGSize) {
        withAnimation(.easeInOut(duration: 0.35)) {
            if zoom > 1.05 {
                zoom = 1
                pan = clamped(.zero, zoom: 1, m: m, size: size, content: atlas.contentSize)
            } else {
                let z: CGFloat = 2.2
                let feet = m.point(atlas.point(globalStep: game.chapter.startStep + step).x,
                                   atlas.point(globalStep: game.chapter.startStep + step).y)
                zoom = z
                pan = clamped(CGPoint(x: size.width / 2 - z * feet.x, y: size.height / 2 - z * feet.y),
                              zoom: z, m: m, size: size, content: atlas.contentSize)
            }
        }
    }
}

struct MapNote: Identifiable, Equatable {
    let title: String
    let body: String
    /// Путь картинки в GameAssets. Для места за туманом — nil, чтобы не показывать ясный вид.
    let image: String?
    var id: String { title + body }
}

/// Карточка почтальона в мире: то же описание, что на первой странице знакомства.
struct HeroNote: View {
    let onClose: () -> Void

    var body: some View {
        FrameScreen(dim: 0.45) { m in
            ZStack {
                Color.clear.contentShape(Rectangle()).onTapGesture(perform: onClose)
                VStack(alignment: .leading, spacing: m.length(16)) {
                    Image(uiImage: HUDImages.image("UI/map/postman"))
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: m.length(280), maxHeight: m.length(420))
                        .accessibilityHidden(true)
                    Text(L10n.text("app.name"))
                        .font(Ink.title(m.length(52)))
                        .foregroundStyle(Ink.brown)
                        .accessibilityAddTraits(.isHeader)
                    Text(L10n.text("onboarding.card0.body"))
                        .font(Ink.font("hand", size: m.length(36)))
                        .foregroundStyle(Ink.pencil)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(action: onClose) {
                        Text(L10n.text("map.close"))
                            .font(Ink.title(m.length(36)))
                            .foregroundStyle(Ink.chalk)
                            .frame(maxWidth: .infinity, minHeight: m.length(100))
                            .background(RoundedRectangle(cornerRadius: m.length(12), style: .continuous).fill(Theme.teal))
                    }
                    .buttonStyle(PressStyle())
                    .accessibilityLabel(L10n.text("map.close"))
                }
                .padding(m.length(28))
                .frame(width: m.length(860))
                .background(
                    RoundedRectangle(cornerRadius: m.length(22), style: .continuous)
                        .fill(Theme.paper)
                        .overlay(RoundedRectangle(cornerRadius: m.length(22), style: .continuous).stroke(Theme.paperEdge, lineWidth: max(1, m.length(3))))
                )
                .accessibilityElement(children: .contain)
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
