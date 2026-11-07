import SwiftUI

@main
struct PostmanApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var game = GameModel()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        HUDFonts.registerAll()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(game)
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active: game.appBecameActive()
            case .background: game.appWentToBackground()
            default: break
            }
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var game: GameModel
    /// Один показ на жизнь процесса. В UserDefaults не пишется.
    @State private var brandSplashDone = false

    var body: some View {
        Group {
            if !brandSplashDone {
                BrandSplash { brandSplashDone = true }
            } else if game.onboardingDone {
                GameView()
            } else {
                OnboardingView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: game.onboardingDone)
    }
}
