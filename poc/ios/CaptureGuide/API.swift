import Foundation
import Network
import os

struct Health: Decodable { let version: String; let busy: Bool; let tools: [String: Bool] }
struct ProjectReply: Decodable { let project_id: String }
struct CaptureReply: Decodable { let capture_id: String }
struct RunReply: Decodable { let run_id: String }
struct ServerError: Decodable { let code: String; let message: String }
struct ErrorReply: Decodable { let error: ServerError }
struct Reconstruction: Decodable { let state: String; let message: String? }
struct Comparison: Decodable { let judgment: String; let reason: String; let view_mode: String }
struct RunStatus: Decodable {
    let run_id: String
    let mode: String
    let state: String
    let stage: String?
    let elapsed_seconds: Double
    let error: ServerError?
    let reconstruction: Reconstruction
    let comparison: Comparison?
}
struct Region: Decodable, Identifiable {
    var id: String { region }
    let region: String
    let points: Int
    let mean_observations: Double
    let heuristic_risk: Double
    let instruction: String?
    let recommended: Bool
    let rank: Int?
    let representative_asset_id: String?
}
struct Report: Decodable {
    let registered_frames: Int
    let input_frames: Int
    let regions: [Region]
    let limitations: [String]
    let message: String
}

enum APIError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case let .message(text) = self { return text }; return nil }
}

final class API: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    let base: URL
    let token: String
    private var progress: (@Sendable (Double) -> Void)?
    private let progressLock = NSLock()
    private func setProgress(_ callback: (@Sendable (Double) -> Void)?) {
        progressLock.lock(); progress = callback; progressLock.unlock()
    }
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 60
        configuration.timeoutIntervalForResource = 600
        return URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }()

    init(address: String, token: String) throws {
        guard let url = URL(string: address.trimmingCharacters(in: .whitespacesAndNewlines)),
              ["http", "https"].contains(url.scheme), let host = url.host,
              !["localhost", "127.0.0.1", "0.0.0.0"].contains(host),
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              url.port.map({ (1...65535).contains($0) }) ?? true,
              url.path.isEmpty || url.path == "/", token.count >= 16 else {
            throw APIError.message("Mac의 LAN 주소(http://192.168.…:8080 또는 .local 호스트명)와 16자 이상 토큰을 입력하세요.")
        }
        self.base = url; self.token = token
    }

    func request(_ path: String, method: String = "GET", body: Data? = nil) -> URLRequest {
        var request = URLRequest(url: base.appendingPathComponent(path))
        request.httpMethod = method
        request.httpBody = body
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return request
    }

    func close() { session.invalidateAndCancel() }

    func checked(_ data: Data, _ response: URLResponse) throws -> Data {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            if let error = try? JSONDecoder().decode(ErrorReply.self, from: data) {
                throw APIError.message("\(error.error.message) [\(error.error.code)]")
            }
            throw APIError.message("서버 요청이 거절되었습니다. 주소·토큰·입력을 확인하세요.")
        }
        return data
    }

    func fetch<T: Decodable>(_ path: String, method: String = "GET", object: [String: Any]? = nil) async throws -> T {
        let body = try object.map { try JSONSerialization.data(withJSONObject: $0) }
        let (data, response) = try await session.data(for: request(path, method: method, body: body))
        return try JSONDecoder().decode(T.self, from: checked(data, response))
    }

    func image(_ path: String) async throws -> Data {
        let (data, response) = try await session.data(for: request(path))
        return try checked(data, response)
    }

    func upload(project: String, file: URL, role: String, progress: @escaping @Sendable (Double) -> Void) async throws -> CaptureReply {
        let boundary = UUID().uuidString
        let bodyURL = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        FileManager.default.createFile(atPath: bodyURL.path, contents: nil)
        defer { try? FileManager.default.removeItem(at: bodyURL) }
        let output = try FileHandle(forWritingTo: bodyURL)
        do {
            try output.write(contentsOf: Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"role\"\r\n\r\n\(role)\r\n--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"capture.mov\"\r\nContent-Type: video/quicktime\r\n\r\n".utf8))
            let input = try FileHandle(forReadingFrom: file)
            defer { try? input.close() }
            while let data = try input.read(upToCount: 1024 * 1024), !data.isEmpty { try output.write(contentsOf: data) }
            try output.write(contentsOf: Data("\r\n--\(boundary)--\r\n".utf8))
            try output.close()
        } catch { try? output.close(); throw error }
        var request = request("projects/\(project)/captures", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        setProgress(progress)
        defer { setProgress(nil) }
        let (data, response) = try await session.upload(for: request, fromFile: bodyURL)
        return try JSONDecoder().decode(CaptureReply.self, from: checked(data, response))
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didSendBodyData bytesSent: Int64,
                    totalBytesSent: Int64, totalBytesExpectedToSend: Int64) {
        progressLock.lock(); let callback = progress; progressLock.unlock()
        if totalBytesExpectedToSend > 0 { callback?(Double(totalBytesSent)/Double(totalBytesExpectedToSend)) }
    }

    func localNetworkDenied() async -> Bool {
        guard let host = base.host, let port = NWEndpoint.Port(rawValue: UInt16(base.port ?? (base.scheme == "https" ? 443 : 80))) else { return false }
        return await withCheckedContinuation { continuation in
            let queue = DispatchQueue(label: "local-network-check")
            let connection = NWConnection(host: NWEndpoint.Host(host), port: port, using: .tcp)
            let completed = OSAllocatedUnfairLock(initialState: false)
            @Sendable func finish(_ denied: Bool) {
                let first = completed.withLock { value in
                    if value { return false }
                    value = true; return true
                }
                guard first else { return }
                connection.cancel(); continuation.resume(returning: denied)
            }
            connection.stateUpdateHandler = { state in
                switch state {
                case .ready: finish(false)
                case .waiting, .failed:
                    if connection.currentPath?.unsatisfiedReason == .localNetworkDenied { finish(true) }
                default: break
                }
            }
            connection.start(queue: queue)
            queue.asyncAfter(deadline: .now()+2) { finish(connection.currentPath?.unsatisfiedReason == .localNetworkDenied) }
        }
    }
}
