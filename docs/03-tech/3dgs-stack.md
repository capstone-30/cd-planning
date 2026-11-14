# 3DGS 확정 스택

결정일: 2026-11-14 · 상태: 채택, 구현 전환 및 실행 검증 전

데이터 처리부터 학습·뷰어까지 빠르게 구축하기 위해 **Nerfstudio + Splatfacto**를 프로젝트의 3DGS 스택으로 고정한다. 본 프로젝트의 구현 기준이며, macOS·iOS PoC는 별도 PoC로 유지한다.

## 구성

| 영역 | 확정 스택 | 역할 |
| --- | --- | --- |
| 처리·학습 환경 | Ubuntu + NVIDIA GPU + CUDA | SfM·3DGS 처리 및 학습 실행 |
| 데이터 처리 | Nerfstudio 데이터 처리 도구 + COLMAP | 영상 프레임 준비, 카메라 자세·희소 점군 추정, 학습 데이터 구성 |
| 학습 | Nerfstudio Splatfacto | 최초 A와 최초+보완 A+B의 3DGS 생성 |
| 학습 프레임워크 | Python + PyTorch | Splatfacto 실행 기반 |
| 래스터화 백엔드 | gsplat | Gaussian 래스터화 |
| 모니터링·뷰어 | Nerfstudio 기본 웹 뷰어 | 학습 상태 및 복원 결과 확인 |

기본 처리 흐름은 **사진·영상 입력 → 프레임 추출·COLMAP 처리 → Splatfacto 학습 → 기본 웹 뷰어 확인 → 결과 내보내기**다. 처리·학습은 Ubuntu GPU 환경을 기준으로 설계한다. 촬영 기기나 브라우저 클라이언트의 OS는 제한하지 않지만 iOS 앱과 Mac 전용 기능 개발은 필수 범위에 포함하지 않는다.

## 적용 범위

- 신규 3DGS 파이프라인은 Brush 대신 Splatfacto를 사용한다. 초기 결과 확인에는 Nerfstudio 기본 웹 뷰어를 사용한다.
- 별도 Three.js 뷰어, 충돌 처리 및 웹 1인칭 체험은 후속 기능이다. Nerfstudio 기본 뷰어 도입만으로 해당 기능을 완료한 것으로 보지 않는다.
- A와 A+B는 동일한 학습 설정으로 실행하고 입력, 버전, 설정, 로그, 체크포인트 및 내보낸 결과 경로를 기록한다. 별도 SfM 좌표계의 정렬과 비교 시점 대응은 계속 필요하다.
- 기존 Mac·Brush 코드와 iOS 앱, 실행 절차와 실측 보고서는 [기존 PoC](../../poc/macos/README.md)로 유지한다. 해당 결과는 새 스택의 실행 성공 근거가 아니다.

## 전환 완료 기준

1. Ubuntu GPU 환경에서 NVIDIA 드라이버·CUDA·PyTorch·Nerfstudio·gsplat 호환 조합을 설치하고 실제 버전을 기록한다. 버전은 첫 실행 검증 후 고정한다.
2. 실제 입력을 Nerfstudio 데이터 처리 도구와 COLMAP으로 처리하고, 카메라·희소 점군을 확인한다. 기존 분석기를 재사용하면 데이터 연결을 별도로 검증한다.
3. Splatfacto로 A와 A+B를 학습하고 브라우저에서 두 결과를 각각 확인한다. 체크포인트 재로딩과 결과 내보내기를 확인한다.
4. 본 프로젝트의 실행 안내와 검증 기록을 작성한다. 기존 PoC의 Mac API 전환과 실기기 P0/P1 판정은 본 프로젝트 완료 조건에 포함하지 않는다.

이번 결정은 문서상의 스택 확정이다. GPU 확보, 패키지 설치, 파이프라인 연동 및 성능 측정은 아직 수행하지 않았다. 기존 Mac 통합 메모리 16GB의 시간·메모리 예산을 Ubuntu GPU 환경의 보장값으로 사용하지 않는다.

## 공식 자료

- [Nerfstudio Splatfacto](https://docs.nerf.studio/nerfology/methods/splat.html)
- [Nerfstudio 데이터 처리](https://docs.nerf.studio/quickstart/custom_dataset.html)
- [gsplat](https://github.com/nerfstudio-project/gsplat)
- [COLMAP](https://colmap.github.io/)
