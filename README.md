# 실내 3DGS 복원 프로젝트

사진·영상에서 실내 공간을 복원하고 브라우저로 확인한다. 본 프로젝트의 스택은 **Ubuntu + NVIDIA GPU + CUDA / Nerfstudio + Splatfacto**로 고정한다. 데이터 처리는 Nerfstudio + COLMAP, 학습은 Python + PyTorch + gsplat, 결과 확인은 Nerfstudio 기본 웹 뷰어를 사용한다.

현재는 스택과 문서 범위를 확정한 단계다. 새 환경의 설치·파이프라인 연동·학습·뷰어 실행은 아직 검증하지 않았다.

## 본 프로젝트 문서

- [프로젝트 계획](docs/01-func/project-plan.md) · [기능 명세](docs/01-func/func-specs.md)
- [뷰어 및 사용자 흐름](docs/02-uxui/uxui-specs.md)
- [기술 명세](docs/03-tech/tech-specs.md) · [3DGS 확정 스택](docs/03-tech/3dgs-stack.md)
- [검증 계획·현황](docs/04-test/validation.md) · [환경 준비·운영 계획](docs/05-ops/runbook.md)
- [학교 제출 양식·참고 자료](docs/univ)

## 분리된 기존 PoC

서버 OS와 모바일 클라이언트를 각각 관리한다.

- [macOS](poc/macos/README.md): Mac 서버·Brush 환경과 운영 절차
- [Windows](poc/windows/README.md): Windows 서버·뷰어 실행 도구
- [iOS](poc/ios/README.md): iPhone 앱·Xcode 프로젝트·화면 명세
- [Android](poc/android/README.md): Android 브라우저용 웹 화면
- [공용 PoC](poc/shared-poc/README.md): Python 분석기·API·Brush 연결·테스트·실험 기록과 로컬 데이터

Ubuntu GPU + Nerfstudio 본 프로젝트는 루트 `docs/`에서 관리하며 구현은 아직 시작하지 않았다. Android 네이티브 앱과 Linux 전용 PoC는 없다. 기존 Brush 실측은 새 Nerfstudio 스택의 검증을 대신하지 않는다.

## 폴더 구조

```text
.
├── docs/                         # 본 프로젝트: Ubuntu·Nerfstudio
├── poc/
│   ├── macos/docs/               # Mac 서버 환경·운영
│   ├── windows/                  # Windows 서버·뷰어 실행
│   ├── ios/                      # iPhone 앱·Xcode·앱 문서
│   ├── android/web/              # Android 브라우저 화면
│   └── shared-poc/
│       ├── poc/                  # 공용 Python·테스트·로컬 데이터
│       └── docs/                 # 공용 운영·실험·과거 기록
└── .github/                      # 이슈·PR 템플릿
```

공용 코드 테스트는 [공용 PoC 안내](poc/shared-poc/README.md)를 따른다. 설치·실행은 각 플랫폼 README에서 안내한다.
