import SwiftUI

struct ContentView: View {
    var body: some View {
        // Directly display the strategy builder view without any auth requirement
        // This assumes simulation mode is enabled and working
        TSStrategyBuilderView()
            .padding()
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}