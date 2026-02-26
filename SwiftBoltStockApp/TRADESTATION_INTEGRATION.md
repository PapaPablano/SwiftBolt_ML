# TradeStation Integration

This document explains how to use the TradeStation OAuth integration in the SwiftBoltStockApp.

## Configuration

Before using this integration, you'll need to:

1. Register your app with TradeStation Developer Portal to get a Client ID and Client Secret
2. Set up the redirect URI in your TradeStation app configuration (should match `swiftbolt://oauth/callback`)
3. Update `TradeStationConfig.swift` with your actual credentials

## Usage

### Environment Toggle

The integration supports both SIM and LIVE environments:

```swift
// In TradeStationConfig.swift
static var environment: TradeStationEnvironment = .sim  // Switch to .live for actual trading
```

### Authentication Flow

1. Create a view with the `TradeStationConnectButton`
2. When the user taps the button, the OAuth flow starts
3. The user will be redirected to TradeStation's login page
4. After authentication, the app receives the authorization code
5. The code is exchanged for access and refresh tokens
6. The tokens are set on the API client for making authenticated requests

### API Client Usage

The `TradeStationAPIClient` handles making requests to TradeStation's API:

```swift
// The client automatically uses the token from setAccessToken
let accounts = apiClient.getAccounts { result in
    // Handle account data
}
```

## Key Components

- **TradeStationConfig**: Configuration for client ID, secrets, and environment
- **TradeStationAuthService**: Handles the OAuth flow using ASWebAuthenticationSession
- **TradeStationAPIClient**: Makes authenticated requests to TradeStation API
- **TradeStationViewModel**: Coordinates authentication state and API calls
- **TradeStationConnectButton**: SwiftUI view for initiating authentication