# 촬영 보완 PoC 공용 코드·실험

macOS·iOS와 Windows·Android 웹 PoC가 함께 쓰는 Python 분석기, FastAPI 서버, Brush 연결 도구, 테스트와 과거 실험 자료다. 플랫폼별 코드를 복제하지 않고 이곳에서 관리한다. Ubuntu·Nerfstudio 본 프로젝트의 구현은 아니다.

- [분석 CLI·실험 도구](poc/README.md)
- [API·Brush 운영](docs/05-ops/runbook.md)
- [검증 기록](docs/04-test/validation.md) · [Mac·Windows 실측](docs/04-test/reports/core-poc-result.md)
- [분리 전 연구 계획](docs/01-func/project-plan-history.md)
- 서버: [macOS](../macos/README.md) · [Windows](../windows/README.md)
- 클라이언트: [iOS 앱](../ios/README.md) · [Android 웹](../android/README.md)

`poc/`에는 서버·CLI·테스트·requirements와 로컬 `data/`, `.venv/`가 있다. 가상환경은 OS마다 별도로 만든다. 이동한 기존 Mac 가상환경은 Python 실행 파일을 사용할 수 있지만 activate·pip 스크립트에는 이전 경로가 남을 수 있으므로 `poc/.venv/bin/python -m pip`를 사용하거나 재생성한다.

공용 서버는 기본적으로 API만 제공한다. `--web-page`로 HTML 파일을 지정하면 `/`에서 해당 화면을 제공한다. Windows 시작 스크립트에서는 선택 인수 `-WebPage`로 전달한다. Android 웹 파일은 `../android/web/index.html`에 있으며 각 플랫폼의 실행 안내에 작업 디렉터리별 경로를 명시했다. API와 이미지 인증은 그대로 적용한다. 데이터 기본 위치는 서버 코드 기준 `poc/data/`이며 `--data` 또는 `POC_DATA`로 변경한다.

저장소 루트에서 공용 테스트:

```sh
cd poc/shared-poc
poc/.venv/bin/python -m unittest discover -s poc -v
```

기존 실험 데이터·모델은 복사 없이 함께 이동했다. Mac·Windows 결과가 섞인 과거 보고서는 원래 환경 표기와 함께 공용 기록으로 보존한다. JSON·로그의 과거 절대 경로와 해시는 당시 증거이므로 수정하지 않는다. 촬영 비교 절차에 기재된 iPhone 조건은 Mac·iOS 실기기 검증용이며 Android 성공 판정으로 사용하지 않는다.
