import SwiftUI

/// Helpers to avoid "Publishing changes from within view updates" by deferring
/// Binding setters to the next run loop when UI controls (Picker, Toggle, TextField)
/// update ObservableObject state during a view update.

extension Binding {
    /// Returns a binding that defers the setter to the next run loop.
    /// Use for bindings to `@Published` properties when the control may update
    /// during a view update (e.g. Picker selection, Toggle, TextField).
    static func deferred(get: @escaping () -> Value, set: @escaping (Value) -> Void) -> Binding<Value> {
        Binding(
            get: get,
            set: { newValue in
                DispatchQueue.main.async { set(newValue) }
            }
        )
    }
}
