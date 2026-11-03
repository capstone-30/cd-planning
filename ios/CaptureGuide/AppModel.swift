import Foundation
import SwiftUI

struct SavedSession: Codable {
    var address = ""
    var project: String?
    var initialCapture: String?
    var supplementCapture: String?
    var initialRun: String?
    var combinedRun: String?
    var localFile: String?
    var role = "initial"
}

@MainActor final class AppModel: ObservableObject {
    @Published var saved: SavedSession { didSet { persist() } }
    @Published var token = ""
    @Published var connected = false
    @Published var busy = false
    @Published var message = ""
    @Published var progress: Double?
    @Published var status: RunStatus?
    @Published var report: Report?
    @Published var screen = 0
    @Published var selectedRun: String?
    private var api: API?
    private var pollTask: Task<Void, Never>?
    private let storage = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("session.json")

    init() {
        saved = (try? JSONDecoder().decode(SavedSession.self, from: Data(contentsOf: storage))) ?? SavedSession()
        selectedRun = saved.combinedRun ?? saved.initialRun
    }

    func persist() { if let data = try? JSONEncoder().encode(saved) { try? data.write(to: storage, options: .atomic) } }

    func explain(_ error: Error) async -> String {
        if let urlError = error as? URLError {
            if let connection = api ?? (try? API(address: saved.address, token: token)), await connection.localNetworkDenied() {
                return "로컬 네트워크 권한이 거부되었습니다. 설정 → 개인정보 보호 및 보안 → 로컬 네트워크에서 촬영 안내 PoC를 허용하세요."
            }
            if urlError.code == .notConnectedToInternet || urlError.code == .cannotFindHost || urlError.code == .cannotConnectToHost {
                return "Mac에 연결할 수 없습니다. 주소·동일 Wi-Fi·설정의 로컬 네트워크 권한을 확인하세요. 영상은 기기에 보관됩니다. (\(urlError.code.rawValue))"
            }
            if urlError.code == .appTransportSecurityRequiresSecureConnection {
                return "HTTP 로컬 연결이 차단되었습니다. Mac의 .local 호스트명을 사용하고 ATS 설정을 확인하세요."
            }
        }
        return error.localizedDescription
    }

    func connect() async {
        busy = true; message = ""
        defer { busy = false }
        do {
            let api = try API(address: saved.address, token: token)
            var keepConnection = false
            defer { if !keepConnection { api.close() } }
            let health: Health = try await api.fetch("health")
            if saved.project == nil {
                let project: ProjectReply = try await api.fetch("projects", method: "POST")
                saved.project = project.project_id
            }
            self.api?.close(); self.api = api; connected = true; keepConnection = true
            let missing = ["ffmpeg", "ffprobe", "colmap"].filter { health.tools[$0] != true }
            message = missing.isEmpty ? "Mac 연결 완료" : "Mac 연결 완료 · 서버 설치 필요: \(missing.joined(separator: ", "))"
            screen = selectedRun == nil ? 1 : 2
            resumePolling()
        } catch { connected = false; message = await explain(error) }
    }

    func resetProject() {
        pollTask?.cancel(); api?.close(); api = nil; connected = false
        let address = saved.address
        saved = SavedSession(address: address)
        selectedRun = nil; status = nil; report = nil; screen = 0
    }

    func recorded(_ url: URL) {
        saved.localFile = url.path
        if saved.role == "initial" { saved.initialCapture = nil } else { saved.supplementCapture = nil }
    }

    func useSupplement() {
        saved.role = "supplement"; saved.localFile = nil
        saved.supplementCapture = nil; screen = 1
        message = "최초 A와 겹치는 시점을 포함해 같은 공간을 촬영하세요."
    }

    func upload() async {
        guard let api, let project = saved.project, let path = saved.localFile else { return }
        busy = true; progress = 0; message = ""
        defer { busy = false; progress = nil }
        do {
            let capture = try await api.upload(project: project, file: URL(fileURLWithPath: path), role: saved.role) { [weak self] value in
                Task { @MainActor in self?.progress = value }
            }
            if saved.role == "initial" { saved.initialCapture = capture.capture_id }
            else { saved.supplementCapture = capture.capture_id }
            message = "서버 접수 완료. 분석을 시작할 수 있습니다."
        } catch { message = await explain(error) }
    }

    var canAnalyze: Bool {
        saved.initialCapture != nil && (saved.role == "initial" || saved.supplementCapture != nil)
    }

    func analyze(mode: String? = nil) async {
        guard let api, let project = saved.project, let initial = saved.initialCapture else { return }
        let combined = (mode ?? saved.role) == "combined" || (mode == nil && saved.role == "supplement")
        if combined && saved.supplementCapture == nil { return }
        busy = true; message = ""
        defer { busy = false }
        do {
            let ids = combined ? [initial, saved.supplementCapture!] : [initial]
            let reply: RunReply = try await api.fetch("projects/\(project)/runs", method: "POST",
                object: ["mode": combined ? "combined" : "initial", "capture_ids": ids])
            if combined { saved.combinedRun = reply.run_id } else { saved.initialRun = reply.run_id }
            selectedRun = reply.run_id; status = nil; report = nil; screen = 2
            resumePolling()
        } catch { message = await explain(error) }
    }

    func selectRun(_ id: String) { selectedRun = id; report = nil; status = nil; screen = 2; resumePolling() }

    func pausePolling() { pollTask?.cancel(); pollTask = nil }

    func resumePolling() {
        pausePolling()
        guard connected, selectedRun != nil else { return }
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self, let api = self.api, let project = self.saved.project, let run = self.selectedRun else { return }
                do {
                    let status: RunStatus = try await api.fetch("projects/\(project)/runs/\(run)")
                    try Task.checkCancellation()
                    self.status = status
                    if status.state == "completed" {
                        let report: Report = try await api.fetch("projects/\(project)/runs/\(run)/report")
                        try Task.checkCancellation()
                        self.report = report; self.screen = 3
                        return
                    }
                    if status.state == "failed" { self.message = status.error?.message ?? "분석 실패"; return }
                    try await Task.sleep(for: .seconds(2))
                } catch is CancellationError { return }
                catch { self.message = await self.explain(error); return }
            }
        }
    }

    func guideImage(_ asset: String) async throws -> Data {
        guard let api, let project = saved.project, let run = selectedRun else { throw APIError.message("연결을 확인하세요.") }
        return try await api.image("projects/\(project)/runs/\(run)/media/\(asset)")
    }
}
