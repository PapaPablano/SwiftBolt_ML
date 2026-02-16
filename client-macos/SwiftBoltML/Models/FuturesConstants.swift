import Foundation

/// Supported futures roots from Yahoo Finance backend
/// Must match backend SUPPORTED_ROOTS in ml/api/routers/futures.py
let supportedFuturesRoots = ["ES", "NQ", "GC", "CL", "ZC", "ZS", "ZW", "HE", "LE", "HG", "SI", "PL", "PA"]

/// Check if a ticker is a supported futures root
func isSupportedFuturesRoot(_ ticker: String) -> Bool {
    return supportedFuturesRoots.contains(ticker.uppercased())
}
