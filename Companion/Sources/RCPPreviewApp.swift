import SwiftUI

/// RCPPreview — the macOS companion for BlenderToRCP.
///
/// Launched by the Blender add-on with `--session <dir>`. It watches that
/// session directory for USD revisions published by the live-export engine and
///   * renders the scene in RealityKit on the desktop (Feature 1), and/or
///   * streams it to a connected Apple Vision Pro via SpatialPreview (Feature 2).
///
/// Which features are active is driven by `control.json` in the session dir, so
/// the two Blender buttons act independently against a single running app.
@main
struct RCPPreviewApp: App {
    @State private var model: SessionModel

    init() {
        _model = State(initialValue: SessionModel(sessionDir: Self.parseSessionDir()))
    }

    var body: some Scene {
        WindowGroup("RealityKit Preview") {
            ContentView(model: model)
                .frame(minWidth: 520, minHeight: 400)
                .task { model.start() }
        }
        .defaultSize(width: 900, height: 640)
    }

    private static func parseSessionDir() -> URL? {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--session"), i + 1 < args.count else {
            return nil
        }
        return URL(fileURLWithPath: args[i + 1], isDirectory: true)
    }
}
