# macOS 서버 실행

> **기존 PoC 실행 안내:** 아래 명령은 macOS·iOS·Brush PoC를 재현하는 절차다. 본 프로젝트의 Ubuntu·Nerfstudio 운영 절차와 구분한다. [기존 PoC 안내](../../README.md)를 따른다.

구현 기준: [기능 명세](../../../ios/docs/01-func/func-specs.md), [UX/UI 명세](../../../ios/docs/02-uxui/uxui-specs.md), [기술 명세](../03-tech/tech-specs.md).
Mac API, 실제 영상용 FFmpeg → COLMAP → 영역 분석, SwiftUI 촬영 앱, P1 운영자 도구를 제공한다.
**실제 장면의 P0/P1 완료 판정은 아직 하지 않았다.** 합성 데모·고정 fixture 테스트는 실제 영상 검증을 대신하지 않는다.

## 1. Mac 준비

Python 3.12 이상이 필요하다. iOS 앱 빌드용 Xcode는 별도 클라이언트 절차에서 준비한다. FFmpeg·COLMAP·Brush는 사용자가 Mac에 설치한다.
아래 `cd` 명령은 저장소 루트에서 실행한다.
예를 들어 Homebrew의 `brew install ffmpeg colmap`으로 앞의 두 도구를 설치하고,
Brush는 [공식 배포](https://github.com/ArthurBrussee/brush/releases)를 사용한다.
Brush CLI를 사용하려면 실행 파일을 `brush`라는 이름으로 PATH에 둔다.
이 저장소는 시스템 패키지를 자동 설치하거나 Brush 옵션을 추측하지 않는다.

```sh
cd poc/shared-poc/poc
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m server.experiment doctor --output gate-tools.json
```

`doctor`는 실제 설치 버전과 각 COLMAP 명령의 help, Brush help를 `gate-tools.json` 및 `gate-logs/`에 보존한다.
도구가 없거나 CPU 옵션을 확인할 수 없으면 실패한다. 설치 후 다시 실행한다.
COLMAP의 이전 `SiftExtraction/SiftMatching`과 새 `FeatureExtraction/FeatureMatching` 옵션은 **설치된 help**로 선택한다.
실제 명령 인수·종료 코드·시간·RSS·시스템 memory pressure·swap은 실행마다 `logs/`에 보존한다.

## 2. 서버 실행

신뢰하는 동일 Wi-Fi에서만 사용한다. Mac의 LAN 주소로 바인딩하고 포트 포워딩하지 않는다.
원본·분석·실패 결과는 자동 삭제하지 않는다. 작업 전 10GB 이상의 여유 공간을 확보한다.

```sh
export POC_TOKEN="$(openssl rand -hex 24)"
# 아래 주소를 자신의 Mac LAN IP로 바꾼다. 토큰 값은 앱에 직접 입력한다.
.venv/bin/python -m server --host 192.168.0.10 --port 8080
```

토큰은 환경 변수에서만 읽으며 서버가 출력하거나 Git에 저장하지 않는다.
앱에 입력할 때 자신의 터미널에서 환경 변수 값을 확인한다. `/health`를 포함한 모든 API·이미지에 토큰이 필요하다.
데이터 기본 위치는 `poc/shared-poc/poc/data/`. `--data /local/path` 또는 `POC_DATA`로 변경할 수 있다.
단일 서버 프로세스만 허용하며 API·P1 운영자 도구는 같은 파일 잠금으로 무거운 작업을 직렬화한다.

초기 G0 설정은 A 최대 60장 / B 최대 40장 / 긴 변 960px / 2fps이다.
G0 이후 필요할 때 `--initial-frames 80 --long-edge 1280`으로 늘리거나 `--initial-frames 40`으로 축소한다.
보완 영상도 축소하려면 `--supplement-frames 20`을 사용한다.
`--matcher exhaustive`는 새 run에서 전체 매칭을 재시도한다. combined는 sequential 이후 전체 매칭으로 A/B 교차 연결을 시도한다.
**선명도 임계값은 실측 전 0으로 비활성화**되어 있다. 모든 프레임의 Laplacian 분산을 기록하므로
G0 샘플의 `capture-*-frames.json`을 확인해 임계값을 정하고 `--blur-threshold 값`으로 고정한다.
B는 10~30초를 접수하지만, 2fps에서 30장 이상을 확보하려면 15초 이상이 필요하다. 흐림 제거를 고려해 20~30초를 권장한다.

## 3. 먼저 실제 영상 게이트 확인

1. 정적인 작은 방을 후면 기본 카메라 1배율·가로 1080p/30fps·SDR로 30~60초 촬영한다.
2. FFmpeg·COLMAP을 실행해 단일 희소 모델을 생성하고 실제 TXT 분석 결과를 확인한다.
3. 왜곡 보정한 데이터로 Brush에서 학습하고 Gaussian PLY가 Mac에서 열리는지 확인한다.
4. 실제 시간·memory pressure·swap·설치 버전을 기록한다. 실패하면 앱 시연 전에 해결한다.

코드 작성과 fixture 테스트는 이 게이트 통과를 의미하지 않는다. 설치 검증 전 프레임 수·해상도를 늘리지 않는다.
CPU SfM 및 M5/16GB에서의 실행 시간·메모리·Brush 호환성은 아직 측정하지 않았다.

## 4. 클라이언트 연결

[iOS 설치·사용](../../../ios/docs/05-ops/runbook.md) 또는 [Android 웹 사용](../../../android/README.md)을 따른다. Android 화면을 제공하려면 서버 실행 인수에 `--web-page ../../android/web/index.html`을 추가한다(공용 `poc/`에서 실행할 때).

## 5. 공용 API·Brush 운영

[API 확인·학습·비교 기록](../../../shared-poc/docs/05-ops/runbook.md)을 따른다.

## 6. 검증

저장소 루트에서 실행한다.

```sh
cd poc/shared-poc
poc/.venv/bin/python -m unittest discover -s poc -v
python3 poc/poc.py --demo --output /tmp/capture-guide-demo
```

기존 분석만 검사할 때는 의존성 없이 `python3 -m unittest discover -s poc -p test_poc.py -v`로 실행할 수 있다.
테스트는 입력·인증·크기 제한·프로젝트 귀속·잠금·상태 저장·재시작·실패·시간 제한·2D 상자·방향·좌표 정렬과
fixture 외부 명령으로 구성한 파이프라인 연결을 검사한다. 실제 COLMAP 또는 Brush 성공을 검증하지 않는다.

실제 장면 체크는 [검증 기록](../../../shared-poc/docs/04-test/validation.md)에 남긴다.

구현 참고: [COLMAP CLI](https://colmap.github.io/cli.html), [Brush](https://github.com/ArthurBrussee/brush),
[Apple SDR/HDR 설정](https://developer.apple.com/documentation/avfoundation/avcapturedevice/automaticallyadjustsvideohdrenabled),
[ATS 로컬 통신](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking),
[NWPath 권한 진단](https://developer.apple.com/documentation/network/nwpath/unsatisfiedreason-swift.enum).
