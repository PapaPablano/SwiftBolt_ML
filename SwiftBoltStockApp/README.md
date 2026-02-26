# SwiftBoltStockApp

SwiftBoltStockApp is a SwiftUI application for stock trading analytics and execution using TradeStation's API.

## Features

- TradeStation API integration with OAuth authentication
- SIM and LIVE environment support
- Account management
- Market data viewing

## TradeStation Integration

This app includes a complete OAuth integration with TradeStation:

- Supports both SIM and LIVE environments
- Uses ASWebAuthenticationSession for secure authentication
- Handles token exchange and storage
- Provides a clean API interface for making authenticated requests

## Getting Started

1. Register your app with TradeStation Developer Portal
2. Update `TradeStationConfig.swift` with your credentials
3. Build and run the app

For detailed usage instructions, see [TRADESTATION_INTEGRATION.md](TRADESTATION_INTEGRATION.md).

## Project Structure

- `TradeStationConfig.swift`: Configuration for API credentials and environment
- `TradeStationAuthService.swift`: OAuth authentication flow
- `TradeStationAPIClient.swift`: API client for making authenticated requests
- `TradeStationViewModel.swift`: ViewModel coordinating authentication and API calls
- `TradeStationConnectButton.swift`: SwiftUI view for authentication