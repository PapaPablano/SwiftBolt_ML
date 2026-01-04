import Foundation
import Combine

@MainActor
final class SymbolSearchViewModel: ObservableObject {
    @Published var searchQuery: String = ""
    @Published private(set) var searchResults: [Symbol] = []
    @Published private(set) var isSearching: Bool = false
    @Published var errorMessage: String?

    private var searchTask: Task<Void, Never>?
    private let debounceInterval: UInt64 = 300_000_000 // 300ms in nanoseconds

    init() {
        setupSearchDebounce()
    }

    private func setupSearchDebounce() {
        $searchQuery
            .removeDuplicates()
            .sink { [weak self] query in
                self?.handleQueryChange(query)
            }
            .store(in: &cancellables)
    }

    private var cancellables = Set<AnyCancellable>()

    var isActive: Bool {
        let hasQuery = !searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return hasQuery || isSearching || !searchResults.isEmpty || errorMessage != nil
    }

    private func handleQueryChange(_ query: String) {
        searchTask?.cancel()

        guard !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            searchResults = []
            errorMessage = nil
            return
        }

        searchTask = Task {
            try? await Task.sleep(nanoseconds: debounceInterval)

            guard !Task.isCancelled else { return }

            await search()
        }
    }

    func search() async {
        let query = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !query.isEmpty else {
            searchResults = []
            return
        }

        print("[DEBUG] Searching for: \(query)")
        isSearching = true
        errorMessage = nil

        do {
            let results = try await APIClient.shared.searchSymbols(query: query)
            print("[DEBUG] Search returned \(results.count) results")
            guard !Task.isCancelled else { return }
            searchResults = results
        } catch {
            print("[DEBUG] Search error: \(error)")
            guard !Task.isCancelled else { return }
            errorMessage = error.localizedDescription
            searchResults = []
        }

        isSearching = false
    }

    func clearSearch() {
        searchQuery = ""
        searchResults = []
        errorMessage = nil
    }
}
