# macOS PoC 실행

기존 Brush 서버용이다. [검증 현황](../../../common/docs/validation.md)·[기술 기준](../03-tech/tech-specs.md)을 따른다.

## 설치

Python 3.12+, FFmpeg·COLMAP(`brew install ffmpeg colmap`), [Brush 배포판](https://github.com/ArthurBrussee/brush/releases)을 준비하고 Brush 실행 파일을 `brush`로 PATH에 둔다. 저장소 루트에서:

```sh
cd poc/common
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m server.experiment doctor --output gate-tools.json
```

`doctor`는 버전·COLMAP CPU 옵션·Brush help를 `gate-tools.json`·`gate-logs/`에 보존한다. 도구 누락·옵션 확인 실패 시 설치를 수정하고 재실행한다.

## 서버

신뢰하는 Wi-Fi 또는 Tailscale 주소에 바인딩한다. Tailscale은 폰·Mac에서 같은 계정으로 연결한다. 포트 포워딩하지 않으며 디스크 여유 10GB를 확보한다.

```sh
export POC_TOKEN="$(openssl rand -hex 24)"
.venv/bin/python -m server --host 192.168.0.10 --port 8080
```

주소를 Mac의 실제 IP로 바꾼다. 토큰은 터미널에서 확인해 앱에 입력하며 로그·Git에 남기지 않는다. 모든 API·이미지에 토큰이 필요하다. 데이터 기본값은 `poc/common/data/`, 변경은 `--data` 또는 `POC_DATA`다. 단일 서버와 운영자 도구는 같은 파일 잠금으로 무거운 작업을 직렬화하며 결과는 자동 삭제하지 않는다.

| 설정 | 초기값·변경 방법 |
| --- | --- |
| 프레임·크기 | A 60장 / B 40장 / 긴 변 960px / 2fps |
| 확대·축소 | G0 후 `--initial-frames 80 --long-edge 1280`, 축소는 `--initial-frames 40 --supplement-frames 20` |
| 매칭 | combined는 sequential 후 전체 매칭으로 A/B 연결 시도. 새 run에서 `--matcher exhaustive` 가능 |
| 선명도 | 임계값 0(비활성). G0의 `capture-*-frames.json`으로 보정 후 `--blur-threshold 값` 고정 |
| 보완 길이 | 접수 10~30초, 2fps 후보 30장 확보에 15초 이상 필요. 흐림 제외를 고려해 20~30초 권장 |

## 연결·검증

1. 실제 작은 정적 방 영상으로 FFmpeg·COLMAP·TXT 분석 → Brush 학습·PLY 열기를 확인한다. 촬영 조건은 [기능 명세](../../../ios/docs/01-func/func-specs.md)를 따른다.
2. 시간·memory pressure·swap·버전·실패를 기록한다. 설치 검증 전에 프레임·해상도를 늘리지 않는다.
3. [iOS](../../../ios/docs/05-ops/runbook.md) 또는 [Android](../../../android/README.md)를 연결한다. Android HTML 제공은 `--web-page ../android/web/index.html`을 추가한다.
4. [공용 API·학습·비교 절차](../../../common/docs/runbook.md)를 수행하고 [검증 기록](../../../common/docs/validation.md)을 갱신한다.

자동 테스트는 [공용 안내](../../../common/README.md)를 따른다. 외부 명령 fixture 통과는 실제 COLMAP·Brush·실기기 성공을 뜻하지 않는다. 분석 데모만 실행하려면 공용 폴더에서 `python3 poc.py --demo --output /tmp/capture-guide-demo`를 사용한다.
