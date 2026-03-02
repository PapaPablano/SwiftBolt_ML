import SwiftUI

@main
struct SwiftBoltMLApp: App {
    @State private var authController = AuthController()

    var body: some Scene {
        WindowGroup {
            Group {
                if authController.isAuthenticated {
                    ContentView()
                } else {
                    LoginView()
                }
            }
            .environment(authController)
            .task {
                authController.startListening()
            }
        }
        .windowStyle(.automatic)
        .defaultSize(width: 1400, height: 900)
        .commands {
            CommandGroup(after: .appInfo) {
                #if DEBUG
                Button("Dev Tools...") {
                    openDevTools()
                }
                .keyboardShortcut("D", modifiers: [.command, .shift])
                #endif
            }
        }

        #if DEBUG
        Window("Dev Tools", id: "dev-tools") {
            DevToolsView()
        }
        .defaultSize(width: 500, height: 400)
        #endif
    }

    private func openDevTools() {
        #if DEBUG
        if let url = URL(string: "swiftboltml://dev-tools") {
            NSWorkspace.shared.open(url)
        }
        #endif
    }
}
