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

    var body: some View {
        Group {
            if game.onboardingDone {
                GameView()
            } else {
                OnboardingView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: game.onboardingDone)
    }
}
