# 4043f1a 재현과 안내 v2 화질 비교 — 2026-11-13 (Windows)

**판정: 4043f1a의 핵심 처리 경로는 Windows PC에서도 재현됐다. Mac에서 메모리 압박으로 중단됐던 안내 v2 화질 비교를 완료했고, 이 데이터에서는 v2 선택이 균등 선택보다 개선되지 않았다. 오히려 작지만 일관되게 낮았다.**

공개 실내 장면 하나에서 카메라 자세를 고정하고 추가 사진만 바꾼 오프라인 비교다. 실제 사람이 안내를 보고 다시 촬영한 실험은 아니다. 기존 문서의 한계([CORE_POC_RESULT.md](CORE_POC_RESULT.md), [GUIDANCE_EVAL_RESULT.md](GUIDANCE_EVAL_RESULT.md), [guidance-v2.md](../docs/guidance-v2.md))는 그대로 적용된다.

## 환경

| 항목 | 값 |
| --- | --- |
| 기준 커밋 | `4043f1a` + 아래 Windows 호환 패치 |
| PC | Windows 11, Intel i5-14600KF, RAM 32GB, AMD Radeon RX 7800 XT (VRAM 16GB) |
| Python | 3.12.16 (uv 관리 인터프리터). `requirements-dev.txt` 고정 버전 그대로 설치 |
| 외부 도구 | FFmpeg 9.0.2 (gyan.dev), COLMAP 4.2.1 nocuda (공식 Windows 빌드), Brush 0.3.0 (공식 Windows 빌드, 배포 SHA256 일치) |
| GPU 사용 | COLMAP은 기존과 같이 CPU. Brush 로그: `AMD Radeon RX 7800 XT`, `DiscreteGpu`, `backend: Vulkan` |
| 입력 | Mip-NeRF 360 `room/images_4`, HF 미러 revision `df31214a…`의 정렬된 첫 100장. 100장 모두 배포된 LFS SHA256과 일치 |

작성자 Mac과 도구 버전은 같다. OS·CPU·GPU가 다르므로 시간과 학습 결과는 비트 단위로 같지 않다.

## Windows 호환 패치

동작을 바꾸지 않고 Windows에서 실행되도록만 고쳤다. macOS·Linux 경로는 기존 코드를 그대로 쓴다.

- `server/store.py`, `server/app.py`: `fcntl.flock` → `lock_file`/`unlock_file` (POSIX는 `fcntl`, Windows는 `msvcrt.locking`)
- `server/runner.py`: 시간 초과 시 `os.killpg` 대신 Windows는 `taskkill /T /F`. RSS는 Windows에서 `tasklist`로 기록. macOS 메모리 압박·swap 기록은 Mac 전용으로 유지(이 PC에서는 기록 없음)
- 텍스트 파일 읽기·쓰기에 `encoding='utf-8'` 명시. 이전에는 Windows에서 한글 보고서가 cp949로 저장되어 깨졌다
- `evaluate_guidance.py`: Brush 실행 파일 `--brush`, 학습 시드 `--seeds` 옵션 추가. 기본값은 기존과 동일(Mac 앱 경로, 시드 42·7)
- `run_core_check.py`(신규): 저장소에 없던 core-check 실행 스크립트를 문서 절차대로 다시 작성

기존 테스트 **26개 모두 Windows에서 통과**했다. `poc.py --demo` 출력 3개 파일은 커밋된 `poc/output/`과 내용이 같다.

## 1. 핵심 처리 경로 재현

A는 앞 60장, B는 다음 40장을 이미지당 0.5초인 960×640 H.264 클립으로 만들었다. 실제 FFprobe·FFmpeg·COLMAP과 FastAPI TestClient의 업로드·작업·보고서·PNG 호출을 사용했다.

| 항목 | Mac (2026-11-10) | Windows (이번) |
| --- | ---: | ---: |
| A 등록 / 입력 | 40 / 60 | 40 / 60 |
| A 희소 점 | 7,577 | 7,581 |
| A+B 등록 / 입력 | 100 / 100 | 100 / 100 |
| A+B 희소 점 | 24,874 | 24,783 |
| 안내 후보 (A / A+B) | 3 / 3 | 3 / 3 |
| A 분석 전체 | 34.1초 | 32.5초 |
| A+B 분석 전체 | 130.1초 | 125.9초 |
| A+B → A 카메라 정렬 상대 RMSE | 0.00232 | 0.00203 |

안내 v2가 고른 추가 10장도 문서와 순서까지 같다: B 39, 15, 37, 10, 23, 19, 5, 35, 2, 11.

## 2. 안내 v2 vs 균등 선택 화질 비교

조건은 [guidance-v2.md](../docs/guidance-v2.md)의 고정 프로토콜과 같다. 초기 A 60장 + 추가 10장, 공통 평가 10장(B의 4의 배수 프레임), 카메라는 A+B 100장 SfM으로 고정, 초기 점군은 A의 7,581점, Brush 3,000스텝·최대 해상도 960·최대 30만 splat.

### 원래 프로토콜 (시드 42, 7)

| 방식 | 시드 | PSNR (dB) | SSIM |
| --- | ---: | ---: | ---: |
| v2 | 42 | 24.039 | 0.8025 |
| 균등 | 42 | 24.449 | 0.8090 |
| v2 | 7 | 24.156 | 0.7965 |
| 균등 | 7 | 24.679 | 0.8094 |

v2 − 균등: 시드 42 **−0.41dB**, 시드 7 **−0.52dB**. SSIM도 둘 다 낮았다. 학습 1회는 약 22~25초였고 메모리 문제로 중단되지 않았다.

### 확장: 시드 10개

시드 2개로는 판단하기 어려워 같은 선택·평가 조건에서 학습 시드만 10개(42, 7, 1~6, 8, 9)로 늘렸다. 원래 프로토콜 폴더와 분리해 새로 고정했다.

| 지표 | 결과 |
| --- | --- |
| v2 평균 PSNR / 균등 평균 PSNR | 24.035dB / 24.318dB |
| 짝 차이 (v2 − 균등) 평균 | **−0.283dB** (표준편차 0.298) |
| v2가 낮았던 시드 | PSNR 8 / 10, SSIM **10 / 10** |
| 짝 부호 뒤집기 순열 검정 (양측) | p ≈ 0.018 |

같은 시드를 다시 실행해도 PSNR이 최대 0.28dB 달랐다(GPU 비결정성). 그래서 시드 하나의 차이로는 판단하지 않고 반복 분포로 판단했다.

### 어디서 손해를 봤나

평가 시점별 평균 차이를 보면 손해가 일부 시점에 몰려 있다. B 28번 프레임 **−1.14dB**, 32번 **−2.02dB**, 40번 **−0.84dB**이고, 나머지 대부분은 0 근처이거나 v2가 약간 높았다(4번 +0.44dB, 24번 +0.38dB).

v2는 B 24~34번 구간에서 한 장도 고르지 않았다(선택: 2, 5, 10, 11, 15, 19, 23, 35, 37, 39). 균등 선택은 이 구간의 26, 30, 34번을 포함했다. v2는 초기 A 점들의 새 시차를 최대화하므로, A에서 거의 보이지 않던 영역은 근거 점이 없어 후보 점수가 낮다. 이게 원인일 가능성이 있다. 이 원인은 검증하지 않았다.

## 결론

1. **처리 파이프라인은 Mac이 아닌 환경에서도 재현된다.** 등록 수·점 수·정렬이 Mac 결과와 거의 같다.
2. **현재 v2 안내는 이 데이터에서 화질 개선을 보이지 않았다.** 같은 추가 10장 예산에서 균등 선택보다 평균 0.28dB 낮았고 SSIM은 10번 모두 낮았다.
3. 이 결과로 "안내가 항상 나쁘다"고 말할 수는 없다. 장면 하나, 고정 자세(미래 카메라 위치를 아는 조건), v2 개발에 이미 쓴 평가 10장, 3,000스텝 짧은 학습이라는 한계가 있다. 다른 방·독립 평가 구간에서 다시 확인해야 한다.
4. 다음에 시도해 볼 만한 것: 초기 점에 근거하지 않는 커버리지 항목 추가(A에서 안 보인 영역), 균등 선택과의 혼합, 여러 장면 반복.

## 재현

```sh
# 도구: ffmpeg/ffprobe, colmap(bin)을 PATH에, Brush는 --brush로 지정
python poc/run_core_check.py --images <room/images_4 폴더> --manifest <source-manifest.json>
python poc/evaluate_guidance.py prepare-v2 --root poc/data/guidance-v2
python poc/evaluate_guidance.py run --root poc/data/guidance-v2 --brush <brush 실행 파일>
python poc/evaluate_guidance.py summarize --root poc/data/guidance-v2
python poc/evaluate_guidance.py prepare-v2 --root poc/data/guidance-v2-seeds10 --seeds 42,7,1,2,3,4,5,6,8,9
```

Windows의 스마트 앱 컨트롤이 서명 없는 `python.exe` 복사본(venv)을 차단해서, venv 대신 uv 인터프리터에 `PYTHONPATH=poc/.venv/site`로 패키지를 지정했다. 보안 설정은 바꾸지 않았다.

## 커밋한 산출물

`poc/data/`는 gitignore 대상이라 아래 파일만 강제로 추가했다. 원본·프레임 이미지, 클립 영상, COLMAP DB, 왜곡 보정 이미지, PLY는 크기 때문에 제외했다. 모두 위 명령으로 다시 만들 수 있다.

- `data/core-check/`: `source-manifest.json`, `clips.json`, `api-evidence.json`, `summary.json`, `clip-logs/`, 각 run의 `status.json`·`run-config.json`·`frames.json`·`capture-*-frames.json`·`logs/`·`analysis/`(보고서·안내 PNG)·`colmap/text/`(희소 모델)
- `data/guidance-v2/`: `protocol.json`, `selection.json`, `results.json`, `comparison.json`, `prepare-logs/`, 각 run의 `result.json`·`logs/`·`eval_3000/`(평가 렌더 PNG)
- `data/guidance-v2-seeds10/`: 위와 같되 평가 렌더 PNG는 제외(20 run × 5MB)
