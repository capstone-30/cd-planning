# Android 웹 클라이언트

`web/index.html`은 Android Chrome에서 촬영 영상 업로드·분석 상태·보완 영역을 확인하는 웹 화면이다. Android 네이티브 앱은 구현되어 있지 않다. Python 서버와 Windows 실행 도구는 별도 폴더에서 관리한다.

브라우저는 카메라 포맷(1배·가로·1080p/30fps·SDR)을 강제하지 못하므로 기존 iPhone P0/P1 완료 판정에 사용하지 않는다. 카메라는 FHD 30, HDR 끔, 후면 기본 카메라 1배로 설정한다.

## 서버 연결

[Windows 환경 준비](../windows/README.md) 후 `poc/windows/`에서 실행한다.

```powershell
.\start-phone-server.ps1 -WebPage ..\android\web\index.html
```

[macOS 서버](../macos/README.md)에서도 공용 `poc/` 폴더에서 아래처럼 페이지를 지정할 수 있다. 토큰 설정·도구 설치는 macOS 안내를 먼저 따른다. Mac 서버와 Android 실기기의 전체 흐름은 미검증이다.

```sh
.venv/bin/python -m server --host 192.168.0.10 --port 8080 \
  --web-page ../../android/web/index.html
```

HTML은 서버의 `/`에서 제공하며 직접 파일을 열지 않는다. 빈 입력 화면은 토큰 없이 열리고 모든 API·이미지 요청에는 토큰이 필요하다.

## 폰에서 사용

폰 (Tailscale 앱이 연결되어 있거나, PC와 같은 Wi-Fi):
1. Chrome에서 표시된 주소를 연다. 반드시 `http://`로 입력한다(`https://` 아님).
2. 토큰 입력 → 연결.
3. **1단계**: 폰을 가로로 들고 30~60초 천천히 촬영 → 업로드 후 자동 분석.
4. 결과 A의 주황 상자 영역을 확인한다.
5. **2단계**: 보완 영상 15~30초 촬영 → 자동으로 A+B 분석.
6. 처음부터 다시 하려면 맨 아래 "새 프로젝트로 처음부터".

## 문제 해결

| 증상 | 해결 |
| --- | --- |
| 폰에서 주소가 안 열림 | Tailscale 주소면 폰 Tailscale 앱이 연결되어 있고 같은 계정인지 확인한다. Wi-Fi 주소면 같은 Wi-Fi인지, `http://`로 입력했는지, PC Wi-Fi가 개인 네트워크인지, 방화벽 허용했는지 |
| `UNAUTHORIZED` | 토큰 오타. 서버를 재시작하면 토큰이 바뀐다 |
| `HDR_UNSUPPORTED` | 카메라에서 HDR 동영상을 끄고 다시 촬영 |
| `VIDEO_DURATION` | A는 30~60초, B는 10~30초(30장 확보를 위해 15초 이상) |
| `FILE_TOO_LARGE` | 해상도를 FHD로 |
| `REGISTRATION_INSUFFICIENT` / `FRAMES_INSUFFICIENT` | 가로로, 더 천천히, 앞 장면과 많이 겹치게 다시 촬영 |
| `SUPPLEMENT_DISCONNECTED` | B를 A에서 찍었던 장면과 겹치게 찍기 |

결과·로그는 서버의 `shared-poc/poc/data/`에 저장된다. [공용 API·Brush 운영](../shared-poc/docs/05-ops/runbook.md)을 참고한다.
