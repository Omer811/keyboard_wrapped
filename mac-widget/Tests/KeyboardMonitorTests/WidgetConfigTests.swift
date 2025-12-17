import XCTest
@testable import KeyboardMonitor

final class WidgetConfigTests: XCTestCase {
    func testRingAnimationsEnabledReflectsConfig() {
        let config = SummaryMonitor.WidgetConfig.load()
        XCTAssertTrue(config.ringAnimationsEnabled, "ring animations flag should match the widget configuration")
    }

    func testRingSettingAccentsAreUnique() {
        let overrides: [[String: Any]] = [
            ["key": "keystrokes", "accent": "blue"],
            ["key": "speed", "accent": "blue"],
            ["key": "balance", "accent": "blue"]
        ]
        let settings = RingSetting.merged(overrides: overrides)
        let accentSet = Set(settings.map { $0.accent.lowercased() })
        XCTAssertEqual(accentSet.count, settings.count, "Merged settings should have unique accent colors")
    }

    func testRingTargetOverridesInWidgetConfig() {
        let targets: [String: Double] = [
            "keystrokes": 123,
            "speed": 45,
            "balance": 67,
            "accuracy": 89
        ]
        let config = SummaryMonitor.WidgetConfig(
            sampleRatio: 0,
            sampleAvgInterval: 0,
            progressPath: "",
            gptFeedPath: "",
            healthPath: "",
            debugLogPath: "",
            ringSettings: RingSetting.defaultSettings,
            handshakeThreshold: 0,
            notificationsEnabled: false,
            ringAnimationsEnabled: true,
            notificationConfig: SummaryMonitor.NotificationConfig.default,
            ringTargets: targets
        )
        XCTAssertEqual(config.target(for: "keystrokes"), 123)
        XCTAssertEqual(config.target(for: "speed"), 45)
        XCTAssertEqual(config.target(for: "balance"), 67)
        XCTAssertEqual(config.accuracyTarget, 89)
    }
}
