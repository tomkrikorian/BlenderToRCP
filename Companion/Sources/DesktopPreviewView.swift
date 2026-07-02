import SwiftUI
import RealityKit
import USDKit

/// Renders the exported scene in RealityKit with built-in orbit camera
/// controls, reloading whenever Blender publishes a new revision.
struct DesktopPreviewView: View {
    let model: SessionModel

    @State private var root = Entity()
    @State private var loadError: String?

    var body: some View {
        RealityView { content in
            content.add(root)
            content.add(Self.makeKeyLight())
        }
        .realityViewCameraControls(.orbit)
        .task(id: model.desktopReload) {
            await reload()
        }
        .overlay(alignment: .topTrailing) {
            Text("Rev \(model.rev)")
                .font(.caption2.monospacedDigit())
                .padding(.horizontal, 8).padding(.vertical, 4)
                .background(.thinMaterial, in: Capsule())
                .padding(10)
        }
        .overlay(alignment: .bottomLeading) {
            if let loadError {
                Text(loadError)
                    .font(.caption)
                    .padding(8)
                    .background(.red.opacity(0.75), in: RoundedRectangle(cornerRadius: 6))
                    .padding(10)
            }
        }
        .background(Color(white: 0.1))
    }

    @MainActor
    private func reload() async {
        guard let url = model.desktopURL else { return }
        do {
            let stage = try USDStage.open(url)
            let component = await USDStageComponent(stage)
            root.components.set(component)
            model.desktopLoadedRev = model.rev
            loadError = nil
        } catch {
            loadError = "Load failed: \(error.localizedDescription)"
        }
    }

    /// A soft directional fill so scenes remain legible even when their own
    /// lighting is sparse. The exported stage's lights still apply.
    @MainActor
    private static func makeKeyLight() -> Entity {
        let light = DirectionalLight()
        light.light.intensity = 2500
        light.orientation = simd_quatf(angle: -.pi / 3, axis: [1, 0.2, 0])
        return light
    }
}
