import Foundation
import Combine

final class TradeStationViewModel: ObservableObject {
    @Published var isAuthenticated: Bool = false
    @Published var lastError: String?
    
    private var apiClient: TradeStationAPIClient
    
    init() {
        let env = TradeStationConfig.environment
        self.apiClient = TradeStationAPIClient(
            baseURL: env.apiBaseURL,
            apiKey: TradeStationConfig.clientID,
            apiSecret: TradeStationConfig.clientSecret,
            redirectURI: TradeStationConfig.redirectURI
        )
    }
    
    func connect(presentingAnchor: ASPresentationAnchor) {
        TradeStationAuthService.shared.startOAuthFlow(
            presentingAnchor: presentingAnchor
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else {
                    return
                }
                
                switch result {
                case .success(let tokens):
                    self.apiClient.setAccessToken(tokens.accessToken, refreshToken: tokens.refreshToken)
                    self.isAuthenticated = true
                    self.lastError = nil
                    print("[TSVM] TradeStation auth success")
                    
                case .failure(let error):
                    self.isAuthenticated = false
                    // Handle the specific error for live trading not allowed
                    if error is TradeStationAuthError && error.localizedDescription == "liveTradingNotAllowed" {
                        self.lastError = "Live trading is not permitted in this environment. Please use SIM mode."
                    } else {
                        self.lastError = error.localizedDescription
                    }
                    print("[TSVM] TradeStation auth error: \(error)")
                }
            }
        }
    }
    
    func loadAccounts() {
        // Check if we're allowed to make live trading calls
        if TradeStationConfig.environment == .live && !TradeStationConfig.allowLiveTrading {
            print("[TSVM] Cannot load accounts: Live trading not allowed in this environment")
            return
        }
        
        apiClient.getAccounts { result in
            switch result {
            case .success(let accounts):
                print("[TSVM] Loaded accounts: \(accounts)")
            case .failure(let error):
                print("[TSVM] Failed to load accounts: \(error)")
            }
        }
    }
}