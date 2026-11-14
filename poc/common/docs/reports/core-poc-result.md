# 핵심 처리 PoC 실측 — 2026-11-10

**판정: 공개 실내 실사 데이터에서 Mac의 핵심 처리 경로는 통과했다. 프로젝트를 계속 진행할 기술적 근거를 확보했다.**

실제 FFmpeg → COLMAP → 규칙 분석·안내 이미지 → Brush 3DGS 학습·PLY 저장·평가 시점 렌더링을 실행했다. 외부 명령을 fixture로 대체하지 않았으며, 공개 데이터에 포함된 카메라·점군도 사용하지 않았다. iPhone을 포함한 P0/P1 전체 완료와 촬영 안내의 품질 개선 효과는 별도 미검증이다.

## 입력과 실행 조건

- 원 데이터: [Mip-NeRF 360](https://jonbarron.info/mipnerf360/)의 실내 `room` 장면. [Hugging Face 미러](https://huggingface.co/datasets/YuanhaoXD/Mip-NeRF360/tree/main/room/images_4)에서 정렬된 첫 100장의 실사 이미지를 받았다. 다운로드 revision과 각 파일의 SHA256을 [source-manifest.json](../../data/core-check/source-manifest.json)에 보존하고 배포된 LFS SHA256과 일치하는지 확인했다.
- A는 앞 60장, B는 다음 40장을 각 이미지당 0.5초인 H.264 영상으로 변환했다. 길이는 A 30초, B 20초다. **실사 정지 이미지를 이어 만든 영상이며 실제 스마트폰 연속 촬영 또는 추천에 따른 재촬영이 아니다.**
- 원본 선택 해상도는 779×519이고 클립은 960×640으로 변환했다. 따라서 이 시험은 고해상도 iPhone 원본의 디코딩 부하를 대표하지 않는다.
- API는 FastAPI TestClient로 실제 업로드·작업 생성·상태 조회·보고서·PNG 다운로드를 호출했다. HTTP 소켓·LAN·iOS 앱은 시험하지 않았다.
- 설치: FFmpeg 9.0.2, COLMAP 4.2.1, [Brush 공식 v0.3.0 arm64 배포](https://github.com/ArthurBrussee/brush/releases/tag/v0.3.0). Brush 압축 파일의 공식 SHA256도 일치했다.
- COLMAP은 CPU, Brush는 Mac에서 실행했다. Brush GUI에서 GPU 이름 `Apple M5`, 유형 `IntegratedGpu`를 확인했다.
- 분석은 기존 기본값인 2fps, A 최대 60장/B 최대 40장, 긴 변 960px, 선명도 임계값 0이다. 선명도 보정은 미실시다.
- Brush는 두 run 모두 3,000스텝·최대 30만 splat·최대 해상도 960·seed 42·8장마다 평가 시점 분리 설정으로 순차 실행했다. 평가 이미지는 학습에서 제외하지만 SfM에는 사용한다. 최종 연구용 학습 예산이나 독립 평가 영상 실험은 아니다.

## 실측 결과

| 항목 | 최초 A | A+B |
| --- | ---: | ---: |
| 입력 프레임 | 60 | 100 |
| 가장 큰 단일 모델 등록 | 40 / 60 (66.7%) | 100 / 100 (100%) |
| 희소 점 | 7,577 | 24,874 |
| 안내 후보 | 3 | 3 |
| 전처리 | 4.55초 | 4.86초 |
| SfM | 28.78초 | 123.24초 |
| 안내 분석 | 0.80초 | 1.99초 |
| 분석 전체 | 34.14초 | 130.09초 |
| Brush 학습·내보내기·평가 포함 명령 | 108.33초 | 108.29초 |
| Gaussian 수 | 16,845 | 53,680 |
| PLY 크기 | 3,976,970 bytes | 12,670,030 bytes |
| 저장된 평가 렌더 PNG | 5 | 13 |
| 전체 단계 중 표본 최대 단일 명령 프로세스 RSS | 1,795.4 MiB | 1,790.5 MiB |
| 기록된 시스템 memory pressure | 정상(1) | 정상(1) |
| 기록된 swap 사용 | 0 | 0 |

시간은 이 데이터·설정의 1회 실행값이다. RSS는 GPU·자식 프로세스·시스템 전체 메모리의 합계가 아니다. 약 2초 간격 표본이므로 표본 사이의 순간 피크도 보장하지 않는다.

두 PLY 모두 binary little endian, Gaussian당 float 속성 59개를 확인했다. vertex 수에 맞는 전체 payload 길이와 모든 float의 유한성을 검사했다. 학습 종료 코드도 모두 0이다.

공통 A 카메라 40개로 A+B → A similarity 정렬을 계산했다. 상대 RMSE는 **0.00232**로 기존 운영 기준 0.1 이하다. 이는 카메라 정렬 가능성의 근거이며 렌더링 품질 개선 수치가 아니다. PLY 좌표는 변경하지 않았다.

A의 평가 렌더 5개는 왜곡 보정 원본과 같은 픽셀 크기에서 비교 가능했고 평균 PSNR은 **29.94dB**였다. 이는 같은 공개 촬영 집합에서 분리한 시점의 구현 점검값이다. 별도 평가 영상·새로운 공간 성능·보완 효과로 해석하지 않는다. A와 A+B는 등록 집합과 평가 시점이 다르므로 두 수치를 그대로 비교하지 않았다. 두 run의 일부 렌더 PNG를 열어 실내 구조·가구가 재현되는 것을 확인했다.

## 발견하여 수정한 실제 호환성 오류

COLMAP 4.2.1의 하위 명령 도움말이 stderr로 출력됐다. 기존 코드는 stdout만 읽어 `COLMAP_OPTIONS`로 실패했다. `Runner.run()`에 stderr 포함을 선택할 수 있도록 하고 COLMAP 도움말 조회에만 적용했다. FFprobe의 JSON stdout에는 stderr를 섞지 않는다.

회귀 테스트를 추가했고 전체 **18개 테스트 통과**, `git diff --check` 통과를 확인했다. 첫 실패 run과 재실행 결과는 별도 폴더에 보존했다.

## 성공으로 판정하지 않은 항목

- iPhone 설치·촬영·권한·LAN 업로드와 연결 복구: 실기기가 없어 미검증.
- PLY의 GUI 재로딩: Brush 창과 GPU 정보는 확인했지만 자동화 도구의 좌표 입력이 `noWindowsAvailable`로 실패했고 파일이 로드된 화면을 확인하지 못했다. 빈 창을 PLY 열기 성공으로 취급하지 않았다. **PLY 자체의 데이터 검증과 학습 중 렌더링 성공은 별도로 확인했다.**
- P1 전체 완료: GUI에서 두 PLY 열기와 대응 화면 3쌍의 비교 기록이 없어 미완료.
- 촬영 안내의 유용성: B는 미리 정한 다음 이미지들이므로 추천에 따라 촬영한 실험이 아니다. 등록률·점 수·Gaussian 수 증가를 안내 효과 또는 화질 개선으로 주장하지 않는다.
- 방향의 접근 가능성, 완전 미관측 영역 탐지, 학습 기반 품질 예측, 독립 공간 평가, 웹 이동·충돌: 기존 미검증 상태를 유지한다.

## 증거와 재현 경로

실험 폴더는 `data/core-check/`이며 원본·영상·로그·PLY를 로컬에 보존했다. `data/`는 Git에서 제외되어 있다.

- [실측 요약](../../data/core-check/summary.json), [API 호출·상태 기록](../../data/core-check/api-evidence.json), [A 렌더 점검](../../data/core-check/initial-render-check.json)
- [Brush 실제 인수](../../data/core-check/brush-argv.json), [Brush 설정](../../data/core-check/brush-settings.json)
- [API 실행 스크립트](../../data/core-check/run_api_check.py), [운영자 명령 실행 스크립트](../../data/core-check/run_brush_check.py)
- project: `12033c82-c669-4ee8-9f62-b3c61a3740dc`
- A run: `c18b037a-1100-49b3-895e-5301edebff12`
- A+B run: `05adea6a-b3bb-4d73-a06b-fe07039267a0`

각 run의 `logs/`에 명령 인수·종료 코드·표준 출력·오류·시간·RSS·memory pressure·swap, `analysis/`에 안내 PNG·특징, `splats/`에 PLY와 평가 렌더가 있다. 검증용 Brush 앱 묶음은 공식 실행 파일을 GUI 도구가 찾도록 로컬에서 만든 것으로 배포 패키지가 아니다.

**진행 결정:** Mac에서 핵심 계산 경로가 실제 실내 영상 내용으로 동작하므로 개발을 계속 진행해도 된다. 다음 검증의 우선순위는 iPhone 실제 촬영 연결, 저장 PLY의 뷰어 확인, 동일 추가 촬영량 기준선과 독립 평가 영상을 사용하는 안내 효과 실험이다.

## Windows 재현 — 2026-11-13

Windows 11 / i5-14600KF / RAM 32GB / RX 7800 XT 16GB, Python 3.12.16, FFmpeg 9.0.2, COLMAP 4.2.1 CPU, Brush 0.3.0 환경에서 동일 공개 `room` 입력의 핵심 경로를 재현했다.

| 항목 | 결과 |
| --- | --- |
| A 정합·희소 점 | 40/60장, 7,581점 |
| A+B 정합·희소 점 | 100/100장, 24,783점 |
| 안내 후보 A / A+B | 3 / 3개 |
| 분석 시간 A / A+B | 32.5초 / 125.9초 |
| A+B → A 정렬 상대 RMSE | 0.00203 |

원본 이미지 100장의 배포 SHA256 일치를 확인했다. 공개 정지 이미지를 연결한 클립의 TestClient 실행이며 실기기 재촬영 시험은 아니다. 상태 표시 후속 점검은 [저장 결과 검증](capture-support-result.md), 시점 선택 비교는 [종료 기록](closed-experiments.md)을 따른다.

새 경로에 핵심 분석을 재현하려면 공용 PoC 루트(`poc/common/`)에서 실행한다:

```sh
python run_core_check.py --images "<room/images_4 폴더>" --manifest data/core-check/source-manifest.json --core data/core-check-repro
```
