import SwiftUI

/// Карманные часы-шагомер по ui/v3 — пластилиновый арт (GameAssets/UI/watch_*.png) + живые цифры.
/// Свёрнуто: закрытые часы на нитке, в окошке — шаги сегодня.
/// Раскрыто: часы с откинутой крышкой, «сегодня» крупно и сабциферблат «всего».
/// Вьюха занимает весь экран (координаты макета 1170×2532 → FrameMapper), тап ловит только корпус.
struct PocketWatchView: View {
    let state: HUDLayout.WatchState
    let mapper: FrameMapper
    let today: Int
    let total: Int
    let expanded: Bool
    let onTap: () -> Void
    /// Скрытый жест: долгое нажатие (StoryReset.holdSeconds) — «Сбросить историю».
    var onLongPress: (() -> Void)? = nil

    private static let ink = Color(red: 34 / 255, green: 20 / 255, blue: 12 / 255)
    private static let labelInk = Color(red: 70 / 255, green: 40 / 255, blue: 22 / 255)
    private static let rimLight = Color(red: 1.0, green: 200 / 255, blue: 120 / 255)

    private var accessibilityText: String {
        expanded
            ? Format.watchExpanded(today: today, total: total)
            : Format.watchToday(today)
    }

    private var hintText: String {
        expanded ? L10n.text("watch.hint.collapse") : L10n.text("watch.hint.expand")
    }

    var body: some View {
        let m = mapper
        let bodyRect = state.body
        ZStack {
            halo(m)
            Image(uiImage: HUDImages.image(state.image))
                .resizable()
                .interpolation(.high)
                .frame(width: m.length(state.width), height: m.length(state.height))
                .position(m.center(x: state.x, y: state.y, width: state.width, height: state.height))
                .allowsHitTesting(false)

            if let todayLabelSpec = state.todayLabel {
                caption(spec: todayLabelSpec, string: L10n.text("watch.today"))
            }
            number(spec: state.today, string: Format.steps(today))
            if let totalLabelSpec = state.totalLabel {
                caption(spec: totalLabelSpec, string: L10n.text("watch.total"))
            }
            if let totalSpec = state.total {
                number(spec: totalSpec, string: Format.steps(total))
            }

            // зона тапа — только корпус часов
            Color.clear
                .contentShape(Rectangle())
                .frame(width: m.length(bodyRect[2]), height: m.length(bodyRect[3]))
                .position(m.center(x: bodyRect[0], y: bodyRect[1], width: bodyRect[2], height: bodyRect[3]))
                .onTapGesture(perform: onTap)
                .onLongPressGesture(minimumDuration: StoryReset.holdSeconds) { onLongPress?() }
                .accessibilityElement()
                .accessibilityLabel(Text(accessibilityText))
                .accessibilityHint(Text(hintText))
                .accessibilityAddTraits(.isButton)
        }
        .frame(width: m.size.width, height: m.size.height)
    }

    /// Тёплый ореол за часами = «живой, можно нажать» (в макете — screen-подсветка).
    private func halo(_ m: FrameMapper) -> some View {
        let r = m.length(state.halo.r) * 1.4
        let o = state.halo.opacity
        return Circle()
            .fill(RadialGradient(colors: [Self.rimLight.opacity(o), Self.rimLight.opacity(o * 0.55), Self.rimLight.opacity(0)],
                                 center: .center, startRadius: 0, endRadius: r))
            .frame(width: r * 2, height: r * 2)
            .position(m.point(state.halo.cx, state.halo.cy))
            .blendMode(.screen)
            .allowsHitTesting(false)
    }

    private func number(spec: HUDLayout.TextSpec, string: String) -> some View {
        text(spec: spec, string: string, color: Self.ink, opacity: 0.95)
    }

    private func caption(spec: HUDLayout.TextSpec, string: String) -> some View {
        text(spec: spec, string: string, color: Self.labelInk, opacity: 0.88)
    }

    private func text(spec: HUDLayout.TextSpec, string: String, color: Color, opacity: Double) -> some View {
        let m = mapper
        let squeeze = CGFloat(spec.squeezeX ?? 1)
        let width = m.length(spec.maxWidth ?? 600) / squeeze
        return Text(string)
            .font(HUDFonts.font(spec.font, size: m.length(spec.size), weight: spec.weight))
            .foregroundStyle(color.opacity(opacity))
            .lineLimit(1)
            .minimumScaleFactor(0.3)
            .frame(width: width)
            .fixedSize(horizontal: false, vertical: true)
            .scaleEffect(x: squeeze, y: 1)
            .rotationEffect(.degrees(spec.rotation ?? 0))
            .position(m.point(spec.cx, spec.lineCY))
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}
