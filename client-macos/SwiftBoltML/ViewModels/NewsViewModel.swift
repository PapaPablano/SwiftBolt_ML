import Foundation

@MainActor
final class NewsViewModel: ObservableObject {
    @Published private(set) var newsItems: [NewsItem] = []
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?

    func loadNews(for symbol: String? = nil) async {
        print("[DEBUG] ========================================")
        print("[DEBUG] NewsViewModel.loadNews() CALLED")
        print("[DEBUG] - Symbol: \(symbol ?? "nil")")
        print("[DEBUG] ========================================")

        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchNews(symbol: symbol)
            newsItems = response.items
            print("[DEBUG] NewsViewModel.loadNews() - SUCCESS!")
            print("[DEBUG] - Received \(newsItems.count) news items")
        } catch {
            print("[DEBUG] NewsViewModel.loadNews() - ERROR: \(error)")
            if APIError.isSupabaseUnreachable(error) {
                errorMessage = "Offline: news unavailable"
            } else {
                errorMessage = error.localizedDescription
            }
            newsItems = []
        }

        isLoading = false
        print("[DEBUG] NewsViewModel.loadNews() COMPLETED")
        print("[DEBUG] ========================================")
    }

    func refresh(for symbol: String? = nil) async {
        await loadNews(for: symbol)
    }

    func clearData() {
        newsItems = []
        errorMessage = nil
    }
}
