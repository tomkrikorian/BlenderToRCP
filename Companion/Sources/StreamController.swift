import Foundation
import Observation
import SpatialPreview
import UniformTypeIdentifiers

/// Streams a USDZ file to a connected Apple Vision Pro using SpatialPreview's
/// `DocumentPreviewSession`. The headset shows the file in the built-in system
/// viewer; there is no app to install on the device and no IP address — the
/// endpoint is discovered over Mac Virtual Display.
@MainActor
@Observable
final class StreamController {
    enum Phase: Equatable {
        case idle
        case connecting
        case streaming
        case needsPicker
        case failed
    }

    private(set) var phase: Phase = .idle
    private(set) var message: String = ""
    private(set) var endpointName: String?

    private let observer = ConnectedSpatialEndpointObserver()
    private var session: DocumentPreviewSession?
    private var currentURL: URL?
    private var stateTask: Task<Void, Never>?

    static let usdzType: UTType =
        UTType(filenameExtension: "usdz")
        ?? UTType(importedAs: "com.pixar.universal-scene-description-mobile")

    /// Begin streaming `url`, discovering the endpoint automatically when a
    /// Vision Pro is connected, otherwise requesting the device picker.
    func start(url: URL) async {
        currentURL = url
        if observer.isEndpointAvailable {
            do {
                let endpoint = try await observer.endpoint
                await connect(to: endpoint)
                return
            } catch {
                // fall through to the picker
            }
        }
        phase = .needsPicker
        message = "Connect Apple Vision Pro via Mac Virtual Display, or choose a device."
    }

    /// Continue with an endpoint chosen from `SpatialPreviewDevicePicker`.
    func useEndpoint(_ endpoint: SpatialPreviewEndpoint) async {
        await connect(to: endpoint)
    }

    /// Push a newly exported revision to the active session.
    func update(url: URL) async {
        currentURL = url
        guard let session, phase == .streaming else { return }
        do {
            try await session.updateContents(url: url)
        } catch {
            message = "Update failed: \(error.localizedDescription)"
        }
    }

    func stop() async {
        stateTask?.cancel()
        stateTask = nil
        if let session {
            try? await session.close()
        }
        session = nil
        phase = .idle
        message = ""
        endpointName = nil
    }

    /// Re-attempt discovery (used by the status bar's retry button).
    func retry() async {
        guard let url = currentURL else { return }
        await start(url: url)
    }

    // MARK: - Private

    private func connect(to endpoint: SpatialPreviewEndpoint) async {
        phase = .connecting
        message = "Connecting…"
        let session = DocumentPreviewSession(name: "scene.usdz", contentType: Self.usdzType)
        do {
            try await session.start(endpoint: endpoint)
            self.session = session
            observeState(session)
            if let url = currentURL {
                try await session.updateContents(url: url)
            }
            phase = .streaming
            endpointName = endpoint.description
            message = "Streaming to Vision Pro"
        } catch {
            phase = .failed
            message = "Stream failed: \(error.localizedDescription)"
        }
    }

    private func observeState(_ session: DocumentPreviewSession) {
        stateTask?.cancel()
        stateTask = Task { @MainActor [weak self] in
            for await state in Observations({ session.state }) {
                guard let self else { return }
                switch state {
                case .waiting:
                    self.message = "Waiting for viewer…"
                case .connected:
                    self.phase = .streaming
                    self.message = "Streaming to Vision Pro"
                case .interrupted:
                    self.message = "Interrupted — keep the Mac Virtual Display open."
                case .invalidated:
                    self.phase = .idle
                    self.message = "Session ended."
                    self.session = nil
                    return
                @unknown default:
                    break
                }
            }
        }
    }
}
