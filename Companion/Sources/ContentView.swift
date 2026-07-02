import SwiftUI
import SpatialPreview

struct ContentView: View {
    @Bindable var model: SessionModel

    var body: some View {
        VStack(spacing: 0) {
            Group {
                if model.sessionDir == nil {
                    placeholder(
                        title: "No session",
                        detail: "Launch from Blender via “Preview in RealityKit” or “Send to Vision Pro”."
                    )
                } else if model.desktopActive {
                    DesktopPreviewView(model: model)
                } else if model.streamActive {
                    streamOnly
                } else {
                    placeholder(title: "Waiting for Blender…", detail: "Keep this window open.")
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            if model.streamActive {
                Divider()
                StreamStatusBar(model: model)
            }
        }
        .sheet(isPresented: $model.showPicker) {
            SpatialPreviewDevicePicker(isPresented: $model.showPicker) { endpoint in
                Task { await model.stream.useEndpoint(endpoint) }
            }
            .frame(minWidth: 380, minHeight: 320)
        }
    }

    private var streamOnly: some View {
        VStack(spacing: 12) {
            Image(systemName: "visionpro")
                .font(.system(size: 56))
                .foregroundStyle(.secondary)
            Text("Streaming to Vision Pro")
                .font(.headline)
            Text("Rev \(model.rev) • desktop preview not active")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(white: 0.12))
    }

    private func placeholder(title: String, detail: String) -> some View {
        VStack(spacing: 10) {
            Image(systemName: "cube.transparent")
                .font(.system(size: 52))
                .foregroundStyle(.secondary)
            Text(title).font(.headline)
            Text(detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 360)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(white: 0.12))
    }
}

struct StreamStatusBar: View {
    @Bindable var model: SessionModel

    var body: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(indicatorColor)
                .frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 1) {
                Text(model.stream.message.isEmpty ? "Vision Pro" : model.stream.message)
                    .font(.callout)
                if let name = model.stream.endpointName, !name.isEmpty {
                    Text(name).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                }
            }
            Spacer()
            if model.stream.phase == .needsPicker || model.stream.phase == .failed {
                Button("Choose Device…") { model.showPicker = true }
                Button("Retry") { Task { await model.stream.retry() } }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    private var indicatorColor: Color {
        switch model.stream.phase {
        case .streaming: return .green
        case .connecting: return .yellow
        case .needsPicker: return .orange
        case .failed: return .red
        case .idle: return .secondary
        }
    }
}
