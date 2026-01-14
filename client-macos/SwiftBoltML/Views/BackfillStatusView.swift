//
//  BackfillStatusView.swift
//  SwiftBoltML
//
//  UI for managing symbol backfills
//  Shows progress and allows manual trigger
//

import SwiftUI
import Supabase

struct BackfillStatusView: View {
    @StateObject private var backfillService: BackfillService
    let ticker: String

    @State private var statuses: [BackfillStatus] = []
    @State private var isRequestingBackfill = false
    @State private var showError = false
    @State private var errorMessage = ""

    init(ticker: String, supabase: SupabaseClient) {
        self.ticker = ticker
        _backfillService = StateObject(wrappedValue: BackfillService(supabase: supabase))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Text("Historical Data Backfill")
                    .font(.headline)

                Spacer()

                if backfillService.isLoading {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }

            if statuses.isEmpty {
                // No backfill yet - show request button
                noBackfillView
            } else {
                // Show backfill progress
                backfillProgressView
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
        .alert("Error", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage)
        }
        .task {
            await loadBackfillStatus()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("RefreshBackfillStatus"))) { _ in
            Task {
                await loadBackfillStatus()
            }
        }
    }

    // MARK: - No Backfill View

    private var noBackfillView: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("No historical data loaded yet")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Text("Load 2 years of intraday data for better charting")
                .font(.caption)
                .foregroundColor(.secondary)

            Button(action: requestBackfill) {
                HStack {
                    Image(systemName: "arrow.down.circle.fill")
                    Text("Load Historical Data (2 Years)")
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(isRequestingBackfill)

            if isRequestingBackfill {
                HStack {
                    ProgressView()
                        .scaleEffect(0.7)
                    Text("Requesting backfill...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
    }

    // MARK: - Backfill Progress View

    private var backfillProgressView: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(statuses) { status in
                BackfillProgressRow(status: status)
            }

            // Overall summary
            if let overallProgress = overallProgress {
                HStack {
                    Text("Overall Progress:")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text("\(Int(overallProgress))%")
                        .font(.caption)
                        .fontWeight(.semibold)

                    Spacer()

                    if allComplete {
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text("Complete")
                                .font(.caption)
                                .foregroundColor(.green)
                        }
                    } else {
                        Text("~\(estimatedTimeRemaining)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.top, 4)
            }

            // Refresh button
            Button(action: { Task { await loadBackfillStatus() } }) {
                HStack {
                    Image(systemName: "arrow.clockwise")
                    Text("Refresh Status")
                }
            }
            .buttonStyle(.bordered)
            .font(.caption)
        }
    }

    // MARK: - Computed Properties

    private var overallProgress: Double? {
        guard !statuses.isEmpty else { return nil }
        let total = statuses.reduce(0.0) { $0 + $1.progressPercentage }
        return total / Double(statuses.count)
    }

    private var allComplete: Bool {
        !statuses.isEmpty && statuses.allSatisfy { $0.isComplete }
    }

    private var estimatedTimeRemaining: String {
        guard let progress = overallProgress, progress > 0 else {
            return "Calculating..."
        }

        let totalChunks = statuses.reduce(0) { $0 + $1.totalChunks }
        let doneChunks = statuses.reduce(0) { $0 + $1.doneChunks }
        let remainingChunks = totalChunks - doneChunks

        // Assume ~4 chunks per minute (based on 5 req/min rate limit)
        let minutesRemaining = Double(remainingChunks) / 4.0

        if minutesRemaining < 60 {
            return "\(Int(minutesRemaining)) min remaining"
        } else {
            let hoursRemaining = minutesRemaining / 60.0
            return "\(String(format: "%.1f", hoursRemaining)) hours remaining"
        }
    }

    // MARK: - Actions

    private func loadBackfillStatus() async {
        do {
            statuses = try await backfillService.getBackfillStatus(for: ticker)
        } catch {
            print("Failed to load backfill status: \(error)")
        }
    }

    private func requestBackfill() {
        isRequestingBackfill = true

        Task {
            do {
                let result = try await backfillService.requestBackfill(for: ticker)
                print("Backfill requested: \(result)")

                // Reload status
                try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
                await loadBackfillStatus()

            } catch {
                errorMessage = error.localizedDescription
                showError = true
            }

            isRequestingBackfill = false
        }
    }
}

// MARK: - Progress Row Component

struct BackfillProgressRow: View {
    let status: BackfillStatus

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(timeframeDisplay)
                    .font(.subheadline)
                    .fontWeight(.medium)

                Spacer()

                Text("\(status.progress)%")
                    .font(.caption)
                    .fontWeight(.semibold)
            }

            // Progress bar
            ProgressView(value: Double(status.progress), total: 100)
                .progressViewStyle(LinearProgressViewStyle())
                .tint(progressColor)

            // Status details
            HStack {
                Text("\(status.doneChunks) / \(status.totalChunks) days")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()

                if status.hasErrors {
                    Text("\(status.errorChunks) errors")
                        .font(.caption)
                        .foregroundColor(.red)
                }

                statusBadge
            }
        }
        .padding(.vertical, 4)
    }

    private var timeframeDisplay: String {
        switch status.timeframe {
        case "m15": return "15-Minute"
        case "h1": return "1-Hour"
        case "h4": return "4-Hour"
        case "d1": return "Daily"
        default: return status.timeframe
        }
    }

    private var progressColor: Color {
        if status.isComplete {
            return .green
        } else if status.hasErrors {
            return .orange
        } else {
            return .blue
        }
    }

    private var statusBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: statusIcon)
            Text(statusText)
        }
        .font(.caption2)
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(statusBackgroundColor)
        .foregroundColor(statusForegroundColor)
        .cornerRadius(4)
    }

    private var statusIcon: String {
        switch status.status {
        case "done": return "checkmark.circle.fill"
        case "running": return "arrow.clockwise.circle.fill"
        case "error": return "exclamationmark.circle.fill"
        default: return "clock.fill"
        }
    }

    private var statusText: String {
        switch status.status {
        case "done": return "Complete"
        case "running": return "Processing"
        case "error": return "Error"
        default: return "Pending"
        }
    }

    private var statusBackgroundColor: Color {
        switch status.status {
        case "done": return Color.green.opacity(0.2)
        case "running": return Color.blue.opacity(0.2)
        case "error": return Color.red.opacity(0.2)
        default: return Color.gray.opacity(0.2)
        }
    }

    private var statusForegroundColor: Color {
        switch status.status {
        case "done": return .green
        case "running": return .blue
        case "error": return .red
        default: return .gray
        }
    }
}

// MARK: - Preview

#Preview {
    BackfillStatusView(
        ticker: "AAPL",
        supabase: SupabaseClient(
            supabaseURL: URL(string: "https://example.supabase.co")!,
            supabaseKey: "test-key",
            options: SupabaseClientOptions(
                auth: .init(emitLocalSessionAsInitialSession: true)
            )
        )
    )
    .frame(width: 400)
    .padding()
}
