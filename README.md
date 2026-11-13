# 실내 촬영 보완 PoC

iPhone 촬영 → Mac 업로드 → COLMAP SfM → 규칙 기반 추가 촬영 후보 → 보완 영상 분석을 연결한다.
Mac의 Brush로 최초/보완 3DGS를 생성하고 비교 기록을 남기는 운영자 도구를 포함한다.

- [실행 안내](poc/RUNBOOK.md): 설치, 서버, iOS 앱, API, Brush 학습·비교
- [검증 기록](poc/VALIDATION.md): 자동 검증 결과와 실제 장면의 미검증 항목
- [핵심 PoC 실측](poc/CORE_POC_RESULT.md): 공개 실내 실사 데이터의 실제 SfM·3DGS 실행 결과
- [동일 추가 프레임 안내 효과](poc/GUIDANCE_EVAL_RESULT.md): 공통 평가 시점의 7회 비교와 원래 방향 안내의 한계
- [Windows 재현·v2 화질 비교](poc/WINDOWS_REPRO_RESULT.md): 4043f1a 핵심 경로 재현, v2 vs 균등 10시드 비교
- [촬영 안내 v2](docs/guidance-v2.md): 가시성·시차·중복 관측에 따른 후보 선택과 앱 반영 범위
- [기능 명세](docs/func-specs.md) · [기술 명세](docs/tech-specs.md)

실제 촬영의 P0/P1 완료 판정은 실기기와 FFmpeg·COLMAP·Brush 실행 후 진행한다.
