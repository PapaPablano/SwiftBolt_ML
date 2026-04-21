import SwiftUI

// MARK: - Design Tokens: Typography

extension DesignTokens {
    enum Typography {
        static let heading = Font.title2.weight(.semibold)
        static let subheading = Font.headline
        static let body = Font.body
        static let caption = Font.caption
        static let mono = Font.system(.body, design: .monospaced)
        static let monoSmall = Font.system(.caption, design: .monospaced)
    }
}

// MARK: - Typography View Modifiers

struct HeadingStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(DesignTokens.Typography.heading)
    }
}

struct CaptionStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(DesignTokens.Typography.caption)
            .foregroundStyle(.secondary)
    }
}

struct MonoStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(DesignTokens.Typography.mono)
    }
}

extension View {
    func headingStyle() -> some View { modifier(HeadingStyle()) }
    func captionStyle() -> some View { modifier(CaptionStyle()) }
    func monoStyle() -> some View { modifier(MonoStyle()) }
}
