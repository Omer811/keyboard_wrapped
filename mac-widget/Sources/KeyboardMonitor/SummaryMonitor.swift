import Foundation
import UserNotifications
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

    private static let accentPalette: [String] = ["accent", "blue", "green", "purple", "orange", "pink", "teal", "yellow"]

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
        let merged = defaults.compactMap { base[$0.key] }
        return enforceUniqueAccents(merged)
    }

    private static func enforceUniqueAccents(_ settings: [RingSetting]) -> [RingSetting] {
        var used = Set<String>()
        var paletteIndex = 0
        return settings.map { setting in
            let normalized = setting.accent.lowercased()
            if used.contains(normalized) {
                while paletteIndex < accentPalette.count && used.contains(accentPalette[paletteIndex]) {
                    paletteIndex += 1
                }
                let replacement = paletteIndex < accentPalette.count ? accentPalette[paletteIndex] : normalized
                paletteIndex += 1
                used.insert(replacement)
                return RingSetting(key: setting.key, title: setting.title, accent: replacement, enabled: setting.enabled)
            }
            used.insert(normalized)
            return setting
        }
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

    private static let canDeliverNotifications: Bool = {
        let bundlePath = Bundle.main.bundleURL.lastPathComponent
        return bundlePath.hasSuffix(".app")
    }()

    struct NotificationConfig {
        let ringMilestonesEnabled: Bool
        let speedStreaksEnabled: Bool
        let keystrokeMilestoneEnabled: Bool
        let keystrokeMilestoneInterval: Int

        static let `default` = NotificationConfig(
            ringMilestonesEnabled: true,
            speedStreaksEnabled: true,
            keystrokeMilestoneEnabled: true,
            keystrokeMilestoneInterval: 100
        )
    }

    struct WidgetConfig {
        let sampleRatio: Double
        let sampleAvgInterval: Double
        let progressPath: String
        let gptFeedPath: String
        let healthPath: String
        let debugLogPath: String
        let ringSettings: [RingSetting]
        let handshakeThreshold: Double
        let notificationsEnabled: Bool
        let ringAnimationsEnabled: Bool
        let notificationConfig: NotificationConfig
        let ringTargets: [String: Double]

        static let defaultRingTargets: [String: Double] = [
            "keystrokes": 5_000,
            "speed": 120,
            "balance": 80,
            "accuracy": 120,
        ]

        var accuracyTarget: Double {
            target(for: "accuracy")
        }

        func target(for key: String) -> Double {
            let normalizedKey = key.lowercased()
            return ringTargets[normalizedKey] ?? WidgetConfig.defaultRingTargets[normalizedKey] ?? 100
        }

        static func load() -> WidgetConfig {
            let defaultConfig = WidgetConfig(
                sampleRatio: 0.05,
                sampleAvgInterval: 210,
                progressPath: "data/widget_progress.json",
                gptFeedPath: "data/widget_gpt_feed.json",
                healthPath: "data/widget_health.json",
                debugLogPath: "data/widget_debug.log",
                ringSettings: RingSetting.defaultSettings,
                handshakeThreshold: 250,
                notificationsEnabled: false,
                ringAnimationsEnabled: true,
                notificationConfig: NotificationConfig.default,
                ringTargets: defaultRingTargets
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
            var targets = WidgetConfig.defaultRingTargets
            if let ringTargetOverrides = widget["ring_targets"] as? [String: Any] {
                for (key, rawValue) in ringTargetOverrides {
                    if let doubleValue = rawValue as? Double {
                        targets[key.lowercased()] = doubleValue
                    } else if let intValue = rawValue as? Int {
                        targets[key.lowercased()] = Double(intValue)
                    }
                }
            }
            targets["accuracy"] = accuracy
            let handshakeThreshold = widget["handshake_threshold_ms"] as? Double ?? defaultConfig.handshakeThreshold
            let notificationsEnabled = widget["notifications_enabled"] as? Bool ?? defaultConfig.notificationsEnabled
            let ringAnimationsEnabled = widget["ring_animations_enabled"] as? Bool ?? defaultConfig.ringAnimationsEnabled
            let notificationsRaw = raw["notifications"] as? [String: Any] ?? [:]
            let notificationConfig = NotificationConfig(
                ringMilestonesEnabled: notificationsRaw["ring_milestones"] as? Bool ?? NotificationConfig.default.ringMilestonesEnabled,
                speedStreaksEnabled: notificationsRaw["speed_streaks"] as? Bool ?? NotificationConfig.default.speedStreaksEnabled,
                keystrokeMilestoneEnabled: (notificationsRaw["keystroke_milestone"] as? [String: Any])?["enabled"] as? Bool ?? NotificationConfig.default.keystrokeMilestoneEnabled,
                keystrokeMilestoneInterval: (notificationsRaw["keystroke_milestone"] as? [String: Any])?["interval"] as? Int ?? NotificationConfig.default.keystrokeMilestoneInterval
            )
            let ringConfigs = (widget["rings"] as? [[String: Any]]) ?? (raw["rings"] as? [[String: Any]])
            let rings = RingSetting.merged(defaults: defaultConfig.ringSettings, overrides: ringConfigs)
            return WidgetConfig(
                sampleRatio: ratio,
                sampleAvgInterval: interval,
                progressPath: progress,
                gptFeedPath: feed,
                healthPath: health,
                debugLogPath: debug,
                ringSettings: rings,
                handshakeThreshold: handshakeThreshold,
                notificationsEnabled: notificationsEnabled,
                ringAnimationsEnabled: ringAnimationsEnabled,
                notificationConfig: notificationConfig,
                ringTargets: targets
            )
        }
    }

    private static let widgetConfig = WidgetConfig.load()

    @Published private(set) var keyProgress: Double = 0
    @Published private(set) var speedProgress: Double = 0
    @Published private(set) var handshakeProgress: Double = 0
    @Published private(set) var keyTarget: Double = SummaryMonitor.widgetConfig.target(for: "keystrokes")
    @Published private(set) var speedTarget: Double = SummaryMonitor.widgetConfig.target(for: "speed")
    @Published private(set) var handshakeTarget: Double = SummaryMonitor.widgetConfig.target(for: "balance")
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
    var ringAnimationsEnabled: Bool {
        SummaryMonitor.widgetConfig.ringAnimationsEnabled
    }

    private var timer: Timer?
    private var currentMode: Mode
    private var summarySource: DispatchSourceFileSystemObject?
    private var summaryFileDescriptor: CInt?
    private let gptRequestQueue = DispatchQueue(label: "com.keyboardmonitor.gpt", qos: .utility)
    private var gptInFlight = false
    private let monitorMode: Bool = ProcessInfo.processInfo.environment["KEYBOARD_WRAPPED_MONITOR"] == "1"
    private lazy var notificationCenter: UNUserNotificationCenter? = {
        guard notificationsEnabled else {
            return nil
        }
        return UNUserNotificationCenter.current()
    }()
    private var notificationAuthorized: Bool = false
    private var notifiedRings = Set<String>()
    private var lastSpeedProgress: Double = 0
    private let notificationConfig = SummaryMonitor.widgetConfig.notificationConfig
    private let configNotificationsEnabled: Bool = SummaryMonitor.widgetConfig.notificationsEnabled
    private var notificationsEnabled: Bool {
        configNotificationsEnabled && SummaryMonitor.canDeliverNotifications
    }
    @Published private(set) var ringPulseTriggers: [String: UUID] = [:]
    private var ringPulseTracker = RingPulseTracker()
    private var lastKeystrokeMilestone: Int = 0

    init() {
        currentMode = Mode.current(from: ProcessInfo.processInfo.arguments)
        isSampleMode = currentMode == .sample
        monitorModeEnabled = monitorMode
        if notificationsEnabled {
            requestNotificationAuthorization()
        }
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
        ensureGptFeedFile()
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

    private func ensureGptFeedFile() {
        let url = gptFeedURL
        guard !FileManager.default.fileExists(atPath: url.path) else {
            return
        }
        let placeholder: [String: Any] = [
            "timestamp": Int(Date().timeIntervalSince1970),
            "mode": currentMode.rawValue,
            "analysis_text": "Awaiting AI insight…",
            "diff": [],
            "progress": [
                "keyProgress": keyProgress,
                "speedProgress": speedProgress,
                "handshakeProgress": handshakeProgress,
                "wordAccuracyScore": accuracyScore,
            ],
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: placeholder, options: .prettyPrinted) else {
            writeDebug("Failed to serialize placeholder GPT feed", monitorOnly: true)
            return
        }
        let dir = url.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try data.write(to: url)
            writeDebug("Created placeholder GPT feed at \(url.path)", monitorOnly: true)
        } catch {
            writeDebug("Unable to persist placeholder GPT feed: \(error)", monitorOnly: true)
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
            var environment = ProcessInfo.processInfo.environment
            let pythonPath = environment["KEYBOARD_WRAPPED_PYTHON"] ?? "/usr/bin/python3"
            process.executableURL = URL(fileURLWithPath: pythonPath)
            process.currentDirectoryURL = SummaryMonitor.repoRootURL
            environment["KEYBOARD_WRAPPED_ROOT"] = SummaryMonitor.repoRootURL.path
            process.environment = environment
            process.arguments = [
                script.path,
                "--mode", self.currentMode.rawValue,
                "--root", SummaryMonitor.repoRootURL.path,
                "--once",
            ]
            self.writeDebug("Launching widget GPT bridge with \(pythonPath)", monitorOnly: true)
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

    private func requestNotificationAuthorization() {
        guard let center = notificationCenter else {
            return
        }
        center.requestAuthorization(options: [.alert, .sound]) { [weak self] granted, error in
            if let error = error {
                self?.writeDebug("Notification authorization error: \(error)", monitorOnly: true)
            }
            self?.notificationAuthorized = granted
        }
    }

    private func deliverNotification(title: String, body: String) {
        guard notificationsEnabled && notificationAuthorized, let center = notificationCenter else {
            return
        }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = UNNotificationSound.default
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        center.add(request) { [weak self] error in
            if let error = error {
                self?.writeDebug("Notification delivery error: \(error)", monitorOnly: true)
            }
        }
    }

    private func checkForRingMilestones() {
        guard notificationsEnabled, notificationConfig.ringMilestonesEnabled else {
            return
        }
        let rings: [(key: String, title: String, current: Double, target: Double)] = [
            ("keystrokes", "Keystrokes", keyProgress, keyTarget),
            ("speed", "Speed Points", speedProgress, speedTarget),
            ("balance", "Keyboard Balance", handshakeProgress, handshakeTarget),
            ("accuracy", "Typing Accuracy", accuracyScore, accuracyTarget),
        ]
        for entry in rings {
            guard entry.current >= entry.target else {
                continue
            }
            if notifiedRings.contains(entry.key) {
                continue
            }
            notifiedRings.insert(entry.key)
            deliverNotification(
                title: "\(entry.title) ring closed!",
                body: "You hit \(Int(entry.current)) / \(Int(entry.target)) and pushed the \(entry.title.lowercased()) ring over the threshold."
            )
        }
        let speedDelta = speedProgress - lastSpeedProgress
        if notificationConfig.speedStreaksEnabled && speedDelta >= 5 {
            deliverNotification(
                title: "Speed streak!",
                body: "You gained \(Int(speedDelta)) speed points in a burst—keep the tempo up."
            )
        }
        lastSpeedProgress = speedProgress
    }

    private func checkForKeystrokeMilestone(totalEvents: Double) {
        guard notificationsEnabled, notificationConfig.keystrokeMilestoneEnabled else {
            return
        }
        let interval = max(1, notificationConfig.keystrokeMilestoneInterval)
        let milestone = Int(totalEvents) / interval * interval
        guard milestone > 0 && milestone > lastKeystrokeMilestone else {
            return
        }
        lastKeystrokeMilestone = milestone
        deliverNotification(
            title: "Keystroke milestone",
            body: "You reached \(milestone) presses—keep that streak moving."
        )
    }

    private func updateRingPulse(with values: [String: Double]) {
        for (key, newValue) in values {
            if ringPulseTracker.shouldPulse(key: key, value: newValue) {
                ringPulseTriggers[key] = UUID()
            }
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
            self.updateRingPulse(with: [
                "keystrokes": min(self.keyTarget, stats.totalEvents),
                "speed": stats.speedScore,
                "balance": stats.handshakeScore,
                "accuracy": accuracyScore
            ])
            self.keyProgress = min(self.keyTarget, stats.totalEvents)
            self.speedProgress = stats.speedScore
            self.handshakeProgress = stats.handshakeScore
            self.accuracyScore = accuracyScore
            self.accuracyTarget = accuracyTarget
            let modeLabel = self.currentMode == .sample ? "Sample" : "Live"
            self.statusText = "\(modeLabel) mode · Pauses \(Int(stats.avgInterval))ms · Rings updated"
            self.persistRingState()
            self.checkForRingMilestones()
            self.checkForKeystrokeMilestone(totalEvents: stats.totalEvents)
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
        case "orange":
            return .orange
        case "pink":
            return Color.pink
        case "teal":
            return Color.teal
        case "yellow":
            return Color.yellow
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

struct RingPulseTracker {
    private var displayCache: [String: Int] = [:]

    mutating func shouldPulse(key: String, value: Double) -> Bool {
        let displayValue = Int(value)
        let lastValue = displayCache[key] ?? 0
        displayCache[key] = displayValue
        return displayValue > lastValue
    }
}
