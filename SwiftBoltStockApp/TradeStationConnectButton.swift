import SwiftUI

struct TradeStationConnectButton: View {
    @StateObject var vm = TradeStationViewModel()
    
    var body: some View {
        VStack {
            Button(action: startAuth) {
                Text(vm.isAuthenticated ? "Connected to TradeStation" : "Connect TradeStation")
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(vm.isAuthenticated ? Color.green : Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            
            if let error = vm.lastError {
                Text("Error: \(error)")
                    .foregroundColor(.red)
                    .font(.caption)
                    .padding(.top, 5)
            }
        }
        .padding()
    }
    
    private func startAuth() {
        guard let window = NSApplication.shared.windows.first else {
            return
        }
        vm.connect(presentingAnchor: window)
    }
}

struct TradeStationConnectButton_Previews: PreviewProvider {
    static var previews: some View {
        TradeStationConnectButton()
    }
}