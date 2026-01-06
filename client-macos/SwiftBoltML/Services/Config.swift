import Foundation

enum Config {
    static let supabaseURL = "https://cygflaemtmwiwaviclks.supabase.co/functions/v1"

    // TODO: Move to Keychain for production
    static let supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"
    
    // Feature flags
    static let ensureCoverageEnabled = false  // Enable once ensure-coverage function is deployed
}
