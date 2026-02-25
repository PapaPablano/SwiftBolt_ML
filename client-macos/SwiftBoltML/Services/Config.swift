import Foundation

class Config {
    static let shared = Config()
    
    private let supabaseURLKey = "SUPABASE_URL"
    private let supabaseAnonKeyKey = "SUPABASE_ANON_KEY"
    private let fastAPIURLKey = "FASTAPI_URL"
    private var cachedSupabaseURL: URL?
    private var cachedSupabaseAnonKey: String?
    private var cachedFastAPIURL: URL?

    private init() {}
    
    // Static convenience accessors for use as Config.supabaseURL (delegates to shared instance)
    static var supabaseURL: URL { shared.supabaseURL }
    static var supabaseAnonKey: String { shared.supabaseAnonKey }
    static var fastAPIURL: URL { shared.fastAPIURL }
    static var functionsBaseURL: URL { shared.functionsBaseURL }
    static var ensureCoverageEnabled: Bool { shared.ensureCoverageEnabled }
    static func functionURL(_ name: String) -> URL { shared.functionURL(name) }
    
    var supabaseURL: URL {
        if let cachedSupabaseURL {
            return cachedSupabaseURL
        }

        // First check if we have a valid URL in environment
        if let envValue = ProcessInfo.processInfo.environment[supabaseURLKey],
           !envValue.isEmpty,
           let url = URL(string: envValue) {
            cachedSupabaseURL = url
            return url
        }

        // If no environment value, try to get from keychain or plist as fallback
        let rawValue = loadOrStoreConfigValue(for: supabaseURLKey)
        guard let url = URL(string: rawValue) else {
            fatalError("Invalid SUPABASE_URL: \(rawValue)")
        }

        cachedSupabaseURL = url
        return url
    }

    var supabaseAnonKey: String {
        if let cachedSupabaseAnonKey {
            return cachedSupabaseAnonKey
        }

        // First check if we have a valid key in environment
        if let envValue = ProcessInfo.processInfo.environment[supabaseAnonKeyKey],
           !envValue.isEmpty {
            cachedSupabaseAnonKey = envValue
            return envValue
        }

        // If no environment value, try to get from keychain or plist as fallback
        let key = loadOrStoreConfigValue(for: supabaseAnonKeyKey)
        cachedSupabaseAnonKey = key
        return key
    }

    var fastAPIURL: URL {
        if let cachedFastAPIURL {
            return cachedFastAPIURL
        }

        // First check if we have a valid URL in environment
        if let envValue = ProcessInfo.processInfo.environment[fastAPIURLKey],
           !envValue.isEmpty,
           let url = URL(string: envValue) {
            cachedFastAPIURL = url
            return url
        }

        // If no environment value, try to get from keychain or plist as fallback
        let rawValue = loadOrStoreConfigValue(for: fastAPIURLKey)
        guard let url = URL(string: rawValue) else {
            fatalError("Invalid FASTAPI_URL: \(rawValue)")
        }

        cachedFastAPIURL = url
        return url
    }
    
    // ✅ Single source of truth for all Edge Function calls
    var functionsBaseURL: URL {
        supabaseURL.appendingPathComponent("functions/v1")
    }
    
    // Convenience helper for building function URLs
    func functionURL(_ name: String) -> URL {
        functionsBaseURL.appendingPathComponent(name)
    }
    
    // Feature flags
    let ensureCoverageEnabled = false  // SPEC-8 orchestrator DISABLED

    private func loadOrStoreConfigValue(for key: String) -> String {
        if let stored = KeychainService.load(key) {
            return stored
        }

        guard let plistValue = Bundle.main.object(forInfoDictionaryKey: key) as? String,
              !plistValue.isEmpty else {
            fatalError("Missing \(key) in Info.plist and Keychain")
        }

        KeychainService.save(key, value: plistValue)
        return plistValue
    }
}
