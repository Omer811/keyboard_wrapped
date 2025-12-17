import XCTest

@testable import KeyboardMonitor

final class RingPulseTrackerTests: XCTestCase {
    func testPulseTriggerOnlyWhenDisplayValueIncreases() {
        var tracker = RingPulseTracker()
        XCTAssertTrue(tracker.shouldPulse(key: "balance", value: 1.0))
        XCTAssertFalse(tracker.shouldPulse(key: "balance", value: 1.4))
        XCTAssertFalse(tracker.shouldPulse(key: "balance", value: 1.9))
        XCTAssertTrue(tracker.shouldPulse(key: "balance", value: 2.1))
        XCTAssertFalse(tracker.shouldPulse(key: "balance", value: 2.1))
        XCTAssertTrue(tracker.shouldPulse(key: "balance", value: 3.0))
    }

    func testDifferentRingsTrackedSeparately() {
        var tracker = RingPulseTracker()
        XCTAssertTrue(tracker.shouldPulse(key: "keystrokes", value: 5))
        XCTAssertTrue(tracker.shouldPulse(key: "speed", value: 1))
        XCTAssertFalse(tracker.shouldPulse(key: "keystrokes", value: 5.2))
        XCTAssertFalse(tracker.shouldPulse(key: "speed", value: 1.5))
        XCTAssertTrue(tracker.shouldPulse(key: "speed", value: 2))
    }
}
