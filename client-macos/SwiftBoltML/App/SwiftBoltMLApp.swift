import SwiftUI

@main
struct SwiftBoltMLApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Dev Tools...") {
                    openDevTools()
                }
                .keyboardShortcut("D", modifiers: [.command, .shift])
            }
        }

        #if DEBUG
        Window("Dev Tools", id: "dev-tools") {
            DevToolsView()
        }
        #endif
    }

    private func openDevTools() {
        #if DEBUG
        NSWorkspace.shared.open(URL(string: "swiftboltml://dev-tools")!)
        #endif
    }
}
