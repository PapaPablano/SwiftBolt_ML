//
//  RealtimeForecastToggle.swift
//  SwiftBoltML
//
//  UI Component for toggling real-time forecast mode
//

import SwiftUI

struct RealtimeForecastToggle: View {
    @ObservedObject var viewModel: ChartViewModel
    @State private var useRealtimeAPI: Bool = false
    @State private var showingHealthCheck: Bool = false
    @State private var apiHealthy: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                // Toggle switch
                Toggle(isOn: $useRealtimeAPI) {
                    HStack(spacing: 6) {
                        Image(systemName: "waveform.path.ecg")
                            .foregroundColor(useRealtimeAPI ? .green : .secondary)
                        
                        Text("Real-time Forecasts")
                            .font(.system(size: 13, weight: .medium))
                    }
                }
                .toggleStyle(.switch)
                .onChange(of: useRealtimeAPI) { _, newValue in
                    handleToggle(enabled: newValue)
                }
                
                // Connection status indicator
                if useRealtimeAPI {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(viewModel.isRealtimeConnected ? Color.green : Color.gray)
                            .frame(width: 8, height: 8)
                        
                        Text(viewModel.isRealtimeConnected ? "Live" : "Offline")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                // Health check button
                Button(action: checkAPIHealth) {
                    HStack(spacing: 4) {
                        Image(systemName: showingHealthCheck ? "hourglass" : "checkmark.circle")
                        Text("Check")
                    }
                    .font(.system(size: 11))
                    .foregroundColor(.blue)
                }
                .disabled(showingHealthCheck)
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(NSColor.controlBackgroundColor))
            )
            
            // Status message
            if let statusMessage = getStatusMessage() {
                HStack(spacing: 6) {
                    Image(systemName: statusMessage.icon)
                        .foregroundColor(statusMessage.color)
                    
                    Text(statusMessage.text)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(statusMessage.backgroundColor)
                )
            }
        }
    }
    
    // MARK: - Actions
    
    private func handleToggle(enabled: Bool) {
        Task {
            if enabled {
                // Check if API is available first
                let healthy = await APIClient.shared.checkRealtimeAPIHealth()
                
                if healthy {
                    // Load real-time chart
                    await viewModel.loadRealtimeChart()
                    
                    // Start WebSocket for live updates
                    await MainActor.run {
                        viewModel.startRealtimeForecastUpdates()
                    }
                } else {
                    // Revert toggle if API not available
                    await MainActor.run {
                        useRealtimeAPI = false
                        viewModel.errorMessage = "Real-time API not available. Make sure FastAPI is running on http://localhost:8000"
                    }
                }
            } else {
                // Stop WebSocket and reload normal chart
                await MainActor.run {
                    viewModel.stopRealtimeForecastUpdates()
                }
                await viewModel.loadChart()
            }
        }
    }
    
    private func checkAPIHealth() {
        showingHealthCheck = true
        
        Task {
            let healthy = await APIClient.shared.checkRealtimeAPIHealth()
            
            await MainActor.run {
                apiHealthy = healthy
                showingHealthCheck = false
                
                if healthy {
                    viewModel.errorMessage = "✅ Real-time API is healthy and ready!"
                } else {
                    viewModel.errorMessage = "❌ Real-time API not responding. Start FastAPI backend with: cd ml && uvicorn api.main:app --reload"
                }
            }
            
            // Clear message after 5 seconds
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            await MainActor.run {
                if viewModel.errorMessage?.contains("Real-time API") == true {
                    viewModel.errorMessage = nil
                }
            }
        }
    }
    
    // MARK: - Status Message
    
    private struct StatusMessage {
        let text: String
        let icon: String
        let color: Color
        let backgroundColor: Color
    }
    
    private func getStatusMessage() -> StatusMessage? {
        if useRealtimeAPI {
            if viewModel.isRealtimeConnected {
                return StatusMessage(
                    text: "Connected to real-time forecast stream",
                    icon: "checkmark.circle.fill",
                    color: .green,
                    backgroundColor: Color.green.opacity(0.1)
                )
            } else {
                return StatusMessage(
                    text: "Connecting to real-time stream...",
                    icon: "arrow.triangle.2.circlepath",
                    color: .orange,
                    backgroundColor: Color.orange.opacity(0.1)
                )
            }
        }
        return nil
    }
}

// MARK: - Preview

struct RealtimeForecastToggle_Previews: PreviewProvider {
    static var previews: some View {
        RealtimeForecastToggle(viewModel: ChartViewModel())
            .frame(width: 400)
            .padding()
    }
}
