import SwiftUI

/// Короткий показ при холодном запуске. Мазок и слово — один холст 1080×1920,
/// одни и те же рамки, поэтому буква не съезжает с глины.
/// Флаг только в памяти: возврат из фона экран не повторяет.
struct BrandSplash: View {
    var onFinished: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var started = false
    /// 0…1 — мягкий край мазка уезжает за правый край кадра. Сама картинка не двигается.
    @State private var brushReveal: CGFloat = 0
    @State private var wordmarkOpacity: Double = 0
    @State private var screenOpacity: Double = 1

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            ZStack {
                fitted("MazkofGamesBrush")
                    .mask { brushMask }
                fitted("MazkofGamesWordmark")
                    .opacity(wordmarkOpacity)
            }
        }
        .opacity(screenOpacity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Mazkof Games")
        .onAppear(perform: playOnce)
    }

    private func fitted(_ name: String) -> some View {
        Image(name)
            .resizable()
            .renderingMode(.original)
            .interpolation(.high)
            .scaledToFit()
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .accessibilityHidden(true)
    }

    /// Белое в маске видно. Мягкий край идёт слева направо и в конце уходит за кадр.
    /// Рамка картинки не меняется.
    private var brushMask: some View {
        GeometryReader { geo in
            let feather = geo.size.width * 0.1
            let shown = brushReveal * (geo.size.width + feather)
            HStack(spacing: 0) {
                Rectangle()
                    .fill(Color.white)
                    .frame(width: max(0, shown - feather))
                LinearGradient(
                    colors: [.white, .clear],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(width: feather)
                .opacity(shown > 0 ? 1 : 0)
            }
            .frame(width: geo.size.width, height: geo.size.height, alignment: .leading)
            .clipped()
        }
    }

    private func playOnce() {
        guard !started else { return }
        started = true
        if reduceMotion {
            brushReveal = 1
            wordmarkOpacity = 0
            screenOpacity = 0
            withAnimation(.easeIn(duration: 0.35)) {
                wordmarkOpacity = 1
                screenOpacity = 1
            }
        } else {
            brushReveal = -0.08
            wordmarkOpacity = 0
            screenOpacity = 1
            withAnimation(.easeInOut(duration: 0.55)) { brushReveal = 1 }
        }
        Task { @MainActor in
            if reduceMotion {
                try? await Task.sleep(nanoseconds: 1_050_000_000)
            } else {
                try? await Task.sleep(nanoseconds: 550_000_000)
                withAnimation(.easeIn(duration: 0.28)) { wordmarkOpacity = 1 }
                try? await Task.sleep(nanoseconds: 830_000_000)
            }
            withAnimation(.easeOut(duration: 0.35)) { screenOpacity = 0 }
            try? await Task.sleep(nanoseconds: 350_000_000)
            onFinished()
        }
    }
}
