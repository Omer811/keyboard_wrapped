import Cocoa
import SwiftUI

final class StatusBarController: NSObject, NSApplicationDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let monitor = SummaryMonitor()

    func applicationDidFinishLaunching(_ notification: Notification) {
        _ = panel
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "circle.grid.3x3.fill", accessibilityDescription: "Keyboard monitor")
            button.target = self
            button.action = #selector(statusItemClicked(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        monitor.start()
    }

    @objc private func statusItemClicked(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else { return }
        if event.type == .rightMouseUp {
            statusItem.button?.window?.orderOut(nil)
            NSApp.terminate(self)
            return
        }
        toggleWindow(relativeTo: sender)
    }

    private lazy var panel: NSPanel = {
        let hosting = NSHostingController(rootView: StatusBarView(monitor: monitor))
        let contentSize = NSSize(width: 320, height: 280)
        let panel = NSPanel(contentRect: NSRect(origin: .zero, size: contentSize),
                            styleMask: [.nonactivatingPanel, .fullSizeContentView],
                            backing: .buffered,
                            defer: false)
        panel.contentView = hosting.view
        panel.isFloatingPanel = true
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.hasShadow = true
        panel.isOpaque = false
        panel.backgroundColor = NSColor.windowBackgroundColor.withAlphaComponent(0.92)
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .ignoresCycle]
        panel.standardWindowButton(.closeButton)?.isHidden = true
        panel.standardWindowButton(.miniaturizeButton)?.isHidden = true
        panel.standardWindowButton(.zoomButton)?.isHidden = true
        panel.isMovableByWindowBackground = true
        return panel
    }()

    private func toggleWindow(relativeTo button: NSStatusBarButton) {
        if panel.isVisible {
            panel.orderOut(nil)
        } else {
            positionPanel(relativeTo: button)
            panel.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    private func positionPanel(relativeTo button: NSStatusBarButton) {
        guard let buttonWindow = button.window else { return }
        let buttonRect = button.convert(button.bounds, to: nil)
        let screenRect = buttonWindow.convertToScreen(buttonRect)
        let panelSize = panel.frame.size
        var x = screenRect.midX - panelSize.width / 2
        let y = screenRect.minY - panelSize.height - 8
        if let screen = buttonWindow.screen {
            let visible = screen.visibleFrame
            x = min(max(visible.minX + 12, x), visible.maxX - panelSize.width - 12)
        }
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }
}

struct StatusBarView: View {
    @ObservedObject var monitor: SummaryMonitor

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Keyboard Rings")
                .font(.title3)
                .bold()
            RingRow(title: "Keystrokes", progress: monitor.keyProgress, accent: Color.accentColor, target: monitor.keyTarget)
            RingRow(title: "Speed Points", progress: monitor.speedProgress, accent: .blue, target: monitor.speedTarget)
            RingRow(title: "Keyboard Balance", progress: monitor.handshakeProgress, accent: .green, target: monitor.handshakeTarget)
            Text(monitor.statusText)
                .font(.footnote)
                .foregroundColor(.secondary)
            Divider()
            HStack {
                Spacer()
                Button(monitor.isSampleMode ? "Switch to Live Data" : "Switch to Sample Data") {
                    monitor.toggleMode()
                }
                .keyboardShortcut("m", modifiers: [.command])
            }
        }
        .padding(12)
        .frame(width: 320)
    }
}

struct RingRow: View {
    let title: String
    let progress: Double
    let accent: Color
    let target: Double

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .stroke(accent.opacity(0.2), lineWidth: 8)
                    .frame(width: 48, height: 48)
                Circle()
                    .trim(from: 0, to: CGFloat(min(progress / target, 1)))
                    .stroke(accent, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .frame(width: 48, height: 48)
                Text("\(Int(progress))")
                    .font(.caption)
                    .foregroundColor(.primary)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline).bold()
                Text("\(Int(progress)) / \(Int(target))")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }
}

let delegate = StatusBarController()
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()
