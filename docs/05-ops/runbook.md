# 환경 준비·운영

[확정 스택](../03-tech/3dgs-stack.md) 기준이며 실행 검증 전이다.

1. 확보 예정인 Ubuntu NVIDIA GPU·디스크를 준비하고 GPU 모델·VRAM·드라이버를 기록한다.
2. 공식 안내로 CUDA·PyTorch·Nerfstudio·gsplat 호환 조합과 COLMAP을 설치한다.
3. 소규모 실제 입력으로 처리 → 학습 → 웹 뷰어 → 재로딩·내보내기를 확인한다.
4. 버전·명령·입출력 경로·접속 방법·시간·자원·실패 사유를 이 문서와 [검증표](../04-test/validation.md)에 기록한다.

설치 버전·CLI 인수·자원 예산·원격 접속 구성은 첫 실행 후 고정한다. 기존 PoC 실행은 [macOS](../../poc/macos/README.md)·[Windows](../../poc/windows/README.md), 클라이언트는 [iOS](../../poc/ios/README.md)·[Android](../../poc/android/README.md)를 따른다.

PoC도 같은 목표 스택으로 이관한다. 기존 Brush 가상환경·데이터·결과를 보존하고 새 학습 환경을 별도로 만든다. 기본 CLI 검증 후 기존 분석·촬영 API를 연결하는 순서는 [이관 범위](../03-tech/3dgs-stack.md)를 따른다. 현재 PoC의 Brush 학습 명령은 Nerfstudio 실행 명령이 아니다.
