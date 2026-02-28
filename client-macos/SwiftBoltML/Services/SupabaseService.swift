import Supabase

/// Singleton wrapper around the Supabase Swift SDK client.
/// Provides a single shared instance used throughout the app.
public class SupabaseService {
    /// Shared singleton instance
    public static let shared = SupabaseService()

    /// The underlying `SupabaseClient` from the SDK.
    public let client: SupabaseClient

    private init() {
        // The Config struct already exposes the URL and anon key via environment or Keychain.
        let url = Config.supabaseURL
        let anonKey = Config.supabaseAnonKey
        client = SupabaseClient(url: url, anonKey: anonKey)
    }
}
