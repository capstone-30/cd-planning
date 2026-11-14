# 분석 CLI

표준 라이브러리로 SfM → 영역 특징 → 규칙 기반 보완 우선순위를 계산한다. `poc/common/`에서:

```sh
python3 poc.py --demo
python3 poc.py --colmap /path/to/colmap-text-model --output real-output
python3 -m unittest discover -s tests -p test_poc.py -v
```

입력은 COLMAP TXT `images.txt`·`points3D.txt`다. 바이너리는 COLMAP에서 text로 내보낸다. CLI가 COLMAP을 실행하지는 않는다. 출력은 `output/report.md`·`features.csv`·`report.json`이며 같은 출력 경로는 덮어쓴다.

## 계산·한계

- 점군을 축별 기본 3등분(`--bins` 1~20)하고 빈 영역은 제외한다.
- 평균 관측 수, 방향 다양성(1 − 점→카메라 단위 벡터 평균 길이), 재투영 오차를 집계한다. 카메라 중심은 `-Rᵀt`다([COLMAP 형식](https://colmap.github.io/format.html)).
- 위험 점수 = `0.5/(1+관측수/3) + 0.3*(1-방향다양성) + 0.2*재투영오차/(1+재투영오차)`. 내림차순이며 가중치는 미보정 예시다.
- 점 5개 미만은 low로 표시한다. 나머지도 통계적 신뢰도·화질·확률이 아니다. 후보 자세가 없어 `direction_vector=null`이다.
- SfM 축은 실내 방향·미터 단위가 아니다. 미관측 공간·장애물·접근성은 추정하지 못한다. 전후 비교에는 공통 좌표 정렬·동일 구획이 필요하다.
- 영상 전처리·3DGS·뷰어·PSNR/SSIM/LPIPS는 이 CLI 범위 밖이다. 학습 기반 예측·관측 수 기준선 비교는 후속 검증이다.

데모는 시드 고정 카메라 8개·점 180개에 관측 수 2/6 차이를 주고 카메라 4·5 관측을 인위적으로 추가한다. 실제 재촬영이 아니며 좌표·재투영 오차는 유지한다. 테스트는 점수·좌표 변환·빈 POINTS2D·출력·정합 실패·잘못된 입력을 검사한다.

[전체 테스트](../README.md) · [API·영상·P1 운영](runbook.md) · [검증 현황](validation.md) · [시점 선택 종료 기록](reports/closed-experiments.md)

## 저장 이미지 보완 비교

```sh
.venv/bin/python check_supplement_effect.py --output data/supplement-effect-new
```

저장된 `guidance-eval/datasets/uniform`의 A 60장/A+10장을 같은 평가 사진 10장·초기 점군으로 Brush 학습한다. `requirements.txt` 환경·로컬 Brush·저장 입력이 필요하다. `--source`·`--brush`로 경로를 지정하고 출력은 존재하지 않는 새 경로를 사용한다. 입력·프로토콜·해시·로그·PLY·렌더·시점별 PSNR/SSIM·비교 JPG를 보존한다. Metal GPU가 제한된 샌드박스에서는 실행 권한이 필요하다.

실제 촬영 안내 효과 시험이나 시점 선택 실험 재개가 아니다. [결과·한계](reports/supplement-effect-result.md)를 따른다.
