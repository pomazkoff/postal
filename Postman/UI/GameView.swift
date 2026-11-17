import SwiftUI
import SpriteKit

/// Главный экран: лента SpriteKit на весь экран + HUD поверх.
struct GameView: View {
    @EnvironmentObject private var game: GameModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            SpriteView(scene: game.scene, preferredFramesPerSecond: 60)
                .ignoresSafeArea()
                .blur(radius: game.roadMenuOpen ? 18 : 0)
                .animation(reduceMotion ? .none : .easeInOut(duration: 0.22), value: game.roadMenuOpen)
            HUDView()
                .environmentObject(game.engine)
        }
        .statusBarHidden(true)
    }
}
