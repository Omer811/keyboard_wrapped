import Cocoa
import SwiftUI

final class StatusBarController: NSObject, NSApplicationDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let monitor = SummaryMonitor()
    private lazy var toggleMenuItem: NSMenuItem = {
        let item = NSMenuItem(title: "", action: #selector(toggleModeFromMenu(_:)), keyEquivalent: "")
        item.target = self
        return item
    }()
    private lazy var contextMenu: NSMenu = {
        let menu = NSMenu(title: "Keyboard Monitor")
        menu.addItem(toggleMenuItem)
        menu.addItem(NSMenuItem.separator())
        let exitItem = NSMenuItem(title: "Exit Monitor", action: #selector(exitApp(_:)), keyEquivalent: "")
        exitItem.target = self
        menu.addItem(exitItem)
        return menu
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        _ = panel
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "circle.grid.3x3.fill", accessibilityDescription: "Keyboard monitor")
            button.target = self
            button.action = #selector(statusItemClicked(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        monitor.start()
        updateToggleMenuTitle()
    }

    func applicationWillTerminate(_ notification: Notification) {
        terminateHelperProcesses()
    }

    @objc private func statusItemClicked(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else { return }
        if event.type == .rightMouseUp {
            showContextMenu(relativeTo: sender)
            return
        }
        toggleWindow(relativeTo: sender)
    }

    @objc private func toggleModeFromMenu(_ sender: Any?) {
        monitor.toggleMode()
        updateToggleMenuTitle()
    }

    @objc private func exitApp(_ sender: Any?) {
        NSApp.terminate(self)
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
            monitor.panelDidReveal()
        }
    }

    private func showContextMenu(relativeTo button: NSStatusBarButton) {
        updateToggleMenuTitle()
        let menuOrigin = NSPoint(x: button.bounds.minX, y: button.bounds.minY)
        contextMenu.popUp(positioning: nil, at: menuOrigin, in: button)
    }

    private func updateToggleMenuTitle() {
        toggleMenuItem.title = monitor.isSampleMode ? "Switch to Live Data" : "Switch to Sample Data"
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

    private func terminateHelperProcesses() {
        terminatePidFile(named: ".keyboard_logger.pid")
        terminatePidFile(named: ".widget_gpt.pid")
    }

    private func terminatePidFile(named name: String) {
        let pidFile = SummaryMonitor.repoRootURL.appending(path: "mac-widget/\(name)")
        guard let pidString = try? String(contentsOf: pidFile, encoding: .utf8),
              let pid = Int(pidString.trimmingCharacters(in: .whitespacesAndNewlines))
        else {
            try? FileManager.default.removeItem(at: pidFile)
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/kill")
        process.arguments = ["-9", "\(pid)"]
        try? process.run()
        try? process.waitUntilExit()
        try? FileManager.default.removeItem(at: pidFile)
    }
}

struct StatusBarView: View {
    @ObservedObject var monitor: SummaryMonitor

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Keyboard Rings")
                .font(.title3)
                .bold()
            ForEach(monitor.activeRingSettings) { ring in
                RingRow(
                    title: ring.title,
                    progress: monitor.progressValue(for: ring.key),
                    accent: monitor.accentColor(for: ring.accent),
                    target: monitor.targetValue(for: ring.key),
                    animate: monitor.ringAnimationsEnabled,
                    pulseID: monitor.ringPulseTriggers[ring.key]
                )
            }
            if monitor.monitorModeEnabled {
                Text(monitor.statusText)
                    .font(.footnote)
                    .foregroundColor(.secondary)
                Text("Logger: \(monitor.healthStatus)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                if !monitor.healthMessage.isEmpty {
                    Text(monitor.healthMessage)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
                if !monitor.debugSnippet.isEmpty {
                    Divider()
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Recent events")
                            .font(.caption2)
                            .bold()
                        Text(monitor.debugSnippet)
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundColor(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .lineLimit(3)
                    }
                }
            }
            Divider()
            VStack(alignment: .leading, spacing: 6) {
                Text(monitor.aiInsight.isEmpty ? "Awaiting AI insight…" : monitor.aiInsight)
                    .font(.callout)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineLimit(nil)
            }
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color.accentColor.opacity(0.12)))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Color.accentColor.opacity(0.3), lineWidth: 1)
            )
            Divider()
            Text("Right-click the icon for data mode or exit.")
                .font(.caption2)
                .foregroundColor(.secondary)
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
    let animate: Bool
    let pulseID: UUID?
    @State private var animatePulse = false

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
                    .scaleEffect(animate && animatePulse ? 1.08 : 1)
                    .animation(animate ? .easeInOut(duration: 0.25) : .none, value: animatePulse)
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
        .onChange(of: pulseID) { _ in
            guard animate else { return }
            animatePulse = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                animatePulse = false
            }
        }
    }
}

let delegate = StatusBarController()
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()
