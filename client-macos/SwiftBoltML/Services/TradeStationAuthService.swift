import Foundation
import CryptoKit
import AuthenticationServices

struct TradeStationTokens: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let tokenType: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case tokenType = "token_type"
    }
}

struct TradeStationAuthStatus: Codable {
    let connected: Bool
    let expired: Bool
}

@MainActor
class TradeStationAuthService: NSObject, ObservableObject {
    static let shared = TradeStationAuthService()
    
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var error: String?
    @Published var authURL: URL?
    
    // Add a completion handler for when authentication is complete
    private var onAuthComplete: ((Bool) -> Void)?
    
    private let clientId = "x3IYfpnSYevmXREQuW34LJUyeXaHBK"
    private let redirectURI = "swiftbolt://oauth/callback"
    private let scopes = "openid+MarketData+Trade+offline_access"
    private let authBaseURL = "https://signin.tradestation.com/authorize"
    private let tokenURL = "https://signin.tradestation.com/oauth/token"
    
    private var codeVerifier: String = ""
    private var codeChallenge: String = ""
    private weak var authSession: ASWebAuthenticationSession?
    
    private let keychainKey = "tradestation_tokens"
    
    override init() {
        super.init()
        checkAuthStatus()
    }
    
    func generatePKCE() -> (verifier: String, challenge: String) {
        var buffer = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, buffer.count, &buffer)
        let verifier = Data(buffer).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        
        let verifierData = Data(verifier.utf8)
        let hash = SHA256.hash(data: verifierData)
        let challenge = Data(hash).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        
        return (verifier, challenge)
    }
    
    func startOAuthFlow(completion: @escaping (Bool) -> Void = { _ in }) {
        // Set up completion handler
        self.onAuthComplete = completion
        
        let (verifier, challenge) = generatePKCE()
        self.codeVerifier = verifier
        
        var components = URLComponents(string: authBaseURL)!
        components.queryItems = [
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "code_challenge", value: challenge),
            URLQueryItem(name: "code_challenge_method", value: "S256"),
            URLQueryItem(name: "redirect_uri", value: redirectURI),
            URLQueryItem(name: "scope", value: scopes)
        ]
        
        self.authURL = components.url
        
        guard let url = components.url else {
            self.error = "Failed to create auth URL"
            onAuthComplete?(false)
            return
        }
        
        let session = ASWebAuthenticationSession(
            url: url,
            callbackURLScheme: "swiftbolt"
        ) { [weak self] callbackURL, error in
            guard let self = self else { return }
            
            if let error = error {
                if (error as NSError).code == ASWebAuthenticationSessionError.canceledLogin.rawValue {
                    self.error = "Login cancelled"
                } else {
                    self.error = error.localizedDescription
                }
                self.onAuthComplete?(false)
                return
            }
            
            guard let callbackURL = callbackURL,
                  let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false),
                  let code = components.queryItems?.first(where: { $0.name == "code" })?.value else {
                self.error = "No authorization code received"
                self.onAuthComplete?(false)
                return
            }
            
            Task { @MainActor in
                await self.exchangeCodeForTokens(code: code)
            }
        }
        
        self.authSession = session
        session.presentationContextProvider = self
        session.start()
    }
    
    func exchangeCodeForTokens(code: String) async {
        isLoading = true
        error = nil
        
        var request = URLRequest(url: URL(string: tokenURL)!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = [
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirectURI,
            "client_id": clientId,
            "code_verifier": codeVerifier
        ]
        
        request.httpBody = body.map { "\($0.key)=\($0.value)" }
            .joined(separator: "&")
            .data(using: .utf8)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw NSError(domain: "TradeStation", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
            }
            
            if httpResponse.statusCode != 200 {
                if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let errorDesc = errorData["error_description"] as? String {
                    throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: errorDesc])
                }
                throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Token exchange failed"])
            }
            
            let tokens = try JSONDecoder().decode(TradeStationTokens.self, from: data)
            try saveTokens(tokens)
            isAuthenticated = true
            
            // Notify completion
            onAuthComplete?(true)
            
        } catch {
            self.error = error.localizedDescription
            onAuthComplete?(false)
        }
        
        isLoading = false
    }
    
    func refreshTokenIfNeeded() async {
        guard let tokens = loadTokens() else {
            isAuthenticated = false
            return
        }
        
        isLoading = true
        
        var request = URLRequest(url: URL(string: tokenURL)!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = [
            "grant_type": "refresh_token",
            "refresh_token": tokens.refreshToken,
            "client_id": clientId
        ]
        
        request.httpBody = body.map { "\($0.key)=\($0.value)" }
            .joined(separator: "&")
            .data(using: .utf8)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                try? deleteTokens()
                isAuthenticated = false
                return
            }
            
            let newTokens = try JSONDecoder().decode(TradeStationTokens.self, from: data)
            try saveTokens(newTokens)
            isAuthenticated = true
            
        } catch {
            try? deleteTokens()
            isAuthenticated = false
        }
        
        isLoading = false
    }
    
    func checkAuthStatus() {
        guard let _ = loadTokens() else {  // Fixed: used underscore for unused variable
            isAuthenticated = false
            return
        }
        
        Task {
            await refreshTokenIfNeeded()
        }
    }
    
    func logout() {
        try? deleteTokens()
        isAuthenticated = false
    }
    
    private func saveTokens(_ tokens: TradeStationTokens) throws {
        let data = try JSONEncoder().encode(tokens)
        guard let string = String(data: data, encoding: .utf8) else { return }
        KeychainService.save(keychainKey, value: string)
    }
    
    func loadTokens() -> TradeStationTokens? {
        guard let string = KeychainService.load(keychainKey),
              let data = string.data(using: .utf8) else {
            return nil
        }
        return try? JSONDecoder().decode(TradeStationTokens.self, from: data)
    }
    
    private func deleteTokens() throws {
        KeychainService.delete(keychainKey)
    }
}

extension TradeStationAuthService: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        return ASPresentationAnchor()
    }
}