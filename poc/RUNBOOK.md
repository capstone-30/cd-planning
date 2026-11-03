# 촬영 안내 PoC 실행

구현 기준: [기능 명세](../docs/func-specs.md), [기술 명세](../docs/tech-specs.md).
Mac API, 실제 영상용 FFmpeg → COLMAP → 영역 분석, SwiftUI 촬영 앱, P1 운영자 도구를 제공한다.
**실제 장면의 P0/P1 완료 판정은 아직 하지 않았다.** 합성 데모·고정 fixture 테스트는 실제 영상 검증을 대신하지 않는다.

## 1. Mac 준비

Python 3.12 이상과 Xcode가 필요하다. FFmpeg·COLMAP·Brush는 사용자가 Mac에 설치한다.
예를 들어 Homebrew의 `brew install ffmpeg colmap`으로 앞의 두 도구를 설치하고,
Brush는 [공식 배포](https://github.com/ArthurBrussee/brush/releases)를 사용한다.
Brush CLI를 사용하려면 실행 파일을 `brush`라는 이름으로 PATH에 둔다.
이 저장소는 시스템 패키지를 자동 설치하거나 Brush 옵션을 추측하지 않는다.

```sh
cd /Users/jeong/Projects/capstone-design/poc
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
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
데이터 기본 위치는 `poc/data/`. `--data /local/path` 또는 `POC_DATA`로 변경할 수 있다.
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

## 4. iPhone 앱

`ios/CaptureGuide.xcodeproj`를 Xcode에서 연다. `CaptureGuide` 타깃의 Signing Team과 고유 Bundle Identifier를 설정하고 iPhone에 설치한다.
iOS 17 이상이 필요하며, 시뮬레이터에는 후면 실제 카메라가 없어 촬영 게이트를 통과할 수 없다.

1. Mac 주소와 개발 토큰 입력 → 연결 확인. 프로젝트가 생성된다.
2. 최초 A 촬영 → 영상 미리보기 → 업로드 → 분석 시작.
3. 작업 진행에서 단계·경과 시간 확인. 전경에서 2초마다 조회하며 완료·실패 시 중지한다.
4. 보완 안내에서 주황 영역 상자와 촬영 문구 확인 → 보완 B 촬영 → 업로드 → 분석 시작. 후보 위치·자세가 없어 축 화살표는 표시하지 않는다. 시점 선택기 v2의 입력 조건은 [새 안내 설계](../docs/guidance-v2.md)를 따른다.
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

## 5. API 확인

아래 명령은 서버와 같은 터미널 또는 `POC_TOKEN`이 설정된 별도 터미널에서 사용한다.

```sh
curl -H "Authorization: Bearer $POC_TOKEN" http://192.168.0.10:8080/health
curl -X POST -H "Authorization: Bearer $POC_TOKEN" http://192.168.0.10:8080/projects
curl -H "Authorization: Bearer $POC_TOKEN" -F role=initial -F file=@/path/to/A.mov \
  http://192.168.0.10:8080/projects/PROJECT_ID/captures
curl -H "Authorization: Bearer $POC_TOKEN" -H 'Content-Type: application/json' \
  -d '{"mode":"initial","capture_ids":["CAPTURE_A_ID"]}' \
  http://192.168.0.10:8080/projects/PROJECT_ID/runs
curl -H "Authorization: Bearer $POC_TOKEN" \
  http://192.168.0.10:8080/projects/PROJECT_ID/runs/RUN_ID
```

combined 요청은 `{"mode":"combined","capture_ids":["CAPTURE_A_ID","CAPTURE_B_ID"]}`이다.
서로 다른 역할 1개씩·같은 프로젝트만 허용한다. 응답을 받지 못한 업로드는 run에 자동 포함되지 않는다.
`/report`는 분석 완료 후에만 제공한다. `/media/{asset_id}`는 report에 등록한 PNG ID만 허용한다.
재시도마다 새 run ID를 만들고 과거 결과는 보존한다. 서버 재시작으로 중단된 작업은 `SERVER_RESTARTED` 실패가 된다.

분석 성공 기준: 하나의 모델에 입력 60% 이상·최소 30장·점 100개 이상.
A+B는 추가로 A 60% 이상과 B 최소 10장이 같은 모델에 있어야 한다.
대표 이미지 상자는 카메라 투영 가정 대신 실제 POINTS2D 관측 경계를 사용한다.
상위 후보는 근거 점 5개 이상인 영역 최대 3개이며, 근거가 없으면 `안내 근거 부족`으로 표시한다.

## 6. P1: Brush와 비교 기록

먼저 각 run의 왜곡 보정 입력을 생성한다. 서버와 **동일한 data 경로**를 사용한다.

```sh
.venv/bin/python -m server.experiment prepare PROJECT_ID RUN_A_ID
.venv/bin/python -m server.experiment prepare PROJECT_ID RUN_AB_ID
brush --help
```

설치된 Brush help를 보고 **그 버전에서 유효한** 학습 명령을 JSON 문자열 배열로 작성한다.
첫 항목은 `brush`, 입력 경로 대신 `{dataset}`, 출력 PLY 경로 대신 `{output}`을 사용한다.
확인하지 않은 학습 옵션명을 예제 명령으로 고정하지 않았다. 도움말이 다른 입력/출력 체계를 요구하면
해당 버전으로 이 연결부를 먼저 검증해야 한다. 명령에는 실제 학습 스텝·해상도·밀도 설정을 명시한다.

별도 `brush-settings.json`에는 동일한 실제 설정을 기록한다. 예:

```json
{"resolution":960,"steps":3000,"density":"설치 버전에서 확인한 실제 값","version":"설치한 Brush 버전"}
```

```sh
.venv/bin/python -m server.experiment train PROJECT_ID RUN_A_ID \
  --argv brush-argv.json --settings brush-settings.json
.venv/bin/python -m server.experiment train PROJECT_ID RUN_AB_ID \
  --argv brush-argv.json --settings brush-settings.json
```

도구는 설치된 help에 없는 긴 옵션을 거절한다. 각 학습을 최대 15분으로 제한하고 메모리 압박을 감시한다.
`--version`을 지원하면 버전을 실행 기록하고, 지원하지 않으면 settings의 version 값을 요구한다.
성공 후 `runs/<run>/splats/result.ply`에 Gaussian 속성과 데이터가 있는지 확인하고 준비 상태를 갱신한다.
이미 ready인 결과는 덮어쓰지 않는다. 메타데이터의 settings가 실제 argv와 일치하는지는 운영자가 확인한다.
해당 PLY 두 개를 Brush 뷰어에서 직접 열어야 F07을 통과한다. 파일 생성만으로 열기 성공을 보고하지 않는다.

화면 JSON은 최소 3쌍의 로컬 이미지 경로 배열이다.

```json
[
  {"initial":"/path/to/a1.png","combined":"/path/to/ab1.png"},
  {"initial":"/path/to/a2.png","combined":"/path/to/ab2.png"},
  {"initial":"/path/to/a3.png","combined":"/path/to/ab3.png"}
]
```

```sh
.venv/bin/python -m server.experiment compare PROJECT_ID RUN_A_ID RUN_AB_ID \
  --screens screens.json --judgment unchanged \
  --view-mode approximate --reason '근사 시점에서 뚜렷한 차이를 관찰하지 못함'
```

공통 A 이미지의 카메라 중심으로 A+B → A similarity를 계산한다. 최소 3개 비공선 중심이 필요하며,
목표 카메라 분산 대비 RMSE 10% 이하면 초기 정렬 기준을 통과한다. 이 임계값도 실측 보정 전 운영 기준이다.
변환·잔차는 `comparison/<A-run>-<AB-run>/alignment.json`에 보존하고 PLY를 변환해서 덮어쓰지 않는다.
뷰어에서 변환과 같은 카메라를 실제로 재현한 경우에만 `--view-mode aligned`로 기록한다.
정렬은 성공했으나 뷰어에서 단순 육안 시점이면 `approximate`. 정렬 실패 또는 관찰 불가는 `--judgment incomparable`로 기록하며
이 경우 `--screens`에 빈 배열을 허용한다. `aligned` 요청인데 좌표 정렬 실패면 기록을 거절하고 실패 근거를 보존한다.
가능한 판단은 `improved / unchanged / worse / incomparable`. 원인 효과·일반화·정량 품질을 주장하지 않는다.

## 7. 검증

```sh
cd /Users/jeong/Projects/capstone-design
poc/.venv/bin/python -m unittest discover -s poc -v
python3 poc/poc.py --demo --output /tmp/capture-guide-demo
xcodebuild -project ios/CaptureGuide.xcodeproj -scheme CaptureGuide -sdk iphoneos \
  -configuration Debug -derivedDataPath ios/build CODE_SIGNING_ALLOWED=NO build
```

기존 분석만 검사할 때는 의존성 없이 `python3 -m unittest discover -s poc -p test_poc.py -v`로 실행할 수 있다.
테스트는 입력·인증·크기 제한·프로젝트 귀속·잠금·상태 저장·재시작·실패·시간 제한·2D 상자·방향·좌표 정렬과
fixture 외부 명령으로 구성한 파이프라인 연결을 검사한다. 실제 COLMAP 또는 Brush 성공을 검증하지 않는다.

실제 장면 체크는 [검증 기록](VALIDATION.md)에 남긴다.

구현 참고: [COLMAP CLI](https://colmap.github.io/cli.html), [Brush](https://github.com/ArthurBrussee/brush),
[Apple SDR/HDR 설정](https://developer.apple.com/documentation/avfoundation/avcapturedevice/automaticallyadjustsvideohdrenabled),
[ATS 로컬 통신](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking),
[NWPath 권한 진단](https://developer.apple.com/documentation/network/nwpath/unsatisfiedreason-swift.enum).
