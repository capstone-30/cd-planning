# 본 프로젝트 환경 준비·운영 계획

기준일: 2026-11-14 · 대상: Ubuntu + NVIDIA GPU + CUDA

새 스택은 실행 검증 전이다. 실제 환경에서 확인한 설치 명령·버전·입출력 경로·뷰어 접속 방법을 이후 이 문서에 기록한다.

## 준비·실행 순서

1. Ubuntu GPU 장비와 디스크 여유 공간을 확보하고 GPU 모델·VRAM·드라이버를 기록한다.
2. Nerfstudio 공식 설치 안내에 따라 CUDA·PyTorch·Nerfstudio·gsplat 호환 조합과 COLMAP을 준비한다.
3. 실제 소규모 사진·영상 입력으로 Nerfstudio 데이터 처리를 수행하고 카메라·점군 출력을 확인한다.
4. Splatfacto 학습을 실행하고 설정·로그·체크포인트를 보존한다.
5. Nerfstudio 기본 웹 뷰어에서 결과를 확인하고 재로딩·내보내기를 검증한다.
6. [검증 기록](../04-test/validation.md)에 실제 버전·명령·경로·시간·실패 사유를 추가한다.

본 프로젝트의 설치 버전·GPU 자원 예산·CLI 인수·원격 접속 구성은 아직 고정하지 않았다. [확정 스택](../03-tech/3dgs-stack.md)을 기준으로 첫 실행 후 고정한다.

기존 PoC의 서버 환경은 [macOS](../../poc/macos/README.md)·[Windows](../../poc/windows/README.md), 모바일 클라이언트는 [iOS](../../poc/ios/README.md)·[Android 웹](../../poc/android/README.md) 안내를 따른다. 공용 Python 코드·Brush 운영·실험 데이터는 [공용 PoC](../../poc/shared-poc/README.md)에서 관리한다.
