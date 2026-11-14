# iOS 설치·사용

iOS 17+ 실기기가 필요하다. Xcode에서 `poc/ios/CaptureGuide.xcodeproj`를 열고 `CaptureGuide`의 Signing Team·고유 Bundle Identifier를 설정해 설치한다. 시뮬레이터로 촬영 게이트를 통과할 수 없다.

1. [Mac](../../../macos/docs/05-ops/runbook.md) 서버의 주소·토큰 입력 → 연결 확인.
2. A 촬영 → 미리보기 → 업로드 → 분석 → 보완 안내 확인.
3. B 촬영·업로드·분석 후 A/A+B 결과를 선택해 확인한다. 실패는 새 작업으로 재시도한다.
4. Mac에서 [P1](../../../common/docs/runbook.md) 실행 후 `Mac 3DGS 준비 상태 갱신`으로 운영자 기록을 확인한다.

[촬영·완료 기준](../01-func/func-specs.md) · [화면·세션 복구](../02-uxui/uxui-specs.md) · [기술·권한 설정](../03-tech/tech-specs.md)

- 가로 오른쪽·H.264 8bit SDR·1080p/30fps를 확인하며 미지원 시 이유를 표시한다. 오디오는 없다.
- Documents의 원본·접수 ID를 보존한다. multipart를 청크로 작성해 파일 업로드하고 실패 시 전체 재전송한다. 재실행 시 토큰을 다시 입력한다.
- Info.plist는 카메라·로컬망 설명과 `NSAllowsLocalNetworking`을 사용한다. 숫자 IP·`.local` 접속과 권한 거부 진단은 실기기 확인이 필요하다.
- [Windows 서버](../../../windows/README.md)도 공통 API를 제공하지만 실기기 연동은 미검증이다. 앱의 Mac 문구·완료 기준은 기존 Mac 시나리오다.

저장소 루트에서 서명 없는 빌드 확인(Xcode·iOS SDK 필요):

```sh
cd poc/ios
xcodebuild -project CaptureGuide.xcodeproj -scheme CaptureGuide -sdk iphoneos \
  -configuration Debug -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
```

빌드 성공은 설치·촬영 성공을 뜻하지 않는다.
