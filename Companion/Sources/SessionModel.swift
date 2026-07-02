import Foundation
import Observation

/// Watches a BlenderToRCP live-session directory and drives the desktop preview
/// and the Vision Pro stream.
///
/// Handoff files in the session directory:
///   * `control.json` (written by Blender) — `{ "desktop": Bool, "stream": Bool }`
///   * `latest.json`  (written by Blender) — `{ "rev": Int, "artifacts": { "desktop": "vNNN/scene.usdc", "stream": "vNNN/scene.usdz" } }`
///   * `status.json`  (written here)       — stream state surfaced back to the Blender panel
@MainActor
@Observable
final class SessionModel {
    let sessionDir: URL?

    // Driven by control.json.
    var desktopActive = false
    var streamActive = false

    // Driven by latest.json.
    var rev = 0
    /// Bumped whenever a new desktop artifact is published; the desktop view
    /// reloads via `.task(id:)` keyed on this value.
    var desktopReload = 0
    /// The revision currently rendered in RealityKit (set by the desktop view
    /// once a stage finishes loading). Surfaced in status.json.
    var desktopLoadedRev = 0
    var desktopURL: URL?
    var streamURL: URL?

    var showPicker = false

    let stream = StreamController()

    private var pollTask: Task<Void, Never>?
    private var lastControlMTime: Date?
    private var lastLatestMTime: Date?

    init(sessionDir: URL?) {
        self.sessionDir = sessionDir
    }

    func start() {
        guard pollTask == nil else { return }
        pollTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                self?.poll()
                try? await Task.sleep(for: .milliseconds(250))
            }
        }
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
    }

    // MARK: - Polling

    private func poll() {
        guard let dir = sessionDir else { return }
        readControl(in: dir)
        readLatest(in: dir)
        writeStatus(in: dir)
    }

    private func readControl(in dir: URL) {
        let url = dir.appendingPathComponent("control.json")
        guard let m = modifiedDate(url) else { return }
        if m == lastControlMTime { return }
        lastControlMTime = m

        guard let obj = readJSONObject(url) else { return }
        let newDesktop = obj["desktop"] as? Bool ?? false
        let newStream = obj["stream"] as? Bool ?? false

        desktopActive = newDesktop

        if newStream != streamActive {
            streamActive = newStream
            if newStream {
                Task { await startStreamIfPossible() }
            } else {
                Task { await stream.stop() }
            }
        }
    }

    private func readLatest(in dir: URL) {
        let url = dir.appendingPathComponent("latest.json")
        guard let m = modifiedDate(url) else { return }
        if m == lastLatestMTime { return }
        lastLatestMTime = m

        guard let obj = readJSONObject(url) else { return }
        rev = obj["rev"] as? Int ?? rev
        let artifacts = obj["artifacts"] as? [String: String] ?? [:]

        if let desktop = artifacts["desktop"] {
            desktopURL = dir.appendingPathComponent(desktop)
            desktopReload &+= 1
        }
        if let streamRel = artifacts["stream"] {
            streamURL = dir.appendingPathComponent(streamRel)
            if streamActive, let u = streamURL {
                Task { await stream.update(url: u) }
            }
        }
    }

    private func startStreamIfPossible() async {
        guard let url = streamURL else { return }
        await stream.start(url: url)
        if stream.phase == .needsPicker {
            showPicker = true
        }
    }

    private func writeStatus(in dir: URL) {
        let dict: [String: Any] = [
            "rev": rev,
            "loaded_rev": desktopLoadedRev,
            "streaming": stream.phase == .streaming,
            "endpoint": stream.endpointName ?? "",
            "message": stream.message,
            "error": stream.phase == .failed ? stream.message : "",
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted) else {
            return
        }
        try? data.write(to: dir.appendingPathComponent("status.json"), options: .atomic)
    }

    // MARK: - Helpers

    private func modifiedDate(_ url: URL) -> Date? {
        (try? FileManager.default.attributesOfItem(atPath: url.path))?[.modificationDate] as? Date
    }

    private func readJSONObject(_ url: URL) -> [String: Any]? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }
}
