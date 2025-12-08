import SwiftUI

struct DevToolsView: View {
    @State private var showSecrets = false
    @State private var keychainValues: [SecretItem] = []

    private struct SecretItem: Identifiable {
        let id = UUID()
        let label: String
        let key: String
        let value: String?
    }

    var body: some View {
        List {
            Section("Keychain values") {
                if keychainValues.isEmpty {
                    Text("No keys found (load to refresh).")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(keychainValues) { item in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.label).font(.headline)
                            Text(display(item.value))
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                }
                Button("Reload from Keychain", action: loadKeychain)
            }

            Section {
                Toggle("Show secret values (masked when off)", isOn: $showSecrets)
            }
        }
        .navigationTitle("Dev Tools")
        .onAppear(perform: loadKeychain)
    }

    private func display(_ value: String?) -> String {
        guard let value else { return "<nil>" }
        return showSecrets ? value : String(repeating: "•", count: min(value.count, 12))
    }

    private func loadKeychain() {
        keychainValues = [
            SecretItem(label: "Massive API Key", key: "MASSIVE_API_KEY", value: KeychainService.load("MASSIVE_API_KEY")),
            SecretItem(label: "Massive Secret Key", key: "MASSIVE_SECRET_KEY", value: KeychainService.load("MASSIVE_SECRET_KEY")),
            SecretItem(label: "Finnhub API Key", key: "FINNHUB_API_KEY", value: KeychainService.load("FINNHUB_API_KEY")),
            SecretItem(label: "Finnhub Secret ID", key: "FINNHUB_SECRET_ID", value: KeychainService.load("FINNHUB_SECRET_ID")),
            SecretItem(label: "Supabase URL", key: "SUPABASE_URL", value: KeychainService.load("SUPABASE_URL")),
            SecretItem(label: "Supabase Anon Key", key: "SUPABASE_ANON_KEY", value: KeychainService.load("SUPABASE_ANON_KEY"))
        ]
    }
}

#Preview {
    NavigationStack {
        DevToolsView()
    }
}
