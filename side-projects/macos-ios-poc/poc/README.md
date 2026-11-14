# 촬영 보완 사이드 프로젝트 — 분석 CLI

[macOS·iOS 사이드 프로젝트](../README.md)의 기존 분석 CLI 안내. Mac API·영상·iOS·P1 도구는 [실행 안내](../docs/05-ops/runbook.md), 완료 여부·기기 검증은 [검증 기록](../docs/04-test/validation.md)을 따른다.

Python 3 표준 라이브러리로 **SfM → 영역 특징 → 규칙 기반 보완 우선순위**를 계산한다. 별도 패키지 불필요. 후보 시점 선택 실험은 [종료 기록](../docs/04-test/reports/closed-experiments.md)만 남겼으며 현재 CLI·서버는 보완 영역을 표시한다.

사이드 프로젝트 루트(`side-projects/macos-ios-poc/`)에서 실행:

```sh
python3 poc/poc.py --demo
python3 -m unittest discover -s poc -p test_poc.py -v
```

출력: `poc/output/report.md`(우선순위), `features.csv`(영역 특징), `report.json`(전체 결과). 같은 경로로 재실행하면 덮어쓴다.

실제 SfM 결과가 있다면:

```sh
python3 poc/poc.py --colmap /path/to/colmap-text-model --output poc/real-output
```

입력: `images.txt`·`points3D.txt`. 바이너리는 COLMAP의 Export model as text로 변환한다. 형식·카메라 중심 `-Rᵀt`는 [공식 문서](https://colmap.github.io/format.html) 참조. CLI는 COLMAP을 실행하지 않는다.

## 계산 방식

- 점군의 축별 범위를 기본 3등분하여 최대 27개 영역을 만든다. 비어 있는 영역은 출력하지 않는다. `--bins`로 1~20 지정 가능.
- 점마다 등록된 관측 이미지 수를 계산하고 영역별 평균을 구한다.
- 점에서 카메라를 향하는 단위 벡터의 평균 길이를 1에서 빼 방향 다양성을 계산한다. 같은 방향이면 0, 분산되어 있으면 커진다.
- 위험 점수 = `0.5/(1+관측수/3) + 0.3*(1-방향다양성) + 0.2*재투영오차/(1+재투영오차)`.
- 가중치는 실험으로 보정하지 않은 예시다. 점수는 확률·렌더링 오차가 아니다. 내림차순으로 우선순위를 표시한다.
- 6개 축 중 반대 방향을 추천하던 규칙은 제거했다. 후보 위치·자세가 없으면 `direction_vector=null`로 두고 보완 영역만 표시한다.
- 5개 미만 점으로 구성된 영역에는 low 표시를 남긴다. 나머지도 통계적으로 검증된 신뢰도는 아니다.

## 데모와 검증 범위

고정 난수 시드로 카메라 8개와 점 180개를 만든다. 공간 한쪽은 2개 시점, 다른 쪽은 6개 시점으로 관측한다. 추가 관측 예시는 카메라 4·5의 관측을 인위적으로 더한다. 추천에 따라 실제 촬영한 결과가 아니며, 점 좌표와 재투영 오차는 그대로 유지한다.

테스트는 관측 추가 전후 규칙 점수, 회전·이동이 있는 카메라 중심 변환, 빈 POINTS2D 줄, 출력 파일 생성, 정합 실패 및 잘못된 입력을 검사한다.

## 다음 검증

1. 실제 정적 실내 영상으로 COLMAP 결과를 만들고 이 스크립트로 영역을 분석한다.
2. 최초·보완 촬영에 동일한 3DGS 설정을 적용하고 독립 평가 시점에서 렌더링 오차를 수집한다.
3. 공간 단위로 데이터를 분리해 관측 수 기준선과 학습 모델을 비교한다.

현재는 영상 전처리·선명도, 학습 예측, 3DGS, 웹 뷰어 및 PSNR/SSIM/LPIPS 평가를 포함하지 않는다. SfM 축은 실내의 상하좌우와 다를 수 있다. 미관측 공간, 장애물과 접근 가능성은 추정하지 않는다. 점군 범위와 구획이 촬영마다 달라질 수 있으므로 실제 전후 비교에는 공통 좌표 정렬과 동일 구획이 필요하다.

## 저장 실사 이미지의 보완 효과 비교

별도 실험 CLI `check_supplement_effect.py`는 저장된 `guidance-eval/datasets/uniform`의 A 60장과 A+10장을 새로 Brush 학습한다. 두 조건은 같은 평가 사진 10장과 초기 점군을 사용한다. 선택 알고리즘 실험을 재개하는 기능은 아니다. [결과와 한계](../docs/04-test/reports/supplement-effect-result.md)를 참고한다.

```sh
poc/.venv/bin/python poc/check_supplement_effect.py --output poc/data/supplement-effect-new
```

기존 `poc/requirements.txt` 환경과 로컬 Brush 실행 파일, 저장 실험 입력이 필요하다. `--source`와 `--brush`로 경로를 지정할 수 있다. `--output`은 존재하지 않는 새 경로를 사용한다. 입력·프로토콜·해시·로그·PLY·렌더·시점별 PSNR/SSIM·전후 비교 JPG를 보존한다. Metal GPU 접근이 제한된 샌드박스에서는 실행 권한이 필요하다. 실제 촬영 안내의 효과를 측정하는 시험은 아니다.
