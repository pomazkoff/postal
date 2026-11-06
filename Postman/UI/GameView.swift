import SwiftUI
import SpriteKit

/// Главный экран: лента SpriteKit на весь экран + HUD поверх.
struct GameView: View {
    @EnvironmentObject private var game: GameModel

    var body: some View {
        ZStack {
            SpriteView(scene: game.scene, preferredFramesPerSecond: 60)
                .ignoresSafeArea()
            HUDView()
                .environmentObject(game.engine)
        }
        .statusBarHidden(true)
    }
}
