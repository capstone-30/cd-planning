# 경량 PoC 기술 명세

작성일: 2026-11-10 · 기능 기준: [func-specs.md](func-specs.md)

초기 명세를 구현 현황에 맞춰 갱신한 문서다. 현재 실행·실측 범위와 미완료 항목은 [검증 기록](validation.md)을 따른다. 공개 실내 데이터의 Mac·Windows 처리 경로와 iOS 빌드는 검증했지만 실기기 전체 흐름은 미검증이다. 시점 선택 실험은 [중단 기록](reports/closed-experiments.md)으로 남겼다.

2026-11-13 갱신: Windows에서도 핵심 경로를 재현했으며 v2 화질 비교에서는 균등 선택 대비 개선을 확인하지 못했다. 제품 목표를 복원 상태 표시·보완 촬영 지원으로 조정했다. 저장 자료의 상태 일치 점검은 [후속 결과](reports/capture-support-result.md), 실기기 지원 효과 검증은 [촬영 절차](capture-support-validation.md)를 따른다.

## 1. 구성과 선택

```text
iPhone 앱 (SwiftUI + AVFoundation + URLSession)
  └─ 동일 Wi-Fi / HTTP + 개발용 토큰
       Mac: FastAPI + 단일 작업 실행 루프 + 로컬 파일
         ├─ FFmpeg: 프레임 추출·영상 방향 반영
         ├─ COLMAP: 특징·매칭·희소 복원·모델 변환·왜곡 보정
         ├─ poc/poc.py: 영역 특징·규칙 점수 (후보 자세 없이 방향 생성 안 함)
         └─ Brush: 3DGS 학습·PLY 저장·Mac 뷰어 (P1, 초기 수동)
```

- 서버는 macOS에서 네이티브 실행한다. Docker·CUDA·PyTorch는 첫 PoC에 도입하지 않는다.
- COLMAP은 macOS 설치를 지원한다. 원본 Graphdeco 3DGS 학습기는 CUDA 의존성이 있어 사용하지 않는다. Brush는 macOS, COLMAP 입력, CLI 및 뷰어를 지원하므로 기본 후보로 선택한다. **M5 호환성과 자원 사용량은 첫 실측 게이트에서 확인한다.** [COLMAP](https://colmap.github.io/install.html), [원본 3DGS](https://github.com/graphdeco-inria/gaussian-splatting), [Brush](https://github.com/ArthurBrussee/brush)
- Python API 의존성은 FastAPI·Uvicorn·python-multipart·NumPy·OpenCV로 제한한다. 기존 분석 모듈은 표준 라이브러리를 유지한다.
- DB·Redis·Celery·WebSocket은 도입하지 않는다. 상태 JSON과 2초 간격 폴링으로 충분하다.
- 작업 루프는 API와 같은 단일 서버 프로세스에서 외부 명령을 순차 실행한다. Uvicorn worker는 1개이며 처리 중 두 번째 실행 요청은 409로 거절한다.

## 2. 먼저 확인할 게이트

| 순서 | 작업 | 통과 기준 / 실패 대응 |
| --- | --- | --- |
| G0 | 짧은 실제 iPhone 영상으로 FFmpeg·COLMAP·Brush 수동 실행 | Mac에서 희소 모델과 3DGS를 각각 생성·열기. 실패 시 앱 구현 전 설치·자원 문제 해결 |
| G1 | 기존 분석기에 실제 COLMAP TXT 입력 | 유효한 영역·점수 산출. 방향 선택은 승인된 후보 자세가 있는 경우에 별도 검증. 합성 데모 성공으로 대체 금지 |
| G2 | FastAPI와 iOS의 촬영·업로드·결과 연결 | 기능 명세의 P0 기준 충족 |
| G3 | 보완 영상과 두 개의 Brush 결과 기록 | P1 기준 충족. 이 시점까지 학습의 수동 실행 허용 |

G0는 최초 30~60 프레임·긴 변 960px로 시작한다. 아래 기본값으로 바로 전체를 구현하지 않는다. 설치 버전, CLI `--help`, 실제 사용 인수를 `run-config.json`에 기록하고 이후 같은 버전으로 고정한다. 아직 확인하지 않은 Brush 옵션명을 명세에서 실행 명령으로 단정하지 않는다.

## 3. 16GB 환경의 초기 처리 예산

아래는 벤치마크 결과가 아닌 초기 설정·중단 기준이다. OS·Xcode·GPU가 통합 메모리를 공유하므로 무거운 단계를 겹치지 않는다.

| 항목 | 기본값 | 축소/중단 정책 |
| --- | --- | --- |
| 영상 | A 최대 60초, B 최대 30초, 각각 250MB | 업로드와 디코딩 후 모두 검증 |
| 프레임 | 2fps 후보, A 최대 80장 / B 최대 40장 | 실패 시 A 40장 / B 20장으로 수동 재실행 |
| 해상도 | 긴 변 1280px, 종횡비 유지 | 메모리·시간 초과 시 960px |
| SfM 매칭 | 시간 순서 sequential, A/B 연결 구간은 별도 교차 매칭 | A+B 최대 120장이므로 필요 시 전체 매칭으로 재시도 |
| 동시 실행 | SfM·Brush 중 1개 | 학습 중 Xcode·시뮬레이터 종료 권장, 실기기 사용 |
| 단계 제한 | 전처리 2분, SfM 10분, 영역 분석 1분, Brush 한 번 15분 | 초과 시 프로세스 그룹 종료 후 failed 기록 |
| 메모리 | 단계별 시스템 memory pressure·swap·프로세스 RSS 기록 | warning/critical 압박이 30초 지속되면 중지. RSS만으로 GPU 포함 전체 사용량을 판단하지 않음 |
| 저장 공간 | 작업 전 여유 10GB 확인 | 부족하면 거절. 자동 삭제하지 않고 운영자가 이전 실험 정리 |
| Brush 설정 | 최초 시험 3,000 step 목표, 같은 설정으로 A/A+B 실행 | 실제 버전에서 지원 여부 확인. 밀도·splat 수 제한 가능 여부도 G0에서 기록 |

학습 스텝·프레임을 줄인 결과는 최종 품질 평가 자료로 취급하지 않는다. Brush가 제한 설정에서 계속 실패하면 P1은 미완료로 남기고, 외부 GPU 도입은 별도 결정한다.

## 4. 영상·SfM·분석 처리

1. 서버가 클라이언트 파일명 대신 생성한 ID로 임시 저장한다. 바이트 수 제한 후 FFprobe로 실제 영상·길이·해상도·코덱을 검사하고 정상 파일만 원자적으로 확정한다.
2. FFmpeg가 회전 메타데이터를 반영해 프레임을 추출한다. iOS에서 SDR로 촬영하며 HDR 입력은 첫 버전에서 거절한다. 긴 변 리사이즈와 결과 픽셀 크기를 기록한다.
3. OpenCV의 그레이스케일 Laplacian 분산으로 선명도를 기록한다. 흐림 제거 임계값은 G0의 실제 샘플로 정한 뒤 고정한다. 남은 후보를 시간축에 고르게 선택하며 프레임 한도만큼 자른다. 흐림 제거 후 30장 미만이면 실패한다.
4. 고정 렌즈 영상마다 카메라 내부 파라미터를 공유한다. A와 B는 별도 카메라 그룹으로 시작해 세션 간 초점 차이를 허용한다. COLMAP 버전의 카메라 모델·CPU 실행 옵션을 확인하고 기록한다.
5. 특징 추출 → 매칭 → incremental mapping을 실행한다. 가장 큰 단일 모델이 등록 비율 60% 이상·등록 이미지 30장 이상·점 100개 이상인지 확인한다. 실패한 작은 모델들을 병합 성공으로 취급하지 않는다.
6. `model_converter`로 `images.txt`, `points3D.txt`, `cameras.txt`를 생성한다. 기존 `read_model()`과 `analyze(..., bins=3)`를 호출한다. 기존 CLI·합성 데모 동작은 유지한다.
7. `heuristic_risk`는 기존 관측 수·방향 다양성·재투영 오차 공식 그대로 사용한다. 선명도는 프레임 필터·기록에만 사용하고 점수에 새 가중치를 넣지 않는다.
8. 5개 이상 점을 가진 영역 중 점수 상위 3개를 안내한다. 해당 영역 점의 2D 관측이 가장 많은 등록 이미지를 대표 이미지로 고르고, 실제 POINTS2D 관측 좌표의 경계 상자를 표시한다. 확대된 상자 크기는 이미지 범위로 제한한다.

현재 파서는 대표 이미지 생성용 POINT3D_ID와 2D 관측 좌표를 읽는다. 카메라 모델을 임의로 pinhole로 가정해 원본 영상에 투영하지 않는다.

### 좌표와 보완 방향

- 카메라 중심은 기존 구현의 `C = -Rᵀt`를 사용한다. SfM 좌표는 중력 방향·미터 단위가 아니다.
- 현재 API는 후보 위치·자세가 없어 `direction_vector=null`, `direction_asset_id=null`, `viewpoint_status=candidate_pose_required`를 반환한다. 앱은 대표 이미지와 보완 영역 문구만 표시한다.
- 자동 촬영 시점 선택 실험은 종료했다. 현재 구현은 보완 영역만 표시하며 실제 이동 경로는 산출하지 않는다.
- A+B 정합에는 A와 B 양쪽 등록 이미지가 있어야 하고, A의 60% 이상과 B의 최소 10장이 같은 모델에 등록되어야 한다. 실패 시 보완 정합 실패로 처리한다.
- A+B에서 영역 구획을 재계산한다. **A와 A+B의 같은 문자열 영역 ID가 같은 실제 공간이라고 가정하지 않는다.** 초기 PoC는 점수의 영역별 증감 그래프를 제공하지 않는다.

## 5. 저장 구조와 상태

```text
data/<project-id>/
  project.json                 # 입력 ID, 작업 목록, P1 수동 결과 상태
  captures/<capture-id>.mov     # role: initial 또는 supplement
  runs/<run-id>/               # initial A / combined A+B / 재실행별 불변 폴더
    status.json                # state, stage, timestamps, error
    run-config.json            # 버전, 입력 ID, 필터·SfM·Brush 설정
    frames/                    # 전역 유일한 이미지명, 원본 시각 매핑
    colmap/                    # database, sparse, text, undistorted
    analysis/                  # report.json, features.csv, guide 이미지
    logs/                      # 명령별 stdout/stderr와 시간·자원 기록
    splats/                    # P1 Brush 결과 PLY
  comparison/                  # 좌표 정렬 기록, 대응 화면, observations.md
```

작업 상태는 `queued → running → completed | failed`, 실행 단계는 `preprocess → sfm → analyze`다. 분석 완료와 P1 복원 준비 상태(`not_started / running / ready / failed`)는 별도 필드로 관리한다. 실패에 코드·사용자 메시지·로그 경로를 남긴다. 상태 JSON은 임시 파일 작성 후 replace한다. 서버 재시작 시 queued/running을 `SERVER_RESTARTED` 실패로 바꾼다. 재시도는 새 run ID를 만들며 기존 결과를 덮어쓰지 않는다.

## 6. 최소 API

모든 API와 미디어에 `Authorization: Bearer <dev-token>`을 요구한다. ID는 서버 생성 UUID이며 프로젝트 귀속을 검사한다. 파일시스템 경로를 클라이언트 입력으로 받지 않는다.

| 메서드 / 경로 | 요청 | 응답·동작 |
| --- | --- | --- |
| GET `/health` | 없음 | 서버 버전, 처리 중 여부 |
| POST `/projects` | 없음 | `project_id` |
| POST `/projects/{id}/captures` | multipart `file`, `role=initial|supplement` | 201 `capture_id`; 중간 파일은 분석 불가 |
| POST `/projects/{id}/runs` | JSON `mode=initial|combined`, `capture_ids` | 202 `run_id`; A 또는 같은 프로젝트 A+B만 허용; 중복 ID·잘못된 역할 422, 처리 중 409 |
| GET `/projects/{id}/runs/{run}` | 없음 | 상태, 단계, 경과 시간, 에러, reconstruction 상태 |
| GET `/projects/{id}/runs/{run}/report` | 없음 | 완료된 분석 결과; 미완료 409 |
| GET `/projects/{id}/runs/{run}/media/{asset_id}` | 없음 | 등록된 guide PNG만 반환; 임의 경로 접근 불가 |

report는 `schema_version=2`, `run_id`, `source=real`, `method=region_guidance_v2`, `registered_frames`, `input_frames`, `regions`, `limitations`를 포함한다. regions는 `representative_asset_id`, 촬영 문구 `instruction`, 정규화된 `[x,y,width,height]` 경계 상자를 제공한다. 후보 자세가 없으면 `direction_asset_id`와 `direction_vector`는 null이다. 점수 의미와 신뢰 수준을 API에서도 보존한다.

네트워크 단절 후 업로드 재시도는 새 capture ID를 만들 수 있다. 클라이언트가 성공 응답으로 받은 ID만 run에 포함하므로 중복 촬영 파일이 자동으로 분석에 들어가지 않는다. 첫 버전은 분할 업로드·자동 백그라운드 재시도 없이 전송 전체를 재시도한다.

## 7. iOS 앱

- SwiftUI 4화면: 서버 연결 / 촬영·미리보기 / 작업 진행 / 보완 안내. 프로젝트·run ID는 로컬에 저장한다.
- AVFoundation으로 가로 1080p/30fps, 기본 후면 렌즈·1배율·SDR을 요청하고 실제 지원 포맷을 확인한다. 오디오 입력은 추가하지 않는다. 지원하지 않으면 이유를 표시하며 다른 포맷으로 조용히 대체하지 않는다.
- URLSession의 파일 업로드를 사용해 영상 전체를 메모리에 올리지 않는다. 분석 상태는 앱이 전경일 때 2초 간격으로 조회하며 완료·실패 시 중단한다.
- 카메라·로컬 네트워크 사용 설명을 Info.plist에 넣는다. Mac 주소는 `localhost`가 아닌 LAN 주소를 사용한다. 개발용 HTTP의 ATS 예외는 사용하는 로컬 주소 방식에 맞춰 최소 범위로 설정하고 숫자 IP·로컬 호스트명 모두 실기기에서 확인한다. 전역 `NSAllowsArbitraryLoads`를 기본값으로 사용하지 않는다. [로컬 네트워크 권한](https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription), [ATS 로컬 설정](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking)
- 앱 설치는 Xcode의 실기기 개발 서명을 사용한다. Xcode·iOS SDK의 기기 지원 여부는 G0에서 확인하며 App Store 배포는 요구하지 않는다.

## 8. P1 복원과 비교

1. A와 A+B의 각 COLMAP 모델에서 왜곡 보정된 이미지·모델을 준비하고 Brush의 지원 입력 형식으로 전달한다.
2. Mac에서 Brush를 수동 실행해 동일 해상도·스텝·밀도 설정으로 순차 학습한다. 각 입력 경로·버전·설정·시간·종료 상태와 PLY 경로를 기록한다. 설치 버전의 명령을 확인한 후에만 서버 subprocess로 자동화한다.
3. 두 SfM 모델은 별도 좌표계를 가질 수 있다. 공통 A 이미지의 카메라 중심 최소 3개(비공선)를 대응시켜 similarity 변환을 구하고 잔차를 확인한다. 퇴화하거나 잔차가 크면 정렬 실패로 남긴다. 변환은 뷰 좌표에 적용하고 Gaussian PLY를 단순 XYZ 변환해 덮어쓰지 않는다.
4. 정렬 및 카메라 이동을 뷰어에서 재현할 수 있으면 대응 화면 최소 3개를 저장한다. 뷰어가 해당 기능을 제공하지 않으면 근사 시점 육안 관찰로 표시한다. “동일 시점 정량 비교”라고 보고하지 않는다.
5. 결과 기록에 개선/변화 없음/악화/비교 불가와 이유를 남긴다. 전후는 입력 수가 다르고 평가용 영상도 분리하지 않은 연결 실험이므로 모델 성능·일반화·촬영 안내의 인과 효과는 주장하지 않는다.

## 9. 검증과 산출물

| 검증 | 최소 범위 |
| --- | --- |
| 기존 분석 회귀 | `python3 -m unittest discover -s poc -v` |
| 서버 경계 | 과대/잘못된 파일, 잘못된 ID·토큰, 작업 중복, 명령 실패·시간 초과, 원자적 상태 저장 |
| 안내 정확성 | 실제 COLMAP POINTS2D와 대표 이미지 경계 상자 대응, 근거 점 부족 제외, 방향 벡터 부호 |
| 실기기 | 카메라·네트워크 권한 거부, 업로드 중 단절·재시도, 앱 재실행 후 상태 복구 |
| 실제 장면 | 기능 명세 P0/P1 체크, 단계별 시간·memory pressure·swap, 입력·설정·화면 기록 |

서버는 신뢰하는 LAN에만 바인딩하고 포트 포워딩하지 않는다. 개발 토큰은 로그·Git에 넣지 않는다. 외부 프로세스는 인수 배열로 실행하고 shell 문자열을 사용하지 않는다. 입력은 스트리밍 저장하고 모든 실행에 타임아웃을 둔다. 원본 실내 영상은 로컬에만 보관하며 삭제는 운영자가 직접 수행한다.

산출물은 iOS 개발 앱, Mac 실행 절차, 실제 A/B 입력과 분석 결과, 두 3DGS, 실행 설정·로그, 짧은 결과 보고서다. 이번 명세 작성에는 구현·설치·실기기 벤치마크를 포함하지 않는다.
