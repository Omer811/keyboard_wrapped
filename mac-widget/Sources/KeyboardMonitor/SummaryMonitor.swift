import Foundation
import SwiftUI
import Darwin

final class SummaryMonitor: ObservableObject {
    static var repoRootURL: URL = {
        if let root = ProcessInfo.processInfo.environment["KEYBOARD_WRAPPED_ROOT"] {
            return URL(fileURLWithPath: root, isDirectory: true)
        }
        let current = URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        if current.lastPathComponent == "mac-widget" {
            return current.deletingLastPathComponent()
        }
        return current
    }()
    enum Mode: String {
        case real
        case sample

        static func current(from arguments: [String]) -> Mode {
            if arguments.contains("--sample") || ProcessInfo.processInfo.environment["KEYBOARD_WRAPPED_MODE"] == "sample" {
                return .sample
            }
            return .real
        }

        var summaryURL: URL {
            let base = SummaryMonitor.repoRootURL
            let summaryFile = self == .sample ? "data/sample_summary.json" : "data/summary.json"
            return base.appending(path: summaryFile)
        }

        var gptURL: URL {
            let base = SummaryMonitor.repoRootURL
            let gptFile = self == .sample ? "data/sample_gpt_insight.json" : "data/gpt_insights.json"
            return base.appending(path: gptFile)
        }
    }

    @Published private(set) var keyProgress: Double = 0
    @Published private(set) var speedProgress: Double = 0
    @Published private(set) var handshakeProgress: Double = 0
    @Published private(set) var keyTarget: Double = 5000
    @Published private(set) var speedTarget: Double = 120
    @Published private(set) var handshakeTarget: Double = 80
    @Published private(set) var statusText: String = "Waiting for data…"
    @Published private(set) var isSampleMode: Bool = false

    private var timer: Timer?
    private var currentMode: Mode
    private var summarySource: DispatchSourceFileSystemObject?
    private var summaryFileDescriptor: CInt?

    init() {
        currentMode = Mode.current(from: ProcessInfo.processInfo.arguments)
        isSampleMode = currentMode == .sample
    }

    deinit {
        timer?.invalidate()
        cleanupSummaryObserver()
    }

    func start() {
        setupSummaryObserver()
        reloadCurrentSummary()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.reloadCurrentSummary()
        }
    }

    func toggleMode() {
        currentMode = currentMode == .real ? .sample : .real
        isSampleMode = currentMode == .sample
        setupSummaryObserver()
        reloadCurrentSummary()
    }

    func reloadCurrentSummary() {
        do {
            let summaryData = try Data(contentsOf: currentMode.summaryURL)
            let summary = try JSONSerialization.jsonObject(with: summaryData, options: []) as? [String: Any]
            guard let summary = summary else {
                throw NSError(domain: "SummaryMonitor", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid summary structure"])
            }
            updateProgress(from: summary)
        } catch {
            statusText = "Unable to load summary: \(error.localizedDescription)"
        }
    }

    private func setupSummaryObserver() {
        summarySource?.cancel()
        summarySource = nil
        if let descriptor = summaryFileDescriptor {
            close(descriptor)
            summaryFileDescriptor = nil
        }

        let path = currentMode.summaryURL.path
        guard FileManager.default.fileExists(atPath: path) else {
            return
        }

        let descriptor = open(path, O_EVTONLY)
        guard descriptor >= 0 else {
            return
        }

        summaryFileDescriptor = descriptor
        let source = DispatchSource.makeFileSystemObjectSource(fileDescriptor: descriptor, eventMask: [.write, .delete, .rename], queue: DispatchQueue.global())
        source.setEventHandler { [weak self, weak source] in
            guard let self = self else { return }
            self.reloadCurrentSummary()
            guard let events = source?.data else { return }
            if events.contains(.delete) || events.contains(.rename) {
                DispatchQueue.main.async {
                    self.setupSummaryObserver()
                }
            }
        }
        source.setCancelHandler { [weak self] in
            if let fd = self?.summaryFileDescriptor {
                close(fd)
                self?.summaryFileDescriptor = nil
            }
        }
        summarySource = source
        source.resume()
    }

    private func cleanupSummaryObserver() {
        summarySource?.cancel()
        summarySource = nil
        if let descriptor = summaryFileDescriptor {
            close(descriptor)
            summaryFileDescriptor = nil
        }
    }

    private func updateProgress(from summary: [String: Any]) {
        let totalKeys = Double(summary["total_events"] as? Int ?? 0)
        let typingProfile = summary["typing_profile"] as? [String: Any] ?? [:]
        let avgInterval = typingProfile["avg_interval"] as? Double ?? 0
        let speedScore = avgInterval > 0 ? min(120, 60000 / avgInterval) : 0
        let handshakeScore = computeHandshake(from: summary, threshold: 250, speedReference: avgInterval)

        DispatchQueue.main.async {
            self.keyProgress = min(self.keyTarget, totalKeys)
            self.speedProgress = speedScore
            self.handshakeProgress = handshakeScore
            let modeLabel = self.currentMode == .sample ? "Sample" : "Live"
            self.statusText = "\(modeLabel) mode · Pauses \(Int(avgInterval))ms · Rings updated"
            self.persistRingState()
        }
    }

    private var widgetProgressURL: URL {
        return SummaryMonitor.repoRootURL.appending(path: "data/widget_progress.json")
    }

    private func persistRingState() {
        let snapshot: [String: Any] = [
            "timestamp": Date().timeIntervalSince1970,
            "mode": currentMode.rawValue,
            "keyProgress": keyProgress,
            "keyTarget": keyTarget,
            "speedProgress": speedProgress,
            "speedTarget": speedTarget,
            "handshakeProgress": handshakeProgress,
            "handshakeTarget": handshakeTarget
        ]
        do {
            try FileManager.default.createDirectory(at: widgetProgressURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: snapshot, options: .prettyPrinted)
            try data.write(to: widgetProgressURL)
        } catch {
            print("Failed to persist widget progress: \(error)")
        }
    }

    private func computeHandshake(from summary: [String: Any], threshold: Double, speedReference: Double) -> Double {
        let keyPairs = summary["key_pairs"] as? [String: [String: Int]] ?? [:]
        let asciiLayout = Array("qwertyuiopasdfghjklzxcvbnm")
        var score = 0
        for (from, targets) in keyPairs {
            guard let fromIndex = asciiLayout.firstIndex(of: Character(from.lowercased())) else { continue }
            for (to, count) in targets {
                guard let toIndex = asciiLayout.firstIndex(of: Character(to.lowercased())) else { continue }
                if abs(fromIndex - toIndex) >= 4 && (speedReference < threshold || speedReference == 0) {
                    score += count
                }
            }
        }
        return min(Double(score), 80)
    }
}
