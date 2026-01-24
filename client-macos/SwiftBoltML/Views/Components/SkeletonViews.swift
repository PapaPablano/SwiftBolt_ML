import SwiftUI

// MARK: - Skeleton Loading Views

/// A shimmer effect modifier for skeleton loading
struct ShimmerEffect: ViewModifier {
    @State private var phase: CGFloat = 0
    private let duration: Double = 1.5
    
    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geometry in
                    LinearGradient(
                        gradient: Gradient(colors: [
                            Color.clear,
                            Color.white.opacity(0.3),
                            Color.clear
                        ]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geometry.size.width * 2)
                    .offset(x: -geometry.size.width + (geometry.size.width * 2 * phase))
                }
            )
            .onAppear {
                withAnimation(
                    Animation.linear(duration: duration)
                        .repeatForever(autoreverses: false)
                ) {
                    phase = 1.0
                }
            }
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerEffect())
    }
}

/// A skeleton rectangle for loading placeholders
struct SkeletonRectangle: View {
    let width: CGFloat?
    let height: CGFloat
    let cornerRadius: CGFloat
    
    init(width: CGFloat? = nil, height: CGFloat = 20, cornerRadius: CGFloat = 8) {
        self.width = width
        self.height = height
        self.cornerRadius = cornerRadius
    }
    
    var body: some View {
        Rectangle()
            .fill(Color.gray.opacity(0.2))
            .frame(width: width, height: height)
            .cornerRadius(cornerRadius)
            .shimmer()
    }
}

/// A skeleton circle for loading placeholders
struct SkeletonCircle: View {
    let size: CGFloat
    
    init(size: CGFloat = 40) {
        self.size = size
    }
    
    var body: some View {
        Circle()
            .fill(Color.gray.opacity(0.2))
            .frame(width: size, height: size)
            .shimmer()
    }
}

/// Skeleton view for forecast quality metrics
struct ForecastQualitySkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Header
            HStack {
                SkeletonRectangle(width: 150, height: 24)
                Spacer()
                SkeletonRectangle(width: 80, height: 32, cornerRadius: 16)
            }
            
            // Quality Score Card
            VStack(alignment: .leading, spacing: 12) {
                SkeletonRectangle(width: 200, height: 20)
                HStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 8) {
                        SkeletonRectangle(width: 100, height: 14)
                        SkeletonRectangle(width: 80, height: 28)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        SkeletonRectangle(width: 100, height: 14)
                        SkeletonRectangle(width: 60, height: 24)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        SkeletonRectangle(width: 120, height: 14)
                        SkeletonRectangle(width: 60, height: 24)
                    }
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            
            // Metrics Grid
            VStack(alignment: .leading, spacing: 12) {
                SkeletonRectangle(width: 150, height: 20)
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    ForEach(0..<4) { _ in
                        VStack(alignment: .leading, spacing: 8) {
                            SkeletonRectangle(width: 100, height: 14)
                            SkeletonRectangle(width: 60, height: 20)
                        }
                        .padding()
                        .background(Color(NSColor.secondarySystemFill))
                        .cornerRadius(6)
                    }
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
        }
    }
}

/// Skeleton view for model training results
struct ModelTrainingSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            // Header
            HStack {
                SkeletonRectangle(width: 150, height: 24)
                Spacer()
                SkeletonRectangle(width: 80, height: 32, cornerRadius: 16)
            }
            
            // Performance Summary
            VStack(alignment: .leading, spacing: 12) {
                SkeletonRectangle(width: 180, height: 20)
                HStack(spacing: 20) {
                    ForEach(0..<3) { _ in
                        VStack(alignment: .leading, spacing: 8) {
                            SkeletonRectangle(width: 100, height: 14)
                            SkeletonRectangle(width: 80, height: 28)
                        }
                    }
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            
            // Metrics Grid
            VStack(alignment: .leading, spacing: 12) {
                SkeletonRectangle(width: 150, height: 20)
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    ForEach(0..<6) { _ in
                        VStack(alignment: .leading, spacing: 8) {
                            SkeletonRectangle(width: 120, height: 14)
                            SkeletonRectangle(width: 70, height: 20)
                        }
                        .padding()
                        .background(Color(NSColor.secondarySystemFill))
                        .cornerRadius(6)
                    }
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
        }
    }
}

/// Animated loading view with pulsing effect
struct PulsingLoadingView: View {
    @State private var isAnimating = false
    let message: String
    
    init(message: String = "Loading...") {
        self.message = message
    }
    
    var body: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(Color.blue.opacity(0.2))
                    .frame(width: 60, height: 60)
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
                    .opacity(isAnimating ? 0.5 : 1.0)
                
                Circle()
                    .fill(Color.blue.opacity(0.4))
                    .frame(width: 40, height: 40)
                    .scaleEffect(isAnimating ? 1.1 : 1.0)
                    .opacity(isAnimating ? 0.7 : 1.0)
                
                ProgressView()
                    .scaleEffect(1.2)
            }
            
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            withAnimation(
                Animation.easeInOut(duration: 1.0)
                    .repeatForever(autoreverses: true)
            ) {
                isAnimating = true
            }
        }
    }
}

/// Smooth fade-in animation modifier
struct FadeInModifier: ViewModifier {
    @State private var opacity: Double = 0
    
    func body(content: Content) -> some View {
        content
            .opacity(opacity)
            .onAppear {
                withAnimation(.easeIn(duration: 0.3)) {
                    opacity = 1.0
                }
            }
    }
}

extension View {
    func fadeIn() -> some View {
        modifier(FadeInModifier())
    }
}

/// Slide-in animation modifier
struct SlideInModifier: ViewModifier {
    @State private var offset: CGFloat = 20
    @State private var opacity: Double = 0
    
    func body(content: Content) -> some View {
        content
            .offset(y: offset)
            .opacity(opacity)
            .onAppear {
                withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
                    offset = 0
                    opacity = 1.0
                }
            }
    }
}

extension View {
    func slideIn() -> some View {
        modifier(SlideInModifier())
    }
}

#if DEBUG
struct SkeletonViews_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            ForecastQualitySkeleton()
                .frame(height: 400)
            
            Divider()
            
            ModelTrainingSkeleton()
                .frame(height: 400)
            
            Divider()
            
            PulsingLoadingView(message: "Loading data...")
                .frame(height: 200)
        }
        .padding()
    }
}
#endif
