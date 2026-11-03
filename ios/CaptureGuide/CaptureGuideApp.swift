import AVKit
import SwiftUI

@main struct CaptureGuideApp: App {
    @StateObject private var model = AppModel()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(model)
                .onChange(of: phase) { _, phase in
                    if phase == .active { model.resumePolling() } else { model.pausePolling() }
                }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if !model.message.isEmpty { Text(model.message).font(.callout).padding(10).frame(maxWidth: .infinity).background(.yellow.opacity(0.12)) }
                TabView(selection: $model.screen) {
                    ConnectionView().tabItem { Label("서버 연결", systemImage: "network") }.tag(0)
                    CaptureView().tabItem { Label("촬영·업로드", systemImage: "video") }.tag(1)
                    StatusView().tabItem { Label("작업 진행", systemImage: "clock") }.tag(2)
                    GuideView().tabItem { Label("보완 안내", systemImage: "viewfinder") }.tag(3)
                }
            }.navigationTitle("촬영 안내 PoC").navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct ConnectionView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        Form {
            Section("같은 Wi-Fi의 Mac") {
                TextField("http://Mac이름.local:8080", text: $model.saved.address)
                    .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                    .disabled(model.connected)
                SecureField("개발 토큰 (앱 재실행 시 다시 입력)", text: $model.token)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                Button("연결 확인") { Task { await model.connect() } }.disabled(model.busy)
            }
            Section {
                Text("가로 1080p / 30fps / 후면 기본 카메라 / 1배율 / SDR. 원본 영상은 iPhone과 Mac에만 보관합니다.")
                Text("로컬 네트워크 권한 거부 여부를 iOS가 연결 오류에서 항상 구분해 주지는 않습니다. 설정 → 개인정보 보호 및 보안 → 로컬 네트워크에서 확인하세요.")
                Button("앱 설정 열기") { UIApplication.shared.open(URL(string: UIApplication.openSettingsURLString)!) }
                Button("새 프로젝트 시작") { model.resetProject() }.disabled(model.busy)
            }
        }
    }
}

struct CaptureView: View {
    @EnvironmentObject var model: AppModel
    @StateObject private var camera = Camera()
    @State private var showCamera = false
    @State private var player: AVPlayer?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(model.saved.role == "initial" ? "최초 영상 A · 30~60초" : "보완 영상 B · 10~30초 (분석용 15초 이상 권장)").font(.title2.bold())
                Text("정적인 공간을 천천히 촬영하고, 인접 시점이 충분히 겹치도록 움직이세요. 보완 영상에도 A에서 본 부분을 포함하세요.")
                if showCamera {
                    CameraPreview(camera: camera).frame(height: 210).background(.black)
                    if camera.recording {
                        Text("촬영 \(camera.elapsed)초").monospacedDigit()
                        HStack {
                            Button("촬영 종료") { camera.stop() }
                            Button("촬영 취소", role: .cancel) { camera.stop(cancel: true) }
                        }
                    } else {
                        Button("녹화 시작") { camera.start(limit: model.saved.role == "initial" ? 60 : 30) }.disabled(!camera.ready)
                    }
                } else if let player {
                    VideoPlayer(player: player).frame(height: 210)
                }
                if camera.denied {
                    Text("카메라 권한이 거부되었습니다. 설정에서 카메라 접근을 허용하세요.")
                    Button("설정 열기") { UIApplication.shared.open(URL(string: UIApplication.openSettingsURLString)!) }
                }
                if !camera.error.isEmpty { Text(camera.error).foregroundStyle(.red) }
                HStack {
                    Button(model.saved.localFile == nil ? "카메라 열기" : "재촬영") {
                        player?.pause(); showCamera = true
                        Task { await camera.configure() }
                    }.disabled(camera.recording || model.busy)
                    Button("영상 업로드") { Task { await model.upload() } }
                        .disabled(!model.connected || model.saved.localFile == nil || model.busy || camera.recording || showCamera)
                    Button("분석 시작") { Task { await model.analyze() } }
                        .buttonStyle(.borderedProminent).disabled(!model.connected || !model.canAnalyze || model.busy || camera.recording)
                }
                if let progress = model.progress { ProgressView(value: progress) { Text("업로드 \(Int(progress*100))%") } }
                if !model.connected { Text("먼저 Mac 서버에 연결하세요.").foregroundStyle(.secondary) }
            }.padding()
        }
        .onAppear {
            camera.finished = { url in
                model.recorded(url); showCamera = false; camera.shutdown(); player = AVPlayer(url: url)
            }
            if let path = model.saved.localFile { player = AVPlayer(url: URL(fileURLWithPath: path)) }
        }
        .onDisappear { player?.pause(); camera.shutdown(); showCamera = false }
    }
}

struct StatusView: View {
    @EnvironmentObject var model: AppModel
    private let stages = ["preprocess": "프레임 추출", "sfm": "SfM 정합", "analyze": "영역 분석"]
    var body: some View {
        Form {
            RunPicker()
            if let status = model.status {
                Section(status.mode == "initial" ? "최초 A" : "최초+보완 A+B") {
                    Text(["queued": "대기", "running": "처리 중", "completed": "완료", "failed": "실패"][status.state] ?? status.state)
                    if let stage = status.stage { Text(stages[stage] ?? stage) }
                    Text("경과 \(Int(status.elapsed_seconds))초").monospacedDigit()
                    if ["queued", "running"].contains(status.state) { ProgressView() }
                    if let error = status.error { Text("\(error.message) [\(error.code)]").foregroundStyle(.red) }
                    Text("3DGS: \(status.reconstruction.state) · \(status.reconstruction.message ?? "")")
                }
            } else { Text("실행할 작업을 선택하거나 촬영 영상을 업로드하세요.") }
            Button("상태 다시 확인") { model.resumePolling() }.disabled(!model.connected)
            if model.status?.state == "failed" {
                Button("새 작업으로 재시도") { Task { await model.analyze(mode: model.status?.mode) } }.disabled(!model.canAnalyze || model.busy)
            }
        }
    }
}

struct RunPicker: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        Section("결과 선택") {
            HStack {
                if let run = model.saved.initialRun { Button("최초 A") { model.selectRun(run) } }
                if let run = model.saved.combinedRun { Button("최초+보완 A+B") { model.selectRun(run) } }
            }
        }
    }
}

struct GuideView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let report = model.report {
                    Text(model.status?.mode == "combined" ? "최초+보완 A+B 결과" : "최초 A 결과").font(.headline)
                    Text("\(report.registered_frames) / \(report.input_frames) 프레임 정합 · \(report.message)").font(.title2.bold())
                    ForEach(report.regions.filter(\.recommended)) { region in
                        VStack(alignment: .leading, spacing: 12) {
                            Text("\(region.rank ?? 0). 추가 촬영 후보 · 영역 \(region.region)").font(.headline)
                            Text("평균 관측 \(region.mean_observations, specifier: "%.1f") · 근거 점 \(region.points)개 · 규칙 기반 참고 점수 \(region.heuristic_risk, specifier: "%.3f")")
                            if let asset = region.representative_asset_id { GuideImage(asset: asset) }
                            Text(region.instruction ?? "표시 영역이 보이는 위치에서 화면에 유지하며 천천히 옆 시점으로 촬영하세요. 이동 가능 여부는 직접 확인하세요.").font(.callout)
                        }.padding().background(.quaternary, in: RoundedRectangle(cornerRadius: 16))
                    }
                    ForEach(report.limitations, id: \.self) { Text($0).font(.footnote).foregroundStyle(.secondary) }
                    if let comparison = model.status?.comparison {
                        Text("운영자 관찰: \(comparison.judgment) · \(comparison.reason) · 시점 \(comparison.view_mode)")
                    }
                    Button("보완 영상 B 촬영") { model.useSupplement() }.buttonStyle(.borderedProminent)
                    Button("Mac 3DGS 준비 상태 갱신") { model.resumePolling() }
                } else { Text("분석이 완료되면 대표 이미지와 추가 촬영 후보가 표시됩니다.") }
            }.padding()
        }
    }
}

struct GuideImage: View {
    @EnvironmentObject var model: AppModel
    let asset: String
    @State private var image: UIImage?
    @State private var error = ""
    var body: some View {
        VStack {
            if let image { Image(uiImage: image).resizable().scaledToFit().accessibilityLabel("추가 촬영 후보의 영역 또는 SfM 참고 방향") }
            else if !error.isEmpty { Text(error).font(.caption); Button("이미지 재시도") { Task { await load() } } }
            else { ProgressView() }
        }.frame(maxWidth: .infinity).task(id: asset) { await load() }
    }
    func load() async {
        do {
            let data = try await model.guideImage(asset)
            guard let decoded = UIImage(data: data) else { throw APIError.message("이미지를 읽을 수 없습니다.") }
            image = decoded; error = ""
        } catch { self.error = error.localizedDescription }
    }
}
