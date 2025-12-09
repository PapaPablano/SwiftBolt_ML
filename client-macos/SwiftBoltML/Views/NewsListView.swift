import SwiftUI

struct NewsListView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var newsViewModel: NewsViewModel {
        appViewModel.newsViewModel
    }

    var body: some View {
        Group {
            if newsViewModel.isLoading {
                LoadingNewsView()
            } else if let error = newsViewModel.errorMessage {
                NewsErrorView(message: error) {
                    Task {
                        await newsViewModel.loadNews(for: appViewModel.selectedSymbol?.ticker)
                    }
                }
            } else if newsViewModel.newsItems.isEmpty {
                EmptyNewsView()
            } else {
                NewsList(items: newsViewModel.newsItems)
            }
        }
    }
}

struct NewsList: View {
    let items: [NewsItem]

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(items) { item in
                    NewsCard(item: item)
                }
            }
            .padding()
        }
    }
}

struct NewsCard: View {
    let item: NewsItem

    var body: some View {
        Button {
            openURL()
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                Text(item.title)
                    .font(.headline)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                if let summary = item.summary {
                    Text(summary)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                }

                HStack {
                    Text(item.source)
                        .font(.caption)
                        .foregroundStyle(.blue)

                    Spacer()

                    Text(formatDate(item.publishedAt))
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(nsColor: .controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.primary.opacity(0.1), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .contentShape(Rectangle())
    }

    private func openURL() {
        if let url = URL(string: item.url) {
            NSWorkspace.shared.open(url)
        }
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

struct LoadingNewsView: View {
    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading news...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct NewsErrorView: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "newspaper")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Failed to load news")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Retry", action: onRetry)
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyNewsView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "newspaper")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No news available")
                .font(.headline)
                .foregroundStyle(.secondary)
            Text("News articles will appear here when available")
                .font(.subheadline)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// Preview removed - NewsItem requires Codable initialization
