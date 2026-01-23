import Foundation
import Combine
import Network

/// Network connection status
enum NetworkStatus {
    case connected
    case disconnected
    case connecting
    
    var isConnected: Bool {
        self == .connected
    }
    
    var icon: String {
        switch self {
        case .connected: return "wifi"
        case .disconnected: return "wifi.slash"
        case .connecting: return "wifi.exclamationmark"
        }
    }
    
    var description: String {
        switch self {
        case .connected: return "Online"
        case .disconnected: return "Offline"
        case .connecting: return "Connecting..."
        }
    }
}

@MainActor
final class NetworkMonitor: ObservableObject {
    static let shared = NetworkMonitor()

    @Published private(set) var isConnected: Bool = true
    @Published private(set) var status: NetworkStatus = .connected
    @Published private(set) var connectionType: String = "Unknown"

    private let monitor: NWPathMonitor
    private let queue = DispatchQueue(label: "com.swiftbolt.network-monitor")

    private init() {
        monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                guard let self = self else { return }
                
                let wasConnected = self.isConnected
                self.isConnected = path.status == .satisfied
                
                // Update status
                switch path.status {
                case .satisfied:
                    self.status = .connected
                case .requiresConnection:
                    self.status = .connecting
                case .unsatisfied:
                    self.status = .disconnected
                @unknown default:
                    self.status = .disconnected
                }
                
                // Determine connection type
                if path.usesInterfaceType(.wifi) {
                    self.connectionType = "Wi-Fi"
                } else if path.usesInterfaceType(.cellular) {
                    self.connectionType = "Cellular"
                } else if path.usesInterfaceType(.wiredEthernet) {
                    self.connectionType = "Ethernet"
                } else if path.usesInterfaceType(.loopback) {
                    self.connectionType = "Loopback"
                } else {
                    self.connectionType = "Unknown"
                }
                
                // Log status changes
                if wasConnected != self.isConnected {
                    print("[NetworkMonitor] Connection changed: \(self.isConnected ? "Connected" : "Disconnected") via \(self.connectionType)")
                }
            }
        }
        monitor.start(queue: queue)
    }
    
    deinit {
        monitor.cancel()
    }
}
