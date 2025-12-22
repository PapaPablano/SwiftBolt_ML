import SwiftUI

// MARK: - Data Health View

struct DataHealthView: View {
    let dataQuality: DataQualityReport
    @State private var isExpanded = false
    
    private var healthColor: Color {
        if dataQuality.healthScore >= 0.95 {
            return .green
        } else if dataQuality.healthScore >= 0.80 {
            return .yellow
        } else {
            return .red
        }
    }
    
    private var healthIcon: String {
        if dataQuality.healthScore >= 0.95 {
            return "checkmark.shield.fill"
        } else if dataQuality.healthScore >= 0.80 {
            return "exclamationmark.shield.fill"
        } else {
            return "xmark.shield.fill"
        }
    }
    
    private var healthLabel: String {
        if dataQuality.healthScore >= 0.95 {
            return "Excellent"
        } else if dataQuality.healthScore >= 0.80 {
            return "Good"
        } else if dataQuality.healthScore >= 0.50 {
            return "Fair"
        } else {
            return "Poor"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Compact header
            Button(action: { isExpanded.toggle() }) {
                HStack(spacing: 12) {
                    // Icon
                    Image(systemName: healthIcon)
                        .foregroundStyle(healthColor)
                        .font(.title3)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text("Data Health")
                                .font(.caption.bold())
                                .foregroundStyle(.primary)
                            
                            Divider()
                                .frame(height: 12)
                            
                            Text(healthLabel.uppercased())
                                .font(.caption.bold())
                                .foregroundStyle(healthColor)
                        }
                        
                        if dataQuality.isClean {
                            Text("All data is clean and complete")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        } else {
                            Text("\(dataQuality.totalNans) missing values in \(dataQuality.columnsWithIssues) columns")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    
                    Spacer()
                    
                    // Health score
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("\(Int(dataQuality.healthScore * 100))%")
                            .font(.title3.bold())
                            .foregroundStyle(healthColor)
                        
                        Text("Health")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
            
            // Expanded details
            if isExpanded {
                Divider()
                    .padding(.vertical, 8)
                
                DataQualityDetailsView(dataQuality: dataQuality, healthColor: healthColor)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
        )
        .animation(.easeInOut(duration: 0.2), value: isExpanded)
    }
}

// MARK: - Data Quality Details View

struct DataQualityDetailsView: View {
    let dataQuality: DataQualityReport
    let healthColor: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Summary stats
            DataQualityStatsGrid(dataQuality: dataQuality)
            
            // Warnings
            if !dataQuality.warnings.isEmpty {
                WarningsSection(warnings: dataQuality.warnings)
            }
            
            // Column issues
            if !dataQuality.columnIssues.isEmpty {
                ColumnIssuesSection(issues: dataQuality.columnIssues)
            }
            
            // Health indicator bar
            HealthIndicatorBar(score: dataQuality.healthScore, color: healthColor)
        }
    }
}

// MARK: - Stats Grid

struct DataQualityStatsGrid: View {
    let dataQuality: DataQualityReport
    
    var body: some View {
        HStack(spacing: 16) {
            StatBox(label: "Rows", value: "\(dataQuality.totalRows)", icon: "list.number")
            StatBox(label: "Columns", value: "\(dataQuality.totalColumns)", icon: "tablecells")
            StatBox(label: "Missing", value: "\(dataQuality.totalNans)", icon: "questionmark.circle")
            StatBox(label: "Severity", value: dataQuality.severity.capitalized, icon: "gauge")
        }
    }
}

struct StatBox: View {
    let label: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(.secondary)
            
            Text(value)
                .font(.caption.bold().monospacedDigit())
                .foregroundStyle(.primary)
            
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Warnings Section

struct WarningsSection: View {
    let warnings: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.yellow)
                Text("Warnings")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            
            ForEach(warnings, id: \.self) { warning in
                HStack(alignment: .top, spacing: 6) {
                    Text("•")
                        .font(.caption2)
                        .foregroundStyle(.yellow)
                    Text(warning)
                        .font(.caption2)
                        .foregroundStyle(.primary)
                }
            }
        }
        .padding(8)
        .background(Color.yellow.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Column Issues Section

struct ColumnIssuesSection: View {
    let issues: [ColumnIssue]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Columns with Issues")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            ForEach(issues.prefix(5), id: \.column) { issue in
                ColumnIssueRow(issue: issue)
            }
            
            if issues.count > 5 {
                Text("+ \(issues.count - 5) more columns")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            }
        }
    }
}

struct ColumnIssueRow: View {
    let issue: ColumnIssue
    
    private var severityColor: Color {
        switch issue.severity.lowercased() {
        case "high":
            return .red
        case "medium":
            return .orange
        case "low":
            return .yellow
        default:
            return .gray
        }
    }
    
    var body: some View {
        HStack {
            Text(issue.column)
                .font(.caption2.monospaced())
                .lineLimit(1)
                .frame(maxWidth: 120, alignment: .leading)
            
            Spacer()
            
            Text("\(issue.nanCount) NaN")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
            
            Text("(\(String(format: "%.1f", issue.nanPct))%)")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(severityColor)
            
            Circle()
                .fill(severityColor)
                .frame(width: 6, height: 6)
        }
    }
}

// MARK: - Health Indicator Bar

struct HealthIndicatorBar: View {
    let score: Double
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Overall Health")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                
                Spacer()
                
                Text("\(Int(score * 100))%")
                    .font(.caption2.bold())
                    .foregroundStyle(color)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.gray.opacity(0.2))
                    
                    RoundedRectangle(cornerRadius: 4)
                        .fill(color)
                        .frame(width: geometry.size.width * score)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: - Preview
// Note: Data models (DataQualityReport, ColumnIssue) are defined in Models/EnhancedPredictionModels.swift

#Preview("Clean Data") {
    DataHealthView(dataQuality: DataQualityReport(
        healthScore: 1.0,
        totalRows: 500,
        totalColumns: 25,
        totalNans: 0,
        columnsWithIssues: 0,
        severity: "clean",
        columnIssues: [],
        warnings: [],
        isClean: true
    ))
    .padding()
    .frame(width: 350)
}

#Preview("Data with Issues") {
    DataHealthView(dataQuality: DataQualityReport(
        healthScore: 0.85,
        totalRows: 500,
        totalColumns: 25,
        totalNans: 47,
        columnsWithIssues: 3,
        severity: "medium",
        columnIssues: [
            ColumnIssue(column: "rsi_14_m15", nanCount: 25, nanPct: 5.0, severity: "low"),
            ColumnIssue(column: "macd_h1", nanCount: 15, nanPct: 3.0, severity: "low"),
            ColumnIssue(column: "volume_d1", nanCount: 7, nanPct: 1.4, severity: "low")
        ],
        warnings: [
            "Data quality below 95% (85%)",
            "3 columns have missing data"
        ],
        isClean: false
    ))
    .padding()
    .frame(width: 350)
}
