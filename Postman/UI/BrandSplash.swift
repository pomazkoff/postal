import SwiftUI

/// Короткий показ логотипа при холодном запуске. Состояние только в памяти вью:
/// возврат из фона его не сбрасывает и второй раз не показывает.
struct BrandSplash: View {
    var onFinished: () -> Void
    @State private var opacity: Double = 0
    @State private var started = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            Image("MazkofGamesLogo")
                .resizable()
                .renderingMode(.original)
                .scaledToFit()
                .padding(.horizontal, 28)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityHidden(true)
        }
        .opacity(opacity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Mazkof Games")
        .onAppear(perform: playOnce)
    }

    private func playOnce() {
        guard !started else { return }
        started = true
        withAnimation(.easeIn(duration: 0.25)) { opacity = 1 }
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 900_000_000)
            withAnimation(.easeOut(duration: 0.35)) { opacity = 0 }
            try? await Task.sleep(nanoseconds: 350_000_000)
            onFinished()
        }
    }
}
