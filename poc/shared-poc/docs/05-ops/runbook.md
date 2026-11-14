# 공용 API·Brush 운영

macOS·Windows용 기존 Brush PoC의 공통 절차다. Ubuntu·Nerfstudio 본 프로젝트와 별개다.
명령은 `poc/shared-poc/poc/`에서 실행한다. 각 OS의 가상환경 Python을 사용하고 서버와 같은 `POC_DATA` 또는 `--data` 경로를 지정한다.
macOS는 `.venv/bin/python`, Windows PowerShell은 `.venv\Scripts\python`을 사용한다.
아래 curl 예시는 POSIX 셸 기준이며 Windows에서는 `curl.exe`와 PowerShell 인용·줄바꿈 문법으로 조정한다.

## 1. API 확인

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

## 2. P1: Brush와 비교 기록

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

