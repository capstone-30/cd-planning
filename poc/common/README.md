# 공용 Brush PoC

macOS·Windows 서버가 공유하는 Python API·분석기·Brush 도구다. 프로젝트와 PoC의 [공통 목표는 Ubuntu·Nerfstudio·Splatfacto](../../docs/03-tech/3dgs-stack.md)이며, 이 폴더의 실행 코드는 아직 Brush 기반이다. 기존 구현·실측은 이관 전 재현 기준으로 보존한다. NVIDIA 환경 확보와 새 경로 검증 후 이관하며, 현재 `server.experiment train`으로 Splatfacto를 실행할 수는 없다.

- [분석 CLI](docs/cli.md) · [API·학습·비교 운영](docs/runbook.md)
- [검증 현황](docs/validation.md) · [실측](docs/reports/core-poc-result.md) · [이전 계획](docs/project-plan-history.md)
- 서버: [macOS](../macos/README.md) · [Windows](../windows/README.md)
- 클라이언트: [iOS](../ios/README.md) · [Android 웹](../android/README.md)

코드는 루트·`server/`, 테스트는 `tests/`, 문서는 `docs/`, 실험 증거는 `docs/reports/`에 둔다. 로컬 입력·모델은 `data/`, 분석 출력은 `output/`이다. 데이터 경로는 `--data` 또는 `POC_DATA`로 변경한다.

가상환경은 OS별로 만든다. 이동한 환경의 activate·pip에 이전 경로가 남으면 재생성하거나 `.venv/bin/python -m pip`를 사용한다. 저장소 루트에서 테스트:

```sh
cd poc/common
.venv/bin/python -m unittest discover -s tests -v
```

서버는 기본 API 전용이며 `--web-page`로 `/`에 HTML을 제공한다. API·이미지에는 토큰이 필요하다. 플랫폼별 실행 경로는 각 README를 따른다.

과거 JSON·로그의 절대 경로·해시는 당시 증거로 보존한다. iPhone 촬영 기준은 Android의 완료 판정으로 사용하지 않는다.
