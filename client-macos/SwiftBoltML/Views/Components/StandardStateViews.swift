import SwiftUI

// MARK: - Improvement 5: Standardized Error/Empty/Loading States

/// A reusable error view with retry capability
struct StandardErrorView: View {
    let title: String
    let message: String
    let icon: String
    let retryAction: (() -> Void)?
    let secondaryAction: (label: String, action: () -> Void)?

    init(
        title: String = "Something went wrong",
        message: String,
        icon: String = "exclamationmark.triangle.fill",
        retryAction: (() -> Void)? = nil,
        secondaryAction: (label: String, action: () -> Void)? = nil
    ) {
        self.title = title
        self.message = message
        self.icon = icon
        self.retryAction = retryAction
        self.secondaryAction = secondaryAction
    }

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 40))
                .foregroundStyle(.red.opacity(0.7))

            Text(title)
                .font(.headline)

            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            HStack(spacing: 12) {
                if let retryAction = retryAction {
                    Button(action: retryAction) {
                        Label("Retry", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(.borderedProminent)
                }

                if let secondary = secondaryAction {
                    Button(action: secondary.action) {
                        Text(secondary.label)
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

/// A reusable empty state view
struct StandardEmptyView: View {
    let title: String
    let message: String?
    let icon: String
    let actionLabel: String?
    let action: (() -> Void)?

    init(
        title: String,
        message: String? = nil,
        icon: String = "tray",
        actionLabel: String? = nil,
        action: (() -> Void)? = nil
    ) {
        self.title = title
        self.message = message
        self.icon = icon
        self.actionLabel = actionLabel
        self.action = action
    }

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 40))
                .foregroundStyle(.secondary.opacity(0.5))

            Text(title)
                .font(.headline)
                .foregroundStyle(.secondary)

            if let message = message {
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }

            if let actionLabel = actionLabel, let action = action {
                Button(action: action) {
                    Text(actionLabel)
                }
                .buttonStyle(.bordered)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

/// A reusable loading view
struct StandardLoadingView: View {
    let message: String

    init(message: String = "Loading...") {
        self.message = message
    }

    var body: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)

            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

/// A compact inline error badge
struct InlineErrorBadge: View {
    let message: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.circle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color.orange.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

/// A compact inline status badge
struct InlineStatusBadge: View {
    enum Status {
        case success
        case warning
        case error
        case info

        var color: Color {
            switch self {
            case .success: return .green
            case .warning: return .orange
            case .error: return .red
            case .info: return .blue
            }
        }

        var icon: String {
            switch self {
            case .success: return "checkmark.circle.fill"
            case .warning: return "exclamationmark.triangle.fill"
            case .error: return "xmark.circle.fill"
            case .info: return "info.circle.fill"
            }
        }
    }

    let status: Status
    let message: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: status.icon)
                .foregroundStyle(status.color)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(status.color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Previews

#if DEBUG
struct StandardStateViews_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            // Error view
            StandardErrorView(
                message: "Failed to load chart data",
                retryAction: { print("Retry") },
                secondaryAction: (label: "Settings", action: { print("Settings") })
            )
            .frame(height: 200)

            Divider()

            // Empty view
            StandardEmptyView(
                title: "No data available",
                message: "Select a symbol to view chart data",
                icon: "chart.line.uptrend.xyaxis",
                actionLabel: "Search",
                action: { print("Search") }
            )
            .frame(height: 200)

            Divider()

            // Loading view
            StandardLoadingView(message: "Loading chart...")
                .frame(height: 100)

            Divider()

            // Inline badges
            HStack(spacing: 12) {
                InlineErrorBadge(message: "Data may be stale")
                InlineStatusBadge(status: .success, message: "Live")
                InlineStatusBadge(status: .warning, message: "Delayed")
            }
        }
        .padding()
    }
}
#endif
