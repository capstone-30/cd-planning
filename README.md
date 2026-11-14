# 실내 3DGS 복원

사진·영상 → COLMAP 데이터 처리 → Splatfacto 학습 → Nerfstudio 웹 뷰어.
**프로젝트·PoC의 공통 목표는 Ubuntu + NVIDIA GPU + CUDA다. GPU는 확보 예정이며, 새 스택의 실행·PoC 이관은 미검증이다.**

- [계획·팀](docs/01-func/project-plan.md) · [기능](docs/01-func/func-specs.md) · [사용 흐름](docs/02-uxui/uxui-specs.md)
- [확정 스택](docs/03-tech/3dgs-stack.md) · [기술 원칙](docs/03-tech/tech-specs.md)
- [검증 현황](docs/04-test/validation.md) · [운영](docs/05-ops/runbook.md) · [학교 자료](docs/univ)

## 기존 PoC

공통 목표 스택으로 이관하기 전의 Brush 기반 구현이다. 실행 코드에는 아직 Brush가 사용되며, 기존 실측은 새 스택의 검증을 대신하지 않는다. [스택 비교·이관 범위](docs/03-tech/3dgs-stack.md)를 따른다.

| 경로 | 내용 |
| --- | --- |
| [poc/common](poc/common/README.md) | Python API·분석 CLI·테스트·실험 기록, 로컬 `data/`·`output/` |
| [poc/macos](poc/macos/README.md) | Mac 서버 설치·운영 |
| [poc/windows](poc/windows/README.md) | Windows 서버·뷰어 실행 |
| [poc/ios](poc/ios/README.md) | iPhone 앱·Xcode·화면 명세 |
| [poc/android](poc/android/README.md) | Android 브라우저 화면 (네이티브 앱 없음) |

문서는 항목별 기준 문서 한 곳에서 관리하고, 다른 문서에서는 링크한다. 학교 양식·실험 증거·과거 기록은 원문을 보존한다.
