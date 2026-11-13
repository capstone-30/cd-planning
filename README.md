# 실내 촬영 보완 PoC

iPhone 촬영 → Mac 업로드 → COLMAP SfM → 규칙 기반 추가 촬영 후보 → 보완 영상 분석을 연결한다.
Mac의 Brush로 최초/보완 3DGS를 생성하고 비교 기록을 남기는 운영자 도구를 포함한다.

현재 목표는 **복원 상태를 보여주고 보완 촬영을 돕는 것**이다. 정합 수와 관측 근거를 표시하고 최초·보완 결과를 보존한다. 최적 시점 추천이나 화질 개선을 보장하지 않는다. 시점 선택 실험은 종료했으며, 결과와 중단 이유만 기록한다.

- [보완 촬영 지원 검증](docs/reports/capture-support-result.md): 저장된 결과의 상태 표시 점검과 실제 촬영 시험 준비
- [보완 이미지 추가 효과 PoC](docs/reports/supplement-effect-result.md): 동일 평가 시점에서 A / A+10의 실제 Brush 학습 비교
- [연구 질문·실제 촬영 비교 절차·기록 양식](docs/capture-support-validation.md): 대표 사진의 영역 표시가 같은 시간의 자유 보완 촬영보다 도움이 되는지 검증

- [실행 안내](docs/runbook.md): 설치, 서버, iOS 앱, API, Brush 학습·비교
- [검증 기록](docs/validation.md): 자동 검증 결과와 실제 장면의 미검증 항목
- [핵심 PoC 실측](docs/reports/core-poc-result.md): 공개 실내 실사 데이터의 실제 SfM·3DGS 실행 결과
- [종료한 시점 선택 실험](docs/reports/closed-experiments.md): 시도한 방법, 핵심 수치, 중단 이유
- [기능 명세](docs/func-specs.md) · [기술 명세](docs/tech-specs.md)

실제 촬영의 P0/P1 완료 판정은 실기기와 FFmpeg·COLMAP·Brush 실행 후 진행한다.

## 폴더 구조

```text
.
├── docs/                       # 명세, 설계, 실행·검증 절차
│   ├── project-plan.md         # 프로젝트 계획서
│   ├── reports/                # 타당성 검토, 실측 보고서, 검증 JSON
│   └── university/             # 학교 제출 양식, 원본 PDF, 참고 이미지
├── ios/                        # iPhone 앱 소스와 Xcode 프로젝트
├── poc/                        # Python 분석 CLI와 실험·검증 스크립트
│   ├── server/                 # API, 처리 파이프라인, 운영자 도구
│   ├── tests/                  # 분석·서버·검증 회귀 테스트
│   ├── output/                 # 버전 관리하는 합성 데모 출력
│   └── data/                   # 로컬 실험 데이터·모델·로그 (Git 제외)
└── .github/                    # 이슈·PR 템플릿
```

[프로젝트 계획서](docs/project-plan.md) · [학교 자료](docs/university/) · [Python CLI 안내](poc/README.md)

저장소 루트에서 전체 테스트:

```sh
poc/.venv/bin/python -m unittest discover -s poc -v
```

`poc/.venv/`, `target/autotune/`, `poc/target/autotune/`, `ios/build/`는 Git에서 제외하는 로컬 환경·빌드 캐시다.
