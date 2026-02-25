import Foundation
import AuthenticationServices
import Alamofire

enum TradeStationAuthError: Error {
    case unableToStartSession
    case missingCallbackURL
    case missingAuthorizationCode
    case invalidTokenResponse
    case liveTradingNotAllowed
}

final class TradeStationAuthService: NSObject {
    static let shared = TradeStationAuthService()
    
    private var authSession: ASWebAuthenticationSession?
    
    private override init() {}
    
    // MARK: - Public API
    
    /// Kick off OAuth login
    func startOAuthFlow(
        presentingAnchor: ASPresentationAnchor,
        completion: @escaping (Result<(accessToken: String, refreshToken: String?), Error>) -> Void
    ) {
        // Check if live trading is allowed
        if TradeStationConfig.environment == .live && !TradeStationConfig.allowLiveTrading {
            print("[TSAuth] Live trading is not allowed in this environment")
            completion(.failure(TradeStationAuthError.liveTradingNotAllowed))
            return
        }
        
        let authURL = buildAuthorizeURL()
        let callbackScheme = URL(string: TradeStationConfig.redirectURI)?.scheme ?? "swiftbolt"
        print("[TSAuth] Starting OAuth flow with url: \(authURL)")
        
        let session = ASWebAuthenticationSession(
            url: authURL,
            callbackURLScheme: callbackScheme
        ) { [weak self] callbackURL, error in
            guard let self = self else {
                return
            }
            
            if let error = error {
                print("[TSAuth] OAuth error: \(error)")
                completion(.failure(error))
                return
            }
            
            guard let callbackURL = callbackURL else {
                print("[TSAuth] OAuth completed but callbackURL is nil")
                completion(.failure(TradeStationAuthError.missingCallbackURL))
                return
            }
            
            print("[TSAuth] Received callback URL: \(callbackURL)")
            
            guard let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false),
                  let code = components.queryItems?.first(where: { $0.name == "code" })?.value else {
                print("[TSAuth] Failed to extract authorization code")
                completion(.failure(TradeStationAuthError.missingAuthorizationCode))
                return
            }
            
            print("[TSAuth] Extracted authorization code (prefix): \(code.prefix(6))…")
            self.exchangeCodeForToken(authorizationCode: code, completion: completion)
        }
        
        session.presentationContextProvider = self
        
        if !session.start() {
            print("[TSAuth] Failed to start ASWebAuthenticationSession")
            completion(.failure(TradeStationAuthError.unableToStartSession))
        } else {
            print("[TSAuth] ASWebAuthenticationSession started successfully")
            self.authSession = session
        }
    }
    
    // MARK: - Private helpers
    
    private func buildAuthorizeURL() -> URL {
        // Base from docs: https://signin.tradestation.com/authorize
        var components = URLComponents(string: "https://signin.tradestation.com/authorize")!
        components.queryItems = [
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "client_id", value: TradeStationConfig.clientID),
            URLQueryItem(name: "audience", value: "https://api.tradestation.com"),
            URLQueryItem(name: "redirect_uri", value: TradeStationConfig.redirectURI),
            URLQueryItem(name: "scope", value: TradeStationConfig.scope)
        ]
        return components.url!
    }
    
    /// Exchange authorization code for tokens
    private func exchangeCodeForToken(
        authorizationCode: String,
        completion: @escaping (Result<(accessToken: String, refreshToken: String?), Error>) -> Void
    ) {
        let url = "https://signin.tradestation.com/oauth/token"
        let parameters: [String: String] = [
            "grant_type": "authorization_code",
            "client_id": TradeStationConfig.clientID,
            "client_secret": TradeStationConfig.clientSecret,
            "code": authorizationCode,
            "redirect_uri": TradeStationConfig.redirectURI
        ]
        
        print("[TSAuth] Exchanging code for token at \(url)")
        
        AF.request(
            url,
            method: .post,
            parameters: parameters,
            encoder: URLEncodedFormParameterEncoder.default,
            headers: ["Content-Type": "application/x-www-form-urlencoded"]
        )
        .validate()
        .responseJSON { response in
            switch response.result {
            case .success(let any):
                guard let json = any as? [String: Any],
                      let accessToken = json["access_token"] as? String else {
                    print("[TSAuth] Invalid token response JSON: \(any)")
                    completion(.failure(TradeStationAuthError.invalidTokenResponse))
                    return
                }
                
                let refreshToken = json["refresh_token"] as? String
                print("[TSAuth] Token exchange success. Access prefix: \(accessToken.prefix(10))…")
                
                // TODO: save tokens to Keychain here if desired
                completion(.success((accessToken, refreshToken)))
                
            case .failure(let error):
                if let data = response.data,
                   let body = String(data, encoding: .utf8) {
                    print("[TSAuth] Token exchange failed: \(error), body: \(body)")
                } else {
                    print("[TSAuth] Token exchange failed: \(error)")
                }
                completion(.failure(error))
            }
        }
    }
}

// MARK: - ASWebAuthenticationPresentationContextProviding
extension TradeStationAuthService: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        // Adapt to your app; for SwiftUI use window from scene / rootView
        return NSApplication.shared.windows.first ?? ASPresentationAnchor()
    }
}