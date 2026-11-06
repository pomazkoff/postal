import SwiftUI
import UIKit

/// Онбординг: карусель карточек о мире и фичах + запрос разрешений на последней.
struct OnboardingView: View {
    @EnvironmentObject private var game: GameModel
    @State private var page: Int = 0
    /// Сдвиг пальца во время драга (px). Непрерывно обновляется в DragGesture.
    @State private var dragX: CGFloat = 0
    /// Ширина пейджера (для расчёта progress).
    @State private var pagerWidth: CGFloat = 1
    @State private var isRequesting = false
    private var cards: [OnboardCard] { OnboardCard.all(fake: game.steps.mode == .fake) }
    private var pageIndex: Int { min(max(page, 0), max(cards.count - 1, 0)) }
    /// Непрерывный прогресс 0…N-1 (дробный во время свайпа).
    private var progress: CGFloat { CGFloat(pageIndex) - dragX / max(pagerWidth, 1) }
    /// Индикатор следует за пальцем — ближайшая страница.
    private var indicatorIndex: Int { min(max(Int(progress.rounded()), 0), cards.count - 1) }

    var body: some View {
        ZStack {
            sky.ignoresSafeArea()

            // Небо/параллакс на весь экран; контент ниже — без ignoresSafeArea.
            GeometryReader { geo in
                parallaxWorld(width: geo.size.width, height: geo.size.height)
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)

            // VStack уважает safe area → «ПОЧТАЛЬОН» целиком ниже Dynamic Island.
            VStack(spacing: 0) {
                header
                    .padding(.top, 10)
                    .padding(.horizontal, 24)
                pager
                footer
                    .padding(.horizontal, 24)
                    .padding(.bottom, 18)
            }
        }
    }

    // MARK: - Layers

    private var sky: some View {
        LinearGradient(
            colors: [
                Color(red: 0.14, green: 0.42, blue: 0.48),
                Theme.teal,
                Color(red: 0.12, green: 0.28, blue: 0.26),
            ],
            startPoint: .top, endPoint: .bottom
        )
    }

    /// Дальний и средний план двигаются медленнее карточек — параллакс при свайпе.
    private func parallaxWorld(width: CGFloat, height: CGFloat) -> some View {
        // Резинка первой карточки (progress < 0) не крутит фон назад — только ≥ 0.
        let px = max(progress, 0) * width
        let farShift = px * 0.22
        let midShift = px * 0.5
        let fgShift = px * 0.95
        // Фиксированные высоты и Y-offset — не зависят от progress/карточек,
        // чтобы при старте drag фон не перелайаутился вверх на один кадр.
        let farH = height * 0.42
        let midH = height * 0.36
        let grassH = height * 0.14
        let hazeH = height * 0.55
        // Как раньше: far по центру экрана чуть выше; mid у низа.
        let farY = height * 0.5 - farH * 0.5 - height * 0.06
        let midY = height - midH + height * 0.02
        return ZStack(alignment: .topLeading) {
            OnboardTileStrip(
                path: "Chapter1/places/bg_far_ridges_tile",
                height: farH,
                shift: farShift,
                viewportWidth: width,
                opacity: 0.55
            )
            .frame(width: width, height: farH, alignment: .leading)
            .offset(y: farY)

            OnboardTileStrip(
                path: "Chapter1/places/bg_mid_fields_tile",
                height: midH,
                shift: midShift,
                viewportWidth: width,
                opacity: 0.7
            )
            .frame(width: width, height: midH, alignment: .leading)
            .offset(y: midY)

            // Мягкая дымка у горизонта — чтобы карточки читались.
            LinearGradient(
                colors: [.clear, Color(red: 0.05, green: 0.12, blue: 0.12).opacity(0.55)],
                startPoint: .top, endPoint: .bottom
            )
            .frame(width: width, height: hazeH)
            .offset(y: height - hazeH)
            .allowsHitTesting(false)

            OnboardTileStrip(
                path: "Chapter1/foreground/fg_grass_a",
                height: grassH,
                shift: fgShift,
                viewportWidth: width,
                opacity: 0.55,
                flipAlternate: true
            )
            .frame(width: width, height: grassH, alignment: .leading)
            .offset(y: height - grassH)
            .allowsHitTesting(false)
        }
        .frame(width: width, height: height, alignment: .topLeading)
        .clipped()
        .allowsHitTesting(false)
    }

    private var header: some View {
        VStack(spacing: 4) {
            Text(AppInfo.displayName)
                .font(Ink.title(36))
                .foregroundStyle(Theme.paper)
                .shadow(color: .black.opacity(0.45), radius: 4, y: 2)
            Text("письмо в Долину")
                .font(Ink.label(15))
                .foregroundStyle(Theme.paper.opacity(0.75))
                .tracking(1.2)
        }
        .frame(maxWidth: .infinity)
        .accessibilityAddTraits(.isHeader)
    }

    /// Собственный пейджер: offset = -progress * width, DragGesture даёт непрерывный offset на iOS 17.
    private var pager: some View {
        let n = cards.count
        return GeometryReader { g in
            let pw = g.size.width
            ZStack {
                ForEach(Array(cards.enumerated()), id: \.element.id) { index, card in
                    let d = CGFloat(index) - progress  // <0 слева, >0 справа
                    let ad = min(abs(d), 1.5)
                    if abs(d) < 1.6 {
                        OnboardCardView(
                            card: card,
                            isLast: index == n - 1,
                            isFake: game.steps.mode == .fake,
                            isRequesting: isRequesting,
                            parallax: d,
                            pictureShift: pw * 0.2,
                            onStart: { startGame() }
                        )
                        .frame(width: pw)
                        .padding(.vertical, 10)
                        // Карточка-бумажка: отъезжает, уменьшается, поворачивается «как лист на столе».
                        .scaleEffect(1 - 0.08 * min(ad, 1))
                        .rotation3DEffect(.degrees(Double(-d) * 14), axis: (x: 0, y: 1, z: 0), perspective: 0.6)
                        .rotationEffect(.degrees(Double(d) * 3.5))
                        .offset(x: d * pw * 0.92, y: ad * 18)
                        .opacity(1 - 0.45 * Double(min(ad, 1)))
                        .zIndex(Double(2 - ad))
                        .allowsHitTesting(index == pageIndex && ad < 0.3)
                        .accessibilityHidden(index != pageIndex)
                    }
                }
            }
            .frame(width: pw, height: g.size.height)
            .contentShape(Rectangle())
            .onAppear { pagerWidth = pw }
            .onChange(of: pw) { _, v in pagerWidth = v }
            .gesture(
                DragGesture(minimumDistance: 10)
                    .onChanged { v in
                        guard abs(v.translation.width) > abs(v.translation.height) * 0.8 || dragX != 0 else { return }
                        var t = v.translation.width
                        // Резинка на краях.
                        if (pageIndex == 0 && t > 0) || (pageIndex == n - 1 && t < 0) { t *= 0.3 }
                        dragX = t
                    }
                    .onEnded { v in
                        let predicted = v.predictedEndTranslation.width
                        var target = pageIndex
                        if dragX < -pw * 0.25 || predicted < -pw * 0.5 { target += 1 }
                        if dragX > pw * 0.25 || predicted > pw * 0.5 { target -= 1 }
                        target = min(max(target, 0), n - 1)
                        withAnimation(.spring(response: 0.55, dampingFraction: 0.78)) {
                            page = target
                            dragX = 0
                        }
                    }
            )
            .accessibilityAdjustableAction { dir in
                withAnimation(.spring(response: 0.55, dampingFraction: 0.8)) {
                    switch dir {
                    case .increment: page = min(pageIndex + 1, n - 1)
                    case .decrement: page = max(pageIndex - 1, 0)
                    default: break
                    }
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private var footer: some View {
        VStack(spacing: 10) {
            HStack(spacing: 9) {
                ForEach(0..<cards.count, id: \.self) { i in
                    Capsule()
                        .fill(i == indicatorIndex ? Theme.waxRed : Theme.paper.opacity(0.4))
                        .frame(width: 8 + 14 * max(0, 1 - abs(CGFloat(i) - progress)), height: 8)
                        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: indicatorIndex)
                }
            }
            .accessibilityLabel("Страница \(pageIndex + 1) из \(cards.count)")

            if pageIndex < cards.count - 1 {
                Text("листай дальше →")
                    .font(Ink.label(13))
                    .foregroundStyle(Theme.paper.opacity(0.65))
            } else {
                Text("доступ можно изменить позже в настройках")
                    .font(.footnote)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Theme.paper.opacity(0.7))
            }
        }
        .padding(.top, 4)
    }

    private func startGame() {
        guard !isRequesting else { return }
        isRequesting = true
        Task {
            await game.completeOnboarding()
            isRequesting = false
        }
    }
}

// MARK: - Card model

private struct OnboardCard: Identifiable {
    let id: Int
    let title: String
    let body: String
    let imagePath: String?
    var overlayPath: String? = nil
    /// Фон под «стоячей» фигурой (почтальон), если imageFit.
    var backdropPath: String? = nil
    /// Рисовать imagePath целиком (fit), а не crop fill.
    var imageFit = false

    static func all(fake: Bool) -> [OnboardCard] {
        [
            OnboardCard(
                id: 0,
                title: "Долина опустела",
                body: "Ты — последний почтальон. Письма — единственная нитка между оставшимися жителями пластилиновой Долины. Впереди дорога: от Почты через Сваи, Звонарню и Кадушки до Седла.",
                imagePath: "Chapter1/places/place_pochta_main"
            ),
            OnboardCard(
                id: 1,
                title: "Шаги — это путь",
                body: "Клади телефон в карман и иди. Каждый реальный шаг двигает почтальона по дороге. Глава первая — около 20 тысяч шагов; вся игра — около 150 тысяч.",
                imagePath: "UI/map/postman",
                backdropPath: "Chapter1/places/place_svai_main",
                imageFit: true
            ),
            OnboardCard(
                id: 2,
                title: "Пока ты гуляешь",
                body: "История не ждёт у экрана. Почтальон доходит до остановок сам. Тебе приходят тихие уведомления: кто встретился, что случилось, какое письмо вручили.",
                imagePath: "Chapter1/places/place_zvonarnya_main",
                overlayPath: "UI/ch1/env_plain"
            ),
            OnboardCard(
                id: 3,
                title: "Вернёшься — прочитаешь",
                body: "В журнале — карточки мест и жителей: что случилось без тебя. Иногда на развилке выбираешь ты — и сюжет повернёт.",
                imagePath: "Chapter1/places/place_kadushki_main",
                overlayPath: "UI/ch1/card_telegram"
            ),
            OnboardCard(
                id: 4,
                title: "Чтобы он шёл с тобой",
                body: fake
                    ? "На симуляторе HealthKit недоступен — шаги добавляются кнопкой «+500». На устройстве игра попросит чтение шагов и уведомления; геолокацию для погоды — мягко, от неё можно отказаться."
                    : "Нужен доступ к шагам из «Здоровья» и уведомлениям об остановках. Шаги только читаем, ничего не записываем. Погоду подстроим под твою: система может спросить геолокацию; без неё будет сезонная.",
                imagePath: "UI/ch1/btn_postman",
                overlayPath: "UI/ch1/env_wax"
            ),
        ]
    }
}

// MARK: - Card view

private struct OnboardCardView: View {
    let card: OnboardCard
    let isLast: Bool
    let isFake: Bool
    let isRequesting: Bool
    /// Дистанция до текущей страницы (index - progress), для параллакса картинки.
    var parallax: CGFloat = 0
    /// Макс. сдвиг слоя картинки внутри рамки, px.
    var pictureShift: CGFloat = 70
    let onStart: () -> Void

    private var imgX: CGFloat { -parallax * pictureShift }

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 4)
            ViewThatFits(in: .vertical) {
                cardContent
                ScrollView(.vertical, showsIndicators: false) { cardContent }
            }
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(Theme.paper)
                    .shadow(color: .black.opacity(0.4), radius: 10, x: 0, y: 6)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(Theme.paperEdge, lineWidth: 1.5)
            )
            .padding(.horizontal, 10)
            .rotationEffect(.degrees(card.id % 2 == 0 ? -0.6 : 0.7))
            Spacer(minLength: 4)
        }
        .accessibilityElement(children: .contain)
    }

    private var cardContent: some View {
        VStack(alignment: .leading, spacing: 14) {
            picture
            Text(card.title)
                .font(Ink.title(26))
                .foregroundStyle(Ink.brown)
                .fixedSize(horizontal: false, vertical: true)
            Text(card.body)
                .font(Ink.label(16))
                .foregroundStyle(Ink.pencil)
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(3)

            if isLast {
                permissionsNote
                startButton
            }
        }
        .padding(18)
    }

    private var picture: some View {
        let h: CGFloat = 220
        return ZStack(alignment: .bottom) {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.78, green: 0.70, blue: 0.52),
                            Color(red: 0.62, green: 0.55, blue: 0.38),
                        ],
                        startPoint: .top, endPoint: .bottom
                    )
                )
            if let backdrop = card.backdropPath {
                Image(uiImage: OnboardArt.image(backdrop, maxWidth: 720))
                    .resizable()
                    .interpolation(.high)
                    .scaledToFill()
                    .frame(maxWidth: .infinity, maxHeight: h)
                    .scaleEffect(1.5)
                    .offset(x: imgX)
                    .opacity(0.85)
            }
            if let path = card.imagePath {
                if card.imageFit {
                    Image(uiImage: OnboardArt.image(path, maxWidth: 320))
                        .resizable()
                        .interpolation(.high)
                        .scaledToFit()
                        .frame(height: h * 0.92)
                        .shadow(color: .black.opacity(0.35), radius: 6, x: 3, y: 4)
                        .padding(.bottom, 4)
                        .frame(maxWidth: .infinity)
                        .offset(x: -imgX * 0.8)
                } else {
                    Image(uiImage: OnboardArt.image(path, maxWidth: 720))
                        .resizable()
                        .interpolation(.high)
                        .scaledToFill()
                        .frame(maxWidth: .infinity, maxHeight: h)
                        .scaleEffect(1.5)
                        .offset(x: imgX)
                }
            }
            if let overlay = card.overlayPath {
                HStack {
                    Spacer()
                    Image(uiImage: OnboardArt.image(overlay, maxWidth: 220))
                        .resizable()
                        .interpolation(.high)
                        .scaledToFit()
                        .frame(width: 72)
                        .rotationEffect(.degrees(8 + Double(parallax) * 18))
                        .offset(x: -imgX * 1.3)
                        .shadow(color: .black.opacity(0.35), radius: 4, x: 2, y: 3)
                        .padding(.trailing, 14)
                        .padding(.bottom, 10)
                        .frame(maxHeight: .infinity, alignment: .bottomTrailing)
                }
            }
        }
        .frame(height: h)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(Ink.brown.opacity(0.35), lineWidth: 1.5)
        )
        .accessibilityHidden(true)
    }

    private var permissionsNote: some View {
        VStack(alignment: .leading, spacing: 6) {
            labelRow(icon: "figure.walk", text: isFake ? "Шаги: тестовый режим" : "Шаги из «Здоровья»")
            labelRow(icon: "bell.fill", text: "Уведомления об остановках")
            labelRow(icon: "cloud.sun.fill", text: "Геолокация для погоды — по желанию")
        }
        .font(Ink.label(13))
        .foregroundStyle(Ink.brown.opacity(0.85))
        .padding(.top, 2)
    }

    private func labelRow(icon: String, text: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.brick)
                .frame(width: 18)
            Text(text)
        }
    }

    private var startButton: some View {
        Button(action: onStart) {
            HStack(spacing: 10) {
                if isRequesting { ProgressView().tint(Theme.paper) }
                Text(isFake ? "Начать" : "Разрешить и начать")
                    .font(Ink.title(18))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .foregroundStyle(Theme.paper)
            .background(Theme.brick, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .shadow(color: .black.opacity(0.25), radius: 4, y: 2)
        }
        .buttonStyle(PressStyle())
        .disabled(isRequesting)
        .padding(.top, 4)
        .accessibilityHint("Запросит доступ к шагам, уведомлениям и при необходимости геолокации")
    }
}

// MARK: - Parallax tile strip

/// Горизонтальная бесшовная лента из тайла фона; сдвигается с параллакс-коэффициентом.
/// Позиционирование через floor-базу — без скачка на границах tileW и при отрицательном shift.
private struct OnboardTileStrip: View {
    let path: String
    let height: CGFloat
    let shift: CGFloat
    let viewportWidth: CGFloat
    var opacity: Double = 1
    /// Зеркалить каждый второй тайл (для травы).
    var flipAlternate: Bool = false

    var body: some View {
        let img = OnboardArt.image(path, maxWidth: 1400)
        let aspect = img.size.height > 0 ? img.size.width / img.size.height : 2.5
        // Для зеркальной травы не раздуваем тайл до ширины экрана — иначе паттерн редкий.
        let tileW = flipAlternate
            ? max(height * aspect, 1)
            : max(height * aspect, viewportWidth * 0.9)
        // База на ближайший меньший кратный tileW — непрерывный скролл без modulo-скачка.
        let base = floor(shift / tileW) * tileW
        let baseIndex = Int(floor(shift / tileW))
        let count = max(6, Int(ceil(viewportWidth / tileW)) + 3)
        return HStack(spacing: 0) {
            ForEach(0..<count, id: \.self) { i in
                // Мировой индекс тайла — чтобы flip не скакал при смене base.
                let worldIndex = baseIndex - 1 + i
                let flipped = flipAlternate && ((worldIndex % 2) + 2) % 2 == 1
                Image(uiImage: img)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFill()
                    .frame(width: tileW, height: height)
                    .clipped()
                    .scaleEffect(x: flipped ? -1 : 1, y: 1)
            }
        }
        // Лента стартует в base - tileW, общий offset = -shift → гладко на любом shift.
        .offset(x: (base - tileW) - shift)
        .frame(width: viewportWidth, height: height, alignment: .leading)
        .clipped()
        .opacity(opacity)
        .allowsHitTesting(false)
    }
}

// MARK: - Assets / scroll

private enum OnboardArt {
    private static var cache: [String: UIImage] = [:]

    static func image(_ relativePath: String, maxWidth: CGFloat) -> UIImage {
        let key = "\(relativePath)#\(Int(maxWidth))"
        if let cached = cache[key] { return cached }
        let url = WorldConfigLoader.assetsRoot.appendingPathComponent(relativePath + ".png")
        guard let full = UIImage(contentsOfFile: url.path) else {
            cache[key] = UIImage()
            return UIImage()
        }
        let out: UIImage
        if full.size.width > maxWidth {
            let s = maxWidth / full.size.width
            out = full.preparingThumbnail(of: CGSize(width: maxWidth, height: full.size.height * s)) ?? full
        } else {
            out = full
        }
        cache[key] = out
        return out
    }
}
