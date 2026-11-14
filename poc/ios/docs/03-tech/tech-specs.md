# iOS 앱 기술 명세

- SwiftUI 4화면: 서버 연결 / 촬영·미리보기 / 작업 진행 / 보완 안내. 프로젝트·run ID는 로컬에 저장한다.
- AVFoundation으로 가로 1080p/30fps, 기본 후면 렌즈·1배율·SDR을 요청하고 실제 지원 포맷을 확인한다. 오디오 입력은 추가하지 않는다. 지원하지 않으면 이유를 표시하며 다른 포맷으로 조용히 대체하지 않는다.
- URLSession의 파일 업로드를 사용해 영상 전체를 메모리에 올리지 않는다. 분석 상태는 앱이 전경일 때 2초 간격으로 조회하며 완료·실패 시 중단한다.
- 카메라·로컬 네트워크 사용 설명을 Info.plist에 넣는다. Mac 주소는 `localhost`가 아닌 LAN 주소를 사용한다. 개발용 HTTP의 ATS 예외는 사용하는 로컬 주소 방식에 맞춰 최소 범위로 설정하고 숫자 IP·로컬 호스트명 모두 실기기에서 확인한다. 전역 `NSAllowsArbitraryLoads`를 기본값으로 사용하지 않는다. [로컬 네트워크 권한](https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription), [ATS 로컬 설정](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking)
- 앱 설치는 Xcode의 실기기 개발 서명을 사용한다. Xcode·iOS SDK의 기기 지원 여부는 G0에서 확인하며 App Store 배포는 요구하지 않는다.


서버 API·영상 처리·저장 구조는 [macOS 서버 기술 명세](../../../macos/docs/03-tech/tech-specs.md), 실행은 [iOS 운영 안내](../05-ops/runbook.md)를 따른다.
