import Foundation

@MainActor
final class NewsViewModel: ObservableObject {
    @Published private(set) var newsItems: [NewsItem] = []
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?

    func loadNews(for symbol: String? = nil) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchNews(symbol: symbol)
            newsItems = response.items
        } catch {
            errorMessage = error.localizedDescription
            newsItems = []
        }

        isLoading = false
    }

    func refresh(for symbol: String? = nil) async {
        await loadNews(for: symbol)
    }

    func clearData() {
        newsItems = []
        errorMessage = nil
    }
}
