# Phase 4 API Documentation

**SwiftBolt ML - SwiftUI Integration APIs**  
**Last Updated**: January 22, 2026

---

## 📚 Overview

This document provides comprehensive API documentation for the Phase 4 SwiftUI ML integration features, including caching, error handling, retry logic, and offline support.

---

## 🔧 Utilities

### CacheManager

**Location**: `Utilities/CacheManager.swift`

Thread-safe cache manager with TTL-based freshness tracking.

#### Cache Freshness Tiers

| Tier | Age | Behavior |
|------|-----|----------|
| Fresh | < 5 min | Use directly, no fetch needed |
| Warm | 5-30 min | Use + background refresh |
| Stale | 30 min - 6 hr | Show warning, prompt refresh |
| Critical | > 6 hr | Force refresh, block until fresh |

#### Usage

```swift
// Get cached value
if let cached = await CacheManager.shared.get("my_key", type: MyType.self) {
    let (value, freshness) = cached
    if freshness == .fresh {
        // Use cached value
    }
}

// Set cached value
await CacheManager.shared.set("my_key", value: myData)
```

#### Methods

- `get<T>(_ key: String, type: T.Type) -> (value: T, freshness: CacheFreshness)?`
- `set<T>(_ key: String, value: T)`
- `remove(_ key: String)`
- `clear()`
- `freshness(for key: String) -> CacheFreshness?`

---

### RequestDeduplicator

**Location**: `Utilities/RequestDeduplicator.swift`

Prevents duplicate concurrent API requests by tracking in-flight requests.

#### Usage

```swift
let result = try await RequestDeduplicator.shared.execute(key: "unique_request_key") {
    try await APIClient.shared.fetchData(...)
}
```

#### Methods

- `execute<T>(key: String, operation: @escaping () async throws -> T) async throws -> T`
- `cancelRequest(key: String)`
- `inFlightCount() -> Int`
- `clearAll()`

---

### RetryPolicy

**Location**: `Utilities/RetryPolicy.swift`

Configurable retry strategies with exponential backoff.

#### Predefined Policies

**Default Policy**:
- Max attempts: 3
- Initial delay: 1.0s
- Max delay: 10.0s
- Backoff multiplier: 2.0x

**Conservative Policy**:
- Max attempts: 2
- Initial delay: 2.0s
- Max delay: 15.0s
- Backoff multiplier: 2.5x

**Aggressive Policy**:
- Max attempts: 5
- Initial delay: 0.5s
- Max delay: 8.0s
- Backoff multiplier: 1.8x

#### Usage

```swift
let result = try await withRetry(policy: .default) {
    try await APIClient.shared.fetchData(...)
}
```

#### Retryable Errors

- Network errors (URLError.timedOut, .networkConnectionLost, etc.)
- Rate limit errors (429)
- Server errors (5xx)
- Service unavailable errors

#### Non-Retryable Errors

- Authentication errors (401, 403)
- Invalid symbol errors (404)
- Decoding errors
- Invalid URL/response errors

---

### ErrorFormatter

**Location**: `Utilities/ErrorFormatter.swift`

Converts technical errors into user-friendly messages.

#### Usage

```swift
let formatted = ErrorFormatter.userFriendlyMessage(from: error)
// formatted.title: "Network Error"
// formatted.message: "Please check your internet connection..."
// formatted.icon: "wifi.slash"
```

#### Error Types Handled

- Network errors → "Network Error" with connection guidance
- Rate limit errors → "Rate Limit Exceeded" with retry timing
- Server errors → "Service Unavailable" with retry suggestion
- Authentication errors → "Authentication Error" with sign-in guidance
- Invalid symbol → "Invalid Symbol" with symbol name
- HTTP errors → Contextual message based on status code

---

### NetworkMonitor

**Location**: `Utilities/NetworkMonitor.swift`

Real-time network connectivity monitoring.

#### Usage

```swift
let monitor = NetworkMonitor.shared
if monitor.isConnected {
    // Online
} else {
    // Offline
}

// Monitor status changes
monitor.$isConnected
    .sink { connected in
        // Handle connection change
    }
```

#### Properties

- `isConnected: Bool` - Current connection status
- `status: NetworkStatus` - Detailed status (connected, disconnected, connecting)
- `connectionType: String` - Connection type (Wi-Fi, Cellular, Ethernet)

---

## 📱 ViewModels

### ForecastQualityViewModel

**Location**: `ViewModels/ForecastQualityViewModel.swift`

Manages forecast quality metrics display and interaction.

#### Published Properties

- `qualityResult: ForecastQualityResponse?` - Current quality metrics
- `isLoading: Bool` - Loading state
- `error: String?` - Error message (user-friendly)
- `isOffline: Bool` - Offline status
- `horizon: String` - Current forecast horizon (1D, 1W, 1M)
- `timeframe: String` - Current timeframe (d1, h1, etc.)

#### Methods

```swift
// Fetch quality metrics
func fetchQuality(
    symbol: String,
    horizon: String = "1D",
    timeframe: String = "d1",
    forceRefresh: Bool = false
) async

// Reset view model state
func reset()
```

#### Computed Properties

- `hasResults: Bool` - Whether results are available
- `formattedQualityScore: String` - Formatted quality score percentage
- `qualityScoreColor: Color` - Color based on score (green/orange/red)
- `hasIssues: Bool` - Whether quality issues exist

#### Features

- ✅ Caching with freshness tiers
- ✅ Request deduplication
- ✅ Retry logic with exponential backoff
- ✅ Offline mode detection
- ✅ User-friendly error messages

---

### ModelTrainingViewModel

**Location**: `ViewModels/ModelTrainingViewModel.swift`

Manages ML model training operations and results.

#### Published Properties

- `trainingResult: ModelTrainingResponse?` - Current training results
- `isLoading: Bool` - Loading state
- `error: String?` - Error message (user-friendly)
- `isOffline: Bool` - Offline status
- `timeframe: String` - Current timeframe
- `lookbackDays: Int` - Lookback period in days

#### Methods

```swift
// Train model
func trainModel(
    symbol: String,
    timeframe: String = "d1",
    lookbackDays: Int = 90,
    forceRefresh: Bool = false
) async

// Reset view model state
func reset()
```

#### Computed Properties

- `hasResults: Bool` - Whether results are available
- `formattedValidationAccuracy: String` - Formatted accuracy percentage
- `validationAccuracyColor: Color` - Color based on accuracy

#### Features

- ✅ Caching with appropriate TTL
- ✅ Request deduplication
- ✅ Retry logic (conservative policy)
- ✅ Offline mode detection
- ✅ User-friendly error messages

---

## 🎨 Views

### ForecastQualityView

**Location**: `Views/ForecastQualityView.swift`

Displays forecast quality metrics with configuration panel.

#### Features

- Split view with configuration panel
- Horizon selector (1D, 1W, 1M)
- Skeleton loading screen
- Pull-to-refresh gesture
- Offline indicator
- Standardized error view
- Enhanced empty state with tips

#### Usage

```swift
ForecastQualityView(symbol: "AAPL", timeframe: "d1")
```

---

### ModelTrainingView

**Location**: `Views/ModelTrainingView.swift`

Displays model training results with configuration panel.

#### Features

- Split view with configuration panel
- Timeframe and lookback configuration
- Skeleton loading screen
- Pull-to-refresh gesture
- Offline indicator
- Standardized error view
- Enhanced empty state with tips

#### Usage

```swift
ModelTrainingView(symbol: "AAPL")
```

---

## 🎯 Best Practices

### Caching

1. **Use appropriate cache keys**: Include all relevant parameters (symbol, horizon, timeframe)
2. **Respect freshness tiers**: Don't force refresh for fresh data
3. **Background refresh**: Use warm data with background refresh for better UX

### Error Handling

1. **Use ErrorFormatter**: Always format errors for user display
2. **Retry appropriate errors**: Network and server errors, not client errors
3. **Show user-friendly messages**: Never expose technical error details

### Offline Support

1. **Check network status**: Use `NetworkMonitor.shared.isConnected`
2. **Show cached data**: When offline, display cached data if available
3. **Clear messaging**: Inform users when showing cached/stale data

### Performance

1. **Use request deduplication**: For operations that might be called multiple times
2. **Pre-compute expensive operations**: Format strings, calculate colors outside view body
3. **Use @ViewBuilder**: For complex view hierarchies
4. **Lazy loading**: Use `LazyVGrid` and `LazyHStack` for large lists

---

## 📊 API Endpoints

### Forecast Quality

**Endpoint**: `POST /forecast-quality`

**Request**:
```json
{
  "symbol": "AAPL",
  "horizon": "1D",
  "timeframe": "d1"
}
```

**Response**:
```json
{
  "symbol": "AAPL",
  "horizon": "1D",
  "timeframe": "d1",
  "qualityScore": 0.75,
  "confidence": 0.80,
  "modelAgreement": 0.85,
  "issues": [
    {
      "level": "warning",
      "type": "low_confidence",
      "message": "Low confidence: 50%",
      "action": "review"
    }
  ],
  "timestamp": "2026-01-22T22:00:00Z"
}
```

### Model Training

**Endpoint**: `POST /train-model`

**Request**:
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "lookbackDays": 90
}
```

**Response**:
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "lookbackDays": 90,
  "status": "success",
  "trainingMetrics": {
    "validationAccuracy": 0.65,
    "trainSamples": 500,
    "validationSamples": 100,
    "trainLoss": 0.45,
    "validationLoss": 0.52
  },
  "ensembleWeights": {
    "random_forest": 0.6,
    "gradient_boosting": 0.4
  },
  "timestamp": "2026-01-22T22:00:00Z"
}
```

---

## 🔍 Troubleshooting

### Cache Not Working

- Check cache key matches exactly (case-sensitive)
- Verify data type matches between set and get
- Check cache freshness - stale data may require refresh

### Retry Not Working

- Verify error is retryable (network/server errors)
- Check retry policy configuration
- Ensure task isn't cancelled before retry

### Offline Detection Not Working

- Verify `NetworkMonitor.shared` is initialized
- Check network status subscription is active
- Ensure ViewModel is observing network status

---

## 📝 Code Examples

### Complete Example: Fetching Forecast Quality

```swift
@StateObject private var viewModel = ForecastQualityViewModel()

// In view
Task {
    await viewModel.fetchQuality(
        symbol: "AAPL",
        horizon: "1D",
        timeframe: "d1"
    )
}

// Display results
if let result = viewModel.qualityResult {
    Text("Quality: \(viewModel.formattedQualityScore)")
        .foregroundStyle(viewModel.qualityScoreColor)
}
```

### Complete Example: Training Model

```swift
@StateObject private var viewModel = ModelTrainingViewModel()

// In view
Task {
    await viewModel.trainModel(
        symbol: "AAPL",
        timeframe: "d1",
        lookbackDays: 90
    )
}

// Display results
if let result = viewModel.trainingResult {
    Text("Accuracy: \(viewModel.formattedValidationAccuracy)")
        .foregroundStyle(viewModel.validationAccuracyColor)
}
```

---

**Document Version**: 1.0  
**Last Updated**: January 22, 2026
