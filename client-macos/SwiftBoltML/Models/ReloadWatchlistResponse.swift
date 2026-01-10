import Foundation

struct ReloadWatchlistResponse: Codable {
    let success: Bool
    let message: String
    let summary: Summary
    let results: [SymbolResult]
    
    struct Summary: Codable {
        let total: Int
        let success: Int
        let errors: Int
    }
    
    struct SymbolResult: Codable {
        let symbol: String
        let status: String
        let message: String?
        let barsLoaded: BarsLoaded?
        
        struct BarsLoaded: Codable {
            let m15: Int?
            let h1: Int?
            let h4: Int?
            let d1: Int?
            let w1: Int?
        }
    }
}
