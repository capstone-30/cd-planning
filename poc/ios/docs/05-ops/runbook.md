# iOS 앱 설치·사용

`poc/ios/CaptureGuide.xcodeproj`를 저장소 루트 기준으로 Xcode에서 연다. `CaptureGuide` 타깃의 Signing Team과 고유 Bundle Identifier를 설정하고 iPhone에 설치한다.
iOS 17 이상이 필요하며, 시뮬레이터에는 후면 실제 카메라가 없어 촬영 게이트를 통과할 수 없다.

1. Mac 주소와 개발 토큰 입력 → 연결 확인. 프로젝트가 생성된다.
2. 최초 A 촬영 → 영상 미리보기 → 업로드 → 분석 시작.
3. 작업 진행에서 단계·경과 시간 확인. 전경에서 2초마다 조회하며 완료·실패 시 중지한다.
4. 보완 안내에서 주황 영역 상자와 촬영 문구 확인 → 보완 B 촬영 → 업로드 → 분석 시작. 후보 위치·자세가 없어 축 화살표는 표시하지 않는다. 자동 촬영 시점 선택은 제공하지 않는다.
5. 작업 진행의 `최초 A` / `최초+보완 A+B`로 각 결과를 조회한다. 실패 시 새 작업으로 재시도한다.
6. Mac에서 P1 작업을 실행한 뒤 앱의 `Mac 3DGS 준비 상태 갱신`을 누르면 상태·운영자 기록을 확인할 수 있다.

앱은 오디오 입력을 만들지 않는다. H.264 8bit SDR·1080p·30fps 포맷을 확인하며 지원하지 않으면 이유를 표시한다.
촬영 방향은 가로 오른쪽으로 고정한다. 로컬 영상과 프로젝트·run·서버 접수 capture ID를 Documents에 보존한다.
업로드는 청크로 multipart 파일을 작성한 다음 URLSession 파일 업로드를 사용한다. 전송 실패 시 원본은 보존되며 전체 재전송한다.
재실행 후 토큰을 다시 입력하면 저장한 run을 조회한다. 토큰은 기기에 영구 저장하지 않는다.

Info.plist에는 카메라·로컬 네트워크 설명과 `NSAllowsLocalNetworking`만 설정했다.
전역 `NSAllowsArbitraryLoads`는 사용하지 않는다. 숫자 IP와 `.local` 호스트명 모두 실기기에서 확인해야 한다.
네트워크 오류 시 NWConnection의 `localNetworkDenied`가 확인되면 권한 거부로 구분하며,
그 외에는 Mac 주소·Wi-Fi·권한을 점검하도록 안내한다. 권한 진단 자체가 실패하면 설정에서 직접 확인한다.

## 빌드 확인

저장소 루트에서 실행한다. Xcode와 iOS SDK가 필요하다.

```sh
cd poc/ios
xcodebuild -project CaptureGuide.xcodeproj -scheme CaptureGuide -sdk iphoneos \
  -configuration Debug -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
```

서명 없는 빌드 성공은 실기기 설치·촬영 성공을 의미하지 않는다.
서버 준비는 [macOS](../../../macos/docs/05-ops/runbook.md) 또는 [Windows](../../../windows/README.md), 앱 화면은 [UX/UI 명세](../02-uxui/uxui-specs.md)를 따른다. 앱에 남아 있는 Mac 문구와 기존 실기기 기준은 원래 Mac 연동 기준이며 Windows와의 실기기 연동은 별도로 검증한다.
