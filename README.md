# 실내 3DGS 복원 프로젝트

사진·영상에서 실내 공간을 복원하고 브라우저로 확인한다. 본 프로젝트의 스택은 **Ubuntu + NVIDIA GPU + CUDA / Nerfstudio + Splatfacto**로 고정한다. 데이터 처리는 Nerfstudio + COLMAP, 학습은 Python + PyTorch + gsplat, 결과 확인은 Nerfstudio 기본 웹 뷰어를 사용한다.

현재는 스택과 문서 범위를 확정한 단계다. 새 환경의 설치·파이프라인 연동·학습·뷰어 실행은 아직 검증하지 않았다.

## 본 프로젝트 문서

- [프로젝트 계획](docs/01-func/project-plan.md) · [기능 명세](docs/01-func/func-specs.md)
- [뷰어 및 사용자 흐름](docs/02-uxui/uxui-specs.md)
- [기술 명세](docs/03-tech/tech-specs.md) · [3DGS 확정 스택](docs/03-tech/3dgs-stack.md)
- [검증 계획·현황](docs/04-test/validation.md) · [환경 준비·운영 계획](docs/05-ops/runbook.md)
- [학교 제출 양식·참고 자료](docs/univ/)

## macOS·iOS 사이드 프로젝트

iPhone 촬영·Mac 업로드·보완 촬영 안내·Brush 학습을 연결한 기존 PoC는 [별도 사이드 프로젝트](side-projects/macos-ios-poc/README.md)로 유지한다. 해당 기능·화면·실행 절차·실측 자료는 그 아래에서 관리한다. iOS 앱과 Mac 지원은 본 프로젝트의 필수 완료 조건에 포함하지 않는다.

기존 구현·문서·로컬 실험 데이터는 `side-projects/macos-ios-poc/` 아래에서 함께 관리한다. Brush 실측은 사이드 프로젝트의 결과이며 Nerfstudio 스택의 검증을 대신하지 않는다.

## 폴더 구조

```text
.
├── docs/
│   ├── 01-func/                # 본 프로젝트 계획·기능
│   ├── 02-uxui/                # 기본 웹 뷰어·사용자 흐름
│   ├── 03-tech/                # Ubuntu·Nerfstudio 스택·설계
│   ├── 04-test/                # 본 프로젝트 검증 계획·현황
│   ├── 05-ops/                 # 본 프로젝트 환경·운영 계획
│   └── univ/                   # 학교 제출 양식·원본·참고 이미지
├── side-projects/
│   └── macos-ios-poc/
│       ├── README.md           # 사이드 프로젝트 안내
│       ├── docs/               # PoC 명세·실행·실험 기록
│       ├── ios/                # iPhone 앱·Xcode 프로젝트
│       └── poc/                # 분석 CLI·Mac API·테스트·로컬 데이터
└── .github/                    # 이슈·PR 템플릿
```

기존 코드 실행과 테스트는 [Python CLI 안내](side-projects/macos-ios-poc/poc/README.md) 및 [사이드 프로젝트 실행 안내](side-projects/macos-ios-poc/docs/05-ops/runbook.md)를 따른다. PoC 명령의 기준 경로는 `side-projects/macos-ios-poc/`다. 본 프로젝트 코드는 구현이 시작될 때 추가한다.

사이드 프로젝트 전체 Python 테스트:

```sh
cd side-projects/macos-ios-poc
poc/.venv/bin/python -m unittest discover -s poc -v
```
