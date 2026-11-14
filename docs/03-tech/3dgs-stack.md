# 3DGS 확정 스택

2026-11-14 채택. 본 프로젝트와 PoC의 **목표 스택을 아래 구성으로 통일**한다. NVIDIA GPU 환경은 확보 예정이며 **PoC 이관·구현·실행은 검증 전**이다.

| 영역 | 스택 |
| --- | --- |
| 실행 환경 | Ubuntu + NVIDIA GPU + CUDA |
| 데이터 처리 | Nerfstudio + COLMAP: 프레임·카메라 자세·희소 점군 |
| 학습 | Nerfstudio Splatfacto (Python + PyTorch + gsplat) |
| 결과 확인 | Nerfstudio 기본 웹 뷰어 |

사진·영상 → 프레임 추출·COLMAP → Splatfacto → 웹 뷰어 → 내보내기.
촬영 기기·브라우저 OS는 제한하지 않는다. iOS·Mac 전용 기능은 필수 범위가 아니다. [기존 Brush PoC](../../poc/common/README.md)는 이관 전 재현 기준으로 보존하며, 신규 복원 경로는 위 목표 스택을 따른다. 기존 서버의 학습 명령을 Splatfacto로 교체하는 작업은 아직 완료하지 않았다.

## 프로젝트·PoC 비교와 선택 이유

| 기준 | 기존 Brush PoC | 목표 Nerfstudio·Splatfacto | 판단 |
| --- | --- | --- | --- |
| 실행 환경 | Mac M5·Windows AMD 환경의 핵심 경로 실측 기록 | Ubuntu·NVIDIA·CUDA, 장비 확보 예정 | 현재 장비 활용은 Brush, 확보 예정 환경의 목표는 Splatfacto |
| 데이터 처리 | FFmpeg·COLMAP 직접 호출, NumPy·OpenCV 분석 | Nerfstudio 데이터 처리도 FFmpeg·COLMAP 사용 | 원본·프레임·SfM 분석을 재사용하되 데이터 경로·카메라 변환 확인 |
| 학습·확장 | Brush 실행 파일·CLI, Python에서 외부 명령 실행 | Python·PyTorch·gsplat 기반 Splatfacto | Python에서 학습·평가를 확장할 경우 목표 스택이 적합 |
| 결과 확인 | Brush PLY·네이티브 뷰어, 기존 웹 화면은 업로드·분석용 | 기본 웹 뷰어·체크포인트 재로딩·렌더링·PLY 내보내기 | 프로젝트의 브라우저 확인 요구에 목표 스택을 우선 적용 |
| 촬영·안내 | FastAPI·로컬 JSON·iOS 앱·Android 웹 구현 있음 | 기본 CLI·뷰어만으로 촬영 API·보완 안내가 생기지는 않음 | 기본 복원 검증 뒤 필요한 기존 기능만 연결 |
| 검증 | 공개 실내 입력의 처리·학습·렌더 기록 있음, 실기기 전체 흐름 미완료 | 저장소 내 실행 근거 없음 | Brush 실측을 Splatfacto 검증 결과로 승계하지 않음 |
| 화질·속도 | 같은 조건의 엔진 간 비교 없음 | 같은 조건의 엔진 간 비교 없음 | 어느 엔진이 더 우수한지 단정하지 않음 |

**선택 이유:** NVIDIA 환경을 확보한다는 사용자 계획과 브라우저 확인·저장 결과 재사용 요구를 기준으로 Splatfacto를 공통 목표로 삼는다. Brush의 지원 플랫폼이 부족해서 전환하는 것은 아니다. Brush도 공식적으로 Mac·Windows·Linux와 여러 GPU, 웹 뷰어를 지원한다. 다만 현재 PoC에는 Brush 웹 뷰어가 통합되어 있지 않으며, 공식 최신 기능이 실측한 0.3.0에서 모두 동작한다고 가정하지 않는다.

## 이관 범위와 완료 조건

1. NVIDIA GPU 확보 후 모델·VRAM·드라이버와 CUDA·PyTorch·Nerfstudio·gsplat의 실제 호환 버전을 기록한다. PoC 가상환경과 분리해 설치한다.
2. 먼저 기본 CLI로 소규모 입력의 처리 → 학습 → 웹 뷰어 → 체크포인트 재로딩 → PLY 내보내기를 검증한다. 기존 FastAPI를 먼저 확장하지 않는다.
3. 기존 원본·A/B 입력 구분·실행별 결과 보존·COLMAP TXT 분석·카메라 정렬 코드를 재사용한다. 이미지명, 카메라 모델, 축·스케일·중심 변환을 확인한 후 분석 영역을 뷰어·렌더 결과와 대응시킨다.
4. `poc/common/server/experiment.py`의 `train`은 Brush 실행 파일·옵션·PLY 검증을 전제로 한다. Splatfacto로 이관할 때 실제 CLI·설정·체크포인트·출력 경로에 맞춰 변경하고 실패·시간 제한·기존 결과 보존 테스트를 갱신한다. 실행 파일 이름만 바꿔 호환된 것으로 처리하지 않는다.
5. 촬영·보완 안내가 필요할 때 기존 FastAPI·로컬 JSON·클라이언트를 연결한다. 분석 완료와 학습 완료의 상태 구분을 유지한다. 새 DB·큐·클라이언트 프레임워크는 통일에 필요하지 않다.
6. 동일 입력의 전체 경로와 A/A+B 좌표·평가 시점 대응을 [검증표](../04-test/validation.md)에 기록한 뒤 활성 PoC도 이관 완료로 표시한다. 이전 Brush 실험·로그·산출물은 비교·재현 자료로 보존한다.

현재 완료한 것은 목표 스택의 통일이며 **실행 코드 통일은 미완료**다. GPU 확보가 지연되는 동안 기존 Brush 경로로 촬영·분석 연결을 점검할 수 있지만, 이를 Splatfacto 검증으로 보고하지 않는다.

근거: [기존 실측](../../poc/common/docs/reports/core-poc-result.md), [Brush 공식 기능](https://github.com/ArthurBrussee/brush), [Nerfstudio 설치](https://docs.nerf.studio/quickstart/installation.html), [Splatfacto 기능](https://docs.nerf.studio/nerfology/methods/splat.html), [FFmpeg·COLMAP 데이터 처리](https://docs.nerf.studio/quickstart/custom_dataset.html). 공식 기능은 2026-11-14 확인했으며 이 저장소의 실행 검증과 구분한다.

[기술 원칙](tech-specs.md) · [전환 완료 기준·현황](../04-test/validation.md)

공식 자료: [Splatfacto](https://docs.nerf.studio/nerfology/methods/splat.html) · [데이터 처리](https://docs.nerf.studio/quickstart/custom_dataset.html) · [gsplat](https://github.com/nerfstudio-project/gsplat) · [COLMAP](https://colmap.github.io/)
