import Foundation
import SwiftUI
import Darwin

struct RingSetting: Identifiable {
    let key: String
    let title: String
    let accent: String
    let enabled: Bool

    var id: String { key }

    static let defaultSettings: [RingSetting] = [
        RingSetting(key: "keystrokes", title: "Keystrokes", accent: "accent", enabled: true),
        RingSetting(key: "speed", title: "Speed Points", accent: "blue", enabled: true),
        RingSetting(key: "balance", title: "Keyboard Balance", accent: "green", enabled: true),
        RingSetting(key: "accuracy", title: "Typing Accuracy", accent: "purple", enabled: true),
    ]

    static func merged(defaults: [RingSetting] = RingSetting.defaultSettings, overrides: [[String: Any]]?) -> [RingSetting] {
        var base = [String: RingSetting]()
        defaults.forEach { base[$0.key] = $0 }
        overrides?.forEach { raw in
            guard let key = raw["key"] as? String else {
                return
            }
            let existing = base[key]
            let title = raw["title"] as? String ?? existing?.title ?? key.capitalized
            let accent = raw["accent"] as? String ?? existing?.accent ?? "accent"
            let enabled = raw["enabled"] as? Bool ?? existing?.enabled ?? true
            base[key] = RingSetting(key: key, title: title, accent: accent, enabled: enabled)
        }
        return defaults.compactMap { base[$0.key] }
    }
}

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

    struct WidgetConfig {
        let sampleRatio: Double
        let sampleAvgInterval: Double
        let progressPath: String
        let gptFeedPath: String
        let healthPath: String
        let debugLogPath: String
        let accuracyTarget: Double
        let ringSettings: [RingSetting]
        let handshakeThreshold: Double

        static func load() -> WidgetConfig {
            let defaultConfig = WidgetConfig(
                sampleRatio: 0.05,
                sampleAvgInterval: 210,
                progressPath: "data/widget_progress.json",
                gptFeedPath: "data/widget_gpt_feed.json",
                healthPath: "data/widget_health.json",
                debugLogPath: "data/widget_debug.log",
                accuracyTarget: 120,
                ringSettings: RingSetting.defaultSettings,
                handshakeThreshold: 250
            )
            let configURL = SummaryMonitor.repoRootURL.appending(path: "config/app.json")
            guard
                let data = try? Data(contentsOf: configURL),
                let raw = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
                let widget = raw["widget"] as? [String: Any]
            else {
                return defaultConfig
            }
            let ratio = widget["sample_total_ratio"] as? Double ?? defaultConfig.sampleRatio
            let interval = widget["sample_avg_interval"] as? Double ?? defaultConfig.sampleAvgInterval
            let progress = widget["progress_path"] as? String ?? defaultConfig.progressPath
            let feed = widget["gpt_feed_path"] as? String ?? defaultConfig.gptFeedPath
            let health = widget["health_path"] as? String ?? defaultConfig.healthPath
            let debug = widget["debug_log_path"] as? String ?? defaultConfig.debugLogPath
            let accuracySettings = raw["word_accuracy"] as? [String: Any] ?? [:]
            let accuracy = accuracySettings["target_score"] as? Double ?? defaultConfig.accuracyTarget
            let handshakeThreshold = widget["handshake_threshold_ms"] as? Double ?? 250.0
            let ringConfigs = widget["rings"] as? [[String: Any]]
            let rings = RingSetting.merged(defaults: defaultConfig.ringSettings, overrides: ringConfigs)
            return WidgetConfig(
                sampleRatio: ratio,
                sampleAvgInterval: interval,
                progressPath: progress,
                gptFeedPath: feed,
                healthPath: health,
                debugLogPath: debug,
                accuracyTarget: accuracy,
                ringSettings: rings,
                handshakeThreshold: handshakeThreshold
            )
        }
    }

    private static let widgetConfig = WidgetConfig.load()

    @Published private(set) var keyProgress: Double = 0
    @Published private(set) var speedProgress: Double = 0
    @Published private(set) var handshakeProgress: Double = 0
    @Published private(set) var keyTarget: Double = 5000
    @Published private(set) var speedTarget: Double = 120
    @Published private(set) var handshakeTarget: Double = 80
    @Published private(set) var statusText: String = "Waiting for data…"
    @Published private(set) var isSampleMode: Bool = false
    @Published private(set) var aiInsight: String = "Awaiting AI insight…"
    @Published private(set) var healthStatus: String = "Logger status unknown"
    @Published private(set) var healthMessage: String = ""
    @Published private(set) var debugSnippet: String = ""
    @Published private(set) var monitorModeEnabled: Bool = false
    @Published private(set) var accuracyScore: Double = 0
    @Published private(set) var accuracyTarget: Double = SummaryMonitor.widgetConfig.accuracyTarget
    @Published private(set) var ringSettings: [RingSetting] = SummaryMonitor.widgetConfig.ringSettings

    private var timer: Timer?
    private var currentMode: Mode
    private var summarySource: DispatchSourceFileSystemObject?
    private var summaryFileDescriptor: CInt?
    private var gptRequestQueue = DispatchQueue(label: "com.keyboardmonitor.gpt", qos: .utility)
    private var gptInFlight = false
    private let monitorMode: Bool = ProcessInfo.processInfo.environment["KEYBOARD_WRAPPED_MONITOR"] == "1"

    init() {
        currentMode = Mode.current(from: ProcessInfo.processInfo.arguments)
        isSampleMode = currentMode == .sample
        monitorModeEnabled = monitorMode
    }

    deinit {
        timer?.invalidate()
        cleanupSummaryObserver()
    }

    func start() {
        setupSummaryObserver()
        reloadCurrentSummary()
        reloadGptInsight()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.reloadCurrentSummary()
            if self?.monitorMode == true {
                self?.reloadDebugLog()
            }
            self?.reloadGptInsight()
        }
        if monitorMode {
            reloadDebugLog()
        }
    }

    func toggleMode() {
        currentMode = currentMode == .real ? .sample : .real
        isSampleMode = currentMode == .sample
        setupSummaryObserver()
        reloadCurrentSummary()
        requestGptInsight()
        if monitorMode {
            reloadDebugLog()
        }
    }

    func reloadCurrentSummary() {
        let maxAttempts = 3
        var lastError: Error?
        for attempt in 1...maxAttempts {
            do {
                let summaryData = try Data(contentsOf: currentMode.summaryURL)
                let summary = try JSONSerialization.jsonObject(with: summaryData, options: []) as? [String: Any]
                guard let summary = summary else {
                    throw NSError(
                        domain: "SummaryMonitor",
                        code: 1,
                        userInfo: [NSLocalizedDescriptionKey: "Invalid summary structure"]
                    )
                }
                let normalized = normalizedSummary(summary)
                updateProgress(from: normalized)
                return
            } catch {
                lastError = error
                if attempt < maxAttempts && shouldRetrySummaryError(error) {
                    usleep(120_000) // allow the writer to complete
                    continue
                }
                break
            }
        }

        guard let error = lastError else {
            return
        }
        DispatchQueue.main.async {
            self.statusText = "Unable to load summary: \(error.localizedDescription)"
        }
        writeDebug("Summary reload error: \(error)")
    }

    private func shouldRetrySummaryError(_ error: Error) -> Bool {
        let nsError = error as NSError
        return nsError.domain == NSCocoaErrorDomain && nsError.code == 3840
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
            writeDebug("Summary file missing at \(path)")
            return
        }

        let descriptor = open(path, O_EVTONLY)
        guard descriptor >= 0 else {
            writeDebug("Unable to open summary descriptor at \(path)")
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
        writeDebug("Observing summary file at \(path)", monitorOnly: true)
    }

    private func cleanupSummaryObserver() {
        summarySource?.cancel()
        summarySource = nil
        if let descriptor = summaryFileDescriptor {
            close(descriptor)
            summaryFileDescriptor = nil
        }
    }

    private var gptFeedURL: URL {
        return SummaryMonitor.repoRootURL.appending(path: SummaryMonitor.widgetConfig.gptFeedPath)
    }

    private func reloadGptInsight() {
        do {
            let data = try Data(contentsOf: gptFeedURL)
            let payload = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
            let text = payload?["analysis_text"] as? String
            DispatchQueue.main.async {
                self.aiInsight = text ?? "Awaiting AI insight…"
            }
        } catch {
            DispatchQueue.main.async {
                self.aiInsight = "Awaiting AI insight…"
            }
            writeDebug("GPT insight reload error: \(error)")
        }
    }

    func requestGptInsight() {
        gptRequestQueue.async { [weak self] in
            guard let self = self else { return }
            guard !self.gptInFlight else {
                return
            }
            self.gptInFlight = true
            defer {
                self.gptInFlight = false
            }
            let script = SummaryMonitor.repoRootURL.appending(path: "scripts/widget_gpt.py")
            guard FileManager.default.fileExists(atPath: script.path) else {
                self.writeDebug("GPT bridge script missing at \(script.path)")
                return
            }
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.currentDirectoryURL = SummaryMonitor.repoRootURL
            var environment = ProcessInfo.processInfo.environment
            environment["KEYBOARD_WRAPPED_ROOT"] = SummaryMonitor.repoRootURL.path
            process.environment = environment
            process.arguments = [
                script.path,
                "--mode", self.currentMode.rawValue,
                "--root", SummaryMonitor.repoRootURL.path,
                "--once",
            ]
            process.standardOutput = nil
            process.standardError = nil
            self.writeDebug("Triggering GPT insight for \(self.currentMode.rawValue) mode", monitorOnly: true)
            do {
                try process.run()
                process.waitUntilExit()
                self.writeDebug("GPT insight finished with \(process.terminationStatus)", monitorOnly: true)
            } catch {
                self.writeDebug("GPT insight invocation failed: \(error)")
            }
            DispatchQueue.main.async {
                self.reloadGptInsight()
            }
        }
    }

    func panelDidReveal() {
        requestGptInsight()
    }

    private func reloadDebugLog() {
        guard monitorMode else {
            DispatchQueue.main.async {
                self.debugSnippet = ""
            }
            return
        }
        let target = debugLogURL
        guard FileManager.default.fileExists(atPath: target.path),
              let text = try? String(contentsOf: target, encoding: .utf8),
              !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            DispatchQueue.main.async {
                self.debugSnippet = ""
            }
            return
        }
        let lines = text
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .filter { !$0.isEmpty }
        let tail = lines.suffix(4)
        DispatchQueue.main.async {
            self.debugSnippet = tail.joined(separator: "\n")
        }
    }

    private func updateProgress(from summary: [String: Any]) {
        reloadHealthStatus()
        let stats = SummaryStats.from(summary: summary, handshakeThreshold: SummaryMonitor.widgetConfig.handshakeThreshold)
        let accuracySummary = summary["word_accuracy"] as? [String: Any] ?? [:]
        let accuracyTarget = SummaryMonitor.widgetConfig.accuracyTarget
        let rawAccuracyScore = accuracySummary["score"] as? Double ?? 0
        let accuracyScore = min(max(rawAccuracyScore, 0), accuracyTarget)

        DispatchQueue.main.async {
            self.keyProgress = min(self.keyTarget, stats.totalEvents)
            self.speedProgress = stats.speedScore
            self.handshakeProgress = stats.handshakeScore
            self.accuracyScore = accuracyScore
            self.accuracyTarget = accuracyTarget
            let modeLabel = self.currentMode == .sample ? "Sample" : "Live"
            self.statusText = "\(modeLabel) mode · Pauses \(Int(stats.avgInterval))ms · Rings updated"
            self.persistRingState()
        }
    }

    private func normalizedSummary(_ summary: [String: Any]) -> [String: Any] {
        guard currentMode == .sample else {
            return summary
        }
        return applySampleAdjustments(summary)
    }

    private func applySampleAdjustments(_ summary: [String: Any]) -> [String: Any] {
        var adjusted = summary
        let ratio = max(0.0, min(1.0, SummaryMonitor.widgetConfig.sampleRatio))
        let scaledKeys = ["total_events", "letters", "actions", "words", "rage_clicks", "long_pauses"]
        for key in scaledKeys {
            if let intValue = summary[key] as? Int {
                adjusted[key] = max(1, Int(round(Double(intValue) * ratio)))
            } else if let doubleValue = summary[key] as? Double {
                adjusted[key] = max(1, Int(round(doubleValue * ratio)))
            }
        }
        var typing = adjusted["typing_profile"] as? [String: Any] ?? [:]
        typing["avg_interval"] = SummaryMonitor.widgetConfig.sampleAvgInterval
        adjusted["typing_profile"] = typing
        return adjusted
    }

    private var widgetProgressURL: URL {
        return SummaryMonitor.repoRootURL.appending(path: SummaryMonitor.widgetConfig.progressPath)
    }

    private var healthStatusURL: URL {
        return SummaryMonitor.repoRootURL.appending(path: SummaryMonitor.widgetConfig.healthPath)
    }

    private var debugLogURL: URL {
        return SummaryMonitor.repoRootURL.appending(path: SummaryMonitor.widgetConfig.debugLogPath)
    }

    private static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private func persistRingState() {
        let snapshot: [String: Any] = [
            "timestamp": Date().timeIntervalSince1970,
            "mode": currentMode.rawValue,
            "keyProgress": keyProgress,
            "keyTarget": keyTarget,
            "speedProgress": speedProgress,
            "speedTarget": speedTarget,
            "handshakeProgress": handshakeProgress,
            "handshakeTarget": handshakeTarget,
            "wordAccuracyScore": accuracyScore,
            "wordAccuracyTarget": accuracyTarget
        ]
        do {
            try FileManager.default.createDirectory(at: widgetProgressURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: snapshot, options: .prettyPrinted)
            try data.write(to: widgetProgressURL)
        } catch {
            print("Failed to persist widget progress: \(error)")
            writeDebug("Failed to persist widget progress: \(error)")
        }
    }

    var activeRingSettings: [RingSetting] {
        ringSettings.filter { $0.enabled }
    }

    func progressValue(for key: String) -> Double {
        switch key {
        case "keystrokes":
            return min(keyProgress, keyTarget)
        case "speed":
            return speedProgress
        case "balance":
            return handshakeProgress
        case "accuracy":
            return accuracyScore
        default:
            return 0
        }
    }

    func targetValue(for key: String) -> Double {
        switch key {
        case "keystrokes":
            return keyTarget
        case "speed":
            return speedTarget
        case "balance":
            return handshakeTarget
        case "accuracy":
            return accuracyTarget
        default:
            return 100
        }
    }

    func accentColor(for accent: String) -> Color {
        switch accent.lowercased() {
        case "blue":
            return .blue
        case "green":
            return .green
        case "purple":
            return .purple
        case "accent":
            return .accentColor
        default:
            return .accentColor
        }
    }

    private func writeDebug(_ message: String, monitorOnly: Bool = false) {
        if monitorOnly && !monitorMode {
            return
        }
        let entry = "[\(SummaryMonitor.isoFormatter.string(from: Date()))] \(message)\n"
        let data = entry.data(using: .utf8) ?? Data()
        let target = debugLogURL
        let dir = target.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            print("Failed to create debug folder: \(error)")
            return
        }
        if FileManager.default.fileExists(atPath: target.path) {
            if let handle = try? FileHandle(forWritingTo: target) {
                handle.seekToEndOfFile()
                handle.write(data)
                try? handle.close()
                return
            }
        }
        try? data.write(to: target)
    }

    private func reloadHealthStatus() {
        let defaultStatus = "Logger offline"
        let defaultMessage = "Waiting for logger data"
        guard
            FileManager.default.fileExists(atPath: healthStatusURL.path),
            let data = try? Data(contentsOf: healthStatusURL),
            let payload = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
        else {
            updateHealthDisplay(status: defaultStatus, message: defaultMessage)
            return
        }
        let status = (payload["status"] as? String ?? "Unknown").capitalized
        let message = payload["message"] as? String ?? ""
        updateHealthDisplay(status: status, message: message)
    }

    private func updateHealthDisplay(status: String, message: String) {
        DispatchQueue.main.async {
            self.healthStatus = status
            self.healthMessage = message
        }
    }

}
