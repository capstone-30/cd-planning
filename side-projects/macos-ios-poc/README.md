# macOS·iOS 촬영 보완 PoC

상태: 사이드 프로젝트로 유지 · 코드·문서 분리일: 2026-11-14

**iPhone 촬영 → Mac 업로드 → FFmpeg·COLMAP → 관측 근거와 보완 영역 표시 → 보완 촬영 → Brush 학습·전후 확인**을 실험하는 프로젝트다. macOS·iOS 전용 기능과 기존 PoC의 실행·실측 기록을 이곳에서 관리한다.

[본 프로젝트](../../README.md)는 Ubuntu GPU 환경에서 Nerfstudio + Splatfacto를 사용한다. 본 프로젝트의 완료 조건에 iOS 앱, Mac API, Brush 지원 또는 이 PoC의 P0/P1 기준을 포함하지 않는다. 두 프로젝트의 실행 성공과 성능 수치는 각각 기록한다.

## 문서

- [기능 명세·P0/P1 기준](docs/01-func/func-specs.md)
- [iOS UX/UI 명세](docs/02-uxui/uxui-specs.md)
- [Mac·Brush 기술 명세](docs/03-tech/tech-specs.md)
- [설치·서버·앱·Brush 실행 안내](docs/05-ops/runbook.md)
- [Android 웹 업로드·Windows 실행 안내](poc/GALAXY.md): 팀원 개발·연습용
- [검증 기록](docs/04-test/validation.md)
- [촬영 지원 연구 질문·파일럿 절차](docs/04-test/capture-support-validation.md)
- [60+10 사용자 비교 실행표](docs/04-test/user-study-session.md)
- [Mac·Windows 핵심 PoC 실측](docs/04-test/reports/core-poc-result.md)
- [보완 촬영 상태 표시 점검](docs/04-test/reports/capture-support-result.md)
- [보완 이미지 추가 효과 실험](docs/04-test/reports/supplement-effect-result.md)
- [종료한 시점 선택 실험](docs/04-test/reports/closed-experiments.md)
- [초기 실현 가능성 검토](docs/04-test/reports/feasibility.md)
- [분리 전 전체 연구 계획](docs/01-func/project-plan-history.md): 과거의 확장 계획과 팀 역할 기록

## 구현·데이터 위치와 검증 상태

구현은 [iOS 앱](ios/)과 [Python 분석 CLI·서버](poc/README.md)에 유지한다. 실행 예시의 `poc/`·`ios/` 경로는 이 사이드 프로젝트 루트(`side-projects/macos-ios-poc/`)를 기준으로 한다. 로컬 실험 데이터·모델도 `poc/data/`에 함께 옮겼다. 기존 실측 JSON·로그에 기록된 절대 경로는 당시 실행 이력으로 보존한다. 보고서의 JSON·비교 이미지도 함께 보존했다.

기존 가상환경을 옮긴 경우 `.venv/bin/python`은 사용할 수 있지만 `pip` 등 실행 스크립트와 `activate`에는 이전 절대 경로가 남을 수 있다. 패키지는 `poc/.venv/bin/python -m pip`로 관리하거나, 실행 안내에 따라 새 가상환경을 만든다.

공개 실내 이미지의 Mac·Windows·Brush 처리 결과와 실기기 전체 흐름은 구분한다. 실제 iPhone 촬영 P0/P1 완료와 촬영 안내의 사용자 효과는 아직 미검증이다. 이곳의 2026-11-14 이전 기록은 당시 환경·판정으로 읽는다.
