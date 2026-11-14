# Windows 서버·Brush 도구

Windows에서 [공용 Python 서버](../common/README.md)를 실행하고 Brush 학습 결과를 연다. 모바일 화면과 앱 소스는 이 폴더에 포함하지 않는다.

## 처음 한 번만

1. [공용 서버 안내](../common/README.md)를 참고해 FFmpeg·COLMAP·Brush를 설치하고 아래 Python 환경을 준비한다.

   ```powershell
   cd poc\common
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   ```
   Windows는 공식 배포판(COLMAP `colmap-x64-windows-nocuda.zip`, Brush `brush-app-x86_64-pc-windows-msvc.zip`)을 `%USERPROFILE%\Tools\colmap`, `%USERPROFILE%\Tools\brush`에 푼다. 시작 스크립트가 PATH에 자동으로 추가한다. 설치 확인은 같은 공용 `poc` 폴더에서 실행한다.

   ```powershell
   $env:Path = "$env:USERPROFILE\Tools\colmap\bin;$env:USERPROFILE\Tools\brush;$env:Path"
   .venv\Scripts\python -m server.experiment doctor --output gate-tools.json
   ```
2. **Tailscale(권장, 같은 Wi-Fi 불필요)**: PC와 폰에 Tailscale을 설치하고 같은 계정으로 로그인한 뒤 연결한다. 폰은 LTE·5G·다른 Wi-Fi에서도 접속할 수 있다.
3. (Wi-Fi 방식만) PC의 Wi-Fi를 **개인 네트워크**로 설정한다. (설정 → 네트워크 및 인터넷 → Wi-Fi → 연결된 Wi-Fi → 네트워크 프로필 유형)
4. 서버를 처음 실행할 때 Windows 방화벽 창에서 **개인 네트워크만** 허용한다.
## 서버 실행

저장소의 `poc/windows/`에서 PowerShell로 실행한다.

```powershell
.\start-phone-server.ps1
```

기본 실행은 API만 제공한다. 표시된 주소와 토큰을 [iOS 앱](../ios/README.md)에 입력하거나, [Android 웹 연결 절차](../android/README.md)대로 HTML 경로를 지정한다. iOS의 Windows 서버 실기기 연동은 미검증이다.

```powershell
.\start-phone-server.ps1 -WebPage ..\android\web\index.html
```

Tailscale 주소가 있으면 `http://100.x.x.x:8080`을 우선 사용하고, 없으면 Wi-Fi 사설 주소를 사용한다. 같은 Wi-Fi에서 Wi-Fi 주소를 강제로 쓰려면 `-Wifi`를 붙인다.

`-WebPage`는 선택한 HTML 경로를 받는다. 시작 스크립트는 특정 모바일 플랫폼의 파일을 기본으로 참조하지 않는다. 토큰은 실행마다 바뀌며 Ctrl+C로 종료한다.

## 학습 결과 열기

```powershell
.\view-3d.ps1
.\view-3d.ps1 -Only A
.\view-3d.ps1 -Only AB
```

기본 데이터는 `../common/data/`다. 학습·비교는 [공용 Brush 운영 절차](../common/docs/runbook.md)를 따른다.
