# Swift App Validator: Implementation Guide

**Quick Reference for Building App-Side Validation**

---

## Phase 1: Backend API Endpoints (2 days)

### Step 1: Create `get-unified-validation` Function

**File**: `backend/supabase/functions/get-unified-validation/index.ts`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") || "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
)

serve(async (req: Request) => {
  try {
    const { searchParams } = new URL(req.url)
    const symbol = searchParams.get("symbol")

    if (!symbol) {
      return new Response(
        JSON.stringify({ error: "symbol parameter required" }),
        { status: 400 }
      )
    }

    // 1. Get latest backtesting score
    const {  backtestData } = await supabase
      .from("model_validation_stats")
      .select("accuracy")
      .eq("symbol", symbol)
      .eq("validation_type", "backtest")
      .order("created_at", { ascending: false })
      .limit(1)
      .single()

    // 2. Get latest walkforward score
    const {  walkforwardData } = await supabase
      .from("model_validation_stats")
      .select("accuracy")
      .eq("symbol", symbol)
      .eq("validation_type", "walkforward")
      .order("created_at", { ascending: false })
      .limit(1)
      .single()

    // 3. Get latest live score
    const {  liveData } = await supabase
      .from("live_predictions")
      .select("accuracy_score")
      .eq("symbol", symbol)
      .order("prediction_time", { ascending: false })
      .limit(1)
      .single()

    // 4. Get multi-timeframe signals (most recent)
    const {  signalsData } = await supabase
      .from("live_predictions")
      .select("timeframe, signal")
      .eq("symbol", symbol)
      .in("timeframe", ["M15", "H1", "D1"])
      .order("prediction_time", { ascending: false })

    // Map signals by timeframe
    const signals = {
      m15: signalsData?.find(s => s.timeframe === "M15")?.signal || "NEUTRAL",
      h1: signalsData?.find(s => s.timeframe === "H1")?.signal || "NEUTRAL",
      d1: signalsData?.find(s => s.timeframe === "D1")?.signal || "NEUTRAL",
    }

    const response = {
      symbol,
      backtest_score: backtestData?.accuracy || 0.5,
      walkforward_score: walkforwardData?.accuracy || 0.5,
      live_score: liveData?.accuracy_score || 0.5,
      m15_signal: signals.m15,
      h1_signal: signals.h1,
      d1_signal: signals.d1,
      timestamp: new Date().getTime(),
    }

    return new Response(JSON.stringify(response), {
      headers: { "Content-Type": "application/json" },
    })
  } catch (error) {
    console.error(error)
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500 }
    )
  }
})
```

**Test**:
```bash
curl 'https://<project>.supabase.co/functions/v1/get-unified-validation?symbol=AAPL'

# Expected response:
# {
#   "symbol": "AAPL",
#   "backtest_score": 0.988,
#   "walkforward_score": 0.825,
#   "live_score": 0.40,
#   "m15_signal": "BULLISH",
#   "h1_signal": "BEARISH",
#   "d1_signal": "BEARISH",
#   "timestamp": 1737460700000
# }
```

---

### Step 2: Create `log-validation-audit` Function

**File**: `backend/supabase/functions/log-validation-audit/index.ts`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") || "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
)

serve(async (req: Request) => {
  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST required" }), {
        status: 405,
      })
    }

    const body = await req.json()
    const { symbol, confidence, weights, timestamp, user_id } = body

    // Optional: Insert audit log
    // Used for debugging why app showed different signals than backend
    await supabase.from("validation_audits").insert({
      symbol,
      confidence_score: confidence,
      weights_config: weights,
      logged_at: new Date(timestamp),
      user_id,
    })

    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json" },
    })
  } catch (error) {
    console.error(error)
    // Fail silently—this is non-critical
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
    })
  }
})
```

**Test**:
```bash
curl -X POST 'https://<project>.supabase.co/functions/v1/log-validation-audit' \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol": "AAPL",
    "confidence": 0.72,
    "weights": {"backtest": 0.4, "walkforward": 0.35, "live": 0.25},
    "timestamp": '$(date +%s)'
  }'
```

---

## Phase 2: Swift App Models (Day 4-5)

### Step 3: Create `UnifiedValidator.swift`

**File**: `SwiftBolt/Models/UnifiedValidator.swift`

```swift
import Foundation

struct UnifiedValidator: Codable {
    let symbol: String
    let backtestScore: Double
    let walkforwardScore: Double
    let liveScore: Double
    let m15Signal: Signal
    let h1Signal: Signal
    let d1Signal: Signal
    let timestamp: Date
    
    // User-configurable weights
    let weights: ValidationWeights
    
    enum CodingKeys: String, CodingKey {
        case symbol
        case backtestScore = "backtest_score"
        case walkforwardScore = "walkforward_score"
        case liveScore = "live_score"
        case m15Signal = "m15_signal"
        case h1Signal = "h1_signal"
        case d1Signal = "d1_signal"
        case timestamp
        case weights
    }
    
    // MARK: - Calculated Properties
    
    /// Single confidence score combining all three metrics
    var confidence: Double {
        (backtestScore * weights.backtest) +
        (walkforwardScore * weights.walkforward) +
        (liveScore * weights.live)
    }
    
    /// Whether live performance is diverging from backtest
    var hasDrift: Bool {
        let divergence = abs(liveScore - backtestScore)
        return divergence > weights.driftThreshold
    }
    
    /// Reconciled consensus from all timeframes
    var timeframeConsensus: Signal {
        reconcileTimeframes()
    }
    
    /// Human-readable time since update
    var lastUpdatedAgo: String {
        let interval = Date().timeIntervalSince(timestamp)
        if interval < 60 {
            return "Just now"
        } else if interval < 3600 {
            return "\(Int(interval / 60)) min ago"
        } else if interval < 86400 {
            return "\(Int(interval / 3600)) hour ago"
        } else {
            return "\(Int(interval / 86400)) day ago"
        }
    }
    
    // MARK: - Private Methods
    
    private func reconcileTimeframes() -> Signal {
        switch weights.timeframeWeight {
        case .durationBased:
            // D1 weighted more heavily (50%), H1 (30%), M15 (20%)
            let weighted = (d1Signal.bullishValue * 0.5) +
                          (h1Signal.bullishValue * 0.3) +
                          (m15Signal.bullishValue * 0.2)
            return weighted > 0.5 ? .bullish : weighted < -0.5 ? .bearish : .neutral
            
        case .equal:
            // Equal weight (1/3 each)
            let count = [m15Signal, h1Signal, d1Signal].filter { $0 == .bullish }.count
            return count >= 2 ? .bullish : count <= 1 ? .bearish : .neutral
            
        case .recentPerformance:
            // Weight by live score quality
            if liveScore > 0.7 {
                // Trust live more
                return m15Signal  // Most recent
            } else if liveScore > 0.5 {
                // Balance
                return h1Signal
            } else {
                // Trust longer timeframe
                return d1Signal
            }
        }
    }
}

extension Signal {
    var bullishValue: Double {
        switch self {
        case .bullish: return 1.0
        case .neutral: return 0.0
        case .bearish: return -1.0
        }
    }
}

struct ValidationWeights: Codable {
    var backtest: Double = 0.40
    var walkforward: Double = 0.35
    var live: Double = 0.25
    var driftThreshold: Double = 0.15
    var timeframeWeight: TimeframeWeight = .durationBased
    
    enum TimeframeWeight: String, Codable {
        case durationBased        // D1 > H1 > M15
        case recentPerformance    // Weight by live score
        case equal                // 1/3 each
    }
    
    // MARK: - Persistence
    
    func save() {
        let encoder = JSONEncoder()
        if let data = try? encoder.encode(self) {
            UserDefaults.standard.set(data, forKey: "validationWeights")
        }
    }
    
    static func load() -> ValidationWeights {
        let decoder = JSONDecoder()
        if let data = UserDefaults.standard.data(forKey: "validationWeights"),
           let weights = try? decoder.decode(ValidationWeights.self, from: data) {
            return weights
        }
        return ValidationWeights()  // Defaults
    }
}

enum Signal: String, Codable {
    case bullish = "BULLISH"
    case bearish = "BEARISH"
    case neutral = "NEUTRAL"
}
```

---

### Step 4: Create `ValidationViewModel.swift`

**File**: `SwiftBolt/ViewModels/ValidationViewModel.swift`

```swift
import Foundation
import Network

@MainActor
class ValidationViewModel: ObservableObject {
    @Published var validator: UnifiedValidator?
    @Published var isLoading = false
    @Published var error: String?
    @Published var isOffline = false
    @Published var lastSyncTime: Date?
    
    @Published var userWeights = ValidationWeights.load() {
        didSet {
            userWeights.save()
            recalculateIfNeeded()  // Instant UI update
        }
    }
    
    let symbol: String
    private var pollTimer: Timer?
    private let cacheDuration: TimeInterval = 5 * 60  // 5 minutes
    private let reachability: NetworkReachability
    private let apiClient: SupabaseClient
    
    init(
        symbol: String,
        reachability: NetworkReachability = .shared,
        apiClient: SupabaseClient = .shared
    ) {
        self.symbol = symbol
        self.reachability = reachability
        self.apiClient = apiClient
    }
    
    func startPolling() {
        pollTimer = Timer.scheduledTimer(
            withTimeInterval: 300,  // 5 minutes
            repeats: true
        ) { [weak self] _ in
            Task { await self?.fetchValidation() }
        }
        // Initial fetch
        Task { await fetchValidation() }
    }
    
    func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }
    
    func fetchValidation() async {
        // Check network connectivity
        guard reachability.isConnected else {
            isOffline = true
            await MainActor.run { loadFromCache() }
            return
        }
        
        isOffline = false
        isLoading = true
        error = nil
        
        do {
            let response = try await apiClient.call(
                "get-unified-validation",
                params: ["symbol": symbol]
            )
            
            // Decode response
            var validator = try JSONDecoder().decode(
                UnifiedValidator.self,
                from: JSONSerialization.data(withJSONObject: response)
            )
            
            // Apply user's weights
            validator.weights = userWeights
            
            await MainActor.run {
                self.validator = validator
                self.lastSyncTime = Date()
            }
            
            // Cache for offline
            cacheValidator(validator)
            
            // Sync audit (fire & forget)
            Task { await syncAuditLog(validator) }
            
        } catch {
            await MainActor.run {
                self.error = error.localizedDescription
                loadFromCache()  // Fall back
            }
        }
        
        isLoading = false
    }
    
    private func loadFromCache() {
        let key = "validationCache_\(symbol)"
        if let cached = UserDefaults.standard.data(forKey: key),
           var validator = try? JSONDecoder().decode(
               UnifiedValidator.self,
               from: cached
           ) {
            validator.weights = userWeights
            self.validator = validator
            if isOffline {
                self.error = "⚠️ Offline: showing cached data from \(validator.lastUpdatedAgo)"
            }
        }
    }
    
    private func cacheValidator(_ validator: UnifiedValidator) {
        let key = "validationCache_\(symbol)"
        if let encoded = try? JSONEncoder().encode(validator) {
            UserDefaults.standard.set(encoded, forKey: key)
        }
    }
    
    private func recalculateIfNeeded() {
        guard var validator = validator else { return }
        validator.weights = userWeights  // Apply new weights
        self.validator = validator
    }
    
    private func syncAuditLog(_ validator: UnifiedValidator) async {
        do {
            try await apiClient.call(
                "log-validation-audit",
                params: [
                    "symbol": validator.symbol,
                    "confidence": validator.confidence,
                    "weights": userWeights,
                    "timestamp": Int(validator.timestamp.timeIntervalSince1970)
                ]
            )
        } catch {
            // Fail silently—auditing is non-critical
            print("[ValidationViewModel] Audit sync failed (non-critical): \(error)")
        }
    }
}
```

---

### Step 5: Create `ValidationDashboardView.swift`

**File**: `SwiftBolt/Views/ValidationDashboardView.swift`

```swift
import SwiftUI

struct ValidationDashboardView: View {
    @StateObject private var viewModel: ValidationViewModel
    @State private var showSettings = false
    
    let symbol: String
    
    init(symbol: String) {
        self.symbol = symbol
        _viewModel = StateObject(wrappedValue: ValidationViewModel(symbol: symbol))
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Unified Confidence")
                        .font(.headline)
                    if let lastSync = viewModel.lastSyncTime {
                        Text("Updated \(lastSync, style: .relative) ago")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                
                if viewModel.isLoading {
                    ProgressView()
                } else {
                    Button(action: {
                        Task { await viewModel.fetchValidation() }
                    }) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
                
                if viewModel.isOffline {
                    Label("Offline", systemImage: "wifi.slash")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
            
            // Main content
            if let validator = viewModel.validator {
                ScrollView {
                    VStack(spacing: 16) {
                        // Large confidence badge
                        ZStack {
                            Circle()
                                .fill(confidenceColor(validator.confidence))
                                .opacity(0.1)
                            
                            VStack(spacing: 4) {
                                Text("\(Int(validator.confidence * 100))%")
                                    .font(.system(size: 48, weight: .bold))
                                Text("Confidence")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .frame(height: 200)
                        
                        // Score breakdown
                        HStack(spacing: 12) {
                            ScoreColumn(
                                label: "Backtest",
                                score: validator.backtestScore,
                                weight: viewModel.userWeights.backtest
                            )
                            ScoreColumn(
                                label: "Walkforward",
                                score: validator.walkforwardScore,
                                weight: viewModel.userWeights.walkforward
                            )
                            ScoreColumn(
                                label: "Live",
                                score: validator.liveScore,
                                weight: viewModel.userWeights.live,
                                isDriftFlagged: validator.hasDrift
                            )
                        }
                        
                        // Timeframe consensus
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Multi-Timeframe Consensus")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            
                            HStack(spacing: 12) {
                                TimeframeRow(
                                    timeframe: "M15",
                                    signal: validator.m15Signal
                                )
                                TimeframeRow(
                                    timeframe: "H1",
                                    signal: validator.h1Signal
                                )
                                TimeframeRow(
                                    timeframe: "D1",
                                    signal: validator.d1Signal
                                )
                                Spacer()
                            }
                            
                            HStack(spacing: 8) {
                                Text("Consensus:")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Capsule()
                                    .fill(signalColor(validator.timeframeConsensus))
                                    .frame(width: 100, height: 24)
                                    .overlay(
                                        Text(validator.timeframeConsensus.rawValue)
                                            .font(.caption2)
                                            .fontWeight(.semibold)
                                            .foregroundColor(.white)
                                    )
                                Spacer()
                            }
                        }
                        .padding(12)
                        .background(Color(.systemGray6))
                        .cornerRadius(8)
                        
                        // Drift alert
                        if validator.hasDrift {
                            HStack(spacing: 8) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.orange)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Drift Detected")
                                        .font(.caption)
                                        .fontWeight(.semibold)
                                    Text("Live performance diverging from backtest (>15%)")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                            }
                            .padding(12)
                            .background(Color.orange.opacity(0.1))
                            .cornerRadius(8)
                        }
                        
                        // Settings button
                        Button(action: { showSettings = true }) {
                            Label("Adjust Weights", systemImage: "sliders.horizontal")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            
            // Error state
            if let error = viewModel.error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(12)
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
            }
            
            Spacer()
        }
        .padding(16)
        .sheet(isPresented: $showSettings) {
            ValidationSettingsView(weights: $viewModel.userWeights)
        }
        .onAppear { viewModel.startPolling() }
        .onDisappear { viewModel.stopPolling() }
    }
    
    private func confidenceColor(_ confidence: Double) -> Color {
        if confidence >= 0.75 { return .green }
        if confidence >= 0.50 { return .yellow }
        return .red
    }
    
    private func signalColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .gray
        }
    }
}

// Helper components
struct ScoreColumn: View {
    let label: String
    let score: Double
    let weight: Double
    var isDriftFlagged = false
    
    var body: some View {
        VStack(spacing: 8) {
            Text(label)
                .font(.caption)
                .fontWeight(.semibold)
            
            ZStack {
                Circle()
                    .stroke(Color.gray.opacity(0.3), lineWidth: 2)
                Circle()
                    .trim(from: 0, to: CGFloat(score))
                    .stroke(isDriftFlagged ? Color.orange : Color.blue, lineWidth: 2)
                    .rotationEffect(.degrees(-90))
                
                Text("\(Int(score * 100))%")
                    .font(.caption)
                    .fontWeight(.semibold)
            }
            .frame(height: 60)
            
            Text("Wt: \(Int(weight * 100))%")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

struct TimeframeRow: View {
    let timeframe: String
    let signal: Signal
    
    var body: some View {
        VStack(spacing: 4) {
            Text(timeframe)
                .font(.caption2)
                .fontWeight(.semibold)
            Capsule()
                .fill(signalColor(signal))
                .frame(height: 20)
                .overlay(
                    Text(signal.rawValue)
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                )
        }
    }
    
    private func signalColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .gray
        }
    }
}

// Settings view stub
struct ValidationSettingsView: View {
    @Binding var weights: ValidationWeights
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section("Validation Weights") {
                    Slider(value: $weights.backtest, in: 0...1, step: 0.05)
                        .onReceive([weights.backtest].publisher, perform: { _ in
                            normalizeWeights()
                        })
                    Text("Backtest: \(Int(weights.backtest * 100))%")
                    
                    Slider(value: $weights.walkforward, in: 0...1, step: 0.05)
                        .onReceive([weights.walkforward].publisher, perform: { _ in
                            normalizeWeights()
                        })
                    Text("Walkforward: \(Int(weights.walkforward * 100))%")
                    
                    Slider(value: $weights.live, in: 0...1, step: 0.05)
                        .onReceive([weights.live].publisher, perform: { _ in
                            normalizeWeights()
                        })
                    Text("Live: \(Int(weights.live * 100))%")
                }
                
                Section("Drift Alert Threshold") {
                    Slider(value: $weights.driftThreshold, in: 0.05...0.50, step: 0.05)
                    Text("Alert at: \(Int(weights.driftThreshold * 100))% divergence")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
    
    private func normalizeWeights() {
        let total = weights.backtest + weights.walkforward + weights.live
        if total > 0 {
            weights.backtest /= total
            weights.walkforward /= total
            weights.live /= total
        }
    }
}

#Preview {
    ValidationDashboardView(symbol: "AAPL")
}
```

---

## Integration Steps

### Add to Dashboard

In your main Dashboard view:

```swift
struct DashboardView: View {
    @State var selectedTab = 0
    let symbol: String
    
    var body: some View {
        TabView(selection: $selectedTab) {
            ValidationDashboardView(symbol: symbol)
                .tabItem {
                    Label("Validation", systemImage: "checkmark.seal")
                }
                .tag(0)
            
            // ... other tabs ...
        }
    }
}
```

---

## Testing Checklist

- [ ] API endpoint returns correct data
- [ ] App polls endpoint every 5 minutes
- [ ] Confidence score calculated correctly
- [ ] Drift detection triggers at 15%+ divergence
- [ ] Weights persist after app restart
- [ ] Offline mode shows cached data
- [ ] Settings UI adjusts weights and triggers recalculation
- [ ] Audit logs synced to backend (verify in DB)
- [ ] Multi-timeframe consensus logic correct
- [ ] UI colors update based on confidence level

---

**Next**: Deploy to TestFlight and gather user feedback!
