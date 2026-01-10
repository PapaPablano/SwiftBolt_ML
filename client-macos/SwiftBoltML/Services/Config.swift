import Foundation

enum Config {
    static let supabaseURL = URL(string: "https://cygflaemtmwiwaviclks.supabase.co")!

    // TODO: Move to Keychain for production
    static let supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"
    
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
}
