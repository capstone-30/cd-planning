# 안드로이드 폰 + Windows PC로 쓰기

iPhone 앱 대신 폰의 Chrome으로 PC 서버의 웹 페이지(`server/web/index.html`, 서버의 `/`)를 열어 촬영·업로드·결과 확인을 한다.
iPhone이 없는 팀원의 개발·연습용이다. 웹 페이지는 카메라 포맷(1배·가로·1080p/30fps·SDR)을 강제할 수 없으므로 **공식 P0/P1 판정에는 사용하지 않는다.**
페이지 자체는 토큰 없이 열리지만(빈 입력 화면만 제공), 모든 API·이미지 요청에는 기존과 같이 토큰이 필요하다.

## 처음 한 번만

1. [실행 안내](../docs/05-ops/runbook.md)대로 이 사이드 프로젝트의 `poc\.venv`를 만들고 FFmpeg·COLMAP·Brush를 설치한다.
   Windows는 공식 배포판(COLMAP `colmap-x64-windows-nocuda.zip`, Brush `brush-app-x86_64-pc-windows-msvc.zip`)을 `%USERPROFILE%\Tools\colmap`, `%USERPROFILE%\Tools\brush`에 풀면 시작 스크립트가 PATH에 자동으로 추가한다.
2. **Tailscale(권장, 같은 Wi-Fi 불필요)**: PC와 폰에 Tailscale을 설치하고 **같은 계정**으로 로그인한다. 폰은 Play 스토어 "Tailscale". 이후 폰이 LTE·5G·다른 Wi-Fi에 있어도 접속된다. 내 계정 기기끼리만 연결되고 인터넷에 공개되지 않는다.
   Tailscale을 안 쓰면 아래 3~4를 따르고 폰과 PC를 같은 Wi-Fi에 둔다.
3. (Wi-Fi 방식만) PC의 Wi-Fi를 **개인 네트워크**로 설정한다. (설정 → 네트워크 및 인터넷 → Wi-Fi → 연결된 Wi-Fi → 네트워크 프로필 유형)
4. 서버를 처음 실행할 때 Windows 방화벽 창에서 **개인 네트워크만** 허용한다. (Tailscale도 개인 네트워크로 잡힌다)
5. 폰 카메라: 동영상 해상도 **FHD 30**, **HDR 동영상 끔**, 후면 기본 카메라 1배.

## 매번

PC (PowerShell, 저장소의 `side-projects\macos-ios-poc\poc` 폴더에서):
```powershell
powershell -ExecutionPolicy Bypass -File .\start-phone-server.ps1
```
화면에 접속 주소와 토큰이 표시된다. Tailscale이 켜져 있으면 `http://100.x.x.x:8080` 주소가, 아니면 Wi-Fi 주소가 나온다. 같은 Wi-Fi에서 Wi-Fi 주소를 강제로 쓰려면 끝에 `-Wifi`를 붙인다. 토큰은 실행할 때마다 바뀐다. 종료는 Ctrl+C.

폰 (Tailscale 앱이 켜져 있거나, PC와 같은 Wi-Fi):
1. Chrome에서 표시된 주소를 연다. 반드시 `http://`로 입력한다(`https://` 아님).
2. 토큰 입력 → 연결.
3. **1단계**: 폰을 가로로 들고 30~60초 천천히 촬영 → 업로드 후 자동 분석.
4. 결과 A의 주황 상자 영역을 확인한다.
5. **2단계**: 보완 영상 15~30초 촬영 → 자동으로 A+B 분석.
6. 처음부터 다시 하려면 맨 아래 "새 프로젝트로 처음부터".

## 문제 해결

| 증상 | 해결 |
| --- | --- |
| 폰에서 주소가 안 열림 | Tailscale 주소면 폰 Tailscale 앱이 켜져 있고 같은 계정인지. Wi-Fi 주소면 같은 Wi-Fi인지, `http://`로 입력했는지, PC Wi-Fi가 개인 네트워크인지, 방화벽 허용했는지 |
| `UNAUTHORIZED` | 토큰 오타. 서버를 재시작하면 토큰이 바뀐다 |
| `HDR_UNSUPPORTED` | 카메라에서 HDR 동영상을 끄고 다시 촬영 |
| `VIDEO_DURATION` | A는 30~60초, B는 10~30초(30장 확보를 위해 15초 이상) |
| `FILE_TOO_LARGE` | 해상도를 FHD로 |
| `REGISTRATION_INSUFFICIENT` / `FRAMES_INSUFFICIENT` | 가로로, 더 천천히, 앞 장면과 많이 겹치게 다시 촬영 |
| `SUPPLEMENT_DISCONNECTED` | B를 A에서 찍었던 장면과 겹치게 찍기 |

결과·로그는 이 사이드 프로젝트의 `poc\data\` 아래 프로젝트별로 쌓인다. 3DGS 학습과 비교는 [실행 안내](../docs/05-ops/runbook.md)를 따른다.
