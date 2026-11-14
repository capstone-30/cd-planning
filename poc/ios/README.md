# iOS 촬영·보완 안내 앱

SwiftUI·AVFoundation 기반 iPhone 클라이언트다. 촬영·업로드·진행 조회·보완 영역 안내를 담당한다. 서버 구현과 서버 OS 준비는 별도 폴더에서 관리한다.

- [설치·사용·빌드](docs/05-ops/runbook.md)
- [기능 명세·기존 iPhone P0/P1 기준](docs/01-func/func-specs.md)
- [화면 명세](docs/02-uxui/uxui-specs.md) · [iOS 기술 명세](docs/03-tech/tech-specs.md)
- [Xcode 프로젝트](CaptureGuide.xcodeproj/) · [Swift 소스](CaptureGuide/)
- 서버 준비: [macOS](../macos/README.md) · [Windows](../windows/README.md)

앱의 기존 Mac 문구와 완료 기준은 원래 Mac 연동 시나리오를 유지한다. 서버의 공통 API를 사용하지만 Windows와의 실기기 연동은 검증하지 않았다. 실제 iPhone 촬영 P0/P1 완료·사용자 효과도 미검증이다.
