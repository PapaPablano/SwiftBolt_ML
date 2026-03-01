import Foundation
import Supabase

// MARK: - Ephemeral Auth Storage

/// A no-op `AuthLocalStorage` adapter.
///
/// This app uses the anon key only and has no user login flow.
/// Passing this to `SupabaseClientOptions.auth.storage` prevents the SDK from
/// reading or writing any session to Keychain, eliminating the stale-JWT 401
/// cascade that occurs when a dev session persists across app launches.
private final class EphemeralAuthStorage: AuthLocalStorage, @unchecked Sendable {
    func store(key: String, value: Data) throws {}    // intentional no-op
    func retrieve(key: String) throws -> Data? { nil }
    func remove(key: String) throws {}               // intentional no-op
}

// MARK: - Supabase Service

/// Singleton wrapper around the Supabase Swift SDK client.
/// Provides a single shared instance used throughout the app.
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
                    storage: EphemeralAuthStorage(),
                    autoRefreshToken: false   // no user session to refresh
                )
            )
        )
    }
}
