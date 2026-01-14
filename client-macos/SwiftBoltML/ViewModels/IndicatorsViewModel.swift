import Foundation
import Combine

@MainActor
final class IndicatorsViewModel: ObservableObject {
    @Published var config: IndicatorConfig

    private var cancellables = Set<AnyCancellable>()

    init(config: IndicatorConfig = IndicatorConfig()) {
        self.config = config
    }

    func setConfig(_ config: IndicatorConfig) {
        self.config = config
    }
}
