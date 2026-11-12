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
                .onOpenURL { game.receiveFirstMail($0) }
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
        ZStack {
            Group {
                if !brandSplashDone {
                    BrandSplash { brandSplashDone = true }
                } else if game.onboardingDone {
                    GameView()
                } else {
                    OnboardingView()
                }
            }
            if FirstMailGate.shouldShow(splashDone: brandSplashDone,
                                        onboardingDone: game.onboardingDone,
                                        pending: game.firstMailPending) {
                FirstMailCard(reading: game.firstMailReading(), onContinue: game.dismissFirstMail)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: game.onboardingDone)
        .onAppear { game.pullFirstMailInbox() }
        .onChange(of: brandSplashDone) { _, _ in game.pullFirstMailInbox() }
        .onChange(of: game.onboardingDone) { _, _ in game.pullFirstMailInbox() }
    }
}
