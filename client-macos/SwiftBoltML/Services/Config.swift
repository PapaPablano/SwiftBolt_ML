import Foundation

enum Config {
    private static let supabaseURLKey = "SUPABASE_URL"
    private static let supabaseAnonKeyKey = "SUPABASE_ANON_KEY"
    private static var cachedSupabaseURL: URL?
    private static var cachedSupabaseAnonKey: String?

    static var supabaseURL: URL {
        if let cachedSupabaseURL {
            return cachedSupabaseURL
        }

        let rawValue = loadOrStoreConfigValue(for: supabaseURLKey)
        guard let url = URL(string: rawValue) else {
            fatalError("Invalid SUPABASE_URL: \(rawValue)")
        }

        cachedSupabaseURL = url
        return url
    }

    static var supabaseAnonKey: String {
        if let cachedSupabaseAnonKey {
            return cachedSupabaseAnonKey
        }

        let key = loadOrStoreConfigValue(for: supabaseAnonKeyKey)
        cachedSupabaseAnonKey = key
        return key
    }
    
    // ✅ Single source of truth for all Edge Function calls
    static var functionsBaseURL: URL {
        supabaseURL.appendingPathComponent("functions/v1")
    }
    
    // Convenience helper for building function URLs
    static func functionURL(_ name: String) -> URL {
        functionsBaseURL.appendingPathComponent(name)
    }
    
    // Feature flags
    static let ensureCoverageEnabled = false  // SPEC-8 orchestrator DISABLED

    private static func loadOrStoreConfigValue(for key: String) -> String {
        if let stored = KeychainService.load(key) {
            return stored
        }

        guard let plistValue = Bundle.main.object(forInfoDictionaryKey: key) as? String,
              !plistValue.isEmpty else {
            fatalError("Missing \(key) in Info.plist and Keychain")
        }

        _ = KeychainService.save(key, value: plistValue)
        return plistValue
    }
}
