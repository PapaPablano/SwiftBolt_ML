import SwiftUI

/// Data Quality Badge - Shows freshness and ML readiness of chart data
struct DataQualityBadge: View {
    let dataQuality: DataQuality?
    @State private var showDetails = false
    
    var body: some View {
        Group {
            if let quality = dataQuality {
                HStack(spacing: 4) {
                    // Status icon
                    Image(systemName: statusIcon(for: quality))
                        .foregroundColor(statusColor(for: quality))
                        .font(.caption)
                    
                    // Age text
                    Text(ageText(for: quality))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(statusColor(for: quality).opacity(0.15))
                )
                .help(detailsText(for: quality))
                .onTapGesture {
                    showDetails.toggle()
                }
                .popover(isPresented: $showDetails) {
                    DataQualityBadgePopover(quality: quality)
                }
            }
        }
    }
    
    private func statusIcon(for quality: DataQuality) -> String {
        if quality.isStale {
            return "exclamationmark.triangle.fill"
        } else if quality.hasRecentData {
            return "checkmark.circle.fill"
        } else {
            return "clock.fill"
        }
    }
    
    private func statusColor(for quality: DataQuality) -> Color {
        if quality.isStale {
            return .orange
        } else if quality.hasRecentData {
            return .green
        } else {
            return .blue
        }
    }
    
    private func ageText(for quality: DataQuality) -> String {
        guard let ageHours = quality.dataAgeHours else {
            return "Unknown age"
        }
        
        if ageHours < 1 {
            return "< 1h old"
        } else if ageHours < 24 {
            return "\(ageHours)h old"
        } else {
            let days = ageHours / 24
            return "\(days)d old"
        }
    }
    
    private func detailsText(for quality: DataQuality) -> String {
        var details: [String] = []
        
        details.append(quality.statusDescription)
        details.append("Historical depth: \(quality.historicalDepthDays) days")
        details.append(quality.mlTrainingStatus)
        
        return details.joined(separator: "\n")
    }
}

/// Detailed Data Quality View (shown in popover)
struct DataQualityBadgePopover: View {
    let quality: DataQuality
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Data Quality Report")
                .font(.headline)
            
            Divider()
            
            // Freshness
            HStack {
                Image(systemName: quality.isStale ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                    .foregroundColor(quality.isStale ? .orange : .green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Freshness")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(quality.statusDescription)
                        .font(.body)
                }
            }
            
            // Data Age
            HStack {
                Image(systemName: "clock.fill")
                    .foregroundColor(.blue)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Data Age")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if let ageHours = quality.dataAgeHours {
                        Text(formatAge(hours: ageHours))
                            .font(.body)
                    } else {
                        Text("Unknown")
                            .font(.body)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            // Historical Depth
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.purple)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Historical Depth")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(quality.historicalDepthDays) days (\(quality.barCount) bars)")
                        .font(.body)
                }
            }
            
            // ML Training Status
            HStack {
                Image(systemName: quality.sufficientForML ? "brain.head.profile" : "exclamationmark.brain.head.profile")
                    .foregroundColor(quality.sufficientForML ? .green : .orange)
                VStack(alignment: .leading, spacing: 2) {
                    Text("ML Training")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(quality.mlTrainingStatus)
                        .font(.body)
                }
            }
            
            if !quality.sufficientForML {
                Divider()
                
                HStack(spacing: 8) {
                    Image(systemName: "info.circle")
                        .foregroundColor(.blue)
                    Text("More historical data needed for accurate ML predictions. Run backfill to improve.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding()
        .frame(width: 300)
    }
    
    private func formatAge(hours: Int) -> String {
        if hours < 1 {
            return "Less than 1 hour"
        } else if hours < 24 {
            return "\(hours) hour\(hours == 1 ? "" : "s")"
        } else {
            let days = hours / 24
            let remainingHours = hours % 24
            if remainingHours == 0 {
                return "\(days) day\(days == 1 ? "" : "s")"
            } else {
                return "\(days)d \(remainingHours)h"
            }
        }
    }
}

// MARK: - Preview
#if DEBUG
struct DataQualityBadge_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            // Fresh data
            DataQualityBadge(dataQuality: DataQuality(
                dataAgeHours: 2,
                isStale: false,
                hasRecentData: true,
                historicalDepthDays: 365,
                sufficientForML: true,
                barCount: 500
            ))
            
            // Recent but not fresh
            DataQualityBadge(dataQuality: DataQuality(
                dataAgeHours: 12,
                isStale: false,
                hasRecentData: false,
                historicalDepthDays: 180,
                sufficientForML: true,
                barCount: 300
            ))
            
            // Stale data
            DataQualityBadge(dataQuality: DataQuality(
                dataAgeHours: 48,
                isStale: true,
                hasRecentData: false,
                historicalDepthDays: 90,
                sufficientForML: false,
                barCount: 150
            ))
            
            // No data quality
            DataQualityBadge(dataQuality: nil)
        }
        .padding()
    }
}
#endif
