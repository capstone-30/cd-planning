# iOS PoC 화면

[기능·표현·완료 기준](../01-func/func-specs.md)을 따른다. `Mac 3DGS` 문구는 기존 Mac 시나리오 기준이다.

상단 `촬영 안내 PoC`·공통 상태 배너, 하단 4개 탭으로 구성한다.

| 탭 / 뷰 | 표시·동작 |
| --- | --- |
| 서버 연결 / `ConnectionView` | 주소·토큰, 연결 확인·설정 열기·새 프로젝트. 연결 중 주소 수정 불가 |
| 촬영·업로드 / `CaptureView` | A/B 시간 안내, 210pt 카메라 미리보기·경과 시간·녹화/종료/취소, AVPlayer 재생·재촬영·업로드·분석 시작, 전송률 |
| 작업 진행 / `StatusView` | A/A+B 선택, 상태·단계·경과 시간·스피너·실패 코드/메시지·3DGS 준비 상태, 조회·새 작업 재시도 |
| 보완 안내 / `GuideView` | 정합/입력 수, 후보 순위·영역·평균 관측·근거 점·참고 점수·주황 상자 이미지·촬영 문구, 한계·운영자 기록·B 촬영·준비 상태 갱신 |

연결 성공 → 촬영(기존 run이 있으면 진행) → 업로드·분석 → 진행 → 완료·리포트 수신 → 안내 → B 촬영.

- `Documents/session.json`: 주소·project·initial/supplement capture·initial/combined run·localFile·role 보존. 토큰은 영구 저장하지 않는다.
- 전경에서 2초마다 조회하고 비활성·완료·실패 시 중단한다.
- 연결 화면은 촬영 조건·원본 보관 위치와 `설정 → 개인정보 보호 및 보안 → 로컬 네트워크`를 안내한다.
- 촬영 헤더는 A 30~60초, B 10~30초(분석용 15초 이상 권장)로 구분한다.
- 후보 PNG 로드 실패 시 이미지 재시도, 후보 없음은 `안내 근거 부족`을 표시한다.
- 카메라 거부 시 설정 열기, `NWConnection.localNetworkDenied` 확인 시 로컬망 허용 안내. 기타 연결 실패는 주소·Wi-Fi·권한 점검과 원본 보존, 분석 실패는 저장 ID 복구·새 작업 재시도를 제공한다.

대표 이미지는 영역 점의 실제 POINTS2D 관측이 가장 많은 프레임이다. 상자는 관측 경계에 `max(10, width*0.1, height*0.1)` 여백을 더해 이미지 안으로 제한한다(BGR 0/150/255, 3px). 후보 위치·자세가 없어 방향·거리·안전 경로는 표시하지 않으며 업로드 외 진행률은 퍼센트로 표시하지 않는다.

촬영 문구: “표시 영역이 보이는 위치에서 화면에 유지하며 천천히 옆 시점으로 촬영하세요. 이동 가능 여부는 직접 확인하세요.”

구현: [CaptureGuideApp.swift](../../CaptureGuide/CaptureGuideApp.swift) · [AppModel.swift](../../CaptureGuide/AppModel.swift) · [guides.py](../../../common/server/guides.py)
