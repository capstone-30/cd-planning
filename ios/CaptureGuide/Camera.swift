import AVFoundation
import SwiftUI
import UIKit

final class Camera: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate, @unchecked Sendable {
    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "capture-camera")
    private let movie = AVCaptureMovieFileOutput()
    @Published var ready = false
    @Published var recording = false
    @Published var denied = false
    @Published var error = ""
    @Published var elapsed = 0
    var finished: ((URL) -> Void)?
    private var timer: Timer?
    private var started: Date?
    private var cancelRecording = false

    func configure() async {
        let allowed = await AVCaptureDevice.requestAccess(for: .video)
        guard allowed else { await MainActor.run { self.denied = true }; return }
        queue.async {
            do {
                if self.session.inputs.isEmpty {
                    self.session.beginConfiguration()
                    defer { self.session.commitConfiguration() }
                    self.session.sessionPreset = .inputPriority
                    guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
                        throw APIError.message("후면 기본 카메라가 없습니다. iPhone 실기기를 사용하세요.")
                    }
                    guard let format = device.formats.first(where: {
                        let dimensions = CMVideoFormatDescriptionGetDimensions($0.formatDescription)
                        return dimensions.width == 1920 && dimensions.height == 1080 &&
                            CMFormatDescriptionGetMediaSubType($0.formatDescription) == kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange &&
                            $0.videoSupportedFrameRateRanges.contains(where: { $0.minFrameRate <= 30 && $0.maxFrameRate >= 30 }) &&
                            $0.supportedColorSpaces.contains(.sRGB)
                    }) else { throw APIError.message("1080p·30fps·8bit SDR 포맷을 지원하지 않습니다.") }
                    let input = try AVCaptureDeviceInput(device: device)
                    guard self.session.canAddInput(input), self.session.canAddOutput(self.movie) else {
                        throw APIError.message("카메라 세션을 구성할 수 없습니다.")
                    }
                    self.session.addInput(input); self.session.addOutput(self.movie)
                    try device.lockForConfiguration()
                    device.activeFormat = format
                    device.activeVideoMinFrameDuration = CMTime(value: 1, timescale: 30)
                    device.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: 30)
                    device.videoZoomFactor = 1
                    device.automaticallyAdjustsVideoHDREnabled = false
                    if format.isVideoHDRSupported { device.isVideoHDREnabled = false }
                    device.activeColorSpace = .sRGB
                    device.unlockForConfiguration()
                    guard let connection = self.movie.connection(with: .video), connection.isVideoRotationAngleSupported(0),
                          self.movie.availableVideoCodecTypes.contains(.h264) else {
                        throw APIError.message("가로 SDR H.264 녹화를 지원하지 않습니다.")
                    }
                    connection.videoRotationAngle = 0
                    self.movie.setOutputSettings([AVVideoCodecKey: AVVideoCodecType.h264], for: connection)
                }
                self.session.startRunning()
                DispatchQueue.main.async { self.ready = true }
            } catch {
                self.session.beginConfiguration()
                for input in self.session.inputs { self.session.removeInput(input) }
                for output in self.session.outputs { self.session.removeOutput(output) }
                self.session.commitConfiguration()
                DispatchQueue.main.async { self.error = error.localizedDescription; self.ready = false }
            }
        }
    }

    func start(limit: Int) {
        guard !recording else { return }
        cancelRecording = false
        let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("captures")
        do { try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true) }
        catch { self.error = error.localizedDescription; return }
        recording = true
        let url = folder.appendingPathComponent(UUID().uuidString).appendingPathExtension("mov")
        queue.async {
            self.movie.maxRecordedDuration = CMTime(seconds: Double(limit), preferredTimescale: 30)
            self.movie.maxRecordedFileSize = 250 * 1024 * 1024
            self.movie.startRecording(to: url, recordingDelegate: self)
        }
    }

    func stop(cancel: Bool = false) {
        cancelRecording = cancel
        queue.async { if self.movie.isRecording { self.movie.stopRecording() } }
    }

    func shutdown() {
        stop()
        queue.async { self.session.stopRunning() }
    }

    func fileOutput(_ output: AVCaptureFileOutput, didStartRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.recording = true; self.elapsed = 0; self.started = Date()
            self.timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
                guard let self, let start = self.started else { return }
                self.elapsed = Int(Date().timeIntervalSince(start))
            }
        }
    }

    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL,
                    from connections: [AVCaptureConnection], error: Error?) {
        DispatchQueue.main.async {
            self.timer?.invalidate(); self.timer = nil; self.recording = false
            let nsError = error as NSError?
            let succeeded = error == nil || nsError?.userInfo[AVErrorRecordingSuccessfullyFinishedKey] as? Bool == true
            if self.cancelRecording { try? FileManager.default.removeItem(at: outputFileURL) }
            else if succeeded { self.finished?(outputFileURL) }
            else { self.error = error?.localizedDescription ?? "촬영 파일을 저장하지 못했습니다." }
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let camera: Camera
    final class Preview: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
    func makeUIView(context: Context) -> Preview {
        let view = Preview()
        view.previewLayer.session = camera.session
        view.previewLayer.videoGravity = .resizeAspect
        if let connection = view.previewLayer.connection, connection.isVideoRotationAngleSupported(0) { connection.videoRotationAngle = 0 }
        return view
    }
    func updateUIView(_ uiView: Preview, context: Context) {}
}
