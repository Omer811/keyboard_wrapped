import Foundation

struct SummaryStats {
    let totalEvents: Double
    let avgInterval: Double
    let speedScore: Double
    let handshakeScore: Double
    let keyPairCount: Int

    private static let asciiLayout: [Character] = Array("qwertyuiopasdfghjklzxcvbnm")

    static func from(summary: [String: Any], handshakeThreshold: Double = 250.0) -> SummaryStats {
        let totalEvents = Double(summary["total_events"] as? Int ?? 0)
        let typingProfile = summary["typing_profile"] as? [String: Any] ?? [:]
        let avgInterval = typingProfile["avg_interval"] as? Double ?? 0
        let speedData = summary["speed_points"] as? [String: Any] ?? [:]
        let earnedPoints = Double(speedData["earned"] as? Int ?? 0)
        let speedScore = earnedPoints
        let keyPairs = summary["key_pairs"] as? [String: [String: Int]] ?? [:]
        let handshakeScore = computeHandshake(keyPairs: keyPairs, threshold: handshakeThreshold, speedReference: avgInterval)
        return SummaryStats(
            totalEvents: totalEvents,
            avgInterval: avgInterval,
            speedScore: speedScore,
            handshakeScore: handshakeScore,
            keyPairCount: keyPairs.count
        )
    }

    private static func computeHandshake(keyPairs: [String: [String: Int]], threshold: Double, speedReference: Double) -> Double {
        var score = 0
        for (from, targets) in keyPairs {
            guard let fromIndex = layoutIndex(for: from) else {
                continue
            }
            for (to, count) in targets {
                guard let toIndex = layoutIndex(for: to) else {
                    continue
                }
                if abs(fromIndex - toIndex) >= 4 {
                    score += count
                }
            }
        }
        let baseScore = Double(min(score, 80))
        let speedFactor: Double
        if threshold <= 0 {
            speedFactor = 1
        } else {
            speedFactor = min(1, threshold / max(speedReference, 1))
        }
        return max(0, baseScore * speedFactor)
    }

    private static func layoutIndex(for key: String) -> Int? {
        guard let character = key.lowercased().first else {
            return nil
        }
        return asciiLayout.firstIndex(of: character)
    }

}
