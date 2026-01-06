import Foundation
import CoreGraphics

struct Downsampler {
    /// Downsamples data points using the Largest-Triangle-Three-Buckets (LTTB) algorithm.
    /// - Parameters:
    ///   - points: The original array of points (x, y).
    ///   - threshold: The maximum number of points to return.
    /// - Returns: A downsampled array of points preserving visual shape.
    static func lttb(points: [CGPoint], threshold: Int) -> [CGPoint] {
        guard points.count > threshold else { return points }
        guard threshold >= 2 else { return points } // Need at least start and end

        var sampledPoints = [CGPoint]()
        sampledPoints.reserveCapacity(threshold)

        // Always add the first point
        sampledPoints.append(points[0])

        // Bucket size (excluding first and last points)
        let every = Double(points.count - 2) / Double(threshold - 2)

        var a = 0
        var nextA = 0
        
        for i in 0..<(threshold - 2) {
            // Calculate bucket boundaries
            let avgRangeStart = Int(floor(Double(i + 1) * every)) + 1
            let avgRangeEnd = Int(floor(Double(i + 2) * every)) + 1
            let avgRange = avgRangeStart..<min(avgRangeEnd, points.count)
            
            // Calculate point average for next bucket (to form the triangle)
            var avgX: Double = 0
            var avgY: Double = 0
            let avgCount = Double(avgRange.count)
            
            if avgCount > 0 {
                for j in avgRange {
                    avgX += points[j].x
                    avgY += points[j].y
                }
                avgX /= avgCount
                avgY /= avgCount
            }

            // Current bucket range
            let rangeStart = Int(floor(Double(i) * every)) + 1
            let rangeEnd = Int(floor(Double(i + 1) * every)) + 1
            let range = rangeStart..<min(rangeEnd, points.count)

            // Point a is the selected point from the previous bucket
            let pointAX = points[a].x
            let pointAY = points[a].y

            var maxArea: Double = -1
            
            for j in range {
                let pointBX = points[j].x
                let pointBY = points[j].y
                
                // Calculate triangle area over three buckets (Point A, Point B, Point Average)
                let area = abs(
                    (pointAX - avgX) * (pointBY - pointAY) -
                    (pointAX - pointBX) * (avgY - pointAY)
                ) * 0.5

                if area > maxArea {
                    maxArea = area
                    nextA = j
                }
            }

            sampledPoints.append(points[nextA])
            a = nextA
        }

        // Always add the last point
        sampledPoints.append(points[points.count - 1])

        return sampledPoints
    }
}
