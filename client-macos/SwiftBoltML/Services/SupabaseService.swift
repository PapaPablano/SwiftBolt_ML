import Foundation
import Supabase

// MARK: - Supabase Service

/// Singleton wrapper around the Supabase Swift SDK client.
/// Provides a single shared instance used throughout the app.
/// Sessions persist to Keychain by default and auto-refresh.
final class SupabaseService {
    /// Shared singleton instance.
    static let shared = SupabaseService()

    /// The underlying `SupabaseClient` from the SDK.
    let client: SupabaseClient

    private init() {
        let url = Config.supabaseURL
        let anonKey = Config.supabaseAnonKey
        client = SupabaseClient(
            supabaseURL: url,
            supabaseKey: anonKey,
            options: SupabaseClientOptions(
                auth: .init(
                    autoRefreshToken: true
                )
            )
        )
    }
}
