import time
import io
import os
import cv2
import numpy as np
from PIL import Image
from ppadb.client import Client as AdbClient

import sys
import datetime

import chest_opener
import party_manager
from screen_capture import capture_screen, capture_screen_bytes, decode_screen_bytes

# 💡 [v1.13.18 신설] 통합 힐링 필요 플래그 및 상자 복귀 감시 전역 변수
# 💡 [v1.17.0] FFXI 콜라보 던전("북쪽의 유령선") 지원, 3채널 BGR 컬러 매칭 수렴 루프 하켄 스턱 완치, 체크포인트 1회 제한 + Redo 연동, 최초 기동 던전 직진입 안전 탈출
need_heal = False
came_from_chest = False

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.21.11
# - 최근 수정일: 2026-09-16
# - 수정 기록:
#   1.21.11: 🆕 눈보라구간/정체탈출가드 후속 완치 3건 + 던전 진입 대기 상향.
#     (1) 던전선택/대설지대 경로선택 → 필드 진입 대기 폴링 10초 → 15초 상향(실기 확인: 일부 전환에서
#     10초를 살짝 넘는 경우 있었음, `src/main.py` 2곳).
#     (2) 눈보라구간 재개 버튼을 탭하기 "전"에 활성/비활성을 먼저 판정하는 `is_resume_button_active()`
#     신설 - 처음엔 고정 절대밝기(125.0) 기준으로 했으나, 실전 스크린샷(logs/2026-09-16-2200-44_
#     reboot1.png)에서 안개 농도 변화로 비활성(밝기154.9)이 활성으로 오판되는 사고가 바로 발견됨.
#     같은 프레임의 "나가기" 버튼(항상 활성으로 보임) 밝기를 기준점 삼아 재개 버튼과 **상대 비교**
#     하는 방식으로 재수정 - 실측 3개 샘플(비활성 비율 0.527/0.638, 활성 0.935)로 절대밝기 방식보다
#     훨씬 크게 분리됨을 확인, 오판됐던 그 스샷도 이 방식으론 정확히 비활성(0.638)으로 잡힘.
#     (3) "정체 탈출 가드"(완화 임계값 0.45) 힐 재시도 한도 3회 → 1회로 축소(사용자 확정: "힐링을
#     세번이나 할 필요는 없다"). 1회 힐링 후에도 또 걸리면 빈사가 아닌 진성 정체로 간주해 나가기
#     버튼(전 던전 공용 도장)을 탭하도록 변경 - 눈보라에 적용한 "안 되면 나가기" 패턴을 FIELD_WAIT
#     공용 블록에도 동일 적용.
#   1.21.10: 🆕 전투 시작 직후 자동전투가 영원히 안 켜진 채 정체하던 결함 + 대설지대 눈보라구간
#     재개버튼 무한 반복 결함, 2건 완치.
#     (1) 자동전투 토글 버튼 도장(auto_off.png/auto_on.png)이 전투패턴 번호 배지가 아이콘에 붙기
#     전(로드맵 4번, 2026-08-30) 구형 모양이라, 배지가 붙은 지금 화면에선 실측 매칭 점수가 0.57
#     까지 떨어져(임계값 0.65 미달) 좌표탐색이 실패했다 - 색상판정(is_auto_combat_yellow)은 정확히
#     "꺼짐"으로 판정하는데 탭할 좌표를 못 찾아 아무 것도 안 하고 넘어가버려, 전투 내내 자동전투가
#     계속 꺼진 채 방치되는 실전 사고가 있었다(사용자 제보 2026-09-13/14, 배속은 정상 주황인데
#     자동전투만 안 켜짐 - 실측 스크린샷으로 원인 확정). 이 버튼의 화면 위치 자체는 배지 숫자와
#     무관하게 고정(1380,1720, 1440x2560 기준, 2026-08-30 실기 확인 완료)이므로, 도장 매칭 실패 시
#     이 고정좌표로 바로 탭하는 폴백을 3개 호출부 전부에 추가(기존에 한 곳에만 있던 폴백을 나머지
#     두 곳에도 동일 적용).
#     (2) 대설지대 눈보라 서브구역에서 재개 버튼이 실제로는 비활성 상태인데 활성/비활성 구분이 안
#     돼 계속 눌리기만 하고 게임 쪽 반응(토스트조차)이 전혀 없어, "없습니다" 토스트 감지에만 의존
#     하던 기존 나가기 트리거가 단 한 번도 안 걸린 채 13분+ 무한 반복한 실전 사고(2026-09-14
#     22:30~22:43+, 이 도중 MuMu 자체가 그래픽 서브디바이스 오류로 크래시해 재개도 못한 채 방치됨)
#     완치. 토스트 없이도 재개 30초 무반응이면 강제로 나가기 전환(전투로 이 분기를 벗어났다 돌아오면
#     30초를 새로 잼 - 전투만으로도 30초를 넘길 수 있어 억울한 판정을 막기 위함), 나가기 후 커서
#     재확인되면 안전지대(700,150) 선제 터치로 잔여 이동을 멈춘 뒤(관성으로 상자 대신 던전 출구를
#     먼저 밟는 사고 방지 - 캠핑 이동 시 이미 쓰던 것과 동일한 방어 패턴) 기존 상자 절차로 복귀.
#     이 분기 안에서 last_state_changed_time을 매 틱 무조건 리셋하던 부분도 제거해, 위 새 안전장치가
#     전부 실패해도 공용 300초 강제재시작 하드리밋이 최후 안전망으로 다시 작동하도록 함(예전엔 이
#     리셋 때문에 300초가 이 분기에서 영원히 안 걸렸음).
#   1.21.9: 🆕 "빈사"(HP 낮음, 힐로 회복)와 "사망"(HP 0, 힐로 절대 안 풀림)을 구분하지 못해 정비를
#     무한 재격발하던 결함 완치. 사용자가 실전 12시간(!)을 이걸로 날린 뒤 보고 - 빈사 픽셀 카운터
#     (count_danger_hp_pixels)는 두 상태를 구분하지 않아, 죽은 캐릭터가 있으면 힐을 아무리 넣어도
#     위험색이 안 사라져 "빈사 감지→정비→빈사 감지"가 6~7초 간격으로 계속 반복되다가 게임 세션이
#     시간초과로 끊겼다(사용자 확인: "예전엔 캐릭 죽었어도 그냥 주회는 돌았거든" - 이 빈사 감지
#     기능 자체가 이번 세션에 새로 생기면서 만든 회귀 버그).
#     사망(해골) 아이콘 도장으로 "진짜 사망"을 먼저 확인하고, 사망이 확인되면 (1) 이후 같은 파티
#     상태에서는 빈사 감지 자체를 억제하고(예전처럼 사망자를 달고 주회 계속), (2) 상자 소진 시와
#     동일한 TRIGGER_EXIT 절차를 그대로 재사용해 마을 회군을 시도한다(사용자 확정: "마을복귀하면
#     확률적으로 부활하기도 함") - 던전별로 다른 귀환 방식을 다시 판단할 필요 없이 기존 검증된
#     로직을 그대로 탄다.
#     ⚠️ 실측 중 결함 3연속 발견 및 완치(전부 §일반 원칙 "실측 필수, 추측 금지"가 지켜낸 사례):
#     (1) 사용자가 처음 준 크롭(stat_dead.png, 세션종료 화면에서 딴 것)은 그레이스케일 밝기가
#     30~147로 낮아, 이 저장소 관례인 이진화(160) 매칭을 쓰면 "아무 화면의 아무 어두운 영역과도
#     무조건 1.000으로 매칭"되는 상태였다(스크린샷 309장 전수 대조로 확인) - 그대로 썼으면 빈사
#     감지 첫 발동 즉시 무조건 "사망"으로 오판해 매번 마을로 도망가는, 원래 버그보다 더 나쁜
#     회귀가 됐을 것. 이진화 대신 원본 그레이스케일 매칭으로 전환.
#     (2) 그레이스케일로 바꾼 뒤 실제 사망 화면 원본(dev/ROI_check/사망.png, 크롭 도구의
#     _crop_metadata.json으로 채팅 첨부 이미지 없이 찾아낸 원본 - 사용자 지적으로 CLAUDE.md/
#     AGENTS.md에 이 방법 자체를 지침으로 남김)으로 재검증하니 정탐/오탐이 아예 역전됐다. 원인은
#     이 스크린샷 자체가 "세션 종료" 오버레이로 파티창 영역 전체가 어둡게 깔린 상태였기 때문(사용자가
#     처음부터 경고한 문제) - 임계값/색상 방식을 바꾸는 미봉책이 아니라 원본 데이터 자체가 못 쓴다는
#     결론까지 내리고 사용자에게 정상 조명 화면에서 재크롭을 요청.
#     (3) 사용자가 정상 조명(필드/전투/상자) 3종을 새로 크롭해줌(dead_inField/dead_inCombat/
#     dead_chest.png) - 이걸로도 처음엔 여전히 정탐이 생존 슬롯보다 낮게 나와 당황했으나, 실제
#     원인은 도장이 아니라 **슬롯 좌표**였다: `chest_opener.SLOT_ROIS`는 "상자 열 캐릭터를 고르는
#     모달 팝업" 전용 좌표인데, 이걸 필드 하단에 상시 떠 있는 파티 HUD에 그대로 재사용해 카드 하나를
#     반토막 내고 옆 카드 내용까지 섞어 읽고 있었다(두 화면은 육안으로는 비슷해 보이지만 실제 픽셀
#     위치가 다름). 실측으로 필드 HUD 전용 좌표(FIELD_PARTY_SLOT_ROIS)를 새로 잡고 dead_inField.png
#     와 짝을 맞추니 정탐 0.999~1.000 vs 오탐 최고 0.585(필드 앵커 통과 스크린샷 38장 전수 대조)로
#     깨끗하게 분리됨을 확인 - "빈사(생존)" 샘플(딸피_필드.png)도 전 슬롯 0.48~0.52로 안전하게
#     걸러짐(빈사와 사망을 확실히 구분). 임계값 0.85로 확정, 정식 검증 완료.
#   1.21.8: 🆕 [화면 과도기 감지] 예상 밖 상태 팝업으로 인한 정체를 능동적으로 해소하는 안전장치
#     추가. 사용자가 관전 중 실전 버그를 목격 - 상자가 미니게임 없이 즉시 열리고 곧장 다음 전투가
#     시작되면서, chest_opener.py의 캐릭터 선택창 진입 판정("열다" 버튼 소멸만으로 판정)이 흔들려
#     고정 좌표 슬롯 탭이 전투 UI의 캐릭터 상태 아이콘 자리에 떨어짐 - 아베니우스의 "눈보라/동상"
#     상태 팝업이 뜬 채로 필드/전투 앵커가 둘 다 가려져 "화면 과도기 감지"가 7초간 돌았다(사용자가
#     수동으로 닫아서 풀림, 자동 복구 수단은 없었음).
#     실측 과정에서 두 번 정정: (1) 기존 범용 "X 닫기" 도장(close_panel.png, 레벨업/여권 팝업용)을
#     재사용하려 했으나 실제 정체 스크린샷 대조 결과 0.586으로 임계값(0.70) 미달 - 그 도장은 "X" 위에
#     "닫기"가 세로로 쌓인 레이아웃인데 이 상태 팝업은 가로로 나란한 다른 레이아웃이라 새 도장
#     (close_panel_inline.png)을 크롭해야 했음(같은 스크린샷에서 1.000 확인). (2) 그 새 도장을 저장소
#     스크린샷 전수 대조하니 상자 "누가 열 거야?" 캐릭터 선택 화면의 'X 닫기'와도 0.92~0.93으로
#     오탐돼, 전체화면 검색 시 진행 중인 상자 개방을 잘못 취소시킬 뻔했음 - 실측으로 두 화면 버튼의
#     Y좌표가 확실히 분리됨을 확인(상태팝업 58.8% vs 캐릭터선택 94.5%, 약 900px 차이)하고 그 차이로
#     구역(STATUS_POPUP_CLOSE_ZONE)을 좁혀 완전히 분리 - 구역 제한 후 전체 스크린샷 321장 재대조,
#     최고 오탐 0.436으로 임계값(0.70)과 충분한 여유 확보. "필드/전투 앵커가 둘 다 없음"으로 판정되는
#     `else` 분기는 `if not combat_active:`로 이미 감싸여 있어 정상 전투 중에는 도달 자체가 없다(이
#     도장이 정상 전투 화면에도 0.96으로 걸리지만 안전한 이유).
#   1.21.7: 🆕 대설지대 "뼈상인"(뼈 줍는 고블린) 조우 처리 신규 추가. 사용자가 실전에서 드디어
#     조우 - 4지선다(유해를 부르는 기름(10,000골드)/모험가의 뼈(1,000골드)/비약(100골드)/아무것도
#     안 산다) 중 사용자 확정 우선순위대로 모험가의 뼈를 1순위로 고정 선택하고, 없으면(오탐/화면
#     변형 등) 유해를 부르는 기름을 2순위로 선택한다. 사용자가 미리 크롭해둔 두 도장
#     (`Dun_dilog_bone.png` = "모험가의 뼈(1,000골드)" 전체 줄, `Dun_dilog_oil.png` = "기름" 2글자만)
#     을 다른 대설지대 선택지(싸운다/빠져나간다)와 동일한 "직접 검색+클릭" 방식으로 연결 -
#     `_handle_dungeon_interrupt()`(필드맵 귀환 루틴용, 하위 5개 호출부 전부 배선)와
#     `start_main_macro()`의 공용 전처리 블록(필드 이동 전체에 걸쳐 상시 감시) 양쪽에 동일하게
#     추가해, 필드맵 귀환 중이든 평소 이동 중이든 어디서 만나도 처리된다. 실측 검증(뼈상인 조우
#     스샷 + 대설지대 기존 스샷 전수 대조): 정탐 둘 다 1.000, "기름" 도장은 2글자뿐이라 다른 화면과
#     근접 오탐 위험이 있어(음성 최고 0.650, combat_dialogue.png) 임계값을 다른 대설지대 선택지들의
#     관례(0.70)보다 높은 0.80으로 설정(뼈는 음성 최고 0.568로 그보다 여유로움, 동일하게 0.80 적용).
#   1.21.6: (이 파일 자체는 변경 없음, 버전 동기화용) 대설지대 주회 한도 도달 시 "마을외곽 ↔
#     경로목록" 무한 왕복 완치 - 한도 도달 시 실제로 여관을 경유하도록 근본 완치. 상세는 main.py 참고.
#   1.21.5: 🚨 대설지대 상자파밍 중 터치가 완전히 죽어도 300초 워치독이 발동 조건에 못 미쳐 3시간
#     넘게 재시작이 안 걸리던 결함 완치. `prev_cursor_dir`(대설지대 전용 커서방향 이동감지 기준값)이
#     매크로 기동 시 딱 한 번만 초기화되고 그 뒤로 갱신되지 않는 구조라, 캐릭터가 실제로는 전혀 못
#     움직였는데도 "지금 방향"이 몇 시간 전의 낡은 기준값과 우연히만 다르면 첫 프레임에서 곧장
#     "이동함"으로 오판되고, 그 오판이 정체 타이머(last_state_changed_time)까지 매번 리셋해 절대
#     워치독(300초) 발동에 필요한 30초 정체 누적 자체가 안 됐다(실전 로그 2026-09-10 03:22~06:44,
#     "상자 자동 이동"→"이동 시작 확인"만 무한 반복. 사용자가 MuMu 관리자 화면에서 해당 인스턴스가
#     "실행이 중지됨" 상태였고 ADB 연결/캡처는 살아있는데 터치만 죽어 있었음을 직접 확인). "상자 자동
#     이동" 탭 직전 화면에서 방향을 다시 찍어 매번 새 기준값을 세우도록 완치 - 비교 대상이 항상
#     "방금 전"이 되도록 해서, 진짜로 안 움직였다면 정체 타이머가 정상 누적돼 기존 300초 워치독이
#     제대로 작동한다. 상세는 main.py 참고.
#   1.21.4: (이 파일 자체는 변경 없음, 버전 동기화용) recover_app_startup()이 대설지대 "마을외곽"
#     화면을 프리셋에 따라 반쪽만 인식하던 결함 완전 완치. 상세는 main.py 참고.
#   1.21.3: 🚨 우물(캠프) 아이콘이 화면 상단 타이틀바에 너무 가까우면 자동이동 버블이 가려 안 보이던
#     결함 + 그 실패가 곧장 앱 전체 재시작으로 이어지던 과잉 대응 완치.
#     실전 로그(2026-09-09 19:05, 경로6 -호반(남)-): 우물 탭 (1059,373) 후 "자동이동 버튼 미검출"이
#     3회 연속돼 자동이동 버튼을 끝내 못 찾고 "failed"→RuntimeError→ADB 서버 리셋(앱 강제 재시작)
#     으로 이어졌다. 사용자가 스크린샷으로 우물이 상단 던전명 타이틀바("경로6 -호반(남)-")에 바짝
#     붙어 있음을 직접 확인 - 탭 지점 근처에 뜨는 자동이동 버블이 그 타이틀바에 가려진 것으로 추정.
#     사용자 지적: "우물을 검색하는 Y축의 범위를 저 위치보다 200픽셀은 더 아래로 한정지어야지 자동
#     이동 버튼이 보일듯" - `_find_first_icon()`에 `min_y` 옵션을 추가해 캠프 분기에서만
#     `FIELDMAP_CAMP_ICON_MIN_Y = 573`(실패 지점 y=373 + 200) 미만의 매칭은 미검출로 간주하도록
#     완치. 상단 근접 매칭이 걸러지면 기존 스와이프 탐색(1차 아이콘 탐색)/작은 안쪽 넛지 스와이프
#     (자동이동 버튼 재탐색 루프)가 그대로 이어받아 더 아래쪽 위치에서 다시 찾는다 - 새 스와이프
#     로직을 추측으로 추가하지 않고 이미 검증된 기존 재시도 경로에 필터만 얹은 것.
#     추가 완치(같은 세션, 사용자 지적): "지금 모든 앵커들이 활성화 잘되어서 붙어있는데 adb를
#     재시작해버리는 것도 문제" - 연결/화면인식 자체는 멀쩡한데 위와 같이 일시적/회복 가능한 상황도
#     곧장 앱 전체 재시작이라는 비싼 복구로 처리되고 있었다. 자동이동 버튼을 끝내 못 찾았을 때의
#     반환값을 "failed"(즉시 RuntimeError)에서 "retry"로 바꿔, 이미 있던 재시도 경로
#     (TRIGGER_EXIT의 fieldmap_return_retry_count, 최대 5회 - 필드맵을 처음부터 다시 열어 재시도)를
#     먼저 거치고, 그마저 5회를 넘겨야만 진짜 앱 재시작으로 넘어가도록 완화.
#   1.21.2: 🚨 return_to_town_via_fieldmap_icon()의 미니맵 확장 전 커서 체크 루프에 캠핑 화면
#     ("쉰다") 감지가 아예 없던 결함 완치. 사용자가 "캠핑하러 와서 쉰다가 나왔는데 필드커서
#     미검출이 뜬다"고 보고해 발견 - 캐릭터가 상자를 찾아 이동하다 마침 캠프 지점(우물) 위에
#     서면, 맵을 열지 않아도 게임이 자동으로 캠핑 선택창을 띄운다. 이 화면엔 압축 미니맵 커서가
#     없으니 "전투 아님/확장도 아님"으로만 판정돼 미니맵 확장 좌표(1217,219)만 계속 눌러대며
#     정체했다(그 좌표는 캠핑 화면에서 아무 의미가 없는 자리라 탭이 헛돎). 커서 미검출 분기에서
#     전투/확장 체크와 같은 순서로 캠핑 화면부터 먼저 확인하도록 추가 - 감지되면 맵 확장을 건너뛰고
#     곧장 perform_camping_rest()로 넘어간다.
#     같은 자리에서 실제 스크린샷(자동 저장분)으로 "쉰다" 화면이 정체 도중 떠 있었음을 확인, 실전
#     로그와 정확히 일치함을 검증(사용자 재현 로그로 재확인).
#   추가 완치(같은 세션, 실측 확정): 자동이동 대기 루프에서는 도착 판정(쉰다/우물말랐다)이
#     _handle_dungeon_interrupt() "뒤"에 있어서, "생명의 우물이 말라버렸다" 화면이 화살표 도장과
#     0.985로 매칭돼(임계값 0.82 초과) 화살표 폴백이 먼저 대화를 넘겨버리는 바람에 도착 체크가 그
#     프레임에서 아예 실행되지 못했다. 캐릭터는 이미 도착해 있으니 재개 버튼이 같은 자리를 다시
#     트리거해 "우물말랐다"가 또 뜨고, 화살표→재개 사이클이 무한 반복됐다(실전 로그: 8회 연속).
#     도착 판정을 인터럽트 처리보다 먼저 체크하도록 순서를 바꿔 완치 - "도착했는가"가 "화살표니까
#     넘긴다"보다 우선순위가 높아야 한다는 원칙.
#     추가 완치(같은 세션, 사용자 지적 - 비대칭 완치): return_to_town_via_fieldmap_icon()이 스와이프
#     탐색 끝까지 목표 아이콘을 못 찾았을 때, 캠핑 분기(is_camp_branch)는 이미 나가기 버튼 폴백
#     (_return_after_camping)이 있는데 하켄 분기(harken_only)만 그냥 "failed"만 반환했다. 사용자
#     지적: "교회구역 외에 다른 구역에 캐릭을 두고 매크로를 실행하면 하켄 없는 맵에서는 나갈 수가
#     없다." 신규 헬퍼 _exit_via_walkout_or_harken()을 추가해 하켄 분기도 아이콘 미검출 시 나가기
#     버튼을 누르고 도보 탈출/하켄 귀환 중 먼저 뜨는 쪽을 그대로 따라가도록 완치(진짜 하켄이 있는
#     구역이면 하켄 귀환으로, 하켄이 없는 구역이면 도보 탈출로 자연히 갈린다). field_anchor 소멸만
#     으로 도보 탈출을 판정하면 하켄 귀환목록/가호 팝업도 전체화면이라 오판할 수 있어(캠핑 화면과
#     동일 유형 함정), 하켄 메뉴가 아닐 때만 그 판정을 신뢰하도록 순서를 맞췄다.
#   1.21.1: 🚨 정체 타이머(last_state_changed_time) 리셋 누락 2건 완치(CLAUDE.md에 이미 기록된 재발
#     패턴과 같은 유형). v1.21.0을 실전 운용하던 사용자가 "힐링 시퀀스 도중 정체로 빠지고, 그 직후
#     뜬 상자를 못 잡는다"고 보고해 발견. (1) 힐링 성공 분기(party_manager.run_party_healing_sequence
#     완료 → 재개 탭) 전체에 리셋이 없었다 - 이 호출이 실전 27초 걸리는 블로킹 함수인데, 그동안(과
#     그 이후에도) 타이머가 힐링 시작 시점에 멈춰 있어 힐링+재개를 마친 직후 곧바로 "31초 정체"로
#     오판됐다(실전 로그 2026-09-09 17:55:56~17:56:27). (2) FIELD_WAIT의 "📦 [메인] '열다' 감지!"
#     경로(가장 빈번하게 도는 상자 진입점 - 사용자가 처음 보고한 정체 사고 직전 로그 줄과 정확히 일치)
#     와 재개-이동 재시도 결과 처리(opened/toast_detected/moved 세 갈래, 전부 진짜 화면 진행)에도
#     리셋이 없었다 - 최종 else(진짜 정체 - 상자없음 판정)는 의도대로 리셋 대상에서 제외했다.
#   1.21.0: 🚀 ADB 화면 캡처를 원시(raw) 방식으로 전환(상세는 main.py 참고, src/screen_capture.py
#     신설). 이 파일이 호출부 46곳 중 가장 많은 29곳을 차지한다 - device.screencap() 직접 호출을
#     capture_screen_bytes(device)로, np.array(Image.open(io.BytesIO(x)))를 decode_screen_bytes(x)로
#     전수 치환(캡처+디코드 한줄짜리 6곳은 capture_screen(device)로 통합). 반환 shape/dtype이
#     기존과 완전히 동일해 호출부의 다른 로직(if raw: / try-except 등)은 손대지 않았다.
#   1.21.0 이전부터 있던 결함이지만 오늘 발견/완치: return_to_town_via_fieldmap_icon()의 스와이프
#     탐색/아이콘 탭 재시도 두 루프가 "for x in range(n):" + 인터럽트 시 continue 패턴이었는데, for
#     루프는 continue해도 range의 다음 값으로 그냥 넘어가서 인터럽트 처리 한 번마다 실제 스와이프 없이
#     예산이 1씩 줄었다(실전 로그: 화살표 감지 4연속 후 "스와이프 1/8"이 바로 "6/8"로 건너뜀). while +
#     실제 진행했을 때만 증가하는 카운터로 완치, 절대시간 워치독도 추가. 겸사겸사 확장된 필드맵 화면에
#     화살표 도장과 0.76~0.81로 근접 매칭되는 UI 요소(접기/펼치기 삼각형으로 추정)를 실측으로 발견해,
#     맵이 열려 있는 3개 호출부(탭 직후 폴링/스와이프 탐색/아이콘 탭 재시도)의 화살표 폴백을 억제했다
#     (구체적 선택지 처리는 그대로 유지 - 오탐 위험은 화살표 단독 폴백에만 있었음).
#   커서 미검출 무한 대기 완치(실전 확인, 2026-09-09): 미니맵 확장 탭 전 커서 체크 루프가 "커서
#     미검출 + 전투 아님 + 확장도 아님"이 겹치면 탭을 시도할 방법이 아예 없어 1.5초씩 무한 대기만
#     했다(실전 로그: 61초간 진행 없이 사용자가 수동 개입). 연속 5회(약 7.5초) 넘게 커서가 안 보이면
#     대기를 포기하고 탭을 시도하는 폴백을 추가했다.
#   1.20.0: 뮤뮤 안드15 전용화 대응은 main.py 참고(이 파일은 화면 캡처 방식 변경 없음). 이 버전에서
#     이 파일은 대설지대 6층 실전 완주 검증 과정에서 발견된 결함들을 완치했다:
#     (1) [전투를 메인 루프에 인계] return_to_town_via_fieldmap_icon()이 전투를 만나면 예전엔
#     "자동전투가 끝나길 기다린다"고 자체적으로 대기했는데, 자동전투가 (탭 오발 등으로) 한 번 깨지면
#     아무도 전투를 몰지 않아 그대로 멈췄다(실전: 사용자가 수동으로 자동전투를 다시 켜줘야 했음).
#     이제 전투를 만나면 즉시 "combat"을 반환해 메인 루프의 IN_COMBAT 상태 기계(자동전투 재활성화/
#     스킬/힐링/사망 감지)로 제어를 넘기고, 호출부는 전투가 끝나면 이 루틴을 처음부터 다시 태운다.
#     확장 탭 판정도 "전투 도장이 안 보이면 탭"(음성 조건, 한 프레임만 흔들려도 오발)에서 "압축
#     미니맵의 노란 커서가 보일 때만 탭"(양성 조건)으로 교체.
#     (2) [캠핑을 공용 전처리 블록에서도 처리] 전투로 메인 루프에 제어가 넘어간 사이 캐릭터가 캠프에
#     도착하면, 캠핑 선택창("쉰다"/"아무것도 안 한다")엔 필드/전투 앵커가 없어 "화면 과도기"로
#     오판되고 30초 뒤 비상 뒤로가기가 주입돼 캠핑이 취소됐다(실전 로그). 공용 전처리 블록에도 캠핑
#     가드를 추가하고, 캠핑 완료를 모듈 전역 플래그(reset_camping_done/is_camping_done)로 집계해
#     "귀환 루틴 안"과 "공용 블록" 어느 쪽에서 캠핑했든 무한 캠핑에 빠지지 않게 했다. "생명의 우물이
#     말라버렸다"(이 필드에서 이미 캠핑함) 메시지도 캠핑 완료 신호로 인식하도록 Dun_camping_dry.png
#     신규 도장 추가(오탐 검증: 양성 1.000 vs 다른 화면 최고 0.205).
#     (3) [눈보라 판별을 미니맵 확장 가능 여부로 교체] "필드 앵커는 있는데 커서 미검출"만으로 눈보라를
#     판정하면, 캠핑을 마친 자리에서 앱이 재시작돼 커서가 캠프 아이콘에 가려진 경우와 구분이 안 돼
#     반응 없는 재개 버튼만 무한히 눌렀다(실전: 이동 명령 이력이 없어 재개가 비활성). 미니맵을 눌러
#     실제로 확장되는지로 확실히 구분하도록 교체(사용자 확인: 눈보라 구간은 확장 자체가 안 됨).
#     이 과정에서 필드 하단 버튼(재개/상자)의 활성/비활성을 픽셀 단위(밝은픽셀 비율)로 판별하는
#     is_field_button_active()를 신설 - 도장 매칭(TM_CCOEFF_NORMED)은 밝기를 정규화해버려 활성/
#     비활성 구분이 원천적으로 불가능함을 실측으로 확인(활성 0.98~0.99 vs 비활성 0.94~0.99, 거의
#     동일). 아이콘 픽셀 기준으로는 완전히 갈림(활성 최대밝기 160+ vs 비활성 80대). ⚠️ 반드시 터치
#     "전" 스크린샷으로 판정할 것 - 터치 후에 재면 항상 활성으로 보인다.
#     (4) [하켄을 대/소 구분 없이 탐색] 필드맵에서 대하켄만 찾던 것을, 대/소 도장을 순서대로 시도하는
#     _find_first_icon() 헬퍼로 교체(같은 게임의 다른 매크로 WVD도 harken→Bharken 순차 폴백 - 같은
#     설계). 새 앵커 FieldMap_Anchor.png("✕ 닫기", 확장 화면 전용)도 필드맵 확장 판정에 추가.
#     실전 검증: 대설지대 6층 1주회 완주(진입→상자파밍→상자없음→귀환→인벤정리→재진입) 확인 완료.
#     (5) [대설지대 6층 신규 조우 + 화살표 사각지대 완치] "울타리에 구멍이 뚫려있다" 조우 -
#     "빠져나간다" 고정 선택 추가(Dun_HS6_doghole.png, 오탐 검증: 양성 1.000 vs 음성 최고 0.458).
#     이 조우 직전 도입 대사처럼 "구체적 선택지 없이 화살표만 있는" 화면은 기존 인터럽트 처리
#     (싸운다/행상인/빠져나간다) 어디에도 안 걸려 커서 미검출만 반복하며 정체했다(실전 로그 17:03,
#     사용자가 수동으로 화살표를 한 번 눌러 넘기자 정상 처리됨). find_and_click_dialogue_advance_arrow()
#     를 두 곳(_handle_dungeon_interrupt/메인 루프 공용 블록) 모두에 최하위 폴백으로 추가 - 반드시
#     구체적 선택지 체크 "뒤"에 둬야 한다(실측 확인: 중립몹 조우 선택지 화면에도 이 화살표가 0.969로
#     같이 찍혀 있어, 순서를 앞에 두면 화살표를 먼저 눌러 엉뚱한 선택지가 골라짐).
#   1.19.2: 대설지대 던전 추가 전 마지막 안정화 릴리즈 - 정체(stuck) 복구 30초 메가블록 내 사망감지
#     분기가 "공식" 사망감지 분기(~1413-1426)와 동일한 get_dead_match_score 체크를 하면서도
#     transition_delay_count 리셋만 빠뜨린 쌍둥이 결함 완치. 같은 유형 버그 재발 방지를 위해
#     CLAUDE.md/AGENTS.md에 "화면 진행 감지 시 정체 카운터 리셋 - 공용 지점과 반드시 대조" 컨벤션 추가.
#     그 외 main.py의 ADB 연결 로그 정리/콘솔창 잔존/스크린샷 캐시 무한증식 완치는 main.py 참고.
#   1.19.1: 유령성4층 착지 스턱을 1회차부터 즉시 전진 스와이프로 단축(재개버튼 신호로 미리 판별하려던
#     시도는 전환 창이 스크린샷 폴링보다 짧고 매칭 방식으로 밝기차를 못 구분해 실전에서 매번 실패함이
#     진단 로그로 확인돼 폐기 - 대신 실전 로그로 "1회차 정체 = 예외 없이 항상 진짜 스턱"임이 반복 확인돼
#     범용 1~2단계 완충 연타를 건너뛰고 1회차부터 전진 스와이프+출구 재탭을 실행하도록 변경, 3층 상자를
#     잘못 열어버릴 위험이 있던 1회차 상자 버튼 연타도 이 던전에선 배제). 재개 오진 방지 재확인 경로의
#     중복 ADB 스크린샷 1회 제거(try_resume_move가 이미 찍은 화면을 재사용) 및 정비/전투/상자 처리 직후
#     FIELD_WAIT 재진입 시 불필요한 4초 쿨타임 파쇄(last_click_time = 0.0 추가) - "재개 오진 방지" 재확인
#     체감 지연이 8초→4초로 단축됨(사용자 실기 확인). 상세는 CLAUDE.md/history.log 참고.
#   1.19.0: 유령성4층 상자파밍 나가기 안정화 2건. (1) '없습니다' 토스트(toastmsg_nochest.png)가 "상자
#     없음"/"경로 없음" 두 메시지에 공용으로 쓰이는데, 직전에 어떤 버튼을 눌렀는지 안 가리고 매 틱 무조건
#     "경로 없음"으로 해석해 불필요한 전진 스와이프가 나가던 결함 완치(사용자 실기 확인: 상자 버튼 눌러서
#     뜬 토스트에도 스와이프 발동) - exit_last_action_was_exit_tap 플래그로 직전 액션이 '나가기'였을 때만
#     반응하도록 게이트. 1차 수정 후 TRIGGER_EXIT 재진입 시 이 플래그를 안 리셋해줘 나가기 버튼을 누르기도
#     전에 스와이프가 먼저 나가는 형태로 재발(실기 로그 2026-08-29 15:35:35 확인) - TRIGGER_EXIT 진입
#     지점 4곳 모두에서 매번 리셋하도록 완치. (2) 재개(1번 Redo) 버튼의 활성/비활성 상태로 "새 필드 착지
#     직후, 아직 이동 명령 없음"을 즉시 판별할 수 있음을 사용자가 실기로 확인 - 이를 이용해 4층→3층 착지
#     스턱 시 기존 정체 사다리(1~5단계, 최소 16~20초)를 기다리지 않고 곧바로 전진 스와이프하는 즉시감지
#     경로를 추가(유령성4층 상자파밍 전용, 절대 워치독 연동). 상세는 CLAUDE.md/history.log 참고.
#   1.18.0: 유령성 4층 상자먹튀파밍 신규 진입/탈출 시퀀스 추가, TRIGGER_EXIT 하켄 메뉴 미처리 완치(공용
#     전처리 블록으로 이동), harken_blessing_donothing/combat_in·slow 이진화 불일치 완치, last_target_coords
#     공유 변수로 인한 오탭 완치, came_from_combat/chest 플래그 소비 지연 완치, 상자 버튼 단일탭화 및
#     "재개(1번)" 버튼 도입(try_resume_move/resume_or_confirm_chest 신설). 상세는 CLAUDE.md/history.log 참고.
#   1.17.1-hotfix9: 일반 정체(30초) 복구용 비상 뒤로가기(KEYCODE_BACK)가 주입 직후 정체 타이머
#     (last_state_changed_time)를 같이 리셋해버려서, 뒤로가기가 실제로 효과가 있었는지와 무관하게 5분(300초)
#     하드 리밋이 영원히 도달하지 못하는 구조적 결함 완치(실전 확인: 2026-08-21 03:38~07:15, 뮤뮤 동결 추정
#     상황에서 3시간 37분간 이 30초 사이클만 무한 반복하며 방치됨). 이제 블라인드 포크는 진짜 정체 타이머를
#     건드리지 않고, 포크 자체의 재시도 간격만 별도 타이머(last_blind_poke_time)로 페이싱한다. main.py의
#     recover_app_startup() 관련 변경(다운로드 유예, 하켄 메뉴 인식)은 main.py 참고.
#   1.17.1-hotfix8: 피장막(딸피 연출) 관통 다중 이진화 패스(check_template_present_multipass, 160/100/85) 도입 -
#     붉은 안개가 씌워지면 흰 글씨 기준 이진화 문턱 160에서 텍스트가 사실상 지워지던 결함(실측: 텍스트 영역
#     최대 밝기 165) 완치. 상자 대화창의 "아무것도 안 한다"를 하켄 가호 팝업으로 오판하던 결함 완치("열다"
#     동시 검출 시 제외). 파티창 주황빛 빈사색 픽셀을 직접 세어(count_danger_hp_pixels) 안개의 원인(빈사
#     상태)을 감지, need_heal 자동 격발. main.py 아웃게임 스캐너에서도 하켄 메뉴 인식이 되도록 함수 재사용
#     지원(check_and_handle_harken_menu에 t_yeolda 인자 추가). 유령성 하켄 가호 이름 우선순위(데몬족 헌터>
#     오드의 가호) 도입 - 색상 등급이 실제 유용도와 안 맞는 사례(녹색 오드가 파란 민첩보다 낮게 판정)를
#     실전 스샷으로 확인 후 이름 도장 우선 인식 + 색상 등급 폴백으로 개선.
#   1.17.1-hotfix7: main.py의 재시작 카운터 미기록 결함 완치(상세는 main.py 참고)에 더해, trigger_harken_escape()에
#     계단(TRIGGER_EXIT) 탈출이 이미 쓰던 검증된 패턴 이식 - 미니맵 크롭(Y:115~315, X:1117~1317) diff로 정체 판정,
#     3회 누적 시 백스텝 스와이프 후 재탭 물리 복구, 최초 정체 후 60초 넘도록 안 풀리면 RuntimeError로 실패 전파
#     (예전엔 재시도/폴백 다 실패해도 무조건 성공 처리해 실패를 호출부에 전혀 못 알렸음). 전투 조우 시엔 정체
#     오판 없이 카운트만 리셋. TRIGGER_EXIT 자체의 절대 워치독도 5분 고정에서 farming_method별(광석파밍 90초/
#     그 외 180초)로 단축.
#   1.17.1-hotfix6: main.py의 뮤뮤 완전 동결 시 자가복구 결함 및 동결감지 구조적 오탐 완치(상세는 main.py 참고)에 더해,
#     이 파일에서는 하켄 앵커 로직을 개편. check_and_resolve_harken_blessing()을 check_and_handle_harken_menu()로
#     대체 - "아무것도 안 한다"(귀환목록/가호팝업 공통 앵커)를 1차 확인 후 "귀환" 유무로 "returned"(귀환 클릭까지
#     완료)/"blessing"(가호 선택까지 완료)/"not_present" 3가지로 분기하는 단일 구조로 재구성, trigger_harken_escape()의
#     재시도 루프도 이 반환값 기준으로 단순화. 이중 판정 구조를 없애 향후 "귀환" 외 다른 텍스트 매칭(예: 특정 구역
#     이동)으로 분기를 늘리기도 쉬워짐. (실전에서 가호 팝업 색상 인식/선택 정상 동작 확인됨: 2026-08-11 첫 실전 등장.)
#   1.17.1-hotfix5: 실전에서 하켄의 가호 오탐지 발견 및 완치. 하켄 구역 이동 목록 화면에도 "아무것도 안 한다"가
#     동일하게 있어 가호 팝업으로 오인식 → 잘못된 좌표(구역 텔레포트 항목)를 터치하는 결함이 실제 로그로 확인됨.
#     "귀환" 텍스트가 함께 있으면 구역 이동 목록으로 판단해 무시하도록 check_and_resolve_harken_blessing()에
#     t_harken_return 파라미터 추가(오탐지됐던 실제 스샷으로 검증 완료). 증거 스샷은 원래대로 터치 전에 저장.
#     추가로, 실전 로그 전체 대조 결과 자정 직후 첫 하켄귀환 시도에서만 재시도가 실패한 걸 발견 - 진짜 가호
#     팝업이 그 타이밍에 떴는데, trigger_harken_escape()의 재시도 루프가 "귀환" 미검출 시 미니맵을 맹목적으로
#     재탭하다가 팝업을 건드려버린 것으로 추정. 재시도 루프 안에서도 매 회차 가호 팝업 여부를 먼저 확인해
#     맹목적 재탭 전에 감지·처리하도록 개선.
#   1.17.1-hotfix4: 하켄의 가호(연 1회, 자정 이후 하켄 귀환 시 3지선다 팝업) 대응 신설: "아무것도 안 한다" 도장
#     (templates/Field/harken_blessing_donothing.png)으로 팝업 감지 → 감지 시 증거 스크린샷(파일명에 harken 포함,
#     기기 /sdcard/Screenshots/) 저장 후, 3개 선택지의 텍스트 색상 등급(흰<녹<파<보라<빨강, 실측 확인은 흰/녹뿐이라
#     파/보라/빨강은 추정 범위)을 비교해 최고 등급을 자동 선택. 특정 던전 우선순위(유령성→데몬 특화 등) 도장 매칭은
#     아직 해당 도장이 없어 추후 연동 예정(resolve_and_click_harken_blessing의 priority_template 인자로 이미 자리는 마련).
#     실전에서 이 팝업이 뜬 적이 아직 없어(연 1회 이벤트) 실기 검증은 못한 상태 - 다음 등장 시 확인 필요.
#   1.17.1-hotfix3: (동기화, 이 파일 자체는 변경 없음 - 이번 핫픽스는 remote_control/server.py의 백그라운드 실행 기능에만 연동됨)
#   1.17.1-hotfix2: (동기화, 이 파일 자체는 변경 없음 - 이번 핫픽스는 remote_control/server.py의 대시보드 기능에만 연동됨)
#   1.17.1-hotfix1: (동기화, 이 파일 자체는 변경 없음 - 이번 핫픽스는 main.py의 팝업 인식/재시작 로직에만 연동됨)
#   1.17.1: (동기화, 이 파일 자체는 변경 없음 - 원격 시작/정지 기능은 main.py/remote_control/에만 연동됨)
#   1.17.0-hotfix2: trigger_harken_escape 재시도 3회(11.25초)→10회(37.5초)로 상향 및 폴백 좌표 탭 이후 재검증(잔류 시 정밀 재클릭) 추가 - wvd 원본 대비 축소됐던 재시도 예산(MAX_TRY_LIMIT 25) 오이식 결함 완치
#   1.17.0-hotfix1: start_main_macro 반환값에 need_pickaxe_refill 플래그 추가(곡괭이 소진 vs 정상 채굴종료 구분), 사령탑이 이 플래그만으로 광석파밍 회군을 판단하도록 지원
#   1.17.0: FFXI 콜라보 북쪽의 유령선 2층 광석파밍(마이닝) 주회 상태 머신 및 presets.json 동적 가변 프리셋 로딩 엔진 구축에 따른 버전 동기화
#   1.16.0: 상자 대화창 우하단 화살표(dialogue_indicator.png) 감지 터치 개편, 공포 상태이상 캐릭 선택 시 "열 수 없다" 대화 팝업 복구 루프 추가, templates/chestopening/ 하위로 상자 관련 템플릿 폴더 정돈에 따른 버전 동기화
#   1.15.0: 지정 슬롯 따개 터치 개편, 상자공포 자동 감지 및 주인공/타 슬롯 우회 회피 시퀀스 추가, whowillopenit 템플릿 의존성 제거 및 '열다' 버튼 소멸 기반 진입 판정 최적화에 따른 버전 동기화
#   1.14.1-hotfix10: 전투 중 배속/자동 8초 가드 단일 블록 통합(상하단 동일 타이머 충돌로 인한 자동전투 8초 감지 영구 스킵 결함 완치), 정비 즉시 재사격 및 상자 없음 인지 시 터치 쿨타임(last_click_time = 0) 파쇄(정비 직후 7초 지연 및 출구 탭 3초 지연 제거)에 따른 버전 동기화
#   1.14.1-hotfix9: 상자깡 완료 연출 마진 sleep(1.0초) 탈거, 전투 중 배속/자동 켜기 가드 8초 쿨타임 주기 검사 도입, 화면 과도기 대기 한계 상향(5회 ➔ 10회)에 따른 버전 동기화
#   1.14.1-hotfix8: 전투 중 딸피 피장막 상황 앵커 소실 버그 해결(배속 앵커 판정을 그레이스케일로 전향하여 피장막 노이즈 우회), 백아 던전 층수 분기 제어(DUNGEON_FLOOR 추가 및 지하 2층 버튼 존재 유무에 따른 고정 좌표 분기 터치 적용)에 따른 버전 동기화
#   1.14.1-hotfix7: 고비용 독 감지 모니터링(HSV 변환 및 6개 슬롯 픽셀 감지) 함수 및 분기 완전 삭제 (CPU 사용량 대폭 경감 및 프레임 렉 근절 최적화)
#   1.14.1-hotfix6: 전투/상자 종료 후 필드 복귀 시 힐링 조건 플래그(came_from_combat/came_from_chest) 누수 버그 패치 및 이진화 매칭/메모리 캐싱 동기화
#   1.14.1-hotfix5: 여관 루프 정체 방지 45초 Watchdog 가드 탑재 및 1:1 이진화 매치 적용에 따른 버전 동기화
#   1.14.1-hotfix4: OpenCV 픽셀 번짐 방지를 위해 동적 리사이저 배제 및 원본 1:1 그레이스케일 매칭 롤백, dungeon_bot 내 load_grayscale_template 정의 유실 NameError 수정 완료
#   1.14.1-hotfix3: 템플릿 크기 및 ROI 정밀 분석 대조를 통한 여백 마진 보강, 그레이스케일 매칭 및 동적 템플릿 축소 스케일러 적용
#   1.14.0-hotfix4: 최초 탈출 정체 시점 타이머 보존 및 5분 절대 Watchdog 가드 구축
#   1.14.0-hotfix3: 바탕화면 튕김/가로 화면 30초 정체 시 예외 격발 및 에뮬레이터 자동 2단계 리부팅 복구 가드 탑재 (동기화)
#   1.14.0-hotfix2: 탈출 5분 리셋 누적 버그/출구 클릭 건너뜀 수정 및 정체 1~2회 시점 예비 연타 기능 이식
#   1.14.0-hotfix1: README 안내 보강에 따른 핫픽스 빌드 반영
#   1.14.0: 빈사/딸피 화면 렉 60초 정체 시 이미지 임계값 0.45 하향 완화 및 힐링 시퀀스 강제 격발 복원 로직 추가 (정식 기능 이식)
#   1.13.20-hotfix1: 탈출 정지 감지 5회 상향 및 백스텝 후 출구 이동 단추 0.1초 간격 2회 탭핑 복구 시퀀스 도입
#   1.13.20: 자동전투 켜기 씹힘 방지(auto_combat_paused_for_skill 가드 우회) 보완
#   1.13.19-hotfix2: 최상단 전투 가드 변수 리셋, 렉 보호 가드 주입, 탈출 앵커 임계치 상향 및 안전지대(700, 150) 터치 조율
#   1.13.19-hotfix1: 던전 최초 탈출 시 출구 이동 버튼 0.2초 간격 2회 터치(더블 탭) 보완
#   1.13.19: 사망/부활(InCombat_dead, btn_resurrect) 흐름 및 기동 복구(recover_app_startup) 연동 고도화
#   1.13.18: 통합 힐링 플래그 need_heal 도입, 상자 완료 필드 앵커 2차 검증 가드 주입, 임의 빈사 힐링 제거 및 임계치 완화
#   1.13.17: 버전 동기화
#   1.13.16: 버전 동기화
#   1.13.7: 버전 동기화
#   1.13.6: 에뮬레이터 콜드 리부트(Emulator Reboot) 기능 및 디스크 파일 연동 연속 오류 방지 가드 도입
#   1.13.5: 일반 필드 상태 정체 시간 리셋 버그 수정 및 5분 필드 정체 시 앱 리셋 재시작 가드 장착
#   1.13.4: 버전 동기화
#   1.13.3: 5분 타임아웃 세이프티 가드 도입 및 백스텝-전진/2번단추 사격 무한 교대식 복구 시퀀스 개편
#   1.13.2: 범용 탈출 물리 백스텝-전진 복구 도입, 최후의 5회차 앱 리셋 가드 탑재, 최초 탈출 시간 누적 보존 패치
#   1.13.1: 버전 동기화
#   1.13.0-hotfix4: 핫픽스 적용 - 글로벌 힐 주기에 따른 치료 정비 처리 및 상자 조우 시 치료 유예 가드 장착
#   1.13.0-hotfix3: 핫픽스 버전 동기화
#   1.12.6: 여관 정비 시 멀티 레벨업 '다음' 팝업 처리 구현 및 실시간 타임스탬프 로깅 래퍼 함수 도입
#   1.12.5: 탈출 정체 복구 카운트 리셋 오류 패치, 블랙박스 및 탈출 정지 최초 정체 시각 표기 추가 및 버전업
#   1.12.4: 힐러방 딸피 암전 시 블라인드 고정좌표 힐 시퀀스 핫픽스 적용 및 버전 동기화
#   1.12.3: 상자 자동 이동 완료 후 '열다' 씹힘 정체 버그 수정
#   1.12.2: 4대 예외 패치 반영에 따른 버전 동기화
#   1.12.1: 마이너 버전업 - 템플릿 디렉토리 구조 다각화(Worldmap, WolfCave, Vill_Isbelg, inn_sleep) 분리 및 동적 파일명 최적화
#   v18.00: 3시간 전 안정 버전 기반 롤백 (Base)
#   v18.01: 메인 좌표 스팟 대응 동기화
#   v18.02: ADB 통신 오류 시 main.py로 예외 throw 처리 (자가 복구 위임)
#   v18.03: trap_minigame_anchor.png/해제 좌표 보정 및 탈출 행군 중 기습 전투 가드 추가
#   v18.04: 6인 독 감지 필터 정밀화 (슬롯별 독 아이콘 영역 국소 스캔)
#   v18.05: 독 감지 필터를 슬롯 전체 보라색 플래시 비율(15% 이상) 스캔 방식으로 전환 (오탐 차단)
#   v18.06: 우측 하단 4번째 단추(상자/출구) 전용 Y축 크롭 매칭(Y: 530~630) 적용하여 2번 단추 오검출 원천 차단
#   v18.07: 힐러 및 따개 멀티 템플릿(healer_*.png, disarmer_*.png) 동적 검출 및 스왑 대응 (동기화)
#   v18.08: 상자단추(Button 4, Y: 530~630)와 출구단추(Button 2, Y: 410~520) 매칭 영역 분화 적용
#   v18.09: 힐러/따개 템플릿 로딩 시 sorted() 정렬 및 우선순위 정책 적용 (동기화)
#   v18.10: 힐러 시스템 예약 파일(healer_auto_btn.png) 제외 필터링 적용 대응 (동기화)
#   18.11.0: 던전 탈출 정체 시 3번 체크포인트 회군 및 재탈출 복구 시스템 탑재 및 SemVer 도입
#   18.11.1: '열다' 터치 씹힘 재시도 및 갇힘 시 '아무것도 안 한다' 터치 탈출 대응 (동기화)
#   18.11.2: 캐릭터 선택창('누가 열 거야?') 정체 복구 가드 탑재 (동기화)
#   18.11.3: 여관 정비 시퀀스 중 ADB 통신 장애 크래시 자가 복구 가드 추가 (동기화)
#   18.11.4: 미니게임 화면 중 재시작 시 30초 정체 대기 없이 즉각 전이 복구 가드 추가 (동기화)
#   18.11.5: 탈출 완료 판정 시 '열다' 및 미니게임 감지 추가로 오판 방지 가드 탑재 (동기화)
#   18.11.6: 여권 만료 팝업 이중 앵커 가드에 맞춰 버전 동기화
#   1.11.7: 로딩 암전 가드, 해상도 크래시 가드, 예외 트레이스백 실시간 로깅 및 Dimension Guard 탑재 (동기화)
#   1.11.8: 4일 경과 로그 파일 자동 청소기 장착, 메인 루프 전체 이중 감시 예외 처리 보강 및 리드미 설명 개정 (동기화)
#   1.11.9: 최초 기동/재시작 자동 스샷 촬영, 스샷 동기화 스레드, 다중 사용자 경로 탐색 가드 탑재 (동기화)
#   1.11.12: 미니맵 absdiff 기반 정체 판정 30->9초 단축, 상자/출구 1회 탭 반응형 변경 및 힐러 안전지대/즉시 재출발 연계 추가
#   1.11.16: 미니게임 앵커 국소 크롭 스캔 범위(X: 57~187, Y: 227~317 마진 적용) 지정 및 임계값 0.70 상향 (동기화)
#   1.11.16-hotfix1: CLEAR_CHECK 진입 시 정체 오판 방지(상태 전환 시 타이머 리셋) 및 아이템 획득(get_item.png) 감지 임계값 완화(0.70 -> 0.65)
# ==============================================================================

# ==============================================================================
# 🕒 [Daphne 던전봇 실시간 타임스탬프 미러링 필터 가드 전격 장착]
# ==============================================================================
def timestamped_print(*args, **kwargs):
    current_time = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    sys.stdout.terminal.write(f"{current_time} ")
    msg = " ".join(map(str, args)) + kwargs.get('end', '\n')
    sys.stdout.terminal.write(msg)
    if sys.stdout.log:
        sys.stdout.log.write(f"{current_time} {msg}")
        sys.stdout.log.flush()

print = timestamped_print 
# ==============================================================================

# ==============================================================================
# ⚙️ [Daphne 마스터 인게임 제어 세팅 변수 구역]
# ==============================================================================
LIMIT_COMBAT_EVENTS = 2      
# ==============================================================================

# 🌐 [Daphne 특허: ADB 통신 거부 WinError 10061 원천 차단 심폐소생 장치 - 예외 전파 사양]
def safe_device_shell(device, command):
    try:
        return device.shell(command)
    except Exception as e:
        print(f"\n🌐⚠️ [dungeon_bot 소켓 단절] 윈도우 ADB 통신 장애 감지: {e}")
        raise e

def load_template(file_path):
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
        return thresh
    except: return None

def load_grayscale_template(file_path):
    if not os.path.exists(file_path): return None
    try:
        return cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    except: return None

def load_dead_template(file_path):
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 65, 255, cv2.THRESH_BINARY)
        return thresh
    except: return None

def get_dead_match_score(img_np, thresh_temp):
    if thresh_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return 0.0
    try:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 65, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val
    except: return 0.0

def click_dead_template(device, img_np, thresh_temp, threshold_val=0.65):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    try:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 65, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            h, w = thresh_temp.shape[:2]
            safe_device_shell(device, f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
        return False
    except: return False

def check_template_present_dynamic(img_np, thresh_temp, threshold_val=0.68, min_brightness_thresh=160):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, min_brightness_thresh, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_template_present(img_np, thresh_temp, threshold_val=0.68):
    return check_template_present_dynamic(img_np, thresh_temp, threshold_val, 160)

# 🩸 [2026-08-16 피장막(딸피 연출) 관통 다중 이진화 패스]
# 주인공이 빈사가 되면 화면 전체에 붉은 피안개 연출이 씌워지는데, 이때 흰 글씨(예: "열다")의
# 그레이스케일 밝기가 통째로 내려앉는다(실측: 안개 화면의 UI 텍스트 영역 최대 밝기 165, 기존
# 이진화 문턱 160에서 살아남는 픽셀이 0.01%뿐 - 사실상 글씨가 지워진 채로 매칭하고 있었음).
#
# 과거 v1.13.x에 "밝기<85면 이진화 문턱을 65로" 방식이 있었으나 v1.14.1-hotfix10에서 제거됨.
# 이번 실측으로 그 방식이 실패했던 이유 2가지를 확인:
#   (1) 이 게임은 정상 화면도 평균밝기 40~70이라 "밝기<85 = 안개" 판정이 상시 참이 됨
#       (당시 함께 있던 "어두우면 필드로 간주(or is_low_hp_dark_mode)" 우회들이 항상 발동 -> 엉뚱한 앵커 오인식).
#   (2) 문턱 65는 값 자체가 부적합 - 어떤 안개 농도에서도 매칭 점수가 0.54를 넘지 못함.
#
# 그래서 안개를 "감지"해서 문턱을 바꾸는 대신, 여러 문턱으로 각각 시도해 하나라도 판정선을
# 넘으면 인정하는 방식으로 간다. 판정 신뢰도(threshold_val)는 그대로 유지하므로 ROI 기반
# 오인식 방지 장치들도 영향받지 않는다.
# 실측 근거(진짜 상자 화면에 농도별 피장막을 합성해 측정한 점수):
#   안개없음 -> bin160:0.967 / 옅음 -> bin160:0.722 / 중간 -> bin100:0.718
#   진함 -> bin100:0.806 / 매우진함 -> bin85:0.815   (전 구간에서 최소 한 패스가 판정선 통과)
# 오탐 검증: 상자가 없는 실제 스샷 89장에 3패스를 전부 적용해도 최고점 0.541 (판정선 0.65 미달, 오탐 0건).
FOG_BIN_PASSES = (160, 100, 85)

def check_template_present_multipass(img_np, thresh_temp, threshold_val=0.68, bin_passes=FOG_BIN_PASSES):
    """피장막 유무와 무관하게 인식되도록 여러 이진화 문턱으로 순차 시도한다(하나라도 통과하면 True)."""
    if thresh_temp is None or img_np is None: return False
    for bin_th in bin_passes:
        if check_template_present_dynamic(img_np, thresh_temp, threshold_val, bin_th):
            return True
    return False

# 🩸 [빈사(딸피) 감지용 파티창 주황픽셀 기준]
# 빈사 캐릭터는 파티창의 이름/HP가 주황빛으로 바뀐다. 안개까지 낀 상태에서 실측한 색이 RGB 약 (140,53,16)로
# 상당히 어두워서, 과거 detect_orange_danger_hp()가 쓰던 HSV 범위(명도 210 이상)로는 0픽셀로 잡혔음(무용지물).
# 실측 분포: 빈사/안개 화면 6109·12092픽셀 vs 정상 화면 최대 2114픽셀 -> 그 사이를 넉넉히 잡아 4000으로 설정.
# (빈사 샘플이 아직 2건뿐이라, 발동 시 실제 픽셀수를 로그로 남겨 추후 조정할 수 있게 한다.)
DANGER_HP_PIXEL_LIMIT = 4000

def count_danger_hp_pixels(img_np):
    """파티창 구역에서 빈사 표시(주황빛 이름/HP) 픽셀 수를 센다."""
    if img_np is None: return 0
    try:
        h, w = img_np.shape[:2]
        if h < 2560 or w < 1440: return 0
        zone = img_np[1900:2560, :, :3].astype(np.int16)
        R, G, B = zone[:, :, 0], zone[:, :, 1], zone[:, :, 2]
        mask = (R > 90) & (R > G * 1.55) & (R > B * 2.0)
        return int(mask.sum())
    except Exception:
        return 0

# 🆕 [2026-09-12 실전 확인] "빈사"(HP 낮음, 힐로 회복)와 "사망"(HP 0, 힐로 절대 안 풀림)은 둘 다
# 파티창 위험색 판정에 걸리는데, 힐로 되돌릴 수 있는 건 빈사뿐이라 사망한 캐릭터는 힐을 아무리 넣어도
# 그대로라 빈사 감지가 무한 재격발된다(실전 로그: 12시간).
# 🚨 [2026-09-12 실측 확정 - 1차] 사용자가 처음 제공한 크롭(templates/Field/stat_dead.png, 세션종료
# 화면에서 딴 것)은 그레이스케일 밝기가 30~147로 낮아, 이 저장소 관례인 이진화(160) 매칭을 쓰면
# "어떤 화면의 어떤 어두운 영역과도 무조건 1.000으로 매칭"되는 상태였다(저장소 스크린샷 309장 전수
# 대조로 확인) - 이진화를 포기하고 원본 그레이스케일 매칭으로 전환.
# 🚨 [2026-09-12 실측 확정 - 2차, 결정적 원인] 그레이스케일로 바꾼 뒤에도 실제 사망 화면 원본
# (`dev/ROI_check/사망.png`, 크롭 도구의 `_crop_metadata.json`으로 찾음)으로 재검증하니 정탐/오탐이
# 아예 역전됐다 - **원인은 슬롯 좌표였다.** `chest_opener.SLOT_ROIS`는 "상자 열 캐릭터를 고르는
# 모달 팝업" 화면 전용 좌표인데, 이걸 그대로 재사용했더니 필드 하단에 항상 떠 있는 파티 HUD와는
# 위치가 안 맞아(모달 팝업이 HUD보다 위쪽에 뜬다) 카드 하나를 반토막으로 자르고 옆 카드 내용까지
# 섞어서 읽고 있었다. 사용자가 정상 조명에서 새로 크롭해준 3종(dead_inField/dead_inCombat/
# dead_chest.png) 중 dead_inField.png와 아래 FIELD_PARTY_SLOT_ROIS(실측으로 새로 잡은 필드 HUD
# 전용 좌표)를 맞춰 재검증하니 정탐 0.999~1.000 vs 오탐 최고 0.585(필드 앵커 통과 스크린샷 38장
# 전수 대조 기준)로 깨끗하게 분리됨을 확인 - "빈사(HP낮음, 생존)" 샘플(`딸피_필드.png`)도 전
# 슬롯 0.48~0.52로 안전하게 걸러짐(빈사와 사망을 확실히 구분). 임계값 0.85로 확정.
FIELD_PARTY_SLOT_ROIS = {
    1: (0, 1900, 480, 2230), 2: (480, 1900, 960, 2230), 3: (960, 1900, 1440, 2230),
    4: (0, 2230, 480, 2560), 5: (480, 2230, 960, 2560), 6: (960, 2230, 1440, 2560),
}

def find_dead_slots(img_np, template, threshold=0.85):
    """죽은(해골 아이콘) 캐릭터가 있는 슬롯 번호 목록을 반환한다. 없으면 빈 리스트.

    ⚠️ chest_opener.SLOT_ROIS(상자 캐릭터 선택 모달 전용 좌표)와 절대 혼동하지 말 것 - 여기는
    필드 하단 상시 파티 HUD 전용 좌표(FIELD_PARTY_SLOT_ROIS)를 쓴다. 위 주석의 실측 정정 참고."""
    if img_np is None or template is None:
        return []
    dead_slots = []
    for slot, (x1, y1, x2, y2) in FIELD_PARTY_SLOT_ROIS.items():
        if img_np.shape[0] < y2 or img_np.shape[1] < x2:
            continue
        crop = img_np[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
            continue
        _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))
        if max_val > threshold:
            dead_slots.append(slot)
    return dead_slots

def check_dialogue_indicator_present(img_np, template, threshold=0.75):
    if img_np is None or template is None:
        return False
    h, w = img_np.shape[:2]
    if h < 2433 or w < 1377:
        return False
    roi = img_np[2349:2433, 1293:1377]
    return check_template_present(roi, template, threshold)

# 🆕 [2026-09-07 대설지대] main.py의 "대화창 저격"(1850-1882행, templates/inn_sleep/arrow_clean.png)을
# dungeon_bot.py에도 이식하되 크롭 영역을 넓힌다 - main.py 원본은 화면 극하단([2200:2560,1100:1440])만
# 보는데, 인벤정리 완료 토스트("소지품을 정리했습니다")처럼 화면 중간(y≈1587)에 뜨는 대화창은 그 영역
# 밖이라 못 잡는다(실측 확인: 좁은 크롭 0점, 화면 하단 절반 검색 시 0.927). 그 대신 임계값은 그대로
# 0.82 유지(main.py 주석: "지형 오탐 억제 목적으로 0.70→0.82 상향") - 크롭을 넓힌 만큼 지형 오탐 여지가
# 늘 수 있으니 임계값을 낮추지 않는다.
DIALOGUE_ADVANCE_ARROW_ZONE = (1300, 2560, 0, 1440)  # (y1, y2, x1, x2)

def check_dialogue_advance_arrow_present(img_np, template, threshold=0.82):
    if img_np is None or template is None:
        return False
    y1, y2, x1, x2 = DIALOGUE_ADVANCE_ARROW_ZONE
    h, w = img_np.shape[:2]
    if h < y2 or w < x2:
        return False
    zone = img_np[y1:y2, x1:x2]
    gray_zone = cv2.cvtColor(zone, cv2.COLOR_RGB2GRAY)
    _, thresh_zone = cv2.threshold(gray_zone, 160, 255, cv2.THRESH_BINARY)
    if thresh_zone.shape[0] < template.shape[0] or thresh_zone.shape[1] < template.shape[1]:
        return False
    result = cv2.matchTemplate(thresh_zone, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold

def find_and_click_dialogue_advance_arrow(device, img_np, template, threshold=0.82):
    """공용 대화 진행(황금 화살표) 탭 - 인벤정리/행상인/캠핑/중립몹 대화 진행에 공용으로 재사용."""
    if img_np is None or template is None:
        return False
    y1, y2, x1, x2 = DIALOGUE_ADVANCE_ARROW_ZONE
    h, w = img_np.shape[:2]
    if h < y2 or w < x2:
        return False
    zone = img_np[y1:y2, x1:x2]
    gray_zone = cv2.cvtColor(zone, cv2.COLOR_RGB2GRAY)
    _, thresh_zone = cv2.threshold(gray_zone, 160, 255, cv2.THRESH_BINARY)
    if thresh_zone.shape[0] < template.shape[0] or thresh_zone.shape[1] < template.shape[1]:
        return False
    result = cv2.matchTemplate(thresh_zone, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold:
        th, tw = template.shape[:2]
        real_x = x1 + max_loc[0] + int(tw / 2)
        real_y = y1 + max_loc[1] + int(th / 2)
        safe_device_shell(device, f"input tap {real_x} {real_y}")
        return True
    return False

# 🆕 [2026-09-07 대설지대] 압축 미니맵의 커서(플레이어 진행방향 화살표)로 이동/정체를 판정한다 - 대설지대는
# 배경(눈보라 파티클 등)이 계속 흔들려서 기존 미니맵 픽셀 diff 비교(Y:115-315,X:1117-1317, 평균차 0.05
# 기준)가 오작동한다. 실측(4방향 도장을 실제 압축 미니맵 스크린샷에 검색): 실제 방향(up)은 0.935, 나머지
# 3방향은 화면 곳곳의 우연한 오탐으로 0.84~0.85까지 나옴 - 임계값을 0.90으로 잡아야 오탐을 피한다.
# (y1, y2, x1, x2) - cursor_up 실측 위치(좌상단 1206,204 / 크기 33x26) 기준으로 커서가 미니맵 안에서
# 다소 흔들려도 담기도록 여유를 준 크롭. 전체화면 오탐 최고치가 0.85였으므로 이 정도 확장은 안전하다.
MINIMAP_CURSOR_ZONE = (150, 300, 1140, 1310)

def get_minimap_cursor_direction(img_np, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right, threshold=0.90):
    """압축 미니맵 커서가 4방향 중 어느 쪽으로 잡히는지 반환("up"/"down"/"left"/"right"), 전부 미검출이면 None."""
    if img_np is None:
        return None
    y1, y2, x1, x2 = MINIMAP_CURSOR_ZONE
    h, w = img_np.shape[:2]
    if h < y2 or w < x2:
        return None
    zone = img_np[y1:y2, x1:x2]
    gray_zone = cv2.cvtColor(zone, cv2.COLOR_RGB2GRAY)
    best_dir, best_score = None, threshold
    for direction, temp in (("up", t_cursor_up), ("down", t_cursor_down), ("left", t_cursor_left), ("right", t_cursor_right)):
        if temp is None:
            continue
        if zone.shape[0] < temp.shape[0] or zone.shape[1] < temp.shape[1]:
            continue
        result = cv2.matchTemplate(gray_zone, temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_dir, best_score = direction, max_val
    return best_dir

# 🆕 [2026-09-07 대설지대] "쉰다"→"쉰다" 2연속 탭 + 휴식 대화 진행 - 6층 귀환뿐 아니라 앞으로 캠핑을 쓸
# 때마다(주회 나가기 전이든 던전 진입 직후든) 항상 고정되는 시퀀스라 독립 헬퍼로 분리(사용자 확정).
CAMP_REST_MAX_TAPS = 4  # "쉰다"는 정상적으로 2회지만, 씹힘 재시도 여유를 두고 폭주는 막는다.

# 🚨 [2026-09-08] 캠핑을 어디서 처리했든("귀환 루틴 안" / "공용 전처리 블록") 한 곳에서 집계하기 위한
# 플래그. 루틴 안에서 캠핑을 마친 직후 전투가 나면 루틴이 "combat"으로 빠져나가는데, 그때 메인 루프가
# 캠핑 완료 사실을 모르면 다음 TRIGGER_EXIT에서 캠프 아이콘을 다시 찾아가 무한 캠핑에 빠진다.
# start_main_macro()가 던전 진입마다 reset_camping_done()으로 초기화한다.
_camping_done_since_reset = False

def reset_camping_done():
    global _camping_done_since_reset
    _camping_done_since_reset = False

def _mark_camping_done():
    global _camping_done_since_reset
    _camping_done_since_reset = True

def is_camping_done():
    return _camping_done_since_reset

def perform_camping_rest(device, t_camp_rest1, t_camp_rest2, t_dialogue_arrow, t_field, max_wait=60.0, t_camp_dry=None):
    """
    캠핑 지점에 도착한 뒤 호출 - "쉰다"를 두 번 누르고 휴식 대화를 넘겨 필드로 복귀할 때까지 몰아간다.

    ⚠️ [2026-09-07 실측] Dun_camping_rest.png와 Dun_camping_rest2.png는 둘 다 "쉰다" 글자라 서로 교차
    매칭된다(rest2 도장이 1차 화면의 "쉰다"에 0.896, rest1 도장이 2차 화면에 0.895). 그래서 "지금이 1차
    화면인지 2차 화면인지"를 도장으로 구분하려 들면 반드시 오판한다 - 두 화면 모두 필요한 동작이 "쉰다
    탭"으로 동일하므로 구분할 실익도 없다. 화면 구분을 아예 포기하고 "쉰다가 보이면 누른다 → 대화
    화살표가 보이면 넘긴다 → 필드 앵커가 돌아오면 종료"라는 수렴 루프로 처리한다.
    종료 판정에 필드 앵커를 쓰는 근거(실측): 캠핑 3개 화면 모두 필드앵커 0.09~0.21로 미검출, 정상 필드는
    0.992로 검출되어 경계가 뚜렷하다.
    """
    start_time = time.time()
    rest_taps = 0
    while time.time() - start_time < max_wait:
        raw = capture_screen_bytes(device)
        if not raw:
            time.sleep(0.5)
            continue
        img_np = decode_screen_bytes(raw)

        # 0) 🆕 [2026-09-09 사용자 확인] "생명의 우물이 말라버렸다." = 이 필드에서 이미 캠핑을 했다는 뜻.
        # 캠핑은 필드 진입당 1회뿐이라 더 시도해도 소용없다 - 대화를 넘기고 "캠핑 완료"로 친 뒤,
        # 호출부가 곧바로 나가기(하켄/나가기버튼) 절차로 넘어가게 한다.
        if t_camp_dry is not None and check_template_present(img_np, t_camp_dry, 0.70):
            print("🏕️ [캠핑] '생명의 우물이 말라버렸다' - 이 필드에서는 이미 캠핑을 마쳤습니다. 완료로 처리합니다.")
            find_and_click_dialogue_advance_arrow(device, img_np, t_dialogue_arrow)
            time.sleep(1.2)
            _mark_camping_done()
            return True

        # 1) 종료 판정: "쉰다"를 2회 이상 누른 뒤 필드로 돌아왔으면 완료
        if rest_taps >= 2 and t_field is not None and check_field_anchor_present(img_np, t_field, 0.65):
            print(f"🏕️ [캠핑] 휴식 완료 - 필드 복귀 확인({rest_taps}회 '쉰다' 탭).")
            _mark_camping_done()
            return True

        # 2) "쉰다"가 보이면 누른다(1차/2차 화면 구분 없음 - 위 주석 참고)
        if rest_taps < CAMP_REST_MAX_TAPS:
            coords = find_and_get_coords(img_np, t_camp_rest1, 0.70)
            if coords is None:
                coords = find_and_get_coords(img_np, t_camp_rest2, 0.70)
            if coords:
                rest_taps += 1
                print(f"🏕️ [캠핑] '쉰다' {rest_taps}회차 탭: {coords}")
                safe_device_shell(device, f"input tap {coords[0]} {coords[1]}")
                time.sleep(1.5)
                continue

        # 3) 휴식 대화창은 공용 화살표 헬퍼로 넘긴다
        if find_and_click_dialogue_advance_arrow(device, img_np, t_dialogue_arrow):
            print("🏕️ [캠핑] 휴식 대화 진행(화살표 탭).")
            time.sleep(1.0)
            continue

        time.sleep(0.7)

    print(f"⚠️ [캠핑] 휴식 시퀀스가 제한 시간({max_wait:.0f}초) 내 끝나지 않았습니다('쉰다' {rest_taps}회 탭).")
    return rest_taps >= 2  # 쉰다를 다 눌렀는데 필드 복귀만 못 잡은 경우엔 일단 다음 단계로 진행시킨다.

# 🆕 [2026-09-08 대설지대] 행상인 조우(대사(1,2,5) -> 선택(3,상품보기) -> 대사(5) -> 아이템목록(6,낡은 망치)
# -> 구매완료(7,화살표)) 처리. trigger_harken_escape()/perform_camping_rest()와 같은 자가완결형 블로킹
# 함수 - 이동 중 아무 때나 튀어나올 수 있는 진짜 인터럽트라 공용 전처리 블록에서 진입만 감지하고 나머지는
# 이 함수가 전부 처리한다. 화면 7개가 이어지지만 "화면이 몇 번째인지" 추적하지 않는다(교훈: 비슷한 화면을
# 도장으로 구분하려 들지 말 것) - 우선순위(구매 대상 > 상품 보기 선택 > 대화 화살표)대로 보이는 걸 누르고,
# 필드로 돌아오면 종료하는 수렴 루프로 충분하다. 사용자 확정: 항상 상품 보기 -> 낡은 망치 구매.
def handle_merchant_encounter(device, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow, t_field, max_wait=60.0):
    start_time = time.time()
    while time.time() - start_time < max_wait:
        raw = capture_screen_bytes(device)
        if not raw:
            time.sleep(0.5)
            continue
        img_np = decode_screen_bytes(raw)

        if check_field_anchor_present(img_np, t_field, 0.65):
            print("🛒 [행상인] 필드 복귀 확인 - 조우 종료.")
            return True

        coords = find_and_get_coords(img_np, t_seller_hammer, 0.70)
        if coords:
            print(f"🛒 [행상인] '낡은 망치' 구매 선택: {coords}")
            safe_device_shell(device, f"input tap {coords[0]} {coords[1]}")
            time.sleep(1.2)
            continue

        coords = find_and_get_coords(img_np, t_seller_let_me_see, 0.70)
        if coords:
            print(f"🛒 [행상인] '상품 보기' 선택: {coords}")
            safe_device_shell(device, f"input tap {coords[0]} {coords[1]}")
            time.sleep(1.2)
            continue

        if find_and_click_dialogue_advance_arrow(device, img_np, t_dialogue_arrow):
            print("🛒 [행상인] 대화 진행(화살표 탭).")
            time.sleep(1.0)
            continue

        time.sleep(0.7)

    print(f"⚠️ [행상인] 조우 처리가 제한 시간({max_wait:.0f}초) 내 끝나지 않았습니다.")
    return False

def check_gray_template_present_specific(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None or img_np is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_gray_coords_specific(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None or img_np is None: return None
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = gray_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
def load_color_template(file_path):
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        return np.array(pil_img)
    except: return None

def get_color_match_score(img_np, color_temp):
    if color_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = color_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return 0.0
    
    # 🚨 [컬러 채널 일치성 가드]
    # 소스 이미지(img_np)나 템플릿(color_temp)이 4채널(RGBA)이면 상위 3채널(RGB)만 슬라이싱하여 일치시킵니다.
    img_match = img_np[:, :, :3] if len(img_np.shape) == 3 and img_np.shape[2] == 4 else img_np
    temp_match = color_temp[:, :, :3] if len(color_temp.shape) == 3 and color_temp.shape[2] == 4 else color_temp
    
    result = cv2.matchTemplate(img_match, temp_match, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def check_color_template_present(img_np, color_temp, threshold_val=0.68):
    return get_color_match_score(img_np, color_temp) > threshold_val

def check_combat_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    # 피장막 상태를 우회하기 위해 그레이스케일 매치 구제 적용
    return check_gray_template_present_specific(crop, template, threshold_val)

def find_and_click_combat_template(device, img_np, template, threshold_val=0.65):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    # 피장막 상태를 우회하기 위해 그레이스케일 좌표 탐색 구제 적용
    coords = find_gray_coords_specific(crop, template, threshold_val)
    if coords:
        cx, cy = coords
        real_x = x1 + cx
        real_y = y1 + cy
        print(f"⚡ [전투 배속 단추 클릭] 그레이스케일 검출 좌표 ({real_x}, {real_y})")
        safe_device_shell(device, f"input tap {real_x} {real_y}")
        return True
    return False
def is_combat_speed_orange(img_np):
    if img_np is None: return False
    h, w = img_np.shape[:2]
    try:
        scale_x, scale_y = w / 1440.0, h / 2560.0
        cx, cy = int(70 * scale_x), int(1706 * scale_y)
        cx = max(0, min(cx, w - 1))
        cy = max(0, min(cy, h - 1))
        
        x1, x2 = max(0, cx - 15), min(w, cx + 15)
        y1, y2 = max(0, cy - 15), min(h, cy + 15)
        crop = img_np[y1:y2, x1:x2]
        
        # img_np는 RGB(Pillow 변환) 포맷이므로, crop[:, :, 0]이 Red, crop[:, :, 2]가 Blue임
        avg_r = np.mean(crop[:, :, 0])
        avg_b = np.mean(crop[:, :, 2])
        
        # 주황색 성분 판정 (Red가 Blue보다 60.0 이상 강하게 튀면 주황색으로 확정)
        is_orange = (avg_r - avg_b) > 60.0
        if is_orange:
            print(f"📊 [배속 색상 분석] 주황색(고속) 확정 검출 (Avg R: {avg_r:.1f}, B: {avg_b:.1f}, 차이: {avg_r - avg_b:.1f})")
        return is_orange
    except Exception as e:
        print(f"⚠️ [배속 색상 분석 오류] {e}")
        return False

def is_auto_combat_yellow(img_np):
    if img_np is None: return False
    h, w = img_np.shape[:2]
    try:
        scale_x, scale_y = w / 1440.0, h / 2560.0
        cx, cy = int(1380 * scale_x), int(1720 * scale_y)
        cx = max(0, min(cx, w - 1))
        cy = max(0, min(cy, h - 1))
        
        x1, x2 = max(0, cx - 15), min(w, cx + 15)
        y1, y2 = max(0, cy - 15), min(h, cy + 15)
        crop = img_np[y1:y2, x1:x2]
        
        # img_np는 RGB 포맷
        avg_r = np.mean(crop[:, :, 0])
        avg_b = np.mean(crop[:, :, 2])
        
        # 노란색 성분 판정 (Red와 Blue 편차가 50.0 이상이면 활성화 노란색으로 확정)
        is_yellow = (avg_r - avg_b) > 50.0
        if is_yellow:
            print(f"📊 [자동 색상 분석] 노란색(자동온) 확정 검출 (Avg R: {avg_r:.1f}, B: {avg_b:.1f}, 차이: {avg_r - avg_b:.1f})")
        return is_yellow
    except Exception as e:
        print(f"⚠️ [자동 색상 분석 오류] {e}")
        return False

# 🆕 [2026-09-16 대설지대 눈보라구간] '재개(1번 Redo)' 버튼 활성/비활성 판정 - 미니맵 확장 패널 안의
# 아이콘으로, 모양은 활성/비활성 둘 다 동일하고 밝기(색)만 다르다(기존 ROADMAP 5/11번 항목에서 이미
# 확인된 패턴과 동일 - matchTemplate 점수로는 구분 불가). 실측(2026-09-16, 실전 정체 스샷 vs 사용자가
# 나가기로 활성화시킨 직후 스샷 직접 대조): 아이콘 중앙 "장화" 솔리드 색상 영역 좌표(1217,468) 8px
# 반경 평균 밝기가 비활성 92 vs 활성 162로 70pt 차이 나며 완전히 분리됨. 이 판정을 재개 탭 "전"에
# 먼저 해서, 비활성이면 굳이 탭하고 30초 기다릴 것 없이 바로 나가기로 직행할 수 있다.
def is_resume_button_active(img_np):
    # 🚨 [2026-09-16 절대밝기 방식 폐기 - 실전 오탐 확인] 고정 절대 밝기 기준(125.0)으로 판정했더니,
    # 안개/조명이 짙은 실전 스크린샷(logs/2026-09-16-2200-44_reboot1.png)에서 비활성인데도 평균 밝기
    # 154.9로 "활성" 오판정이 실제로 발생함(전투가 아닌데도 재개만 계속 무의미하게 눌림). 실측해보니
    # 화면 전체 밝기(안개 농도 등)에 따라 활성/비활성 절대 밝기 자체가 프레임마다 흔들려서 고정 문턱
    # 하나로는 못 잡는다(사용자 지적).
    # 같은 미니맵 패널 안에 있는 "나가기"류 버튼(우상단, 항상 활성 상태로 보임 - 좌표 1354,467~1362,474)
    # 을 "이번 프레임의 활성 밝기 기준점"으로 같이 재고, 재개 버튼(1211,466~1219,471)과 상대 비교하는
    # 방식으로 교체 - 안개 농도가 바뀌어도 같은 프레임 안의 두 버튼은 같은 조명 조건을 공유하므로 비율은
    # 안정적이다. 실측(3개 샘플, 나가기 대비 재개 밝기 비율): 비활성 0.527/0.638 vs 활성 0.935로
    # 절대밝기 방식보다 훨씬 크게 분리됨(절대밝기 방식은 154.9로 활성 오판했던 바로 그 스샷도 이 방식
    # 으론 비율 0.638로 정확히 비활성 판정됨).
    if img_np is None: return True  # 판정 불가 시 기존 동작(일단 탭 시도) 유지 - 안전 폴백
    h, w = img_np.shape[:2]
    try:
        scale_x, scale_y = w / 1440.0, h / 2560.0
        def _patch_mean(cx0, cy0, cx1, cy1):
            x1, x2 = int(cx0 * scale_x), int(cx1 * scale_x)
            y1, y2 = int(cy0 * scale_y), int(cy1 * scale_y)
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if x2 <= x1 or y2 <= y1: return None
            return float(np.mean(img_np[y1:y2, x1:x2]))

        exit_ref_brightness = _patch_mean(1354, 467, 1362, 474)
        resume_brightness = _patch_mean(1211, 466, 1219, 471)
        if exit_ref_brightness is None or resume_brightness is None or exit_ref_brightness < 1.0:
            return True
        ratio = resume_brightness / exit_ref_brightness
        is_active = ratio > 0.80
        print(f"📊 [재개 버튼 상대밝기 분석] 재개 {resume_brightness:.1f} / 나가기(기준) {exit_ref_brightness:.1f} = 비율 {ratio:.3f} → {'활성' if is_active else '비활성'} (기준 0.80)")
        return is_active
    except Exception as e:
        print(f"⚠️ [재개 버튼 밝기 분석 오류] {e}")
        return True

def check_auto_btn_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    return check_gray_template_present_specific(crop, template, threshold_val)

def find_and_get_auto_btn_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    coords = find_gray_coords_specific(crop, template, threshold_val)
    if coords:
        cx, cy = coords
        return x1 + cx, y1 + cy
    return None

def check_field_anchor_present(img_np, template, threshold_val=0.65):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1420 * scale_x)
    y1, y2 = int(380 * scale_y), int(530 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_open_minimap_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1130 * scale_x), int(1290 * scale_x)
    y1, y2 = int(510 * scale_y), int(590 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        return x1 + max_loc[0] + int(w_temp / 2), y1 + max_loc[1] + int(h_temp / 2)
    return None

def check_field_btn_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1100 * scale_x), int(1440 * scale_x)
    y1, y2 = int(350 * scale_y), int(750 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_and_get_field_btn_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1100 * scale_x), int(1440 * scale_x)
    y1, y2 = int(350 * scale_y), int(750 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        return x1 + max_loc[0] + int(w_temp / 2), y1 + max_loc[1] + int(h_temp / 2)
    return None

def find_chest_btn_coords(img_np, t_act, t_deact, threshold_val=0.70):
    coords = find_and_get_field_btn_coords(img_np, t_act, threshold_val)
    if coords: return coords
    return find_and_get_field_btn_coords(img_np, t_deact, threshold_val)

def find_checkpoint_btn_coords(img_np, t_act, t_deact, threshold_val=0.70):
    coords = find_and_get_field_btn_coords(img_np, t_act, threshold_val)
    if coords: return coords
    return find_and_get_field_btn_coords(img_np, t_deact, threshold_val)

# 🚨 [2026-08-28 상자파밍 이동 재개 도입] 광석파밍 루트에서 이미 실전 검증된 "재개(1번 Redo)" 버튼 패턴
# (find_checkpoint_btn_coords + t_move_resume_act/deact)을 상자파밍(힐/전투/상자 처리 직후)에도 재사용한다.
# 던전 필드에서 멈춰서 확인하는 시간 자체가 기습 위험이라, 중단된 이동을 처음부터 다시 찾지 않고 "재개"
# 버튼으로 즉시 이어간다. 버튼을 못 찾으면 아무 것도 안 하고 'not_found'만 반환 - 호출부는 다음 정상
# FIELD_WAIT 사이클(상자 버튼)이 자연스럽게 이어받도록 그대로 둔다. 반환값: 'not_found' | 'moved' |
# 'no_chest' | 'none'. 두 번째 반환값은 이 함수가 마지막으로 캡처한 스크린샷(없으면 인자로 받은 img_np) -
# 호출부(resume_or_confirm_chest)가 같은 화면을 재활용해 ADB 스크린샷 왕복을 한 번 아낄 수 있게 한다.
def try_resume_move(device, img_np, t_move_resume_act, t_move_resume_deact, t_no_chest=None):
    resume_coords = find_checkpoint_btn_coords(img_np, t_move_resume_act, t_move_resume_deact, 0.70)
    if not resume_coords:
        return 'not_found', img_np
    rx, ry = resume_coords
    print(f"⏭️ [이동 재개] '재개(1번 Redo)' ({rx}, {ry}) 터치 주입")
    safe_device_shell(device, f"input tap {rx} {ry}")

    time.sleep(0.5)
    prev_mini = None
    last_img = img_np
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    for _step in range(2):
        try:
            raw = capture_screen_bytes(device)
            if raw is None: continue
            img_np_sub = decode_screen_bytes(raw)
            last_img = img_np_sub
        except Exception:
            continue

        if t_no_chest is not None and check_template_present(img_np_sub, t_no_chest, 0.55):
            return 'no_chest', last_img

        gray_sub = cv2.cvtColor(img_np_sub, cv2.COLOR_RGB2GRAY)
        mini = gray_sub[int(115 * scale_y):int(315 * scale_y), int(1117 * scale_x):int(1317 * scale_x)]
        if prev_mini is not None:
            diff = cv2.absdiff(mini, prev_mini)
            if (np.mean(diff) / 255.0) >= 0.05:
                return 'moved', last_img
        prev_mini = mini
        time.sleep(0.3)

    return 'none', last_img

# 🚨 [2026-08-28 재개 오진 방지 - 사용자 확정 설계] 재개 버튼이 이미 도착한 예전 목적지를 다시 가리켜서
# "없습니다" 토스트가 뜰 수 있다. 이걸 곧바로 던전 나가기 신호로 오인하지 않도록, 상자 버튼(4번)으로 한
# 번 더 확인한 뒤에도 없을 때만 진짜 "상자 없음"으로 판정한다. 반환값: True면 진짜 상자 없음(나가기로
# 전환), False면 정상(다음 FIELD_WAIT 사이클에 맡김).
def resume_or_confirm_chest(device, img_np, t_move_resume_act, t_move_resume_deact,
                             t_move_chest_act, t_move_chest_deact, t_no_chest):
    outcome, img_check = try_resume_move(device, img_np, t_move_resume_act, t_move_resume_deact, t_no_chest)
    if outcome != 'no_chest':
        return False

    # 🚨 [2026-08-30 재개 오진 방지 경로 단축] try_resume_move()가 '없습니다' 판정 때 이미 찍어둔 스크린샷을
    # 그대로 재사용한다(상자 버튼 위치는 토스트 유무와 무관하므로 재사용 가능) - ADB 스크린샷 왕복 1회를
    # 절약해 이 재확인 경로의 체감 지연을 줄인다(사용자 지적: "이거 꽤 오래걸리는데").
    print("⚠️ [재개 오진 방지] 재개 중 '없습니다' 감지 - 상자 버튼으로 1회 재확인합니다.")
    coords = find_chest_btn_coords(img_check, t_move_chest_act, t_move_chest_deact, 0.70)
    if not coords:
        return False
    cx, cy = coords
    safe_device_shell(device, f"input tap {cx} {cy}")
    time.sleep(0.5)
    try:
        raw2 = capture_screen_bytes(device)
        img_check2 = decode_screen_bytes(raw2) if raw2 else img_check
    except Exception:
        img_check2 = img_check
    if check_template_present(img_check2, t_no_chest, 0.55):
        print("📦🚫 [상자 없음 재확인] 재개+상자 버튼 둘 다 '없습니다' - 진짜 없는 것으로 판정, 탈출로 전환합니다.")
        return True
    return False

def find_and_get_coords_dynamic(img_np, thresh_temp, threshold_val=0.68, min_brightness_thresh=160):
    if thresh_temp is None or img_np is None: return None
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return None
    
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, min_brightness_thresh, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def find_and_get_coords(img_np, thresh_temp, threshold_val=0.68):
    return find_and_get_coords_dynamic(img_np, thresh_temp, threshold_val, 160)




def check_minimap_movement(device, duration=1.5, interval=0.5):
    """
    지정된 시간(duration) 동안 미니맵의 픽셀 변화가 있는지 체크합니다.
    움직임이 감지되면 True, 멈춰 있으면 False를 반환합니다.
    """
    steps = int(duration / interval)
    prev_map = None
    
    for step in range(steps + 1):
        if step > 0:
            time.sleep(interval)
        try:
            raw = capture_screen_bytes(device)
            if raw is None: continue
            img = decode_screen_bytes(raw)
            h, w = img.shape[:2]
            
            # 해상도 스케일링 대응 (1440x2560 기준 Y: 115~315, X: 1117~1317)
            scale_x = w / 1440.0
            scale_y = h / 2560.0
            y1, y2 = int(115 * scale_y), int(315 * scale_y)
            x1, x2 = int(1117 * scale_x), int(1317 * scale_x)
            
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            minimap = gray[y1:y2, x1:x2]
            
            if prev_map is not None:
                diff = cv2.absdiff(minimap, prev_map)
                mean_diff = np.mean(diff) / 255.0
                if mean_diff >= 0.05:
                    return True
            prev_map = minimap
        except:
            continue
    return False


def find_and_click_template_in_bot(device, img_np, thresh_temp, threshold_val=0.68):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    try:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            h, w = thresh_temp.shape[:2]
            safe_device_shell(device, f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
        return False
    except: return False

# [독 감지 모니터링 기능은 1.14.1-hotfix7에서 렉 최적화를 위해 탈거되었습니다]

def find_and_click_color_template_in_bot(device, img_np, color_temp, threshold_val=0.75):
    """
    3채널 BGR/RGB 컬러 템플릿 매칭으로 대상 좌표를 탐색하고 클릭합니다.
    """
    if color_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = color_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    try:
        img_match = img_np[:, :, :3] if len(img_np.shape) == 3 and img_np.shape[2] == 4 else img_np
        temp_match = color_temp[:, :, :3] if len(color_temp.shape) == 3 and color_temp.shape[2] == 4 else color_temp
        
        result = cv2.matchTemplate(img_match, temp_match, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            h, w = temp_match.shape[:2]
            safe_device_shell(device, f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
        return False
    except: return False

# 🎁 [하켄의 가호] 하루 한 번(자정 이후) 하켄 귀환 시 뜨는 3지선다 가호 팝업 대응.
# 좌표는 1440x2560 기준 고정 (dev/ROI_check/필드-하켄의가호.png 실측): 3개 선택지 + "아무것도 안 한다".
HARKEN_BLESSING_ROWS = [(720, 1580), (720, 1750), (720, 1915)]

def save_device_screencap_evidence(device, prefix):
    """
    take_screencap_backup(main.py)과 동일한 방식(안드로이드 셸을 통한 백그라운드 캡처)을
    dungeon_bot.py 자체적으로 수행합니다 (main.py를 임포트하면 순환참조가 생기므로 로컬 중복 구현).
    """
    try:
        time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screencap_{prefix}_{time_str}.png"
        device.shell("mkdir -p /sdcard/Screenshots")
        print(f"📸 [{prefix.upper()} 스크린샷] 안드로이드 셸을 통해 화면을 백그라운드로 캡처합니다: {filename}")
        device.shell(f"screencap -p /sdcard/Screenshots/{filename}")
    except Exception as err:
        print(f"⚠️ [{prefix.upper()} 스크린샷 실패] {err}")

def sample_text_color(img_np, x, y, box=18, brightness_floor=90):
    """
    (x, y) 주변 작은 영역에서 배경(어두움)을 제외한 글자 획(밝은 픽셀)만 골라 평균 RGB를 구합니다.
    """
    h, w = img_np.shape[:2]
    x0, x1 = max(0, x - box), min(w, x + box)
    y0, y1 = max(0, y - 8), min(h, y + 8)
    region = img_np[y0:y1, x0:x1, :3].reshape(-1, 3).astype(np.int32)
    brightness = region.sum(axis=1)
    bright_pixels = region[brightness > brightness_floor * 3]
    if len(bright_pixels) == 0:
        return None
    r, g, b = bright_pixels.mean(axis=0)
    return int(r), int(g), int(b)

def classify_blessing_tier(rgb):
    """
    가호 등급을 텍스트 색상으로 판정합니다 (흰 < 녹 < 파 < 보라 < 빨강).
    실측 확인(2026-08-09): 흰=(244,244,244)류, 녹=(122~124,164~165,103~105)류.
    파/보라/빨강은 실전에서 아직 못 봐서 색상 범위가 추정치입니다 - 실제로 뜨면
    콘솔에 찍히는 RGB 값을 보고 아래 분기를 보정해주세요.
    """
    if rgb is None:
        return 0, "판정불가(흰색 취급)"
    r, g, b = rgb
    max_c, min_c = max(r, g, b), min(r, g, b)
    sat = (max_c - min_c) / max_c if max_c > 0 else 0
    if sat < 0.15:
        return 0, f"흰({rgb})"
    if g >= r and g >= b:
        return 1, f"녹({rgb})"
    if b >= r and b > g:
        return 2, f"파-추정({rgb})"
    if r > g and b > g:
        return 3, f"보라-추정({rgb})"
    return 4, f"빨강-추정({rgb})"

# 🎁 [2026-08-19 유령성 하켄 가호 이름 우선순위] 색상 등급(흰<녹<파<보라<빨강)이 실제 유용도와 항상
# 일치하지 않는다는 게 실전 데이터로 확인됨(예: "오드의 가호"는 녹색인데 파란색 "민첩의 가호"보다 우선해야
# 하고, "데몬족 헌터"도 다른 녹색 가호들보다 우선해야 함 - 색상 하나만 보면 뒤바뀜). 이름으로 먼저 식별하고
# 안 맞으면 색상 등급으로 폴백한다. 우선순위 점수는 색상 등급(0~4) 범위보다 항상 높게 잡아서, 이름이
# 인식되면 색상과 무관하게 항상 이긴다.
# 도장은 실제 컬러 가호 텍스트(흰 제외 전부 그레이스케일 밝기가 낮음, 실측 최저 약 95)를 놓치지 않도록
# load_dead_template()(이진화 문턱 65)로 로드한다 - load_template()의 기본 문턱 160으로는 컬러 텍스트가
# 통째로 사라져 매칭 자체가 불가능함(실측으로 확인).
NAMED_BLESSING_PRIORITY = [
    # (도장 경로, 우선순위 점수 - 높을수록 우선, 색상등급 최대치 4보다 항상 큼, 라벨)
    ("templates/HarkenBlessing/Father.png", 110, "신부님은 아이들의 아버지"),  # 🆕 [2026-09-07] 대설지대 최우선 가호(사용자 확정)
    ("templates/HarkenBlessing/demon_hunter.png", 100, "데몬족 헌터"),
    ("templates/HarkenBlessing/od_blessing.png", 90, "오드의 가호"),
]
_named_blessing_templates_cache = None

def _load_named_blessing_templates():
    global _named_blessing_templates_cache
    if _named_blessing_templates_cache is None:
        _named_blessing_templates_cache = []
        for path, score, label in NAMED_BLESSING_PRIORITY:
            temp = load_dead_template(path)
            if temp is not None:
                _named_blessing_templates_cache.append((temp, score, label))
    return _named_blessing_templates_cache

def classify_blessing_named_priority(img_np, y, match_threshold=0.85):
    """
    지정된 가호 줄(y 좌표)이 이름 우선순위 목록의 어떤 가호와 일치하는지 확인합니다.
    가로 전체 폭에서 이진화(문턱 65) 매칭을 시도 - 색상과 무관하게 텍스트 모양으로 식별합니다.
    일치하면 (우선순위 점수, 라벨), 아니면 None을 반환합니다.
    """
    h, w = img_np.shape[:2]
    y1, y2 = max(0, y - 70), min(h, y + 70)
    band = img_np[y1:y2, 0:w]
    if band.shape[0] < 10:
        return None
    gray = cv2.cvtColor(band, cv2.COLOR_RGB2GRAY)
    _, thresh_band = cv2.threshold(gray, 65, 255, cv2.THRESH_BINARY)

    best = None
    for temp, score, label in _load_named_blessing_templates():
        h_t, w_t = temp.shape[:2]
        if thresh_band.shape[0] < h_t or thresh_band.shape[1] < w_t:
            continue
        result = cv2.matchTemplate(thresh_band, temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > match_threshold and (best is None or score > best[0]):
            best = (score, f"{label}(이름 매칭 {max_val:.2f})")
    return best

def resolve_and_click_harken_blessing(device, img_np, priority_template=None):
    """
    하켄의 가호 3지선다 중 최선의 선택지를 탭합니다.
    1. 각 줄을 이름 우선순위 목록(NAMED_BLESSING_PRIORITY)과 먼저 대조 - 일치하면 색상과 무관하게
       그 우선순위 점수(항상 색상등급보다 높음)를 사용.
    2. priority_template(레거시 단일 도장 인자, 호출부에서 넘겨줄 경우)이 매칭되면 그것도 즉시 최우선 선택.
    3. 위 어느 것도 안 맞으면 텍스트 색상 등급(흰<녹<파<보라<빨강)으로 폴백.
    """
    if priority_template is not None:
        coords = find_and_get_coords(img_np, priority_template, 0.75)
        if coords:
            print(f"⭐ [하켄가호] 우선순위 가호(도장 매칭) 발견! 좌표 {coords} 터치")
            safe_device_shell(device, f"input tap {coords[0]} {coords[1]}")
            return True

    ranked = []
    for x, y in HARKEN_BLESSING_ROWS:
        named = classify_blessing_named_priority(img_np, y)
        if named is not None:
            score, label = named
            print(f"   [하켄가호] ({x},{y}) 줄 이름 우선판정: {label}")
        else:
            score, label = classify_blessing_tier(sample_text_color(img_np, x, y))
            print(f"   [하켄가호] ({x},{y}) 줄 등급 판정: {label}")
        ranked.append((score, x, y))

    best_tier, best_x, best_y = max(ranked, key=lambda t: t[0])
    print(f"🎁 [하켄가호] 최고 우선순위(score={best_tier}) 선택지 터치: ({best_x}, {best_y})")
    safe_device_shell(device, f"input tap {best_x} {best_y}")
    return True

_camp_rest_guard_template_cache = None
_camp_rest_guard_template_loaded = False

def _get_camp_rest_guard_template():
    """
    캠핑 대화창("쉰다") 판별용 도장을 1회만 로드해 캐시한다(하켄 메뉴 오판 차단용).
    ⚠️ 캐시 여부는 반드시 별도 bool 플래그로 판단할 것 - 로드된 값이 numpy 배열이라
    `if cache == "미로드"` 같은 값 비교를 쓰면 배열 전체 비교가 되어 ValueError가 나고,
    그 예외를 상위 except가 삼켜 하켄 메뉴 처리가 통째로 죽는다(리뷰 중 실제로 발생시킨 회귀).
    """
    global _camp_rest_guard_template_cache, _camp_rest_guard_template_loaded
    if not _camp_rest_guard_template_loaded:
        _camp_rest_guard_template_cache = load_template("templates/Dungeon_dialogue/Dun_camping_rest.png")
        _camp_rest_guard_template_loaded = True
    return _camp_rest_guard_template_cache

def check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, priority_template=None, img_np=None, t_yeolda=None):
    """
    "아무것도 안 한다"(귀환목록 화면과 가호 팝업에 공통으로 존재)를 1차 앵커로 삼아
    하켄 메뉴 자체가 떠 있는지 먼저 확인하고, 그 다음 "귀환" 텍스트 유무로 두 화면을 구분해 처리합니다.
    (추후 "귀환" 대신 다른 텍스트가 매칭되는 경우로 분기를 늘려 다른 구역 이동 등에도 재사용 가능)
    img_np를 주면(예: 재시도 루프에서 이미 찍어둔 화면) 새로 스크린샷을 찍지 않고 그걸 그대로 검사합니다.
    반환값: "not_present"(하켄 메뉴 자체가 안 떠있음) | "returned"(귀환목록 화면, 귀환 클릭 완료) | "blessing"(가호 팝업, 선택 완료)
    """
    if t_harken_blessing_donothing is None:
        return "not_present"
    try:
        if img_np is None:
            raw = capture_screen_bytes(device)
            if not raw:
                return "not_present"
            img_np = decode_screen_bytes(raw)
        if not check_template_present(img_np, t_harken_blessing_donothing, 0.70):
            return "not_present"

        # 🚨 [2026-08-16 상자 오판 완치] 상자 대화창("열다" / "아무것도 안 한다")에도 "아무것도 안 한다"가
        # 그대로 있어서, donothing=True & 귀환=False 조건이 성립해 상자 화면을 가호 팝업으로 오판하고 있었음
        # (실전 확인: 2026-08-16 20:26~20:27 2분 사이에만 상자 화면을 찍은 harken 증거 스샷 10장 발생,
        # 실제로는 가호 줄 좌표를 엉뚱하게 탭하고 있었음). 상자 화면에는 "열다"가 같이 있고 가호 팝업에는
        # 없다는 차이로 구분해 차단한다.
        if t_yeolda is not None and check_template_present_multipass(img_np, t_yeolda, 0.65):
            return "not_present"

        # 🚨 [2026-09-07 캠핑 화면 오판 차단] 위 상자 화면과 완전히 같은 유형의 함정이 캠핑 1차 화면에도
        # 있다 - 캠핑 대화창도 "쉰다 / 아무것도 안 한다" 2지선다라서 "아무것도 안 한다"가 그대로 존재한다
        # (실측: camping_rest1.png에서 donothing 앵커가 0.962로 매칭됨). 그대로 두면 donothing=True &
        # 귀환=False 조건이 성립해 캠핑 화면을 가호 팝업으로 오판하고 가호 줄 고정좌표를 탭해버린다.
        # 캠핑 화면에만 있는 "쉰다"로 구분해 차단한다(도장은 모듈 캐시라 호출부 시그니처 변경 불필요 -
        # main.py 등 다른 호출부도 이 가드를 자동으로 함께 받는다).
        t_camp_rest_guard = _get_camp_rest_guard_template()
        if t_camp_rest_guard is not None and check_template_present(img_np, t_camp_rest_guard, 0.70):
            return "not_present"

        # "아무것도 안 한다"만으로는 귀환목록 화면과 가호 팝업을 구분할 수 없음(실전 오탐 사례로 확인) -
        # 귀환목록 화면에는 "귀환" 항목이 같이 있고, 가호 팝업에는 "귀환" 텍스트 자체가 없다는 차이로 구분한다.
        if check_color_template_present(img_np, t_harken_return, 0.75):
            find_and_click_color_template_in_bot(device, img_np, t_harken_return, 0.75)
            return "returned"

        print("🎁 [하켄가호] '하켄의 가호' 팝업 감지! 증거 스크린샷 저장 후 선택지를 고릅니다.")
        # 💡 증거 스샷은 반드시 터치 전에 찍어야 함 - 터치 후에 찍으면 이미 선택이 반영되거나
        # 팝업이 닫힌 "결과" 화면만 남아서, 정작 필요한 "3개 선택지가 무엇이었는지"를 기록하지 못함.
        save_device_screencap_evidence(device, prefix="harken")
        resolve_and_click_harken_blessing(device, img_np, priority_template)
        time.sleep(2.0)
        return "blessing"
    except Exception as err:
        print(f"⚠️ [하켄메뉴] 판정/처리 중 예외 발생: {err}")
        return "not_present"

def trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing=None, t_combat_in=None, t_combat_slow=None, t_yeolda=None):
    """
    하켄 탈출 수렴 루프: 3채널 BGR 컬러 매칭으로 하켄 귀환 창이 뜰 때까지 대기하며,
    만약 보이지 않으면 출구이동(미니맵 2번) 터치를 재시도하며 안정적으로 귀환 버튼을 클릭하고 탈출합니다.
    """
    harken_clicked = False
    harken_stuck_count = 0
    harken_first_stuck_time = None
    harken_recovery_attempted = False
    prev_minimap = None
    # 💡 [v1.17.0-hotfix1] wvd 원본(script.py)의 동일 화면("ReturnText"/"leaveDung"/"donothing" 하켄 목록) 대응 로직을
    # 확인해보니 대기시간 3.75초 자체는 wvd에서 맞게 가져온 값이었지만, 실제 재시도 횟수는 wvd의 MAX_TRY_LIMIT(기본 25회)인데
    # 이식 과정에서 3회로 축소되어 있었음. 구역이 많이 열린 던전은 하켄 목록 렌더링이 오래 걸려 11.25초 안에 못 뜨는 경우가 있어
    # 폴백 좌표를 허공에 찍고도 성공으로 오판정하던 결함을 완치하기 위해 10회(약 37.5초)로 상향.
    print("⏳ [하켄귀환] 귀환 팝업 대기 및 BGR 컬러 수렴 루프 기동 (간격: 3.75초, 최대 10회)")
    for h_wait in range(10):  # 3.75초 간격 * 10회 = 약 37.5초
        time.sleep(3.75)
        try:
            raw_h = capture_screen_bytes(device)
            if raw_h:
                img_np_h = decode_screen_bytes(raw_h)

                # ⚔️ [2026-08-12 정체오판 방지] 전투 조우는 그 자체로 "먹통이 아니다"라는 증거이므로(사용자 지적),
                # 정체 카운트/워치독을 리셋만 하고 이번 회차는 하켄 메뉴 체크 없이 넘어간다 - 전투를 대신 치러주진
                # 않고, 다음 회차부터 다시 하켄 메뉴 확인을 재개한다.
                if check_combat_template_present(img_np_h, t_combat_in, 0.80) or check_combat_template_present(img_np_h, t_combat_slow, 0.80):
                    print(f"⚔️ [하켄귀환] 이동 중 전투 조우 감지 - 정체 아님, 판정 리셋 ({h_wait+1}/10)")
                    harken_stuck_count = 0
                    harken_first_stuck_time = None
                    harken_recovery_attempted = False
                    prev_minimap = None
                    continue

                # "아무것도 안 한다" 앵커로 하켄 메뉴 유무를 먼저 확인하고, "귀환" 유무로 귀환목록/가호 팝업을 구분한다.
                menu_state = check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, img_np=img_np_h, t_yeolda=t_yeolda)
                if menu_state == "returned":
                    print(f"🚪 [하켄귀환] 귀환 버튼 BGR 컬러 인식 및 터치 성공! (대기 {h_wait+1}회차)")
                    harken_clicked = True
                    break

                if menu_state == "blessing":
                    print(f"🎁 [하켄귀환] 재시도 도중 하켄의 가호 팝업을 감지해 처리했습니다. 귀환 목록 재확인을 계속합니다.")
                    harken_stuck_count = 0
                    harken_first_stuck_time = None
                    harken_recovery_attempted = False
                    prev_minimap = None
                    continue

                # 🚨 [2026-08-12 하켄 정체 복구 이식] TRIGGER_EXIT(계단/던전탈출)이 이미 쓰던, 미니맵 영역만 잘라
                # (Y:115~315, X:1117~1317) 직전 스캔과 비교하는 방식을 그대로 재사용 - 4장 대설지대 같은 시야
                # 제한 구역에서도 미니맵의 노란 현재위치 커서는 가려지지 않아 신뢰도 높은 정체 판정 기준이 된다.
                h_img, w_img = img_np_h.shape[:2]
                scale_x, scale_y = w_img / 1440.0, h_img / 2560.0
                gray_h = cv2.cvtColor(img_np_h, cv2.COLOR_RGB2GRAY)
                current_mini = gray_h[int(115 * scale_y):int(315 * scale_y), int(1117 * scale_x):int(1317 * scale_x)]
                if prev_minimap is not None:
                    mean_diff = np.mean(cv2.absdiff(current_mini, prev_minimap)) / 255.0
                    if mean_diff < 0.05:
                        harken_stuck_count += 1
                        if harken_first_stuck_time is None:
                            harken_first_stuck_time = time.time()
                        elapsed = time.time() - harken_first_stuck_time
                        print(f"⚠️ [하켄귀환] 미니맵 정지 감지 ({harken_stuck_count}회, 누적 경과 {elapsed:.0f}초)")

                        # 정체 3회 누적 시 백스텝 스와이프(물리 후진) 후 출구 단추 재탭 - TRIGGER_EXIT와 동일 제스처.
                        # 이번 정체 구간에서 1회만 시도(연타 방지).
                        if harken_stuck_count >= 3 and not harken_recovery_attempted:
                            harken_recovery_attempted = True
                            print("🔙 [하켄귀환] 정체 복구: 백스텝 스와이프 후 출구 단추 재탭")
                            sx = int(720 * scale_x)
                            sy1, sy2 = int(1200 * scale_y), int(1600 * scale_y)
                            safe_device_shell(device, f"input swipe {sx} {sy1} {sx} {sy2} 300")
                            time.sleep(1.0)
                            exit_coords = find_and_get_field_btn_coords(img_np_h, t_move_exit, 0.70)
                            if exit_coords:
                                safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                            else:
                                safe_device_shell(device, "input tap 1140 572")
                            prev_minimap = None  # 후진/재접근 연출 대기 1턴 스킵 (TRIGGER_EXIT와 동일)
                            continue

                        # 절대 워치독: 백스텝 복구까지 거쳤는데도 정체 최초 감지 후 60초를 넘기면 진짜 먹통으로 판단해
                        # 실패를 전파한다(예전엔 여기서도 그냥 재시도만 반복 - 무한루프 원인). main.py의 restart_process()로
                        # 이어지도록 dungeon_bot.py 안에서 잡지 않고 그대로 던진다.
                        if elapsed >= 60.0:
                            raise RuntimeError(f"하켄 탈출 실패: 정체 최초 감지 후 {elapsed:.0f}초 경과, 백스텝 복구로도 해소되지 않아 강제 앱 재시작을 요청합니다.")
                    else:
                        harken_stuck_count = 0
                prev_minimap = current_mini

                if h_wait < 2:
                    # 처음 1~2회차에만 미니맵 2번 재타격 (그 이후엔 이미 하켄 목록 화면일 가능성이 높아 재탭 생략)
                    print(f"🔄 [하켄귀환] 귀환 버튼 미검출로 미니맵 2번 터치 재주입 시도 ({h_wait+1}/10)")
                    exit_coords = find_and_get_field_btn_coords(img_np_h, t_move_exit, 0.70)
                    if exit_coords:
                        safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                    else:
                        safe_device_shell(device, "input tap 1140 572")
                else:
                    print(f"🔄 [하켄귀환] 귀환 버튼 미검출, 화면 안착 대기 재시도 ({h_wait+1}/10)")
        except RuntimeError:
            raise  # 절대 워치독 예외는 그대로 상위(main.py의 restart_process)로 전파
        except Exception as scan_err:
            print(f"⚠️ [하켄귀환] 스크린샷 스캔 중 예외 발생: {scan_err}")

    if not harken_clicked:
        print("⚠️ [하켄귀환] 컬러 인식 실패. 1440x2560 표준 고정 좌표 (720, 1920) 강제 터치 주입!")
        safe_device_shell(device, "input tap 720 1920")
        time.sleep(2.0)
        # 🚨 [재검증] 폴백 좌표가 실제로 맞았는지 확인 없이 무조건 성공 처리하던 결함 완치.
        # 폴백 탭 이후에도 여전히 귀환 화면이 잔류하면, 이번엔 실제 매칭 좌표로 한 번 더 정밀 재클릭한다.
        try:
            raw_verify = capture_screen_bytes(device)
            if raw_verify:
                img_np_v = decode_screen_bytes(raw_verify)
                if check_color_template_present(img_np_v, t_harken_return, 0.75):
                    print("⚠️ [하켄귀환] 폴백 좌표 이후에도 귀환 목록 화면 잔류 감지! 실제 매칭 좌표로 정밀 재클릭을 시도합니다.")
                    find_and_click_color_template_in_bot(device, img_np_v, t_harken_return, 0.75)
                    time.sleep(2.0)
        except Exception as verify_err:
            print(f"⚠️ [하켄귀환] 폴백 재검증 중 예외 발생: {verify_err}")

        # 🚨 [2026-08-12 무한 성공처리 완치] 예전엔 여기서 그냥 무조건 harken_clicked=True로 성공 처리했는데,
        # 실전(모바일 로그인으로 세션이 끊긴 상황)에서 이게 "실패를 호출부에 전혀 못 알리는" 결함으로 확인됨.
        # 최종 재확인까지 거치고도 여전히 미확인이면 RuntimeError로 실패를 전파한다.
        final_state = check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, t_yeolda=t_yeolda)
        if final_state in ("returned", "blessing"):
            harken_clicked = True
        else:
            elapsed = (time.time() - harken_first_stuck_time) if harken_first_stuck_time else 0.0
            raise RuntimeError(f"하켄 탈출 실패: 정체 최초 감지 후 {elapsed:.0f}초 경과, 백스텝 복구로도 해소되지 않아 강제 앱 재시작을 요청합니다.")

    time.sleep(4.0)  # 퇴장 연출 대기

    # 🎁 [하켄의 가호] 연 1회(자정 이후) 등장하는 팝업 대응 - 매번 호출되지만 미검출 시 오버헤드는 스캔 1회뿐.
    check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, t_yeolda=t_yeolda)

    return True

# 🆕 [2026-09-07 대설지대] 필드맵을 확장해 캠프/대하켄 아이콘을 찾아 자동이동으로 복귀하는 범용 귀환 루틴 -
# 캠핑/하켄 아이콘이 있는 던전이면 대설지대 외에도 재사용할 예정이라 던전 이름을 함수명에 넣지 않는다.
# TRIGGER_EXIT의 기존 나가기-버튼-도보 로직을 대체(return_method가 "exit_button"이면 이 함수 자체를
# 호출하지 않으므로 다른 던전은 전혀 영향 없음). 템플릿은 이 함수 안에서 직접 로드한다(inn_manager의
# run_inn_sleep_sequence()와 같은 자가완결형 패턴 - 던전 탈출 시 1회만 호출되므로 매 틱 성능 부담 없음).
FIELDMAP_EXPAND_TAP_COORDS = (1217, 219)  # (1204,202)~(1231,237) 영역 중앙, 사용자 실측 검증
FIELDMAP_EXPANDED_ANCHOR_ZONE = (2239, 2336, 340, 445)  # (y1,y2,x1,x2) - 확장 시 필드 앵커 백업 크롭 자리
# 🆕 [2026-09-08] 필드맵이 열렸을 때만 존재하는 전용 앵커("✕ 닫기" 버튼). 위 백업 크롭은 "필드 앵커가
# 확장 화면에서 옮겨간 자리"를 다시 딴 것이라 의미가 간접적인데, 이건 확장 화면 고유 UI라 판정이 명확하다.
# 실측(크롭 기준): 확장 화면 0.925~1.000 vs 비확장 화면 -0.09~0.27 → 임계값 0.80이면 양쪽으로 여유가 크다.
# 다른 도장과의 교차 오탐도 전수 확인함(최고 0.431 = inn_sleep/levelup_close_btn, 안전).
FIELDMAP_CLOSE_ANCHOR_ZONE = (2395, 2508, 553, 802)  # 도장 ROI (583,2425)-(772,2478) + 여유 30px
FIELDMAP_CLOSE_ANCHOR_THRESHOLD = 0.80
FIELDMAP_CLOSE_TAP_COORDS = (677, 2451)  # 위 존의 중앙 - 확장된 필드맵을 닫을 때 탭한다

# 🚨 [2026-09-11 실전 확인] "X 닫기"(가로 배치, close_panel_inline.png)는 캐릭터 상태/버프 팝업뿐
# 아니라 상자 "누가 열 거야?" 캐릭터 선택 화면에도 똑같이 있어서(오탐 0.92~0.93), 전체화면 검색하면
# 진행 중인 상자 개방을 잘못 취소시킬 위험이 있다. 실측으로 확인한 두 화면의 버튼 Y중심(상태팝업
# 1505=58.8%, 캐릭터선택 2418=94.5%, 약 900px 차이)을 근거로 상태팝업 쪽만 좁게 잡은 검색 구역 -
# 이 구역 밖에서는 절대 안 찾으므로 캐릭터선택 화면과는 원천적으로 섞이지 않는다.
STATUS_POPUP_CLOSE_ZONE = (1350, 1650, 500, 1050)  # (y1, y2, x1, x2)

def _match_gray_in_zone(img_np, template, zone):
    """지정 크롭 영역 안에서 그레이스케일 매칭 최고점을 반환. 매칭 불가 상황이면 None."""
    if template is None or img_np is None:
        return None
    y1, y2, x1, x2 = zone
    h, w = img_np.shape[:2]
    if h < y2 or w < x2:
        return None
    crop = img_np[y1:y2, x1:x2]
    if crop.shape[0] < template.shape[0] or crop.shape[1] < template.shape[1]:
        return None
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED))
    return max_val


def _check_fieldmap_expanded(img_np, t_field_expanded, t_close_anchor=None, threshold=0.65):
    """필드맵이 확장(열림) 상태인지 판정. 두 앵커 중 하나만 잡혀도 확장으로 본다.

    두 도장은 서로 강점이 다르다(실측): 지도를 가장자리까지 끌었을 때는 '닫기' 앵커가 0.925로 조금
    내려가는 대신 백업 크롭이 0.99를 유지하고, 교회구역처럼 배경이 다른 곳에서는 반대로 '닫기'가
    0.992로 더 안정적이다(백업은 0.94). 그래서 우선순위(닫기 → 백업)로 두되 둘 다 살려둔다.
    """
    close_score = _match_gray_in_zone(img_np, t_close_anchor, FIELDMAP_CLOSE_ANCHOR_ZONE)
    if close_score is not None and close_score > FIELDMAP_CLOSE_ANCHOR_THRESHOLD:
        return True
    backup_score = _match_gray_in_zone(img_np, t_field_expanded, FIELDMAP_EXPANDED_ANCHOR_ZONE)
    return backup_score is not None and backup_score > threshold

FIELDMAP_ICON_THRESHOLD = 0.80   # 🚨 실측: 대하켄 도장이 엉뚱한 지형에 0.72~0.76으로 오탐(진짜는 0.83~1.00)
FIELDMAP_AUTOMOVE_THRESHOLD = 0.80  # 🚨 실측: 자동이동 버블 진짜 0.90~1.00 vs 없는 화면 0.47~0.50으로 분리 뚜렷

def _find_automove_button(img_np, t_automove_primary, t_automove_fallback, threshold=FIELDMAP_AUTOMOVE_THRESHOLD):
    """
    자동이동("자동 이동") 버블을 화면 전체에서 찾는다.
    🚨 [2026-09-07 설계 정정] 원래는 "탭 지점 Y축 -170px 부근"만 국소 검색했는데, 실측 결과 버블이
    아이콘 바로 위가 아니라 가장자리에서는 가로로 최대 121px까지 밀려서 뜬다(교회구역_대하켄_자동이동:
    아이콘 중심 x=1311 vs 버블 중심 x=1190). 반면 버블은 화면에 동시에 두 개가 뜰 수 없고 전체검색
    분리도가 매우 뚜렷해(진짜 0.90~1.00 / 없는 화면 0.47~0.50) 위치를 추측할 이유가 없다 - 전체검색으로
    바꿔 위치 추정 오차라는 실패 요인 자체를 제거한다. 반투명 아이콘이라 이진화는 하지 않는다(실측:
    원본 그레이스케일 0.90 vs 이진화 0.54~0.74).
    """
    if img_np is None:
        return None
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    for temp in (t_automove_primary, t_automove_fallback):
        if temp is None or gray_img.shape[0] < temp.shape[0] or gray_img.shape[1] < temp.shape[1]:
            continue
        result = cv2.matchTemplate(gray_img, temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold:
            th, tw = temp.shape[:2]
            return max_loc[0] + int(tw / 2), max_loc[1] + int(th / 2)
    return None

# 🚨 [2026-09-08 실전 확인] return_to_town_via_fieldmap_icon()은 자기 안에서 반복 폴링하는 자기완결형
# 블로킹 함수라, 이 함수가 실행되는 동안은 중립몹/행상인 핸들러가 있는 공용 전처리 블록이 아예 안 돈다
# (실전 확인: 미니맵 확장 재시도 도중 중립몹 조우가 끼어들었는데 아무도 처리를 못 해 3회 재시도를 전부
# 헛탭으로 날리고 실패 처리됨 - 사용자 스크린샷+로그로 확인). 전투 감지만으로는 부족하다 - 중립몹 조우는
# "전투 시작 전" 대사/선택지 화면이라 t_combat_in/slow 도장에 안 걸린다. 이 헬퍼를 각 폴링 루프 안에서
# 호출해 감지되면 처리하고 True를 반환한다 - 호출부는 재시도 예산을 소모하지 않고 다시 스크린샷부터
# 진행해야 한다(전투 감지와 동일한 방침).
def _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow, t_field, t_doghole=None, t_dilog_bone=None, t_dilog_oil=None, t_dilog_elixir=None, t_dilog_bonegoblin_name=None):
    if img_np is None:
        return False
    if t_dilog_fight is not None:
        fight_coords = find_and_get_coords(img_np, t_dilog_fight, 0.70)
        if fight_coords:
            print(f"⚔️ [필드맵 귀환 - 중립몹 조우] '싸운다' 선택지 발견 - 고정 선택 탭: {fight_coords}")
            safe_device_shell(device, f"input tap {fight_coords[0]} {fight_coords[1]}")
            time.sleep(1.0)
            return True
    # 🆕 [2026-09-09 대설지대 6층] "울타리에 구멍이 뚫려있다" 조우 - "빠져나간다"/"그만둔다" 2택,
    # 항상 빠져나간다를 고정 선택한다(사용자 확정). 오탐 검증: 양성 1.000 vs 음성 최고 0.458(전투 대화창).
    if t_doghole is not None:
        doghole_coords = find_and_get_coords(img_np, t_doghole, 0.70)
        if doghole_coords:
            print(f"🕳️ [필드맵 귀환 - 울타리 구멍] '빠져나간다' 선택지 발견 - 고정 선택 탭: {doghole_coords}")
            safe_device_shell(device, f"input tap {doghole_coords[0]} {doghole_coords[1]}")
            time.sleep(1.0)
            return True
    # 🆕 [2026-09-10 대설지대] "뼈 줍는 고블린"(뼈상인) 조우 - 4지선다(유해를 부르는 기름(10,000골드)/
    # 모험가의 뼈(1,000골드)/비약(100골드)/아무것도 안 산다) 중 사용자 확정 우선순위: 모험가의 뼈를
    # 1순위로 먼저 찾고, 없으면(오탐/화면 변형 등) 유해를 부르는 기름을 2순위로 고른다.
    # 🚨 실측(뼈상인 조우 스샷 + 대설지대 기존 스샷 전수 대조): 두 도장 다 정탐 1.000. "기름"은 텍스트가
    # 2글자뿐이라 다른 화면과 근접 오탐 위험이 있음(음성 최고 0.650, combat_dialogue.png) - 임계값을
    # 관례(0.70)보다 높은 0.80으로 잡아 여유 확보(뼈는 음성 최고 0.568로 그보다 여유로움).
    if t_dilog_bone is not None:
        bone_coords = find_and_get_coords(img_np, t_dilog_bone, 0.80)
        if bone_coords:
            print(f"🦴 [필드맵 귀환 - 뼈상인 조우] '모험가의 뼈' 선택지 발견 - 고정 선택 탭: {bone_coords}")
            safe_device_shell(device, f"input tap {bone_coords[0]} {bone_coords[1]}")
            time.sleep(1.0)
            return True
    if t_dilog_oil is not None:
        oil_coords = find_and_get_coords(img_np, t_dilog_oil, 0.80)
        if oil_coords:
            print(f"🛢️ [필드맵 귀환 - 뼈상인 조우] '모험가의 뼈' 미검출 - 2순위 '유해를 부르는 기름' 선택 탭: {oil_coords}")
            safe_device_shell(device, f"input tap {oil_coords[0]} {oil_coords[1]}")
            time.sleep(1.0)
            return True
    # 🆕 [2026-09-14] 뼈/기름을 이미 구매했어도 뼈상인을 다시 조우하는 경우가 있는데, 이때 대화창에
    # "비약(100골드)"만 뜨는 경우가 실전 확인됨(뼈/기름 재고 소진 등으로 추정) - 3순위로 비약도 사게
    # 확장. 단, "비약(100골드)" 텍스트만으로 매칭하면 대설지대 일반 "수상한 행상인"의 판매 목록에 있는
    # "나무 향의 비약(3,000골드)"/"수제 상처약(100골드)"과 실측 0.7978까지 근접 오탐이 난다(임계값
    # 0.80과 위험할 정도로 가까움 - `templates/Dungeon_dialogue/_crop_metadata.json`의
    # `Dun_dilog_elixir`/`Dun_dilog_bonegoblin_name` 원본 스샷 대조 참고). 그래서 뼈상인 고유의
    # 화자명 "뼈 줍는 고블린" 텍스트(전수 스캔 정탐 1.000 vs 오탐 최고 0.2934 - 완전 분리 확인)가
    # 같은 화면에 함께 있을 때만 비약을 탭하도록 가드한다.
    if t_dilog_elixir is not None and t_dilog_bonegoblin_name is not None:
        if check_template_present(img_np, t_dilog_bonegoblin_name, 0.80):
            elixir_coords = find_and_get_coords(img_np, t_dilog_elixir, 0.80)
            if elixir_coords:
                print(f"🧪 [필드맵 귀환 - 뼈상인 조우] '모험가의 뼈'/'유해를 부르는 기름' 미검출 - 3순위 '비약' 선택 탭: {elixir_coords}")
                safe_device_shell(device, f"input tap {elixir_coords[0]} {elixir_coords[1]}")
                time.sleep(1.0)
                return True
    if t_seller_label is not None and check_template_present(img_np, t_seller_label, 0.80):
        print("🛒 [필드맵 귀환 - 행상인 조우] '수상한 행상인' 대사 화면 감지 - 조우 처리 루틴 진입.")
        handle_merchant_encounter(device, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow, t_field)
        return True
    # 🚨 [2026-09-09 실전 확인] 위 3개(싸운다/행상인/빠져나간다)는 전부 "구체적으로 아는 선택지"만 잡는다.
    # 그런데 그런 선택지가 뜨기 "전" 단계로 서술문만 있고 화살표만 있는 화면(예: 울타리 구멍 조우 직전의
    # 도입 대사)이 있을 수 있는데, 이건 위 어디에도 안 걸려서 아무도 못 넘기고 커서 미검출만 반복하며
    # 정체했다(실전 로그 2026-09-09 17:03, 사용자가 수동으로 화살표를 눌러 대화를 한 번 넘기자 그제서야
    # '빠져나간다' 선택지가 나와 정상 처리됨). ⚠️ 반드시 위 3개 구체적 선택지 체크 "뒤"에 둬야 한다 -
    # 중립몹 조우 등 실제 선택지 화면에도 이 화살표가 함께 찍혀 있어서, 순서를 앞에 두면 화살표를 먼저
    # 눌러 엉뚱한 선택지가 골라질 수 있다(사용자 확정 규칙).
    if t_dialogue_arrow is not None and find_and_click_dialogue_advance_arrow(device, img_np, t_dialogue_arrow):
        print("💬 [필드맵 귀환 - 대화 진행] 화살표 감지 - 다음 화면으로 넘깁니다.")
        time.sleep(0.8)
        return True
    return False

# 🚨 [2026-09-09 실측 확정] 필드 하단 버튼(재개/상자 등)의 활성·비활성 판별.
#
# 도장 매칭(TM_CCOEFF_NORMED)으로는 원천적으로 구분이 불가능하다 - 활성/비활성 도장은 모양이 완전히
# 같고 밝기만 다른데, 그 지표가 밝기를 정규화해버리기 때문(실측: 활성 0.98~0.99 vs 비활성 0.94~0.99).
# 예전에 "색상/밝기로도 안 된다"고 결론냈던 건 잘못된 실험이었다(사용자 지적) - 검사보다 먼저 터치를
# 넣어버려서 이미 활성화된 화면을 재고 있었다. 크롭 "평균" 밝기도 버튼 뒤 배경(눈밭/어두운 지형)에
# 오염돼 애매했다.
#
# 아이콘 픽셀 기준으로 보면 아주 깨끗하게 갈린다(실측):
#   resume_act 도장   : 밝은픽셀(>100) 비율 29.5% / 최대밝기 161.7
#   resume_deact 도장 : 밝은픽셀 비율  0.0% / 최대밝기  81.7
#   라이브 화면(비활성 확정)의 재개 버튼 : 0.0% / 83.0
#   같은 화면의 상자 버튼(활성)          : 24.0% / 171.7   ← 같은 조명에서 정반대로 갈림
# 비활성은 최대밝기가 83을 넘지 않고 활성은 160을 넘으므로, 문턱은 그 중간(밝은픽셀 5%)이면 충분하다.
#
# ⚠️ 반드시 "터치를 넣기 전"의 스크린샷으로 판정할 것. 터치 후에 재면 항상 활성으로 보인다.
BUTTON_ACTIVE_BRIGHT_PIXEL_RATIO = 0.05   # 밝은픽셀(>100) 비율이 이 값을 넘으면 활성
BUTTON_ACTIVE_BRIGHTNESS = 100

def is_field_button_active(img_np, coords, template):
    """필드 하단 버튼이 활성 상태인지 판정. 판정 불가면 None(호출부가 기존 동작을 유지하도록)."""
    if img_np is None or coords is None or template is None:
        return None
    h, w = template.shape[:2]
    cx, cy = coords
    y1, x1 = cy - h // 2, cx - w // 2
    ih, iw = img_np.shape[:2]
    if y1 < 0 or x1 < 0 or y1 + h > ih or x1 + w > iw:
        return None
    crop = img_np[y1:y1 + h, x1:x1 + w]
    if crop.ndim == 3:
        gray = crop.mean(axis=2)
    else:
        gray = crop.astype(float)
    return float(np.mean(gray > BUTTON_ACTIVE_BRIGHTNESS)) > BUTTON_ACTIVE_BRIGHT_PIXEL_RATIO


# 🚨 [2026-09-09 실전 확인] 캠프(우물) 아이콘이 화면 상단에 너무 가까우면(실전 로그: y=373 지점 탭),
# 탭 후 뜨는 "자동 이동" 버블이 상단 던전명 타이틀바("경로6 -호반(남)-" 등)에 가려지거나 화면 밖으로
# 밀려 안 보인다 - 자동이동 버튼 재탐색 3회를 전부 소진하고 앱이 강제 재시작됐다(사용자가 스크린샷으로
# 우물 위치와 상단 타이틀바 근접을 직접 확인). 사용자 지적대로 그 지점(y=373)보다 200px 아래(573)부터만
# 유효한 매칭으로 인정 - 그 위쪽은 미검출로 간주해 기존 스와이프 탐색/자리 재탐색이 계속 화면을 조정해
# 더 아래쪽에서 다시 찾도록 넘긴다.
FIELDMAP_CAMP_ICON_MIN_Y = 573

def _find_first_icon(img_np, templates, min_y=None):
    """후보 도장들을 순서대로 시도해 처음 잡히는 좌표를 반환(하켄 대/소처럼 같은 목적의 여러 도장용).
    min_y를 주면 그보다 위쪽(화면 상단)에서 잡힌 매칭은 미검출로 간주한다 - FIELDMAP_CAMP_ICON_MIN_Y
    주석 참고(자동이동 버블이 상단 타이틀바에 가려지는 문제 회피용)."""
    for tmpl in templates:
        if tmpl is None:
            continue
        coords = find_gray_coords_specific(img_np, tmpl, FIELDMAP_ICON_THRESHOLD)
        if coords and (min_y is None or coords[1] >= min_y):
            return coords
    return None


def _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                          t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda):
    """캠핑을 마치고 필드로 돌아온 상태에서의 공통 꼬리 - 나가기 버튼 탭 → 도보 탈출 확인 또는 하켄 귀환.

    🚨 [2026-09-08 실전 확인] 캠핑은 귀환 루틴 안에서 일어날 수도 있고(정상 흐름), 루틴이 전투로 메인
    루프에 제어를 넘긴 사이 공용 전처리 블록에서 처리될 수도 있다. 후자의 경우 다음 TRIGGER_EXIT에서
    루틴이 처음부터 다시 도는데, 그때 "캠핑은 끝났으니 하켄으로 가면 된다"며 return_method를
    "harken_only"로 바꿔치기했더니 엉뚱한 경로를 탔다 - harken_only는 "필드맵에서 대하켄 아이콘을 찾아
    자동이동"하는 교회구역용 경로라, 6층에서는 그 아이콘을 못 찾고 스와이프 8회를 모두 소진한 뒤 앱을
    재시작했다(실전 로그 23:57). 캠핑 이후에 필요한 건 아이콘 탐색이 아니라 "필드의 나가기 버튼 → 하켄
    귀환"이므로, 그 꼬리를 이렇게 따로 떼어 양쪽에서 같이 쓴다.
    """
    exit_coords = None
    for _try in range(5):
        raw = capture_screen_bytes(device)
        if raw:
            img_np = decode_screen_bytes(raw)
            exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
            if exit_coords:
                break
        time.sleep(1.0)
    if not exit_coords:
        print("⚠️ [필드맵 귀환] 휴식 후 일반 나가기 버튼을 찾지 못했습니다.")
        return "failed"
    print(f"🚪 [필드맵 귀환] 휴식 후 나가기 버튼 탭: {exit_coords}")
    safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
    time.sleep(2.0)

    if return_method == "camp_then_exit_button":
        # 🚨 [2026-09-07 반환 의미 정정] 이 분기는 하켄을 안 거치고 걸어서 던전을 빠져나가는 던전용이라,
        # 나가기 버튼을 눌렀다는 것만으로는 아직 탈출이 끝난 게 아니다. "필드 화면이 완전히 사라짐"을 확인한다.
        walk_deadline = time.time() + 90.0
        while time.time() < walk_deadline:
            raw = capture_screen_bytes(device)
            if raw:
                img_np = decode_screen_bytes(raw)
                if not check_field_anchor_present(img_np, t_field, 0.62):
                    print("🎉 [필드맵 귀환] 필드 화면 소멸 확인 - 도보 탈출 완료.")
                    return "returned"
            time.sleep(2.0)
        print("⚠️ [필드맵 귀환] 나가기 버튼 이후 90초 내 필드를 벗어나지 못했습니다.")
        return "failed"

    return "returned" if trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda) else "failed"


def _exit_via_walkout_or_harken(device, t_move_exit, t_field, t_harken_return, t_harken_blessing_donothing, t_yeolda, max_wait=60.0):
    """목표 아이콘(하켄)을 못 찾았을 때의 탈출 폴백 - 나가기 버튼을 누른 뒤 도보 탈출과 하켄 귀환 중
    먼저 뜨는 쪽을 그대로 따라간다.

    🚨 [2026-09-09 사용자 지적 - 비대칭 완치] harken_only 분기(교회구역 전용)는 스와이프 탐색 끝까지
    목표 하켄 아이콘을 못 찾으면 그냥 "failed"만 반환했다 - 캠핑 분기는 아이콘 미검출 시 나가기 버튼
    폴백(_return_after_camping)이 있는데 하켄 분기만 없어서, 사용자가 교회구역이 아닌 다른 구역에
    이 return_method로 매크로를 잘못 태우면(또는 그 구역에 하켄이 아예 없으면) 탈출 수단이 전혀 없이
    막혔다("하켄 없는 맵에서는 나갈 수가 없다"). 이 함수가 그 대칭짝이다 - 나가기 버튼을 눌러 도보
    탈출과 하켄 귀환목록 중 어느 쪽이 뜨든 따라간다(교회구역처럼 진짜 하켄이 있으면 하켄 귀환으로,
    하켄이 없는 구역이면 도보 탈출로 자연스럽게 갈린다).

    ⚠️ field_anchor 소멸만으로 "도보 탈출 완료"를 판정하면 안 된다 - 하켄 귀환목록/가호 팝업도 캠핑
    화면과 마찬가지로 전체화면 다이얼로그라 field_anchor를 가린다(실측: perform_camping_rest 주석의
    캠핑 3화면 0.09~0.21 사례와 동일 유형). 그래서 "하켄 메뉴가 뜬 게 아니면서 field_anchor도 없다"는
    조건일 때만 도보 탈출로 인정한다 - 하켄 메뉴는 먼저 확인해 처리하고, 메뉴가 없는데 field_anchor도
    없는 경우에만 도보 탈출로 판정한다.
    """
    exit_coords = None
    for _try in range(5):
        raw = capture_screen_bytes(device)
        if raw:
            img_np = decode_screen_bytes(raw)
            exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
            if exit_coords:
                break
        time.sleep(1.0)
    if not exit_coords:
        print("⚠️ [필드맵 귀환] 하켄 미검출 폴백 - 일반 나가기 버튼조차 찾지 못했습니다.")
        return "failed"
    print(f"🚪 [필드맵 귀환] 하켄 미검출 폴백 - 나가기 버튼 탭(도보 탈출/하켄 귀환 중 먼저 뜨는 쪽을 따라갑니다): {exit_coords}")
    safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
    time.sleep(2.0)

    deadline = time.time() + max_wait
    while time.time() < deadline:
        raw = capture_screen_bytes(device)
        if not raw:
            time.sleep(1.0)
            continue
        img_np = decode_screen_bytes(raw)

        menu_state = check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda)
        if menu_state == "returned":
            print("✅ [필드맵 귀환] 하켄 미검출 폴백 - 하켄 '귀환' 클릭 완료.")
            return "returned"
        if menu_state == "blessing":
            print("🎁 [필드맵 귀환] 하켄 미검출 폴백 - 가호 팝업 처리 완료, 귀환 목록을 계속 기다립니다.")
            time.sleep(1.0)
            continue

        if not check_field_anchor_present(img_np, t_field, 0.62):
            print("🎉 [필드맵 귀환] 하켄 미검출 폴백 - 필드 화면 소멸 확인, 도보 탈출 완료.")
            return "returned"

        time.sleep(1.5)

    print(f"⚠️ [필드맵 귀환] 하켄 미검출 폴백이 {max_wait:.0f}초 내 끝나지 않았습니다.")
    return "failed"


def return_to_town_via_fieldmap_icon(device, return_method, t_combat_in=None, t_combat_slow=None, max_swipe_attempts=8):
    """
    필드맵을 확장해 캠프/대하켄 아이콘을 찾아 자동이동으로 복귀하는 범용 귀환 루틴.
    return_method: "camp_then_exit_button" | "camp_then_harken" | "harken_only" ("exit_button"은 호출 안 함).
    반환: "returned"(귀환 완료) / "combat"(전투 조우 - 호출부가 메인 루프의 IN_COMBAT으로 넘기고, 전투가
          끝나면 이 루틴을 처음부터 다시 태운다) / "retry"(자동이동이 멈춰 재개/상자 사다리까지 태웠으나
          여전히 진행이 없음 - 필드맵을 다시 열어 명령을 새로 내려야 함) / "failed"(실패 - 호출부가
          재시도/앱재시작 판단).

    🚨 [2026-09-08 실전 확인] 이 루틴은 전투를 절대 스스로 기다리지 않는다. 예전엔 "자동전투가 끝나기를
    기다린다"는 방침이었는데, 자동전투가 (탭이 잘못 들어가는 등의 이유로) 한 번 깨지면 아무도 전투를
    몰지 않아 그대로 멈춰버렸다(실기 확인: 사용자가 수동으로 자동전투를 다시 켜줘야 했음). 전투 처리는
    메인 루프의 IN_COMBAT 상태 기계가 담당하므로(자동전투 재활성화/스킬/힐링/사망 감지 전부 거기 있음),
    전투를 만나면 즉시 "combat"으로 빠져나가 메인 루프에 제어를 돌려준다.
    """
    if return_method not in ("camp_then_exit_button", "camp_then_harken", "harken_only"):
        print(f"⚠️ [필드맵 귀환] 알 수 없는 return_method '{return_method}' - 호출 오류로 판단, 실패 처리.")
        return "failed"
    is_camp_branch = return_method in ("camp_then_exit_button", "camp_then_harken")

    t_field = load_grayscale_template("templates/Field/field_anchor.png")
    t_field_expanded = load_grayscale_template("templates/Field/Fieldmap_exit_icon.png")
    t_fieldmap_close = load_grayscale_template("templates/Field/FieldMap_Anchor.png")  # 확장 화면 전용 "✕ 닫기"
    t_camp = load_grayscale_template("templates/Field/Fieldmap_camping.png")
    t_harken_large = load_grayscale_template("templates/Field/FieldMap_harkenLarge_left.png")
    t_harken_small = load_grayscale_template("templates/Field/FieldMap_harkensmall.png")
    t_automove_camp = load_grayscale_template("templates/Field/FieldMap_automove.png")
    t_automove_harken = load_grayscale_template("templates/Field/FieldMap_harkenLarge_Automove.png")
    t_camp_rest1 = load_template("templates/Dungeon_dialogue/Dun_camping_rest.png")
    t_camp_rest2 = load_template("templates/Dungeon_dialogue/Dun_camping_rest2.png")
    t_camp_dry = load_template("templates/Dungeon_dialogue/Dun_camping_dry.png")  # "생명의 우물이 말라버렸다"
    t_dialogue_arrow = load_template("templates/inn_sleep/arrow_clean.png")
    t_move_exit = load_grayscale_template("templates/Field/exit_dungeon.png")
    t_harken_return = load_color_template("templates/FFXI/harken_return.png")
    t_harken_blessing_donothing = load_template("templates/Field/harken_blessing_donothing.png")
    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_move_resume_act = load_grayscale_template("templates/Field/resume_act.png")
    t_move_resume_deact = load_grayscale_template("templates/Field/resume_deact.png")
    # 🆕 [2026-09-08] "지금 확실히 필드 위인가"를 양성 조건으로 판정하기 위한 압축 미니맵 커서 도장 4종
    t_cursor_up = load_grayscale_template("templates/Field/cursor_up.png")
    t_cursor_down = load_grayscale_template("templates/Field/cursor_down.png")
    t_cursor_left = load_grayscale_template("templates/Field/cursor_left.png")
    t_cursor_right = load_grayscale_template("templates/Field/cursor_right.png")
    # 🆕 [2026-09-08] 자동이동이 멈췄을 때 기존 재개→상자 사다리를 그대로 재사용하기 위한 도장
    t_move_chest_act = load_grayscale_template("templates/Field/chest_act.png")
    t_move_chest_deact = load_grayscale_template("templates/Field/chest_deact.png")
    t_no_chest = load_template("templates/Field/toastmsg_nochest.png")
    # 🆕 [2026-09-08] 이 함수 안에서도 중립몹/행상인 조우를 처리하기 위한 도장(_handle_dungeon_interrupt용)
    t_dilog_fight = load_template("templates/Dungeon_dialogue/Dun_dilog_fight.png")
    t_seller_label = load_template("templates/Dungeon_dialogue/Dun_seller_label.png")
    t_seller_let_me_see = load_template("templates/Dungeon_dialogue/Dun_seller_let_me_see.png")
    t_seller_hammer = load_template("templates/Dungeon_dialogue/Dun_seller_hammer.png")
    t_doghole = load_template("templates/Dungeon_dialogue/Dun_HS6_doghole.png")  # "울타리 구멍으로 빠져나간다"
    t_dilog_bone = load_template("templates/Dungeon_dialogue/Dun_dilog_bone.png")  # "뼈상인" 1순위: "모험가의 뼈"
    t_dilog_oil = load_template("templates/Dungeon_dialogue/Dun_dilog_oil.png")  # "뼈상인" 2순위: "기름"("유해를 부르는 기름")
    t_dilog_elixir = load_template("templates/Dungeon_dialogue/Dun_dilog_elixir.png")  # "뼈상인" 3순위: "비약"
    t_dilog_bonegoblin_name = load_template("templates/Dungeon_dialogue/Dun_dilog_bonegoblin_name.png")  # 비약 오탐 방지용 화자명 가드

    # 🎯 캠핑 분기는 캠프 아이콘/캠핑용 자동이동만, 하켄 분기(교회구역)는 대하켄/대하켄용 자동이동만
    # 참조한다 - 처음부터 완전히 분리된 갈래라 서로의 탭 좌표/도장을 참조하지 않는다(사용자가 걱정한
    # "캠핑 처리 중 나가기가 잘못 눌리는" 꼬임 방지).
    # 🚨 캠핑이 이미 끝났다면(공용 전처리 블록이 처리한 경우) 미니맵 확장/캠프 아이콘 탐색을 통째로
    # 건너뛰고 "나가기 버튼 → 하켄" 꼬리부터 이어간다. 캠프 아이콘을 다시 찾아가면 무한 캠핑이 되고,
    # 그렇다고 harken_only로 바꿔치우면 6층에 없는 대하켄 아이콘을 찾다가 실패한다(위 함수 주석 참고).
    if is_camp_branch and is_camping_done():
        print("🏕️ [필드맵 귀환] 이번 탈출의 캠핑은 이미 끝났습니다 - 나가기 버튼부터 이어서 진행합니다.")
        return _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                                     t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)

    # 🆕 [2026-09-09 사용자 지침] 하켄으로 나갈 때는 대/중/소 구분 없이 "하켄이면 아무거나" 찾아야 한다.
    # 캠핑 분기는 캠프 아이콘 하나만 본다(캠프와 하켄을 섞으면 엉뚱한 곳으로 자동이동할 수 있음).
    target_icons = [t_camp] if is_camp_branch else [t for t in (t_harken_large, t_harken_small) if t is not None]
    automove_primary = t_automove_camp if is_camp_branch else t_automove_harken
    automove_fallback = t_automove_harken if is_camp_branch else t_automove_camp

    # 1~2. 압축 미니맵 확장 탭 → 확장 확인
    # 🚨 [2026-09-07] 예전엔 탭 1회 + 1초 대기 후 단 한 번만 확인하고 실패 시 곧바로 False(→호출부에서
    # RuntimeError→앱 재시작)로 빠졌다. 확장 애니메이션이 조금만 늦거나 탭이 한 번 씹혀도 앱을 통째로
    # 재시작하는 과한 실패라, 최대 3회까지 재탭하며 총 ~9초간 확인한다.
    # 🚨 [2026-09-08 실전 확인] 사용자 지적 + 실제 로그로 확인된 결함: 이 구간에 전투 감지가 전혀 없어서,
    # 탭 직전~직후(맵이 "완전히" 열리기 전까지)에 몹을 조우하면 화면이 전투로 바뀌는데도 계속 같은 좌표를
    # 재탭하기만 하다 3회를 다 소진해 앱을 통째로 재시작해버렸다(실전: 확장 탭 3회 동안 조우 추정, 매번
    # 미확장 판정 후 RuntimeError). 완전히 확장되면 던전 자체 타이머가 멈춰 그 이후엔 조우가 없다는
    # 사용자 확인에 따라, "확장 확인 전까지"만 전투를 감시하면 된다 - 전투면 탭/재시도 횟수를 소모하지
    # 않고 자동전투가 끝나기를 기다렸다가 이어간다(다른 루프와 동일 방침 - 전투를 대신 치러주지 않음).
    ex, ey = FIELDMAP_EXPAND_TAP_COORDS
    img_np = None
    expanded = False
    expand_attempts_used = 0
    combat_wait_deadline = time.time() + 180.0  # 절대 워치독 - 전투가 끝없이 이어지는 이상 상황 대비
    # 🚨 [2026-09-09 실전 확인] "커서 미검출 + 전투 아님 + 확장도 아님"이 겹치면 이 루프가 탭을 시도할
    # 방법이 아예 없어 1.5초씩 수동 개입 전까지 계속 헛돌았다(실전 로그 17:36:27~17:37:26, 61초간
    # 아무 진행 없이 "필드 커서 미검출" 반복 - 180초 워치독까지는 살아있었지만 그 이후엔 앱 전체 재시작
    # 이라는 비싼 실패로 이어짐). 커서가 안 보이는 진짜 원인(전투/확장)이 둘 다 아니라면, 이후에도 계속
    # 없을 걸 기다리는 것보다 그냥 탭을 시도하는 편이 낫다 - 연속 실패 카운터를 두고 한계를 넘으면
    # 대기를 포기하고 탭으로 넘어간다.
    cursor_wait_miss_count = 0
    CURSOR_WAIT_MISS_LIMIT = 5
    while expand_attempts_used < 3 and time.time() < combat_wait_deadline:
        # 탭 전 전투/중립몹/행상인 조우 여부 확인 - 조우 중이면 탭 자체를 보류(재시도 횟수 소모 안 함)
        raw = capture_screen_bytes(device)
        if not raw:
            time.sleep(1.0)
            continue
        img_np = decode_screen_bytes(raw)
        if _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow, t_field, t_doghole=t_doghole, t_dilog_bone=t_dilog_bone, t_dilog_oil=t_dilog_oil, t_dilog_elixir=t_dilog_elixir, t_dilog_bonegoblin_name=t_dilog_bonegoblin_name):
            continue
        # 🚨 [2026-09-09 실전 확인] 이 함수엔 캠핑 화면("쉰다") 감지가 아예 없었다 - 상자를 찾아 이동하던
        # 캐릭터가 마침 캠프 지점(우물) 위에 서 있으면, 맵을 열지 않아도 게임이 자동으로 캠핑 선택창을
        # 띄우는데, 그 화면엔 압축 미니맵 커서가 없으니 "커서 미검출"로만 잡혀 미니맵 확장 좌표만 계속
        # 눌러대며 정체했다(실전 로그: TRIGGER_EXIT 진입 직후부터 "쉰다"가 떠 있었는데도 탭 1/3, 2/3을
        # 헛되이 반복). 커서가 없는 원인을 확인하는 다른 것들(전투/확장)과 같은 순서로, 여기서도 먼저
        # 캠핑 화면인지부터 본다.
        if is_camp_branch and (find_and_get_coords(img_np, t_camp_rest1, 0.70) or check_template_present(img_np, t_camp_dry, 0.70)):
            print("🏕️ [필드맵 귀환] 미니맵 확장 전에 캠핑 화면이 이미 떠 있습니다 - 맵 확장 없이 곧장 캠핑을 진행합니다.")
            if perform_camping_rest(device, t_camp_rest1, t_camp_rest2, t_dialogue_arrow, t_field, t_camp_dry=t_camp_dry):
                return _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                                             t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
            return "failed"
        # 🚨 [2026-09-08 실전 확인] 예전엔 "전투 도장이 안 보이면 탭"이라는 음성 조건이었는데, 전투 중
        # 단 한 프레임만 매칭이 흔들려도 탭이 나가 자동전투가 깨지고 그대로 멈추는 사고가 났다(실기:
        # 전투 감지 로그가 연달아 찍히던 와중에 탭이 나갔고, 사용자가 수동으로 자동전투를 다시 켜줬더니
        # 또 탭이 들어감). 이제 "압축 미니맵의 노란 커서가 실제로 보일 때만" 탭하는 양성 조건으로 바꾼다
        # - 커서가 보인다 = 지금 확실히 필드 위다. 안 보이면 무슨 화면인지부터 판별한다.
        if get_minimap_cursor_direction(img_np, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right) is None:
            if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                print("⚔️ [필드맵 귀환] 전투 조우 - 메인 루프의 전투 처리로 넘깁니다(전투 종료 후 귀환 재시도).")
                return "combat"
            # 커서가 안 보이는 정상 사유가 하나 더 있다 - 맵이 이미 확장돼서 압축 미니맵 자체가 사라진
            # 경우. 탭 직후 폴링이 확장을 놓쳤을 때 여기서 건져내지 않으면, 다시 탭하지도(재탭하면 오히려
            # 맵이 닫힘) 확장을 확정하지도 못한 채 워치독까지 대기하게 된다.
            if _check_fieldmap_expanded(img_np, t_field_expanded, t_fieldmap_close):
                print("🗺️ [필드맵 귀환] 커서 미검출이지만 확장 상태 확인됨 - 확장 완료로 판정합니다.")
                expanded = True
                break
            cursor_wait_miss_count += 1
            if cursor_wait_miss_count < CURSOR_WAIT_MISS_LIMIT:
                print(f"⏳ [필드맵 귀환] 필드 커서 미검출(전투 아님) - 화면이 안정될 때까지 탭을 보류합니다. ({cursor_wait_miss_count}/{CURSOR_WAIT_MISS_LIMIT})")
                time.sleep(1.5)
                continue
            print(f"⚠️ [필드맵 귀환] 커서 미검출이 {CURSOR_WAIT_MISS_LIMIT}회 연속돼 대기를 포기하고 탭을 시도합니다.")
            cursor_wait_miss_count = 0

        expand_attempts_used += 1
        print(f"🗺️ [필드맵 귀환] 미니맵 확장 탭 {expand_attempts_used}/3: ({ex},{ey})")
        safe_device_shell(device, f"input tap {ex} {ey}")

        combat_interrupted = False
        for _poll in range(3):
            time.sleep(1.0)
            raw = capture_screen_bytes(device)
            if not raw:
                continue
            img_np = decode_screen_bytes(raw)
            # 🚨 [2026-09-09 실측 확정] 여기부터는 화살표 폴백을 끈다(t_dialogue_arrow 대신 None 전달) -
            # 맵이 열리는 중이라 확장 화면 UI(예: 하단 접기/펼치기 삼각형)가 화살표 도장과 0.76~0.81로
            # 매우 근접해 매칭된다(실측: 4개 확장 화면 스크린샷 전수 검증, 임계값 0.82 바로 아래). 실전
            # 캡처 노이즈로 이 근접치가 0.82를 넘어 오탐이 실제로 발생함을 확인(2026-09-09 17:16 로그 -
            # 화살표 감지가 4회 연속 찍히며 스와이프 예산을 대신 소모). 구체적 선택지(싸운다/행상인/
            # 빠져나간다)는 그대로 처리한다 - 오탐 위험은 오직 "화살표만 있고 아무 선택지도 안 걸리는" 폴백 경로에만 있다.
            if _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, None, t_field, t_doghole=t_doghole, t_dilog_bone=t_dilog_bone, t_dilog_oil=t_dilog_oil, t_dilog_elixir=t_dilog_elixir, t_dilog_bonegoblin_name=t_dilog_bonegoblin_name):
                print("⚠️ [필드맵 귀환] 탭 직후 중립몹/행상인 조우 처리 - 이번 시도는 재시도 횟수에서 제외합니다.")
                combat_interrupted = True
                expand_attempts_used -= 1  # 조우로 무산된 시도는 예산에서 다시 돌려준다
                break
            if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                print("⚔️ [필드맵 귀환] 탭 직후 전투 조우 - 메인 루프의 전투 처리로 넘깁니다(전투 종료 후 귀환 재시도).")
                return "combat"
            if _check_fieldmap_expanded(img_np, t_field_expanded, t_fieldmap_close):
                expanded = True
                break
        if expanded:
            break
        if combat_interrupted:
            time.sleep(2.0)

    if not expanded or img_np is None:
        print("⚠️ [필드맵 귀환] 미니맵 확장이 확인되지 않았습니다 - 좌표/타이밍 재검토 필요.")
        return "failed"

    # 3. 목표 아이콘 탐색 (안 보이면 스와이프 재시도 - 필드맵은 월드맵보다 훨씬 작아 폭/횟수는
    # 실기 로그로 튜닝 예정, 우선 보수적인 소폭 스와이프로 시작)
    icon_coords = None
    swipe_waypoints = [
        (720, 1600, 720, 900),   # 위로
        (720, 900, 720, 1900),   # 아래로(원위치+더)
        (1100, 1300, 400, 1300), # 왼쪽으로
        (400, 1300, 1300, 1300), # 오른쪽으로(원위치+더)
    ]
    # 🚨 [2026-09-08 정정] 예전엔 "맵이 확장되면 던전 타이머(=몹 조우)가 멈춘다"고만 알고 있었는데,
    # 사용자 실기 확인 결과 조건이 붙는다 - (1) 캐릭터가 움직이는 중이 아니어야 하고, (2) 확장 후 1~2초
    # 안에 전투 조우가 없어야 한다. 둘 중 하나라도 어긋나면 확장 상태에서도 전투가 열린다. 그래서 이
    # 이후 단계에도 조우/전투 체크를 계속 유지한다(값싼 방어가 아니라 실제로 필요한 방어다).
    # 🚨 [2026-09-09 실전 확인 - 카운터 소모 버그 완치] 예전엔 "for attempt in range(max_swipe_attempts):"
    # 였는데, 인터럽트 처리 후 continue를 해도 for 루프는 range의 다음 값으로 그냥 넘어간다 - 즉
    # 인터럽트 한 번 처리할 때마다 실제로 스와이프를 안 했는데도 예산이 1씩 줄어들었다(실전 로그: 화살표
    # 감지가 4번 연속 찍히자 "스와이프 탐색 1/8" 다음이 바로 "6/8"로 건너뜀 - 2~5회차가 전부 인터럽트
    # 처리에 조용히 소모됨). while 루프 + 실제로 스와이프했을 때만 증가하는 카운터로 분리해 완치.
    # 화살표 폴백도 억제한다(사유는 위 탭 직후 폴링과 동일 - 확장 화면 UI 삼각형이 0.76~0.81로 근접 매칭).
    attempt = 0
    # 🚨 인터럽트 처리는 이제 attempt를 안 까먹으므로 이론상 무한정 반복될 수 있다(실제 진행 없이
    # 인터럽트만 계속 뜨는 이상 상황 대비) - 절대시간 워치독을 추가한다(다른 루프들과 동일 패턴).
    swipe_search_deadline = time.time() + 120.0
    while attempt < max_swipe_attempts and time.time() < swipe_search_deadline:
        if _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, None, t_field, t_doghole=t_doghole, t_dilog_bone=t_dilog_bone, t_dilog_oil=t_dilog_oil, t_dilog_elixir=t_dilog_elixir, t_dilog_bonegoblin_name=t_dilog_bonegoblin_name):
            raw = capture_screen_bytes(device)
            if raw:
                img_np = decode_screen_bytes(raw)
            continue
        icon_coords = _find_first_icon(img_np, target_icons, min_y=FIELDMAP_CAMP_ICON_MIN_Y if is_camp_branch else None)
        if icon_coords:
            break
        wp = swipe_waypoints[attempt % len(swipe_waypoints)]
        print(f"🔍 [필드맵 귀환] 목표 아이콘 미검출 - 스와이프 탐색 {attempt + 1}/{max_swipe_attempts}")
        safe_device_shell(device, f"input swipe {wp[0]} {wp[1]} {wp[2]} {wp[3]} 400")
        time.sleep(1.0)
        attempt += 1
        raw = capture_screen_bytes(device)
        if not raw:
            continue
        img_np = decode_screen_bytes(raw)

    if not icon_coords:
        print("⚠️ [필드맵 귀환] 스와이프 탐색 끝까지 목표 아이콘을 찾지 못했습니다.")
        # 🆕 [2026-09-09 사용자 확인] 캠핑을 마친 자리에서 앱이 재시작되면 캐릭터가 캠프 아이콘 위에
        # 서 있어서 필드맵에서 그 아이콘을 확인할 수 없다. 이때는 아이콘 탐색을 포기하고 그냥 나가기
        # 버튼을 눌러 하켄으로 빠져나가면 된다(캠핑은 어차피 필드당 1회라 다시 할 수도 없다).
        if is_camp_branch:
            print("🏕️ [필드맵 귀환] 캠프 아이콘 미검출 - 이미 그 자리에 서 있는 경우로 보고 나가기 버튼으로 진행합니다.")
            return _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                                         t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
        # 🆕 [2026-09-09 사용자 지적 - 비대칭 완치] 하켄 분기도 대칭적으로 나가기 버튼 폴백을 탄다.
        # 상세 사유는 _exit_via_walkout_or_harken() 주석 참고.
        print("🚪 [필드맵 귀환] 하켄 아이콘 미검출 - 나가기 버튼으로 도보 탈출/하켄 귀환을 시도합니다(하켄이 없는 구역 대비).")
        return _exit_via_walkout_or_harken(device, t_move_exit, t_field, t_harken_return,
                                           t_harken_blessing_donothing, t_yeolda)

    # 4. 아이콘 탭 → 자동이동 버튼 확인(전체검색). 가장자리를 탭하면 버튼이 아예 안 뜨므로 재탐색한다.
    tap_x, tap_y = icon_coords
    automove_coords = None
    # 🚨 [2026-09-09] 여기도 스와이프 탐색 루프와 동일한 종류의 결함이 있었다(for range + continue가
    # 인터럽트 처리만으로 예산을 까먹음) - while + 실제 탭했을 때만 증가하는 카운터로 통일. 화살표
    # 폴백도 같은 이유로 억제한다(맵이 아직 열려 있는 상태 - 확장 화면 UI 삼각형 오탐 위험).
    retry = 0
    icon_tap_deadline = time.time() + 60.0
    while retry < 3 and time.time() < icon_tap_deadline:
        print(f"📍 [필드맵 귀환] 목표 아이콘 탭: ({tap_x},{tap_y})")
        safe_device_shell(device, f"input tap {tap_x} {tap_y}")
        time.sleep(0.8)
        raw = capture_screen_bytes(device)
        if not raw:
            continue
        img_np = decode_screen_bytes(raw)
        if _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, None, t_field, t_doghole=t_doghole, t_dilog_bone=t_dilog_bone, t_dilog_oil=t_dilog_oil, t_dilog_elixir=t_dilog_elixir, t_dilog_bonegoblin_name=t_dilog_bonegoblin_name):
            continue
        automove_coords = _find_automove_button(img_np, automove_primary, automove_fallback)
        if automove_coords:
            break
        retry += 1
        print(f"⚠️ [필드맵 귀환] 자동이동 버튼 미검출(가장자리 탭 추정) - 재탐색 {retry}/3")
        icon_coords = _find_first_icon(img_np, target_icons, min_y=FIELDMAP_CAMP_ICON_MIN_Y if is_camp_branch else None)
        if icon_coords:
            tap_x, tap_y = icon_coords
        else:
            safe_device_shell(device, f"input swipe 720 1300 820 1450 300")  # 살짝 안쪽으로 밀어보기
            time.sleep(1.0)

    if not automove_coords:
        # 🚨 [2026-09-09 사용자 지적] 이전엔 여기서 곧장 "failed"를 반환해 TRIGGER_EXIT가 즉시
        # RuntimeError → 프로세스 강제 재시작(ADB 서버 리셋)으로 이어졌다. 사용자 지적: "지금 모든
        # 앵커들이 활성화 잘되어서 붙어있는데" - 즉 연결/화면인식 자체는 멀쩡한데, 아이콘이 상단에
        # 가까워 자동이동 버블이 안 보이는(위 FIELDMAP_CAMP_ICON_MIN_Y로 완치 시도) 것처럼 일시적/
        # 회복 가능한 상황조차 앱 전체 재시작이라는 비싼 복구로 이어지고 있었다. 이미 있는 "retry"
        # 경로(TRIGGER_EXIT의 fieldmap_return_retry_count, 최대 5회)로 돌려보내면 필드맵을 처음부터
        # 다시 열어 재시도하고, 그마저 5회를 넘길 때만 진짜 앱 재시작으로 넘어간다.
        print("⚠️ [필드맵 귀환] 자동이동 버튼을 끝내 찾지 못했습니다 - 필드맵을 다시 열어 재시도합니다.")
        return "retry"

    # 5. 자동이동 탭 → 도착 대기
    safe_device_shell(device, f"input tap {automove_coords[0]} {automove_coords[1]}")
    print(f"🚶 [필드맵 귀환] 자동이동 탭: {automove_coords}")
    time.sleep(2.0)

    arrival_deadline = time.time() + 60.0
    arrived = False
    interrupted = False  # 🚨 중립몹/행상인 조우로 이동이 끊겼는지 - 끊겼다 풀린 뒤에만 재개 버튼을 누른다
                         #    (전투는 여기서 처리하지 않고 "combat"으로 메인 루프에 넘긴다)
    # 🆕 [2026-09-08 사용자 실기 확인] 자동이동을 눌렀다고 실제로 걸어가는 건 아니다. 필드로 돌아온 뒤
    # 압축 미니맵 커서의 "방향"이 바뀌는지로 이동 여부를 판정한다 - 커서의 위치는 미니맵 중앙에 고정이라
    # 위치 추적은 무의미하고(사용자 확인), 직진만 오래 하는 구간은 거의 없어 방향 변화만으로 충분하다.
    # 정지로 판정되면 기존 재개→상자 사다리(resume_or_confirm_chest)를 그대로 태우고, 그 사다리마저
    # "없습니다"로 끝나면 필드맵을 다시 열어 캠핑/하켄 명령을 새로 내린다("retry").
    prev_cursor_dir = None
    last_cursor_change_time = time.time()
    AUTOMOVE_STALL_SECONDS = 15.0
    while time.time() < arrival_deadline:
        raw = capture_screen_bytes(device)
        if not raw:
            time.sleep(1.0)
            continue
        img_np = decode_screen_bytes(raw)

        if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
            # 🚨 여기서도 기다리지 않는다 - 메인 루프의 IN_COMBAT이 전투를 몰아야 자동전투가 깨져도 복구된다.
            print("⚔️ [필드맵 귀환] 자동이동 중 전투 조우 - 메인 루프의 전투 처리로 넘깁니다(전투 종료 후 귀환 재시도).")
            return "combat"

        # 🚨 [2026-09-09 실측 확정 - 화살표가 도착 판정을 가로채는 결함 완치] 이 체크를 예전엔
        # _handle_dungeon_interrupt() 뒤(아래)에 뒀는데, "생명의 우물이 말라버렸다" 화면은 화살표
        # 도장과 0.985로 매칭돼(임계값 0.82 초과) _handle_dungeon_interrupt의 화살표 폴백이 먼저
        # 대화를 넘겨버리고 continue - 그러면 이 도착 체크가 그 프레임에서 아예 실행되지 못했다.
        # 캐릭터는 이미 도착해 있으니 다음 틱에 눌리는 재개 버튼이 같은 자리를 다시 트리거해
        # "우물이 말라버렸다"가 또 뜨고, 이 사이클이 무한 반복됐다(실전 로그 2026-09-09 17:56 -
        # "화살표 감지"와 "인터럽트 종료 - 재개 버튼" 쌍이 8회 연속). "도착했는가"는 "그냥 화살표니까
        # 넘긴다"보다 우선순위가 높아야 하므로, 인터럽트 처리보다 먼저 체크한다.
        if is_camp_branch and (find_and_get_coords(img_np, t_camp_rest1, 0.70)
                                or check_template_present(img_np, t_camp_dry, 0.70)):
            arrived = True
            break

        if _handle_dungeon_interrupt(device, img_np, t_dilog_fight, t_seller_label, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow, t_field, t_doghole=t_doghole, t_dilog_bone=t_dilog_bone, t_dilog_oil=t_dilog_oil, t_dilog_elixir=t_dilog_elixir, t_dilog_bonegoblin_name=t_dilog_bonegoblin_name):
            interrupted = True  # 조우 처리 후에도 자동이동이 끊겼을 수 있으니 재개 버튼 대상으로 취급
            last_cursor_change_time = time.time()  # 조우 처리에 쓴 시간은 정지 시간으로 치지 않는다
            continue

        # 🆕 이동 여부 판정 - 필드 위(커서 검출)일 때만 의미가 있다
        cursor_dir = get_minimap_cursor_direction(img_np, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right)
        if cursor_dir is not None:
            if prev_cursor_dir is None or cursor_dir != prev_cursor_dir:
                prev_cursor_dir = cursor_dir
                last_cursor_change_time = time.time()
            elif time.time() - last_cursor_change_time >= AUTOMOVE_STALL_SECONDS:
                print(f"🧭 [필드맵 귀환] 커서 방향이 {AUTOMOVE_STALL_SECONDS:.0f}초간 그대로 - 자동이동 정지로 판정, 재개 사다리를 태웁니다.")
                if resume_or_confirm_chest(device, img_np, t_move_resume_act, t_move_resume_deact,
                                           t_move_chest_act, t_move_chest_deact, t_no_chest):
                    print("🔁 [필드맵 귀환] 재개/상자 모두 '없습니다' - 필드맵을 다시 열어 명령을 새로 내립니다.")
                    return "retry"
                last_cursor_change_time = time.time()  # 사다리를 태웠으니 정지 시계를 다시 시작
                continue

        if not is_camp_branch:
            # 🚨 캠핑 분기의 도착 판정은 위(전투 체크 직후)로 옮겼다 - 화살표 폴백에 가로채이지 않도록.
            # 여기서는 하켄 분기(교회구역)만 처리한다.
            menu_state = check_and_handle_harken_menu(device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda)
            if menu_state == "returned":
                print("✅ [필드맵 귀환] 하켄 '귀환' 클릭 완료.")
                return "returned"
            if menu_state == "blessing":
                # 🚨 가호 팝업은 "처리했을 뿐" 아직 귀환한 게 아니다 - 팝업을 닫은 뒤 귀환 목록이 다시
                # 뜨므로 루프를 계속 돈다(trigger_harken_escape의 기존 처리와 동일한 방침).
                print("🎁 [필드맵 귀환] 하켄의 가호 팝업 처리 완료 - 귀환 목록을 계속 기다립니다.")
                time.sleep(1.0)
                continue

        # 🚨 [2026-09-07 재개 남발 방지] 원래는 매 틱(2초)마다 재개 버튼을 눌렀는데, 재개 버튼은 필드에
        # 항상 떠 있어(활성/비활성 도장 둘 다 찾음) 자동이동이 정상 진행 중일 때도 계속 눌러버렸다.
        # 재개는 "직전 이동 명령"을 다시 거는 버튼이라 자동이동을 엉뚱한 목적지로 되돌릴 수 있다.
        # 사용자 지침대로 "전투/행상인 등으로 이동이 끊겼다가 풀린 직후"에만 1회 누른다.
        if interrupted:
            resume_coords = find_checkpoint_btn_coords(img_np, t_move_resume_act, t_move_resume_deact, 0.70)
            if resume_coords:
                print(f"🔁 [필드맵 귀환] 인터럽트 종료 - 재개 버튼으로 자동이동을 이어갑니다: {resume_coords}")
                safe_device_shell(device, f"input tap {resume_coords[0]} {resume_coords[1]}")
            interrupted = False
        time.sleep(2.0)

    if is_camp_branch and not arrived:
        # 🚨 [2026-09-09 실전 확인] 예전엔 여기서 곧장 실패 처리(→ 앱 강제 재시작)했다. 그런데 이미
        # 캠프사이트 위/앞에 서 있는 상태에서 자동이동을 누르면 갈 곳이 없어 아무 화면 전환도 없고,
        # 60초를 통째로 버린 뒤 앱을 재시작하는 최악의 흐름이 됐다(실전 로그 00:21~00:22). 캠핑은
        # 필드당 1회뿐이라 여기서 더 시도할 실익도 없으니, 아이콘 미검출 케이스와 동일하게 나가기
        # 버튼 → 하켄 경로로 넘어간다.
        print("⚠️ [필드맵 귀환] 캠핑 지점 도착을 확인하지 못했습니다(60초 초과) - 이미 캠핑했거나 그 자리에 서 있는 경우로 보고 나가기 버튼으로 진행합니다.")
        return _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                                     t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)

    # 6. 캠핑 분기: 휴식 시퀀스(필드 복귀까지 확인해줌) → 캠핑 이후 공통 꼬리
    if is_camp_branch:
        if not perform_camping_rest(device, t_camp_rest1, t_camp_rest2, t_dialogue_arrow, t_field, t_camp_dry=t_camp_dry):
            return "failed"
        return _return_after_camping(device, return_method, t_move_exit, t_field, t_harken_return,
                                     t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)

    # 7. 하켄 메뉴 처리 - "harken_only"가 위 도착 대기에서 하켄 메뉴를 못 잡고 타임아웃했을 때의 폴백
    # (trigger_harken_escape가 자체 재시도/나가기 재탭을 갖고 있음).
    return "returned" if trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda) else "failed"

def fire_target_monster_body(device, img_np, t_next, t_arrow):
    target_coords = find_and_get_coords(img_np, t_next, 0.65)
    if target_coords:
        body_x = target_coords[0]
        body_y = target_coords[1] + 260
        print(f"      🎯 [몸통 저격] 적 'NEXT' 마크 기반 Daphne 공식 사격! 수치: ({body_x}, {body_y})")
        safe_device_shell(device, f"input tap {body_x} {body_y}")
        return True
        
    target_coords = find_and_get_coords(img_np, t_arrow, 0.60)
    if target_coords:
        body_x = target_coords[0]
        body_y = target_coords[1] + 130
        print(f"      🎯 [몸통 저격] '▼(적 화살표)' 마크 기반 Daphne 공식 사격! 수치: ({body_x}, {body_y})")
        safe_device_shell(device, f"input tap {body_x} {body_y}")
        return True
        
    print("      ⚠️ 타깃 인디케이터 인식 지연! 적 배치 중앙 안전 가드 스팟 강제 사격.")
    safe_device_shell(device, "input tap 720 1300") 
    return True



def start_main_macro(device, run_skill_logic=False, healing_loops=1, heal_after_chest=True, healer_slot=5, masked_adventurer_slot=5, chest_opener_slot=6, farming_method="상자파밍", dungeon_name="일반 던전", from_dungeon_select=False, dungeon_floor_name=None, return_method="exit_button"):
    # - farming_method: "상자파밍"(범용 상자 순회 방식) 또는 "광석파밍"(FFXI 유령선 전용)
    # - dungeon_name: "북쪽의 유령선"과 같이 특수 던전 제어 구분을 위함 (일반 상자파밍 던전은 범용 로직 공유)
    if not device: return False, False, False

    print("\n=======================================")
    print("🎨 [dungeon_bot] 코어 마스크 도장을 로드합니다...")
    # 🗺️ [1.14.1 버전 신규 필드 UI 템플릿 연동부]
    t_field = load_grayscale_template("templates/Field/field_anchor.png")
    t_open_minimap = load_grayscale_template("templates/Field/open_minimap.png")
    t_move_exit = load_grayscale_template("templates/Field/exit_dungeon.png")
    # 🚨 [2026-08-27 하켄 메뉴 판정 여유 확보] check_and_handle_harken_menu()가 이 도장을
    # check_template_present()(라이브 화면 이진화 160 후 비교)로 매칭하는데, 도장 자체는 원본
    # 그레이스케일로 로드돼 있어 "이진화 화면 vs 비이진화 도장" 불일치가 있었음. 실측(2026-08-27,
    # 하켄 사당 화면): 현재 방식 0.786(통과선 0.70, 여유 0.086) vs 도장도 이진화 시 0.997(여유 0.30).
    # 아직 통과는 했지만 여유가 얇아 조명/압축 조건에 따라 실패할 수 있어 다른 도장들과 동일하게
    # load_template(이진화)로 통일한다.
    t_harken_blessing_donothing = load_template("templates/Field/harken_blessing_donothing.png")
    
    t_move_chest_act = load_grayscale_template("templates/Field/chest_act.png")
    t_move_chest_deact = load_grayscale_template("templates/Field/chest_deact.png")
    t_move_check_act = load_grayscale_template("templates/Field/check_act.png")
    t_move_check_deact = load_grayscale_template("templates/Field/check_deact.png")
    
    t_move_resume_act = load_grayscale_template("templates/Field/resume_act.png")
    t_move_resume_deact = load_grayscale_template("templates/Field/resume_deact.png")
    t_no_chest = load_template("templates/Field/toastmsg_nochest.png")
    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_dialogue_indicator = load_template("templates/chestopening/dialogue_indicator.png")

    # 🆕 [2026-09-08 대설지대] 중립몹 조우 / 행상인 조우 인터럽트 핸들러용 도장 - 다른 던전은
    # dungeon_name == "대설지대" 조건에서만 실제로 참조되므로 로드만 해도 영향 없음.
    t_dilog_fight = load_template("templates/Dungeon_dialogue/Dun_dilog_fight.png")
    t_seller_label = load_template("templates/Dungeon_dialogue/Dun_seller_label.png")
    t_seller_let_me_see = load_template("templates/Dungeon_dialogue/Dun_seller_let_me_see.png")
    t_seller_hammer = load_template("templates/Dungeon_dialogue/Dun_seller_hammer.png")
    t_doghole_common = load_template("templates/Dungeon_dialogue/Dun_HS6_doghole.png")  # "울타리 구멍으로 빠져나간다"
    t_dilog_bone_common = load_template("templates/Dungeon_dialogue/Dun_dilog_bone.png")  # "뼈상인" 1순위: "모험가의 뼈"
    t_dilog_oil_common = load_template("templates/Dungeon_dialogue/Dun_dilog_oil.png")  # "뼈상인" 2순위: "기름"
    t_dilog_elixir_common = load_template("templates/Dungeon_dialogue/Dun_dilog_elixir.png")  # "뼈상인" 3순위: "비약"
    t_dilog_bonegoblin_name_common = load_template("templates/Dungeon_dialogue/Dun_dilog_bonegoblin_name.png")  # 비약 오탐 방지용 화자명 가드
    t_dialogue_arrow_common = load_template("templates/inn_sleep/arrow_clean.png")
    # 🚨 [2026-09-08 실전 확인] 캠핑 선택창("쉰다"/"아무것도 안 한다")은 필드 앵커도 전투 앵커도 없어서,
    # 귀환 루틴 밖에서 이 화면을 만나면 공용 전처리 블록이 "화면 과도기"로 오판하고 30초 뒤 비상
    # 뒤로가기를 주입해 캠핑을 취소해버렸다(실전 로그 23:30). 루틴이 전투로 메인 루프에 제어를 넘긴 사이
    # 캐릭터가 캠프에 도착하면 반드시 이 상황이 되므로, 공용 블록에서도 캠핑을 처리해야 한다.
    t_camp_rest1_common = load_template("templates/Dungeon_dialogue/Dun_camping_rest.png")
    t_camp_rest2_common = load_template("templates/Dungeon_dialogue/Dun_camping_rest2.png")
    t_camp_dry_common = load_template("templates/Dungeon_dialogue/Dun_camping_dry.png")
    # 눈보라 판별(미니맵 확장 여부)용
    t_field_expanded_common = load_grayscale_template("templates/Field/Fieldmap_exit_icon.png")
    t_fieldmap_close_common = load_grayscale_template("templates/Field/FieldMap_Anchor.png")
    reset_camping_done()  # 이번 던전 진입 기준으로 캠핑 완료 플래그 초기화(중복 캠핑 방지)
    t_cursor_up = load_grayscale_template("templates/Field/cursor_up.png")
    t_cursor_down = load_grayscale_template("templates/Field/cursor_down.png")
    t_cursor_left = load_grayscale_template("templates/Field/cursor_left.png")
    t_cursor_right = load_grayscale_template("templates/Field/cursor_right.png")

    t_heal_auto = load_template("templates/healer_auto_btn.png")
    t_heal_confirm = load_template("templates/confirm_recover.png")
    t_heal_close = load_template("templates/close_panel.png")
    # 🆕 [2026-09-11] close_panel.png는 "X" 위에 "닫기"가 세로로 쌓인 레이아웃인데, 캐릭터 상태/버프
    # 팝업(전투 중 인물 아이콘 탭 시 뜨는 것)은 "X 닫기"가 가로로 나란한 다른 레이아웃을 쓴다(실측:
    # 실전 정체 스크린샷에서 close_panel.png 점수 0.586로 임계값 0.70 미달 - 조용히 놓쳤을 것). 실제
    # 스크린샷에서 새로 크롭해 별도 도장으로 분리, 같은 스크린샷에서 1.000으로 확인.
    t_close_inline = load_template("templates/close_panel_inline.png")

    # 🆕 [2026-09-12 실전 확인, 재크롭 후 검증 완료] 파티창의 사망(해골) 아이콘 - "빈사"(HP 낮음,
    # 힐로 해결)와 "사망"(HP 0, 힐로 절대 안 풀림)을 구분하려고 추가. 사용자가 처음 준 크롭
    # (stat_dead.png, 세션종료 화면이라 흐릿함 + 슬롯 좌표도 잘못돼 있었음)은 폐기하고, 정상 조명의
    # 필드 화면에서 새로 크롭한 도장(당시 파일명 dead_inField.png)으로 교체해
    # FIELD_PARTY_SLOT_ROIS(올바른 필드 HUD 좌표)와 짝을 맞춰 재검증하니 정탐 0.999~1.000 vs 오탐
    # 최고 0.585로 깨끗하게 분리됨(상세는 find_dead_slots() 주석). 이후 전투 화면(사망-컴뱃.png)에도
    # 같은 도장+같은 좌표로 0.9785(1번 슬롯)로 잘 걸림을 추가 확인 - 상자 캐릭선택 화면 전용
    # dead_chest.png(그 화면만 아이콘이 더 작게 렌더링돼 크기가 다름, 35x39 vs 43x49)는 지금 사망
    # 판정을 아예 안 하는 화면이라 불필요 판단, 사용자 확인 후 dead_inCombat.png와 함께 삭제하고
    # 이 도장 하나만 `dead_stat.png`로 정식 명명해 남겼다(필드/전투 공용으로 검증 완료).
    t_stat_dead = load_grayscale_template("templates/Field/dead_stat.png")

    t_combat_in = load_grayscale_template("templates/combat_in.png")
    t_combat_slow = load_grayscale_template("templates/combat_slow.png") 
    t_auto_off = load_grayscale_template("templates/auto_off.png")     
    t_auto_on = load_grayscale_template("templates/auto_on.png")       
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    
    if dungeon_name == "북쪽의 유령선":
        t_dungeon_sel = load_template("templates/FFXI/FFXI_dungeon_Anchor.png")
    else:
        t_dungeon_sel = load_template("templates/WolfCave/dungeon_select.png")
        
    # 📂 [v1.17.0 FFXI 광석 채굴용 전용 템플릿 로딩]
    t_mining_ready = load_color_template("templates/FFXI/mining_ready.png")
    t_mining_done = load_color_template("templates/FFXI/mining_done.png")
    t_mining_get = load_color_template("templates/FFXI/mining_get.png")
    t_need_pickaxe = load_color_template("templates/FFXI/need_pickaxe.png")
    t_harken_return = load_color_template("templates/FFXI/harken_return.png")
    
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    t_incombat_dead = load_template("templates/InCombat_dead.png")
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_err_retry = load_template("templates/Error_retry.png")
    t_err_to_title = load_template("templates/Error_to_title.png")
    
    t_sc_cheonja = load_template("templates/shortcut_cheonja_core.png") 
    t_btn_lvl_ok = load_template("templates/btn_level_confirm.png")      
    t_btn_lvl1 = load_template("templates/btn_level_1.png")         
    t_btn_lvl1_atv = load_template("templates/btn_level_1_atv.png") 
    
    t_sc_jeongmil = load_template("templates/shortcut_jeongmil.png")    
    t_sc_ttang = load_template("templates/shortcut_ttang.png")          
    
    t_next = load_template("templates/indicator_next.png")              
    t_arrow = load_template("templates/indicator_arrow.png")

    print("=======================================")

    transition_delay_count = 0
    state = "FIELD_WAIT"
    last_click_time = 0 
    came_from_combat = False 
    event_counter = 0
    
    last_state_changed_time = time.time()
    previous_state = "FIELD_WAIT"
    exit_start_time = 0
    prev_minimap_zone = None
    # 🚨 [2026-08-21 무한 정체 탈출 결함 완치] 아래 '일반 정체 복구' 블라인드 뒤로가기 전용 페이싱 타이머.
    # 실전 확인(2026-08-21 03:38~07:15, 3시간 37분): 이 블라인드 포크가 last_state_changed_time을 같이
    # 리셋해버려서 5분 하드 리밋이 영원히 도달 못 하는 결함이 있었음(상세는 아래 해당 분기 주석 참고).
    last_blind_poke_time = 0
    
    global need_heal, came_from_chest
    need_heal = False
    came_from_chest = False
    low_threshold_active_until = 0.0
    low_threshold_reset_count = 0
    # 🆕 [2026-09-12 실전 확인] 빈사(딸피) 픽셀 카운터가 "사망"과 "빈사"를 구분 못 해, 실제로 죽은
    # 캐릭터가 있으면 힐을 아무리 넣어도 위험색이 안 사라져 정비를 무한 재격발하던 결함(실전 로그:
    # 12시간 동안 힐-재감지만 반복하다 게임 세션이 시간초과로 끊김) 완치용 플래그. 사망을 한 번
    # 확인하고 나면, 그 뒤로는 같은 빈사 신호를 다시 힐 트리거로 쓰지 않는다(예전처럼 사망자를 달고
    # 그냥 주회를 계속한다) - 상세는 "2-1. 빈사 감지" 분기 주석 참고.
    death_confirmed_and_handled = False
    
    # 💡 [반응형 이동 및 즉시 복귀 상태 변수]
    last_target_coords = None
    exit_stuck_count = 0
    exit_prev_minimap = None
    # 🚨 [2026-08-29 유령성4층 경로없음 스와이프 오발동 완치] '없습니다' 토스트 템플릿(toastmsg_nochest.png)이
    # "상자가 없습니다"와 "경로를 찾을 수 없습니다" 두 메시지에 공용으로 쓰이는데(임계값 0.55로 느슨하게 매칭),
    # 정체 1회차 복구(상자 단추 연타)가 유발한 '상자 없음' 토스트를 다음 틱에서 '경로 없음'으로 오인해 불필요한
    # 전진 스와이프가 나가버리는 결함이 있었음(사용자 실기 확인: "상자누르고 없습니다 떠도 위로 스와이프 한 번
    # 하는데 이거 쓸모없다"). 마지막으로 누른 단추가 '출구'였을 때만 이 토스트를 '경로 없음'으로 해석한다.
    # 🚨 [2026-08-29 재발 완치] 기본값을 True로 뒀더니, TRIGGER_EXIT 최초 진입 시(아직 출구를 한 번도 안
    # 누른 시점)에 직전 FIELD_WAIT의 '상자 없음' 재시도 토스트 잔상을 '경로 없음'으로 오인해 출구 탭보다
    # 먼저 스와이프가 나가는 재발이 있었음(실기 로그 확인: 2026-08-29 15:35:35, 첫 출구 탭은 15:35:42).
    # 출구 버튼을 실제로 한 번이라도 눌러야만 이 체크가 켜지도록 기본값을 False로 정정한다.
    exit_last_action_was_exit_tap = False

    yuzuna_done = False
    milana_done = False
    guksu_done = False 
    
    auto_combat_paused_for_skill = False
    skill_mission_success_this_combat = False
    combat_entry_start_time = time.time()
    last_combat_color_check_time = 0
    
    last_empty_shortcut_detected_time = 0
    continuous_heal_retry_count = 0
    yeolda_stuck_retry_count = 0
    exit_clicked_once = False
    exit_first_start_time = None
    exit_recovery_retry_count = 0
    # 🚨 [2026-08-12 워치독 단축] 기존 5분(300초)은 실전 감각상 너무 길다는 피드백 - 채굴(광석파밍)은
    # 복귀 동선이 짧아 1분30초, 그 외(상자파밍 등 백아류)는 동선이 더 길 수 있어 3분으로 구분.
    exit_watchdog_seconds = 90.0 if farming_method == "광석파밍" else 180.0
    minimap_expanded = False
    checkpoint_pressed_count = 0
    is_initial_start = True
    blizzard_exit_tapped = False  # 🆕 [2026-09-08 대설지대] 눈보라 서브구역에서 나가기를 이미 눌렀는지
    # 🚨 [2026-09-09] "커서 미검출"이 눈보라인지, 아이콘에 가려진 것인지의 판정 상태.
    # "unknown"=아직 안 봄 / "yes"=눈보라 확정(필드맵 확장 실패) / "no"=눈보라 아님(확장 성공).
    # 커서가 다시 보이면 "unknown"으로 되돌린다. 판별은 미니맵을 눌러 확장되는지로 한다(사용자 확인:
    # 눈보라 구간은 필드맵 확장 자체가 안 된다).
    blizzard_state = "unknown"
    # 🆕 [2026-09-15] "재개를 눌러도 30초 넘게 안 풀리면 나가기로 전환"용 타이머 2종. 실전 사고
    # (2026-09-14 22:30~22:43+, 13분+ 재개만 무한 반복)의 원인은 재개 버튼이 실제로는 비활성인데
    # 활성/비활성 구분이 안 돼 계속 눌리기만 하고 게임 쪽 반응(토스트조차)이 아예 없었던 것으로 추정-
    # 토스트 감지에만 의존하던 기존 나가기 트리거를 시간 기반으로 보강한다.
    blizzard_resume_start_time = None  # 이 시각부터 30초 카운트. 전투 등으로 이 분기를 벗어났다 돌아오면
                                        # (아래 blizzard_last_tick_time과의 간격으로 감지) 새로 잰다 -
                                        # 전투만으로도 30초를 넘길 수 있어 그 시간을 억울하게 합산하지
                                        # 않기 위함(사용자 확정).
    blizzard_last_tick_time = None
    # 🆕 [2026-09-08] 필드맵 귀환 "retry"(자동이동 정지 → 재개/상자 사다리도 소득 없음 → 필드맵 재확장)
    # 예산. 이 경로는 TRIGGER_EXIT의 기존 탈출 워치독(exit_first_start_time)을 타지 않아서 자체 상한이
    # 없으면 무한히 재확장만 반복할 수 있다.
    fieldmap_return_retry_count = 0
    FIELDMAP_RETURN_RETRY_LIMIT = 5
    prev_cursor_dir = None  # 🆕 [2026-09-08 대설지대] 커서 기반 이동감지용 직전 방향
    need_pickaxe_refill = False  # 💡 [광석파밍 전용] 곡괭이 소진으로 탈출한 경우에만 True. 사령탑이 이 플래그로만 마을 회군 여부를 판단합니다.

    cap_fail_counter = 0
    resolution_fail_counter = 0  # 🚨 [v1.14.0-hotfix3] 해상도 미달 가드 연속 카운터 추가
    while True:
        current_time = time.time()
        if current_time < low_threshold_active_until:
            field_threshold = 0.45
            combat_threshold = 0.50
            yeolda_threshold = 0.45
        else:
            field_threshold = 0.65
            combat_threshold = 0.80
            yeolda_threshold = 0.65

        try:
            import sys
            if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'update_heartbeat'):
                sys.modules['__main__'].update_heartbeat()
        except:
            pass

        try:
            raw_cap = capture_screen_bytes(device)
            if raw_cap is None: raise RuntimeError("Screencap returned None")
            img_np = decode_screen_bytes(raw_cap)
            cap_fail_counter = 0
        except Exception as cap_err:
            cap_fail_counter += 1
            print(f"\n🌐⚠️ [dungeon_bot 캡처 실패] 실시간 캡처 유실!! 오류: {cap_err} ({cap_fail_counter}/5)")
            if cap_fail_counter >= 5:
                raise cap_err
            time.sleep(0.5)
            continue

        height, width = img_np.shape[:2]
        if height < 2560 or width < 1440:
            resolution_fail_counter += 1
            print(f"⚠️ [dungeon_bot 해상도 미달 가드] 현재 화면 크기({width}x{height})가 기준 해상도(1440x2560) 미만입니다. 1.0초 대기합니다. ({resolution_fail_counter}/30)")
            if resolution_fail_counter >= 30:
                raise RuntimeError(f"dungeon_bot 내 해상도 미달 상태 30초 지속 감지 (화면 크기: {width}x{height})")
            time.sleep(1.0)
            continue
        else:
            resolution_fail_counter = 0  # 정상 해상도 검출 시 카운터 리셋

        mean_brightness = np.mean(img_np)
        if mean_brightness < 5.0:
            print("⏳ [dungeon_bot 로딩 가드] 화면 전환/로딩 중(암전) 포착! 0.5초 대기 후 재스캔합니다.")
            time.sleep(0.5)
            continue
        is_poisoned = False

        if check_template_present(img_np, t_dungeon_sel, 0.70):
            print("🚪 [dungeon_bot] 현실 화면이 '던전 선택창'으로 식별되었습니다! 사령탑으로 즉시 퇴장합니다.")
            return False, skill_mission_success_this_combat, need_pickaxe_refill

        # 🚨 [v1.14.1-hotfix11] 재부팅/최초 기동 시 던전 내부인 경우 즉시 던전 밖으로 탈출
        if farming_method == "광석파밍" and (not from_dungeon_select) and is_initial_start:
            if check_field_anchor_present(img_np, t_field, field_threshold):
                print("🚨 [최초 기동 감지] 던전 선택창을 거치지 않고 던전 내부에서 시작된 것이 포착되었습니다! 안전한 순회를 위해 즉시 하켄 탈출을 단행합니다.")
                is_initial_start = False
                exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                if exit_coords:
                    print(f"👉 [출구이동] 미니맵 2번 단추 터치 ({exit_coords[0]}, {exit_coords[1]})")
                    safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                else:
                    safe_device_shell(device, "input tap 1140 572")
                
                last_state_changed_time = time.time()
                trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
                last_state_changed_time = time.time()
                return False, skill_mission_success_this_combat, need_pickaxe_refill

        # 🚨 [2026-08-27 유령성 4층 상자파밍 신규 진입 시퀀스] 4층은 던전선택 층 버튼이 없어(자동이동 버그로 한 번에
        # 못 감), 3층(floor="3rd")으로 진입한 뒤 미니맵 체크포인트 이동 + 수동 스와이프(좌→상×2)로 걸어서 4층
        # 문을 통과해야 함. 실기 검증 완료(2026-08-27, 사용자와 함께 라이브 ADB로 좌표/스와이프 순서 확정): 체크포인트
        # 버튼 탭 → 좌스와이프(방향 전환) → 상스와이프 ×2(전진 2칸) → 검은 로딩 화면(과도기, 위 mean_brightness<5.0
        # 가드가 이미 처리) → 4층 필드 도착(도착 직후 바로 전투 조우 가능 - 정상). from_dungeon_select일 때만
        # 발동시켜(재시작 중 이미 4층 안에 있는 경우 재발동해 엉뚱하게 또 이동하는 사고 방지) 최초 1회만 실행한다.
        if dungeon_name == "북쪽의 유령선" and farming_method == "상자파밍" and from_dungeon_select and is_initial_start:
            if check_field_anchor_present(img_np, t_field, field_threshold):
                print("🚪 [유령성 4층 진입] 3층 필드 도착 확인 - 체크포인트 이동 + 스와이프로 4층 진입을 시도합니다.")
                # 🚨 [2026-09-05 화면 과도기 카운터 미리셋 완치] 아래 공용 전처리 블록(check_field_anchor_present
                # 성공 시 transition_delay_count = 0)과 달리 이 블록은 3층 필드 도착이라는 명백한 "화면 안착"
                # 이벤트를 감지하고도 카운터를 리셋 안 하고 있었음 - 그 결과 3층 로딩 대기(1~4)에 이어 4층
                # 로딩 대기가 1부터 다시 시작하지 않고 5~8로 누적되던 결함(사용자 실기 확인: "화면과도기 감지가
                # 초기화가 안된다"). 서로 독립된 두 번의 정상 로딩을 하나의 10회 예산으로 합쳐 세는 셈이라,
                # 실제로는 각각 문제없는 로딩인데도 예산이 조기 소진돼 "길 잃음 복구"가 잘못 격발될 위험이
                # 있었음. 공용 블록과 동일하게 여기서도 리셋한다.
                transition_delay_count = 0
                is_initial_start = False
                check_coords = find_checkpoint_btn_coords(img_np, t_move_check_act, t_move_check_deact, 0.70)
                if check_coords:
                    print(f"      👉 [체크포인트] 버튼 탭 ({check_coords[0]}, {check_coords[1]})")
                    safe_device_shell(device, f"input tap {check_coords[0]} {check_coords[1]}")
                else:
                    print("      ⚠️ [체크포인트] 버튼 미검출. 실측 고정 좌표(1210, 578)로 강제 탭합니다.")
                    safe_device_shell(device, "input tap 1210 578")
                time.sleep(3.0)

                h_e, w_e = img_np.shape[:2]
                scale_x, scale_y = w_e / 1440.0, h_e / 2560.0
                print("      👉 [4층 진입] 좌측 스와이프(방향 전환)")
                safe_device_shell(device, f"input swipe {int(1000*scale_x)} {int(1400*scale_y)} {int(400*scale_x)} {int(1400*scale_y)} 300")
                time.sleep(1.0)
                for _ in range(2):
                    print("      👉 [4층 진입] 전진 스와이프(1칸)")
                    safe_device_shell(device, f"input swipe {int(720*scale_x)} {int(1500*scale_y)} {int(720*scale_x)} {int(900*scale_y)} 300")
                    time.sleep(1.5)

                last_state_changed_time = time.time()
                continue

        # 🌐 [통합 네트워크 에러 감시 가드]
        if check_template_present(img_np, t_err_retry, 0.70):
            print("🌐⚠️ [네트워크 가드] 'Error_retry.png' 포착! 즉시 재시도 터치를 주입합니다.")
            if find_and_click_template_in_bot(device, img_np, t_err_retry, 0.70):
                time.sleep(3.0)
                last_state_changed_time = time.time()
                continue
                
        if check_template_present(img_np, t_err_to_title, 0.70):
            raise RuntimeError("Error_to_title.png 검출로 인한 강제 앱 리부트 요구")

        if check_template_present(img_np, t_net_error, 0.75):
            print("🌐 [인게임 통신 가드] 네트워크 팝업 포착!! 즉시 재시도 처리를 단행합니다.")
            net_coords = find_and_get_coords(img_np, t_net_retry, 0.70)
            if net_coords: safe_device_shell(device, f"input tap {net_coords[0]} {net_coords[1]}")
            else: safe_device_shell(device, "input tap 1380 1720") 
            time.sleep(4.0)
            last_state_changed_time = time.time()
            continue

        if state == previous_state:
            stuck_duration = time.time() - last_state_changed_time
            stuck_limit = 180.0 if state == "IN_COMBAT" else 30.0
            
            # 🚨 [v1.13.20-hotfix4] 60초 이상 앵커 미인식 정체 시 임계값 하향 완화 검증
            if stuck_duration >= 60.0 and current_time >= low_threshold_active_until:
                temp_thresh_f = 0.45
                temp_thresh_c = 0.50
                temp_thresh_y = 0.45
                
                field_matched_low = check_field_anchor_present(img_np, t_field, temp_thresh_f)
                combat_matched_low = check_combat_template_present(img_np, t_combat_in, temp_thresh_c) or check_combat_template_present(img_np, t_combat_slow, temp_thresh_c)
                yeolda_matched_low = check_template_present_dynamic(img_np, t_yeolda, temp_thresh_y, 160)
                
                if field_matched_low or combat_matched_low or yeolda_matched_low:
                    print(f"🚨 [정체 탈출 가드] 임계값 0.45 완화 시 앵커 매칭 성공! (필드:{field_matched_low}, 전투:{combat_matched_low}, 상자:{yeolda_matched_low})")
                    # 🚨 [2026-09-16 재설계] 예전엔 이 완화 매칭이 성공할 때마다 최대 3회까지 "빈사(딸피)
                    # 장막"으로 간주해 힐 재시도 + 타이머 리셋을 반복했다. 사용자 지적: 힐링을 세 번씩이나
                    # 할 필요는 없다 - 한 번 힐링하고 돌아왔는데도 또 같은 완화 매칭이 걸린다면, 그건 이미
                    # 진짜 빈사가 아니라 다른 원인(예: 완화 임계값 0.45가 전혀 무관한 화면에서 우연히
                    # 걸린 오탐)일 가능성이 높다. 그래서 힐 시도는 1회로 줄이고, 그 이후엔 힐 대신 곧장
                    # 나가기 버튼을 눌러 던전을 이탈 시도한다(대설지대 눈보라구간에 적용한 것과 동일한
                    # "안 되면 나가기" 패턴을 이 공용 블록에도 적용 - 모든 던전이 공유하는 t_move_exit
                    # 도장을 그대로 재사용하므로 던전 종류를 안 가림). check_field_anchor_present()/
                    # check_combat_template_present()는 둘 다 작은 고정 ROI(우상단 필드앵커, 좌상단 배속
                    # 버튼)만 크롭해서 매칭하므로 전체화면 오탐 위험은 이미 낮지만(사용자 확인: "필드앵커의
                    # roi값 지정하고 그랬던 것" 그대로), 그래도 완전히 무관한 화면에서 그 좁은 영역만
                    # 우연히 걸릴 가능성 자체는 남아있어 이 안전장치가 여전히 필요하다.
                    low_threshold_active_until = current_time + 60.0
                    if low_threshold_reset_count < 1:
                        need_heal = True
                        last_state_changed_time = current_time  # 정체 타이머 리셋
                        low_threshold_reset_count += 1
                        print(f"🔴 빈사(딸피) 장막 간섭 판정: 완화 모드 리셋 적용 ({low_threshold_reset_count}/1) - 힐링 1회 시도 후에도 또 걸리면 진성 정체로 간주해 나가기를 시도합니다.")
                    else:
                        need_heal = False  # 더 이상 빈사로 보지 않음 - 힐 재시도 대신 탈출 시도로 전환
                        print("🔴 빈사(딸피) 완화 리셋 한계(1회) 도달! 힐링으로도 안 풀리는 진성 정체로 판단해 나가기 버튼을 시도합니다.")
                        exit_coords_lowthresh = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                        if exit_coords_lowthresh:
                            print(f"🚪 [정체 탈출 가드] 나가기 버튼 탭: {exit_coords_lowthresh}")
                            safe_device_shell(device, f"input tap {exit_coords_lowthresh[0]} {exit_coords_lowthresh[1]}")
                            time.sleep(1.5)
                        else:
                            print("🚪 [정체 탈출 가드] 나가기 버튼 미검출 - 다음 정체 사이클(60초 후)에 재시도합니다.")
                        continue  # 위에서 이미 조치했으므로 아래 블랙박스 경고/KEYCODE_BACK과 중복 작동하지 않도록 다음 틱으로.

            if stuck_duration > stuck_limit:
                if state == "TRIGGER_EXIT":
                    last_state_changed_time = time.time()
                    continue
                stuck_time_str = datetime.datetime.fromtimestamp(last_state_changed_time).strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n⚠️ [🚨 블랙박스 경고] 현재 던전봇이 '{state}' 상태로 정체 중... (정체 시작: {stuck_time_str}, 경과: {int(stuck_duration)}초)")
                
                # 🛑 [v1.13.5 추가] 일반 상태 5분 이상 정체 시 자동 재부팅 세이프티 가드
                if stuck_duration >= 300.0:
                    raise RuntimeError(f"던전 필드 정체 한계 초과: '{state}' 상태로 {int(stuck_duration)}초간 정체되어 강제 앱 재시작을 수행합니다.")
                
                if state == "TRIGGER_EXIT":
                    print("🚪🚨 [탈출 정체 복구 시스템 작동] 던전 출구에서 30초간 정체 감지! 회군을 시작합니다.")
                    chk_coords = find_checkpoint_btn_coords(img_np, t_move_check_act, t_move_check_deact, 0.70)
                    if chk_coords:
                        cx, cy = chk_coords
                        print(f"📍 [체크포인트] 3번 버튼 검출 성공 ({cx}, {cy}) 터치하여 안전 지대로 회군합니다.")
                        safe_device_shell(device, f"input tap {cx} {cy}")
                    else:
                        print("📍 [체크포인트] 3번 버튼 미검출. 기본 고정 좌표(1215, 572)로 강제 사격합니다.")
                        safe_device_shell(device, "input tap 1215 572")
                    
                    print("⏳ 회군 연출 및 위치 재조정을 위해 4.0초간 제어를 홀딩합니다...")
                    time.sleep(4.0)
                    
                    state = "FIELD_WAIT"
                    last_state_changed_time = time.time()
                    continue
                
                # [독 치료 복구 가드는 1.14.1-hotfix7에서 탈거되었습니다]

                if check_template_present(img_np, t_dungeon_sel, 0.70): return False, skill_mission_success_this_combat, need_pickaxe_refill
                
                close_coords_bot = find_and_get_coords(img_np, t_heal_close, 0.70)
                if close_coords_bot:
                    safe_device_shell(device, f"input tap {close_coords_bot[0]} {close_coords_bot[1]}")
                    time.sleep(1.5)
                    state = "FIELD_WAIT"
                    last_state_changed_time = time.time()
                    continue
                
                if get_dead_match_score(img_np, t_anchor_dead) > 0.65:
                    if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                        safe_device_shell(device, "input tap 720 1200")
                    time.sleep(2.0)
                    state = "IN_COMBAT"
                    last_state_changed_time = time.time()
                    # 🚨 [2026-09-05] 아래 "공식" 사망 감지 분기(~1413-1426, 동일한 get_dead_match_score
                    # 체크)는 transition_delay_count를 리셋하는데 이 정체(stuck) 복구 경로의 쌍둥이 분기는
                    # 빠뜨리고 있었음 - 유령성4층 진입 카운터 미리셋 버그와 같은 유형(사용자가 지적한 "공용
                    # 리셋 지점과 특수 분기가 불일치하는" 구조적 패턴). CLAUDE.md/AGENTS.md 컨벤션 참고.
                    transition_delay_count = 0
                    continue

                # 🚨 [v1.14.0-hotfix5] 일반 정체 30초 지속 시 비상 뒤로가기(KEYCODE_BACK)를 날려 팝업 갇힘을 극복
                # 🚨 [2026-08-21 무한 정체 탈출 결함 완치] 예전엔 이 블라인드 포크 직후 last_state_changed_time을
                # 같이 리셋해버려서, 뒤로가기가 실제로 효과가 있었는지와 무관하게 위 300초 하드 리밋이 영원히
                # 도달하지 못하는 구조적 결함이 있었음(실전 확인: 2026-08-21 03:38~07:15, 뮤뮤 동결 추정 상황에서
                # 3시간 37분간 이 30초 사이클만 무한 반복하며 방치됨). 이제 이 블라인드 포크는 진짜 정체 타이머
                # (last_state_changed_time)를 건드리지 않고, 포크 자체의 재시도 간격만 별도 타이머로 페이싱한다.
                # 뒤로가기가 실제로 화면을 바꿨다면 다음 루프에서 정상적으로 앵커가 인식되며 last_state_changed_time이
                # 그 지점(state 전이 또는 위쪽의 실제 탐지 성공 분기)에서 리셋되고, 아무 효과가 없었다면
                # stuck_duration이 계속 누적되어 결국 300초 하드 리밋(RuntimeError → 강제 재시작)으로 정상 승격된다.
                if time.time() - last_blind_poke_time >= 30.0:
                    print("⏰ [일반 정체 복구] 30초간 정체 지속되어 비상 뒤로가기(KEYCODE_BACK)를 1회 주입합니다.")
                    safe_device_shell(device, "input keyevent 4")
                    time.sleep(1.0)
                    last_blind_poke_time = time.time()
                continue

            # 💀 [주인공 사망 부활 가드] 전멸 또는 부활 대기 화면 감지 시
            if get_dead_match_score(img_np, t_anchor_dead) > 0.65 or check_template_present(img_np, t_btn_resurrect, 0.60):
                print("💀 [주인공 사망 감지] 전멸/주인공 사망 화면이 식별되었습니다. 부활을 집도합니다.")
                if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    safe_device_shell(device, "input tap 720 1200")
                time.sleep(1.0)
                safe_device_shell(device, "input tap 705 1241")
                print("⏳ 부활 암전 연출 대기... 무조건 10초간 제어를 홀딩합니다.")
                time.sleep(10.0)
                need_heal = True  # 부활 즉시 정비 플래그 강제 작동
                state = "IN_COMBAT"
                last_state_changed_time = time.time()
                transition_delay_count = 0
                continue

            # 💀 [아군 사망 부활 가드] 아군 사망 앵커 감지 시
            if check_template_present(img_np, t_incombat_dead, 0.75):
                print("💀 [아군 사망 감지] 아군 사망 앵커가 포착되었습니다. 1초 간격 5회 부활 연타를 주입합니다.")
                state = "IN_COMBAT"
                last_state_changed_time = time.time()
                time.sleep(1.0) # 첫 진입 연출 대기
                import random
                for i in range(5):
                    rx = 640 + random.randint(0, 160)
                    ry = 1200 + random.randint(0, 160)
                    print(f"  👉 부활 시도 ({i+1}/5) - 터치 좌표: ({rx}, {ry})")
                    safe_device_shell(device, f"input tap {rx} {ry}")
                    time.sleep(1.0) # 매 클릭 간격 1초
                need_heal = True  # 부활 후 즉각 파티 힐링 정비 강제 작동
                transition_delay_count = 0
                continue

            combat_active = False
            if check_combat_template_present(img_np, t_combat_in, combat_threshold) or check_combat_template_present(img_np, t_combat_slow, combat_threshold):
                combat_active = True
                transition_delay_count = 0
                if state != "IN_COMBAT":
                    print("⚔️ [메인 가드] 배속 고정 UI 포착, 적 인카운터 확정! 전투 대기(`IN_COMBAT`) 진입.")
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time()
                    last_empty_shortcut_detected_time = 0
                    last_state_changed_time = time.time()
                    continue

            if not combat_active:
                # 🚨 [2026-08-27 던전 나가기 하켄 메뉴 인식 결함 완치 - 2차] 이전에 TRIGGER_EXIT 상태 분기
                # 안쪽에만 하켄 체크를 넣었었는데, 그 분기는 이 공용 전처리 블록(state와 무관하게 매 틱 먼저
                # 실행됨)이 먼저 "화면 과도기"로 잡아 continue해버려서 도달 자체가 안 되는 죽은 코드였음(실전
                # 로그로 확인: 2026-08-27 21:06경, 하켄 메뉴가 뜬 채로 화면 과도기 1~10회를 계속 반복하며 5분
                # 이상 정체). 상태 분기 진입 전인 여기서 먼저 잡아야 TRIGGER_EXIT뿐 아니라 어떤 상태에서
                # 하켄이 뜨든 전부 커버된다(사용자 확인: 앞으로 던전 나가기 대부분이 하켄을 거칠 것).
                harken_menu_state_common = check_and_handle_harken_menu(
                    device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda
                )
                if harken_menu_state_common in ("returned", "blessing"):
                    print(f"   ➔ 🚪 [공용 하켄 가드] 하켄 메뉴 감지, '{harken_menu_state_common}' 처리 완료.")
                    transition_delay_count = 0
                    time.sleep(2.0)
                    last_state_changed_time = time.time()
                    continue

                # 🆕 [2026-09-08 대설지대] 이동 중 아무 때나 튀어나올 수 있는 진짜 인터럽트 2종.
                # ⚠️ 순서 중요: 중립몹 조우 화면에도 대화 화살표가 함께 찍혀 있어서, 화살표를 먼저 처리하는
                # 코드가 있다면 이 검사보다 반드시 뒤에 둬야 한다(안 그러면 화살표를 눌러 "회복약을 쓴다"
                # 등 엉뚱한 선택지가 골라질 수 있음). 현재 이 공용 블록엔 화살표 핸들러가 없어 순서 문제는
                # 없지만, 나중에 추가할 때도 이 규칙을 지킬 것.
                if dungeon_name == "대설지대":
                    # 🏕️ 캠핑 선택창은 중립몹/행상인보다 먼저 본다 - 이 화면엔 다른 선택지 도장이 없어
                    # 순서 충돌이 없고, 방치하면 위 주석대로 비상 뒤로가기로 캠핑이 취소된다.
                    if (return_method in ("camp_then_exit_button", "camp_then_harken")
                            and (find_and_get_coords(img_np, t_camp_rest1_common, 0.70)
                                 or check_template_present(img_np, t_camp_dry_common, 0.70))):
                        print("🏕️ [캠핑 감지] 캠핑 화면 확인 - 휴식 시퀀스를 진행합니다.")
                        if perform_camping_rest(device, t_camp_rest1_common, t_camp_rest2_common, t_dialogue_arrow_common, t_field, t_camp_dry=t_camp_dry_common):
                            print("✅ [캠핑 완료] 이번 탈출의 캠핑을 마쳤습니다 - 이후 귀환은 하켄으로 진행합니다.")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        continue

                    fight_coords = find_and_get_coords(img_np, t_dilog_fight, 0.70)
                    if fight_coords:
                        print(f"⚔️ [중립몹 조우] '싸운다' 선택지 발견 - 고정 선택 탭: {fight_coords}")
                        safe_device_shell(device, f"input tap {fight_coords[0]} {fight_coords[1]}")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(1.0)
                        continue

                    # 🆕 [2026-09-09 대설지대 6층] "울타리에 구멍이 뚫려있다" 조우 - "빠져나간다" 고정 선택
                    # (오탐 검증: 양성 1.000 vs 음성 최고 0.458).
                    doghole_coords = find_and_get_coords(img_np, t_doghole_common, 0.70)
                    if doghole_coords:
                        print(f"🕳️ [울타리 구멍] '빠져나간다' 선택지 발견 - 고정 선택 탭: {doghole_coords}")
                        safe_device_shell(device, f"input tap {doghole_coords[0]} {doghole_coords[1]}")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(1.0)
                        continue

                    # 🆕 [2026-09-10 대설지대] "뼈 줍는 고블린"(뼈상인) 조우 - 4지선다(유해를 부르는
                    # 기름(10,000골드)/모험가의 뼈(1,000골드)/비약(100골드)/아무것도 안 산다) 중 사용자
                    # 확정 우선순위: 모험가의 뼈를 1순위로 먼저 찾고, 없으면 유해를 부르는 기름을
                    # 2순위로 고른다. 임계값 0.80 근거는 _handle_dungeon_interrupt()의 동일 주석 참고
                    # (기름 도장은 2글자뿐이라 다른 화면과 근접 오탐 위험 - 음성 최고 0.650).
                    bone_coords = find_and_get_coords(img_np, t_dilog_bone_common, 0.80)
                    if bone_coords:
                        print(f"🦴 [뼈상인 조우] '모험가의 뼈' 선택지 발견 - 고정 선택 탭: {bone_coords}")
                        safe_device_shell(device, f"input tap {bone_coords[0]} {bone_coords[1]}")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(1.0)
                        continue

                    oil_coords = find_and_get_coords(img_np, t_dilog_oil_common, 0.80)
                    if oil_coords:
                        print(f"🛢️ [뼈상인 조우] '모험가의 뼈' 미검출 - 2순위 '유해를 부르는 기름' 선택 탭: {oil_coords}")
                        safe_device_shell(device, f"input tap {oil_coords[0]} {oil_coords[1]}")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(1.0)
                        continue

                    # 🆕 [2026-09-14] 뼈/기름 재조우 시 "비약(100골드)"만 뜨는 경우 대응(3순위) - 오탐
                    # 방지 가드 근거는 _handle_dungeon_interrupt()의 동일 주석 참고(일반 행상인 상품
                    # 목록의 "나무 향의 비약"/"수제 상처약"과 실측 0.7978까지 근접 오탐 확인, 화자명
                    # "뼈 줍는 고블린" 가드로 완전 분리).
                    if check_template_present(img_np, t_dilog_bonegoblin_name_common, 0.80):
                        elixir_coords = find_and_get_coords(img_np, t_dilog_elixir_common, 0.80)
                        if elixir_coords:
                            print(f"🧪 [뼈상인 조우] '모험가의 뼈'/'유해를 부르는 기름' 미검출 - 3순위 '비약' 선택 탭: {elixir_coords}")
                            safe_device_shell(device, f"input tap {elixir_coords[0]} {elixir_coords[1]}")
                            transition_delay_count = 0
                            last_state_changed_time = time.time()
                            time.sleep(1.0)
                            continue

                    if check_template_present(img_np, t_seller_label, 0.80):
                        print("🛒 [행상인 조우] '수상한 행상인' 대사 화면 감지 - 조우 처리 루틴 진입.")
                        handle_merchant_encounter(device, t_seller_let_me_see, t_seller_hammer, t_dialogue_arrow_common, t_field)
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(0.5)
                        continue

                    # 🚨 [2026-09-09 실전 확인] 위 3개(캠핑/싸운다/행상인)는 전부 "구체적으로 아는 선택지"만
                    # 잡는다. 그 선택지가 뜨기 "전" 서술문만 있고 화살표만 있는 화면(예: 울타리 구멍 조우
                    # 직전의 도입 대사)은 위 어디에도 안 걸려서 아무도 못 넘기고 정체했다(실전 로그
                    # 2026-09-09 17:03, 필드맵 귀환 루틴 안에서 발견 - 이 공용 블록은 필드 이동 전체에
                    # 걸쳐 있으니 같은 위험을 대칭으로 완치). ⚠️ 반드시 위 3개 뒤에 둬야 한다(순서 원칙은
                    # _handle_dungeon_interrupt() 주석 참고).
                    if find_and_click_dialogue_advance_arrow(device, img_np, t_dialogue_arrow_common):
                        print("💬 [대화 진행] 화살표 감지 - 다음 화면으로 넘깁니다.")
                        transition_delay_count = 0
                        last_state_changed_time = time.time()
                        time.sleep(0.8)
                        continue

                if check_template_present_multipass(img_np, t_yeolda, yeolda_threshold):
                    transition_delay_count = 0
                    if yeolda_stuck_retry_count < 3:
                        yeolda_stuck_retry_count += 1
                        # 🚨 [2026-08-28 상자 첫 감지 오해성 로그 정정] 이 분기는 AUTO_MOVING이 아닌 상태(부팅
                        # 직후 재연결 등)에서 '열다'를 처리하는 공용 경로라, 실제로는 아무것도 실패한 적 없는
                        # 첫 감지에도 카운터가 1부터 찍혀 "갇힘 복구...진입 실패" 경고 문구가 매번 떴었다
                        # (기능은 정상, 문구만 오해의 소지). 첫 회는 중립적인 정상 감지 문구로, 진짜 재시도인
                        # 2/3회차부터만 경고 문구를 쓴다.
                        if yeolda_stuck_retry_count == 1:
                            print("📦 [메인] '열다' 감지(공용 경로)! 상자 해제 시퀀스로 진입.")
                        else:
                            print(f"⚠️ [블랙박스 상자 해제 갇힘 복구] '열다'가 보이나 진입 실패 상태입니다. 상자 오프닝을 재시도합니다. ({yeolda_stuck_retry_count}/3)")
                        if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                            state = "BRANCH_CHECK"
                        last_state_changed_time = time.time()
                    else:
                        print("⚠️ [블랙박스 상자 해제 갇힘 복구] '열다' 재시도 3회 초과! '아무것도 안 한다' 강제 터치로 상자창을 확실히 탈출합니다.")
                        safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.855)}")
                        time.sleep(1.0)
                        yeolda_stuck_retry_count = 0
                        state = "FIELD_WAIT"
                elif chest_opener.is_minigame_screen(img_np, height, width):
                    transition_delay_count = 0
                    state = "PLAY_MINIGAME"
                elif check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75):
                    transition_delay_count = 0
                    state = "CLEAR_CHECK"
                elif check_field_anchor_present(img_np, t_field, field_threshold):
                    transition_delay_count = 0
                    if state != "TRIGGER_EXIT":
                        if state == "IN_COMBAT":
                            print("🎉 [전투 종료 감지] 배속 마크 소멸 및 필드 안착 확인! (came_from_combat = True)")
                            came_from_combat = True
                            # 🚨 [2026-08-28 정비 후 엉뚱한 좌표 재탭 결함 완치] last_target_coords는 "상자 이동"
                            # 버튼(AUTO_MOVING)과 "출구 이동" 버튼(TRIGGER_EXIT) 둘 다가 공유하는 단일 변수라,
                            # 전투 돌입 전 마지막으로 누른 게 출구 버튼이었으면 그 좌표가 그대로 남아있다가
                            # 전투 종료 후 힐링 완료 시점에 "즉각 이동 재개" 로직이 엉뚱하게 출구 버튼을
                            # 재탭하는 사고를 실전 로그로 확인(2026-08-28 00:52경, 사용자 지적). 전투가 끝나면
                            # 전투 전 상황은 이미 무효화된 것이므로 여기서 초기화해 다음 정상 사이클(상자 이동
                            # 시도)이 새로 좌표를 잡게 한다.
                            last_target_coords = None
                            # 🚨 [2026-08-28 이동 재개 최적화 - hotfix] 전투 종료 직후 "재개(1번 Redo)" 버튼으로
                            # 중단된 이동을 즉시 이어간다(광석파밍에서 이미 검증된 패턴 재사용). 못 찾으면
                            # 아무 것도 안 하고 다음 정상 FIELD_WAIT 사이클(상자 버튼)이 맡는다.
                            # 🚨 [hotfix] resume_or_confirm_chest()가 "없습니다"를 확정해도 여기서 곧장
                            # TRIGGER_EXIT로 넘기지 않는다 - came_from_combat 플래그는 FIELD_WAIT 상태의
                            # 전투 카운트/need_heal 집계 지점(아래 "1. 전투 종료 복구 검증")에서 소비돼야 하는데,
                            # 여기서 바로 TRIGGER_EXIT로 새면 그 집계가 건너뛰어져 힐링 판단이 몇 분 뒤(다음
                            # FIELD_WAIT 안착 시점)까지 미뤄지는 결함을 실전 로그로 확인함(2026-08-28 01:56경,
                            # 사용자 지적: 전투 끝나고 한참 뒤, 하켄 나가기 직후에야 뜬금없이 힐링 발동). 항상
                            # FIELD_WAIT로 보내 그 집계가 먼저 실행되게 하고, 진짜 상자 없음 판정은 그 다음
                            # 정상 사이클의 기존 로직에 맡긴다.
                            if farming_method == "상자파밍":
                                resume_or_confirm_chest(
                                    device, img_np, t_move_resume_act, t_move_resume_deact,
                                    t_move_chest_act, t_move_chest_deact, t_no_chest
                                )
                                last_click_time = 0.0  # 🚀 [2026-08-30] FIELD_WAIT 상자탭 4초 쿨타임 파쇄
                            state = "FIELD_WAIT"
                            # 🚀 [2026-09-08 체감 지연 단축] 예전엔 여기서 무조건 2초를 더 쉬었다("전투 종료
                            # 안착 연출 마진"). 그런데 상자파밍 경로는 이 지점에 오기까지 이미 (1) 필드 앵커로
                            # 안착을 확인했고(그래서 이 분기가 실행됨), (2) 바로 위 resume_or_confirm_chest()가
                            # 재개 탭 후 약 1.9초(0.5초 + 2회 폴링)를 더 소비했다 - 연출은 이미 끝난 뒤라
                            # 이 2초는 순수 낭비다. 실전 로그(2026-09-08 23:26): 재개 탭 후 '열다' 반응까지
                            # 7초가 걸려 사용자가 답답함을 지적. 재개 경로를 타지 않는 광석파밍은 그 1.9초가
                            # 없으므로 기존 2초 마진을 그대로 유지한다.
                            if farming_method != "상자파밍":
                                time.sleep(2.0)  # 전투 종료 안착 연출 마진
                            continue
                        elif state in ["BRANCH_CHECK", "PLAY_MINIGAME", "CLEAR_CHECK"]:
                            print("✨ [상자깡 완료 감지] 상자 처리 후 필드 안착 확인! (came_from_chest = True)")
                            came_from_chest = True
                            # 🚨 [2026-08-28 hotfix] 위 전투 종료 지점과 동일 사유 - came_from_chest도 아래
                            # "2. 상자 정산 완료 후 복귀 검증" 지점에서 소비돼야 하므로 항상 FIELD_WAIT로 보낸다.
                            if farming_method == "상자파밍":
                                resume_or_confirm_chest(
                                    device, img_np, t_move_resume_act, t_move_resume_deact,
                                    t_move_chest_act, t_move_chest_deact, t_no_chest
                                )
                                last_click_time = 0.0  # 🚀 [2026-08-30] FIELD_WAIT 상자탭 4초 쿨타임 파쇄
                            state = "FIELD_WAIT"
                            continue
                        state = "FIELD_WAIT"
                else:
                    # 🆕 [2026-09-11 실전 확인] 필드/전투 앵커가 둘 다 안 보이는 이유가 항상 로딩
                    # 연출(진짜 과도기)인 것만은 아니다 - 예상 밖의 순간(미니게임 없이 상자가 즉시
                    # 열리고 곧장 다음 조우로 이어지는 등)에 뜨는 캐릭터 상태/레벨업 등 팝업도 두
                    # 앵커를 전부 가려서 똑같이 "과도기"로 오인된다(실전 로그: 상자 개방 직후 새 전투가
                    # 거의 동시에 시작돼, chest_opener.py의 캐릭터 선택창 진입 판정("열다" 버튼 소멸만
                    # 으로 판정, 화면 자체를 확인하지 않음)이 흔들려 고정 좌표 슬롯 탭이 전투 UI의
                    # 캐릭터 상태 아이콘 자리에 떨어짐 - 아베니우스의 "눈보라/동상" 상태 팝업이 뜬 채로
                    # 7초간 정체됐다가 사용자가 수동으로 닫아서야 풀림, 자동 복구 수단은 없었음).
                    # 🚨 실측 정정(1차): 처음엔 기존 범용 "X 닫기" 도장(close_panel.png, 레벨업/여권
                    # 팝업용)을 재사용하려 했으나, 실제 정체 스크린샷으로 검증하니 0.586으로 임계값
                    # (0.70) 미달이었다 - 그 도장은 "X" 위에 "닫기"가 세로로 쌓인 레이아웃인데, 이 상태
                    # 팝업은 "X 닫기"가 가로로 나란한 다른 레이아웃이었다(같은 "닫기" 버튼도 팝업 종류에
                    # 따라 배치가 다름). 같은 스크린샷에서 새로 크롭한 close_panel_inline.png는 1.000.
                    # 🚨 실측 정정(2차, 더 중요함): 그런데 이 새 도장을 저장소 스크린샷 전수 대조해보니
                    # 상자 "누가 열 거야?" 캐릭터 선택 화면의 'X 닫기'와도 0.92~0.93으로 강하게 오탐됨 -
                    # 그 화면에서 이 버튼을 누르면 진행 중이던 상자 개방을 통째로 취소해버리는 훨씬 나쁜
                    # 결과로 이어진다. 다행히 두 화면의 버튼 Y좌표가 확실히 분리된다(실측: 상태팝업
                    # Y중심 1505=화면의 58.8%, 캐릭터선택 Y중심 2418=94.5% - 약 900px/35% 차이). 그래서
                    # 전체화면 검색 대신 상태팝업 쪽 Y대역(1350~1650)으로 제한된 구역에서만 찾는다 -
                    # 이 구역 안에서는 캐릭터선택 화면의 버튼이 절대 안 걸린다(900px 이상 떨어져 있음).
                    # 정체 카운터는 증가시키지 않는다 - 수동적으로 기다리는 게 아니라 능동적으로 해소한
                    # 것이므로.
                    # ⚠️ 이 else 분기는 위 `if not combat_active:`(약 2555행)로 이미 감싸여 있어, 전투가
                    # 정상 인식되는 틱에는 아예 도달하지 않는다 - close_panel_inline.png가 정상 전투
                    # 화면(예: 톤베리전투 스샷)에서도 높은 점수(0.96)로 걸리는 게 확인됐지만, 그 화면들은
                    # combat_active=True로 먼저 걸러지므로 실제로는 도달할 일이 없다.
                    close_coords_transition = None
                    if t_close_inline is not None:
                        y1, y2, x1, x2 = STATUS_POPUP_CLOSE_ZONE
                        if img_np.shape[0] >= y2 and img_np.shape[1] >= x2:
                            zone_crop = img_np[y1:y2, x1:x2]
                            zone_gray = cv2.cvtColor(zone_crop, cv2.COLOR_RGB2GRAY)
                            _, zone_bin = cv2.threshold(zone_gray, 160, 255, cv2.THRESH_BINARY)
                            if zone_bin.shape[0] >= t_close_inline.shape[0] and zone_bin.shape[1] >= t_close_inline.shape[1]:
                                zres = cv2.matchTemplate(zone_bin, t_close_inline, cv2.TM_CCOEFF_NORMED)
                                _, zmv, _, zloc = cv2.minMaxLoc(zres)
                                if zmv > 0.70:
                                    zh, zw = t_close_inline.shape[:2]
                                    close_coords_transition = (x1 + zloc[0] + zw // 2, y1 + zloc[1] + zh // 2)
                    if close_coords_transition:
                        print(f"🚪 [화면 과도기 감지] 예상 밖 상태 팝업의 'X 닫기' 버튼 발견 - 탭으로 치웁니다: {close_coords_transition}")
                        safe_device_shell(device, f"input tap {close_coords_transition[0]} {close_coords_transition[1]}")
                        time.sleep(1.0)
                        continue

                    if transition_delay_count < 10:
                        transition_delay_count += 1
                        print(f"⏳ [화면 과도기 감지] 필드/전투 앵커 일시 소실. 화면 안착 대기 중... ({transition_delay_count}/10)")
                        time.sleep(1.0)
                        continue
                    else:
                        transition_delay_count = 0
                        print("🔍 [길 잃음 복구] 10초간 앵커 연속 미검출로 stuck 판정, 안전지대(700, 150) 터치 및 뒤로가기(ESC) 입력을 주입합니다.")
                        safe_device_shell(device, "input tap 700 150")
                        time.sleep(0.5)
                        safe_device_shell(device, "input keyevent 4")
                        time.sleep(1.0)
                        state = "FIELD_WAIT"
            
        else:
            previous_state = state
            last_state_changed_time = time.time()
            yeolda_stuck_retry_count = 0
            low_threshold_reset_count = 0
        # 🎮 [미니게임 즉각 돌입 가드] 화면이 미니게임 해제 창인 경우 30초 정체 대기 없이 즉시 전이
        if state in ["FIELD_WAIT", "AUTO_MOVING"] and chest_opener.is_minigame_screen(img_np, height, width):
            print("🎮 [dungeon_bot] 미니게임 화면 포착! 즉각 PLAY_MINIGAME 상태로 진입합니다.")
            state = "PLAY_MINIGAME"
            last_state_changed_time = time.time()
            continue



        # [메인 루프 독 치료 가드는 1.14.1-hotfix7에서 탈거되었습니다]

        if state in ["FIELD_WAIT", "AUTO_MOVING"] and not minimap_expanded:
            # 🗺️ [미니맵 오토-오픈 가드] 매크로 가동 후 미니맵이 펼쳐질 때까지만 감지 작동 (ROI: 1287-1387, 415-500)
            field_present = check_field_anchor_present(img_np, t_field, field_threshold)
            if field_present:
                open_minimap_coords = find_open_minimap_coords(img_np, t_open_minimap, 0.70)
                if open_minimap_coords:
                    ox, oy = open_minimap_coords
                    print(f"🗺️ [미니맵 제어] 미니맵 접힘 상태(삼각형 마크) 감지! 펼침 시퀀스를 시작합니다. (좌표: {ox}, {oy})")
                    
                    for attempt in range(3):
                        print(f"🗺️ [미니맵 제어] 펼침 단추 터치 시도 ({attempt+1}/3)...")
                        safe_device_shell(device, f"input tap {ox} {oy}")
                        time.sleep(1.2) # 펼침 애니메이션 대기
                        
                        # 화면 갱신 후 상자 버튼 활성화 확인
                        try:
                            raw_cap = capture_screen_bytes(device)
                            img_np_check = cv2.imdecode(np.frombuffer(raw_cap, np.uint8), cv2.IMREAD_COLOR)
                            img_np_check = cv2.cvtColor(img_np_check, cv2.COLOR_BGR2RGB)
                        except:
                            continue
                            
                        chest_found = (check_field_btn_template_present(img_np_check, t_move_chest_act, 0.70) or 
                                       check_field_btn_template_present(img_np_check, t_move_chest_deact, 0.70))
                        if chest_found:
                            print("🗺️ [미니맵 제어] 미니맵이 성공적으로 펼쳐졌습니다!")
                            minimap_expanded = True
                            break
                    
                    if not minimap_expanded:
                        print("🗺️ [미니맵 제어] 3회 터치 시도 후에도 펼침 감지 실패. 고정 좌표(1215, 557) 물리 예비 사격을 가합니다.")
                        scale_x, scale_y = width / 1440.0, height / 2560.0
                        safe_device_shell(device, f"input tap {int(1215 * scale_x)} {int(557 * scale_y)}")
                        time.sleep(1.2)
                        minimap_expanded = True  # 중복 루프 방지를 위해 플래그 설정
                    continue

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if check_template_present_multipass(img_np, t_yeolda, 0.65):
                print("📦 [메인] '열다' 감지! 상자 해제 시퀀스로 진입.")
                if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                    state = "BRANCH_CHECK"
                # 🚨 [2026-09-09 실전 확인 - 정체 타이머 리셋 누락 완치] CLAUDE.md에 이미 기록된 재발 패턴과
                # 같은 유형 - 상자 해제라는 명백한 화면 진행인데도 리셋이 없었다. 이 경로는 사용자가 최초로
                # 보고한 정체 사고의 직전 로그 줄("📦 [메인] '열다' 감지!")과 정확히 일치하는, 아주 빈번하게
                # 도는 자리라 영향이 크다.
                last_state_changed_time = time.time()
                continue

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if not check_field_anchor_present(img_np, t_field, 0.62):
                if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                    print("⚔️ [메인] 배속 고정 UI 포착,적 인카운터 확정! 전투 대기(`IN_COMBAT`) 진입.")
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time() 
                    last_empty_shortcut_detected_time = 0 
                    last_combat_color_check_time = 0 
                    continue

        if state == "FIELD_WAIT":
            # 🚨 [독립 최상단 가드] 암전/블러 화면 포함 곡괭이 부족 메시지(t_need_pickaxe) 포착 시 즉시 하켄 탈출
            if check_color_template_present(img_np, t_need_pickaxe, 0.70):
                need_pickaxe_refill = True
                print("⚠️ [곡괭이 부족] 팝업 화면에서 need_pickaxe BGR 컬러 확정! 즉시 여관 숙박 회군을 단행합니다.")
                exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                if exit_coords:
                    safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                else:
                    safe_device_shell(device, "input tap 1140 572")
                
                last_state_changed_time = time.time()
                trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
                last_state_changed_time = time.time()
                return False, skill_mission_success_this_combat, need_pickaxe_refill

            if check_field_anchor_present(img_np, t_field, 0.65):
                # 1. 전투 종료 복귀 검증 및 카운팅
                was_from_combat = False
                if came_from_combat:
                    came_from_combat = False
                    was_from_combat = True
                    event_counter += 1
                    print(f"⚔️ [전투 종료 복구] 필드 복귀 안착 확인! (전투 카운트: {event_counter}/{healing_loops})")
                    if healing_loops > 0 and event_counter >= healing_loops:
                        print(f"💊 [정비 도달] 전투 누적 횟수가 설정 주기({healing_loops}회)에 달해 need_heal = True로 전환합니다.")
                        need_heal = True

                # 2. 상자 정산 완료 후 복귀 검증
                if came_from_chest:
                    came_from_chest = False
                    if heal_after_chest:
                        print("📦 [상자 정산 완료 필드 안착] need_heal = True로 전환합니다.")
                        need_heal = True

                # 2-1. 🩸 [피장막(딸피) 감지 -> 즉시 정비] 주인공이 빈사가 되면 화면에 붉은 피안개 연출이 씌워지는데,
                # 이건 연출일 뿐이고 실제 해법은 그냥 힐을 주는 것(사용자 확인). 다만 안개 자체를 화면 통계로
                # 판별하려던 과거 방식은 실패했음 - 실측 결과 이 게임은 정상 화면도 평균밝기 40~70이라 밝기 기준이
                # 무용지물이고, 붉은 색조 역시 황금 상자 화면(+6.7~14.7)이 실제 안개 화면(+5.0)보다 오히려 더 붉어
                # 구분이 안 됨. 그래서 안개(결과) 대신 원인인 "빈사 상태"를 직접 본다 - 빈사 캐릭터는 파티창의
                # 이름/HP가 주황빛으로 바뀌므로(실측 RGB 약 (140,53,16)), 파티창 구역에서 그 색 픽셀을 센다.
                # 🚨 [2026-09-12 실전 확인 - 완치] 위 판정은 "빈사"(힐로 회복)와 "사망"(힐로 절대 안
                # 풀림)을 구분하지 못했다 - 사망한 캐릭터는 파티창 위험색이 영구히 안 사라지므로, 힐을
                # 넣어도 다음 틱에 또 danger_px가 기준을 넘어 정비를 무한 재격발했다(실전 로그: 6~7초
                # 간격으로 "빈사 감지→정비→빈사 감지"가 12시간 반복되다 게임 세션이 시간초과로 끊김 -
                # 사용자가 직접 목격/보고: "예전엔 캐릭 죽었어도 그냥 주회는 돌았거든"). 사망이 한 번
                # 확인되면(death_confirmed_and_handled), 그 뒤로는 이 빈사 신호를 아예 재평가하지
                # 않는다 - 사망자를 그대로 달고 예전처럼 주회를 계속한다(힐 시도 자체를 반복하지 않음).
                if not need_heal and not death_confirmed_and_handled:
                    danger_px = count_danger_hp_pixels(img_np)
                    if danger_px >= DANGER_HP_PIXEL_LIMIT:
                        dead_slots = find_dead_slots(img_np, t_stat_dead)
                        if dead_slots:
                            print(f"💀 [사망 확인] {dead_slots}번 슬롯에서 사망(해골) 아이콘 감지 - 힐로는 해결되지 않는 상태입니다. "
                                  f"이후 이 파티 상태에서는 빈사 감지를 억제하고 주회를 계속합니다.")
                            death_confirmed_and_handled = True
                            # 🆕 [2026-09-12 사용자 확정] "사망확인되면 일단 마을 복귀하고 여관 들르는게
                            # 좋음(마을복귀하면 확률적으로 부활하기도 함)". 새 탈출 경로를 따로 만들지
                            # 않고, 상자 소진 시와 동일한 TRIGGER_EXIT 진입 절차를 그대로 재사용한다 -
                            # 이러면 던전마다 다른 귀환 방식(하켄/캠핑/도보 등)을 여기서 다시 판단할
                            # 필요 없이 기존에 검증된 던전별 귀환 로직이 그대로 처리한다. 마을 도착 후
                            # 실제로 여관까지 들르는지는 던전/프리셋별 기존 정책을 따른다(예: 대설지대
                            # 6층 기본값은 여관을 안 들르는 resupply_mode="items_only" - 이 부분까지
                            # 강제로 바꾸는 건 더 큰 변경이라 이번 완치 범위에서는 제외).
                            print("🏠 [사망 확인] 마을로 회군을 시도합니다(확률적 부활 기대).")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            exit_clicked_once = False
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                            exit_last_action_was_exit_tap = False
                            last_click_time = 0.0
                            last_state_changed_time = time.time()
                            continue
                        else:
                            print(f"🩸 [빈사 감지] 파티창 빈사색 픽셀 {danger_px}개 (기준 {DANGER_HP_PIXEL_LIMIT}) - 피장막 유발 상태로 판단해 정비를 격발합니다.")
                            need_heal = True

                # 3. 통합 힐링 기동: 안전 필드 안착 및 힐링 플래그 감지 시 작동
                if need_heal:
                    if check_template_present_multipass(img_np, t_yeolda, 0.65):
                        print("📦 [상자 발견 가드] 화면에 '열다' 버튼이 노출되어 있어 상자 해제를 우선 처리하고 힐링을 다음 루프로 유예합니다.")
                    else:
                        print("💊 [통합 힐링 기동] 안전 필드 안착 확인. 정비 시퀀스를 시작합니다.")
                        heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close, healer_slot=healer_slot, masked_adventurer_slot=masked_adventurer_slot)
                        if heal_success:
                            # 🚨 [2026-09-09 실전 확인] 이 분기 전체(힐링 성공 → 재개 탭 → continue)에
                            # last_state_changed_time 리셋이 빠져 있었다 - CLAUDE.md에 이미 기록된 재발
                            # 패턴("화면 진행 감지 시 정체 카운터 리셋 누락")과 정확히 같은 유형. 힐링
                            # 시퀀스(party_manager.run_party_healing_sequence)는 블록킹 호출로 실전 27초가
                            # 걸렸는데, 그동안 타이머가 힐링 시작 시점에 멈춰 있어 힐링+재개 탭까지 마친
                            # 직후 정체 감지가 "31초 정체"로 즉시 오판해 비상 뒤로가기를 주입했다(실전 로그
                            # 2026-09-09 17:55:56~17:56:27 - 그 뒤로가기가 마침 새로 뜬 상자 화면을 건드려
                            # 정상 스캔 기회를 날림). 힐링 완료는 명백한 화면 진행이므로 여기서 리셋한다.
                            last_state_changed_time = time.time()
                            low_threshold_active_until = 0.0
                            event_counter = 0
                            need_heal = False
                            # 🚨 [2026-08-28 이동 재개 최적화] 상자파밍은 정비 직후 "재개(1번 Redo)" 버튼으로
                            # 이동을 이어간다. 예전엔 last_target_coords를 그대로 재탭했는데, 상자/출구 버튼이
                            # 공유하는 단일 변수라 엉뚱한 버튼을 재탭하는 사고가 있었음(오늘 완치). 다른
                            # 파밍방식(광석파밍 등)은 기존 방식 그대로 유지한다.
                            if farming_method == "상자파밍":
                                if resume_or_confirm_chest(
                                    device, img_np, t_move_resume_act, t_move_resume_deact,
                                    t_move_chest_act, t_move_chest_deact, t_no_chest
                                ):
                                    state = "TRIGGER_EXIT"
                                    exit_start_time = time.time()
                                    exit_clicked_once = False
                                    exit_stuck_count = 0
                                    exit_prev_minimap = None
                                    exit_last_action_was_exit_tap = False
                                    last_click_time = 0.0
                                else:
                                    last_click_time = 0.0  # 🚀 [2026-08-30] FIELD_WAIT 상자탭 4초 쿨타임 파쇄
                            elif last_target_coords:
                                print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                                safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                                last_click_time = 0.0
                            continue
                        else:
                            print("⚠️ [통합 힐링 실패] 기습 또는 인터럽트로 인해 치료 미완료. 힐링 플래그(need_heal = True)를 유지합니다.")

                # 4. 힐링 미작동 시 전투 종료 직후 첫 루프 가드
                if was_from_combat:
                    continue
                
                # 🚨 [던전 공통 최우선 철칙] 화면에 상자 "열다" (t_yeolda) 앵커 포착 시 즉시 상자 해제 구동
                if check_template_present_multipass(img_np, t_yeolda, 0.65):
                    print("📦 [공통 상자 감지] 던전 필드에서 '열다' 버튼 포착! 상자 해제/개봉 시퀀스를 최우선 격발합니다.")
                    if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                        came_from_chest = True
                        last_click_time = time.time()
                        last_state_changed_time = time.time()
                        continue

                if time.time() - last_click_time > 4.0:
                    if farming_method == "광석파밍":
                        # ⛏️ [v1.14.1-hotfix11 광석파밍 주회 로직]
                        # 1) 최초 1회만 미니맵 3번(체크포인트)으로 이동, 그 이후는 1번(Redo)으로 이동
                        moved = False
                        if checkpoint_pressed_count == 0:
                            chk_coords = find_checkpoint_btn_coords(img_np, t_move_check_act, t_move_check_deact, 0.70)
                            if chk_coords:
                                cx, cy = chk_coords
                                print(f"⛏️ [광석이동] 최초 1회 '체크포인트 자동 이동(3번)' ({cx}, {cy}) 터치 주입")
                                safe_device_shell(device, f"input tap {cx} {cy}")
                                checkpoint_pressed_count += 1
                                last_click_time = time.time()
                                last_state_changed_time = time.time()
                                moved = True
                                time.sleep(3.0)
                        else:
                            # 1번 Redo(이동 재개) 단추 터치
                            resume_coords = find_checkpoint_btn_coords(img_np, t_move_resume_act, t_move_resume_deact, 0.70)
                            if resume_coords:
                                rx, ry = resume_coords
                                print(f"⛏️ [광석이동] '이동 재개(1번 Redo)' ({rx}, {ry}) 터치 주입")
                                safe_device_shell(device, f"input tap {rx} {ry}")
                                last_click_time = time.time()
                                last_state_changed_time = time.time()
                                moved = True
                                time.sleep(3.0)
                            else:
                                print("⛏️ [광석이동] 이동 재개(1번 Redo) 단추 미검출. 폴백으로 체크포인트(3번) 재조준 시도")
                                chk_coords = find_checkpoint_btn_coords(img_np, t_move_check_act, t_move_check_deact, 0.70)
                                if chk_coords:
                                    cx, cy = chk_coords
                                    print(f"⛏️ [광석이동] '체크포인트 자동 이동(3번)' ({cx}, {cy}) 터치 주입")
                                    safe_device_shell(device, f"input tap {cx} {cy}")
                                    last_click_time = time.time()
                                    last_state_changed_time = time.time()
                                    moved = True
                                    time.sleep(3.0)

                        if moved:
                            # 2) 도착 화면 재캡처 및 상태 분석
                            try:
                                raw = capture_screen_bytes(device)
                                if raw:
                                    img_np = decode_screen_bytes(raw)
                            except: pass
                            
                            # 🚨 [이동 안착 지점 2차 상자 포착 가드]
                            if check_template_present_multipass(img_np, t_yeolda, 0.65):
                                print("📦 [이동 도중 상자 발견!] 광석 이동 도착 지점/경로에서 '열다' 상자 포착! 상자 해제 시퀀스를 단행합니다.")
                                if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                                    came_from_chest = True
                                    last_click_time = time.time()
                                    last_state_changed_time = time.time()
                                    continue

                            is_ready = check_color_template_present(img_np, t_mining_ready, 0.78)
                            is_done = check_color_template_present(img_np, t_mining_done, 0.78)
                            
                            print(f"📊 [광석 식별 - 컬러매치] ready(캘수있음):{is_ready} | done(캠):{is_done}")
                            
                            if is_ready and not is_done:
                                print("⛏️ [채굴 개시] 광석 매칭 확정! (731, 859) 연타 마이닝을 시작합니다.")
                                mine_start = time.time()
                                while time.time() - mine_start < 40.0:  # 최대 40초 안전 가드
                                    # 연타 주입
                                    safe_device_shell(device, "input tap 731 859")
                                    time.sleep(0.5)
                                    
                                    # 재스캔 및 예외 검증
                                    try:
                                        raw_mine = capture_screen_bytes(device)
                                        if raw_mine is None: continue
                                        img_np_mine = decode_screen_bytes(raw_mine)
                                    except:
                                        continue
                                        
                                    # 수령 창 매칭 시 넘김
                                    if check_color_template_present(img_np_mine, t_mining_get, 0.75):
                                        print("💎 [아이템 수령] 획득창 감지! (731, 859) 터치로 수령.")
                                        safe_device_shell(device, "input tap 731 859")
                                        time.sleep(1.0)
                                        
                                    # 곡괭이 부족 감지 시 ➔ 여관 복귀 (3채널 BGR 컬러 매칭 0.75 적용)
                                    if check_color_template_present(img_np_mine, t_need_pickaxe, 0.75):
                                        need_pickaxe_refill = True
                                        print("⚠️ [곡괭이 부족] need_pickaxe BGR 컬러 감지! 여관 숙박 회군을 개시합니다.")
                                        exit_coords = find_and_get_field_btn_coords(img_np_mine, t_move_exit, 0.70)
                                        if exit_coords:
                                            safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                        else:
                                            safe_device_shell(device, "input tap 1140 572") # 고정
                                        
                                        last_state_changed_time = time.time()
                                        trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
                                        last_state_changed_time = time.time()
                                        return False, skill_mission_success_this_combat, need_pickaxe_refill
                                    
                                    # 채굴 완료 완료
                                    if check_color_template_present(img_np_mine, t_mining_done, 0.78):
                                        print("⛏️ [채굴 완료] mining_done 검출 완료! 마이닝을 성공적으로 마칩니다.")
                                        safe_device_shell(device, "input keyevent 4")
                                        time.sleep(1.5)
                                        
                                        print("⚠️ [회군 격발] 채굴 완수로 즉시 여관 숙박 회군 탈출 절차를 격발합니다.")
                                        exit_coords = find_and_get_field_btn_coords(img_np_mine, t_move_exit, 0.70)
                                        if exit_coords:
                                            safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                        else:
                                            safe_device_shell(device, "input tap 1140 572")
                                        
                                        last_state_changed_time = time.time()
                                        trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
                                        last_state_changed_time = time.time()
                                        return False, skill_mission_success_this_combat, need_pickaxe_refill
                                
                            else:
                                # 3) 이미 캠 or 광석이 없는 상태 ➔ 던전 탈출 복귀
                                print("🚪 [광석 없음/소진] 2번 나가기(하켄귀환) 절차를 집도합니다.")
                                exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                                if exit_coords:
                                    print(f"👉 [출구이동] 미니맵 2번 단추 터치 ({exit_coords[0]}, {exit_coords[1]})")
                                    safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                else:
                                    safe_device_shell(device, "input tap 1140 572")
                                
                                last_state_changed_time = time.time()
                                trigger_harken_escape(device, t_harken_return, t_move_exit, t_harken_blessing_donothing, t_combat_in, t_combat_slow, t_yeolda)
                                last_state_changed_time = time.time()
                                return False, skill_mission_success_this_combat, need_pickaxe_refill
                        continue

                    # 🆕 [2026-09-08 대설지대 눈보라 서브구역] 배경(눈보라 파티클)이 계속 흔들려 미니맵
                    # 자체가 안 뜨는 구간. 상자 버튼도 비활성이라 기존 resume_or_confirm_chest()의
                    # "상자로 재확인" 단계를 쓸 수 없어 별도 분기로 처리한다:
                    # 재개 반복 -> "없습니다" 뜨면 나가기 1회(자력 탈출 수단이 이것뿐).
                    #
                    # 🚨 [2026-09-09 판별 방식 교체 - 사용자 확인] 예전엔 "필드 앵커는 있는데 커서 미검출"만으로
                    # 눈보라라고 단정했는데, 캠핑을 마친 자리에서 앱이 재시작되면 커서가 캠프 아이콘과 겹쳐
                    # 가려져서 똑같은 조건이 된다. 그 상태에선 이동 명령 이력이 없어 재개 버튼이 비활성이라
                    # 눌러도 무반응이고, 재개만 무한 반복하며 영영 멈췄다(실전 로그 00:00).
                    # 확실한 구분법: 미니맵을 눌러본다 - 눈보라 구간은 필드맵 확장 자체가 안 되고,
                    # 아이콘에 가려진 경우는 정상적으로 확장된다(사용자 확인).
                    if dungeon_name == "대설지대" and check_field_anchor_present(img_np, t_field, 0.65):
                        cursor_dir = get_minimap_cursor_direction(img_np, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right)
                        if cursor_dir is not None:
                            # 🆕 [2026-09-15] 나가기 탭으로 눈보라를 빠져나온 직후라면(blizzard_exit_tapped)
                            # 아래 상자 시퀀스로 곧장 넘기지 않고 "안전지대"를 먼저 한 번 터치해 캐릭터의
                            # 잔여 이동 모션을 확실히 멈춘다 - 이동 중에 곧바로 다음 이동 명령(상자 탭 등)을
                            # 주면, 관성 때문에 의도한 지점(상자)에 닿기도 전에 캐릭터가 계속 걸어가 던전
                            # 출구(계단)를 먼저 밟고 다음 던전으로 넘어가버릴 수 있다(사용자 확인 - 캠핑
                            # 이동 시 동일한 문제로 이미 안전지대 선제 터치를 쓰고 있음, party_manager.py:204
                            # 참고). 좌표는 기존 "길 잃음 복구"에서 쓰는 빈 공터 좌표를 그대로 재사용한다.
                            if blizzard_exit_tapped:
                                print("🧊 [눈보라구간] 나가기 이후 잔여 이동 정지를 위해 안전지대(700, 150) 터치.")
                                safe_device_shell(device, "input tap 700 150")
                                time.sleep(0.8)
                            # 커서가 보임 = 일반 구간 - 판정을 초기화하고 아래 기존 상자 시퀀스로 넘긴다.
                            blizzard_state = "unknown"
                            blizzard_exit_tapped = False
                            blizzard_resume_start_time = None
                            blizzard_last_tick_time = None
                        elif blizzard_state == "unknown":
                            ex_bz, ey_bz = FIELDMAP_EXPAND_TAP_COORDS
                            print("🔎 [눈보라 판별] 커서 미검출 - 미니맵을 눌러 필드맵 확장 여부로 눈보라인지 확인합니다.")
                            safe_device_shell(device, f"input tap {ex_bz} {ey_bz}")
                            time.sleep(1.5)
                            expanded_bz = False
                            raw_bz_chk = capture_screen_bytes(device)
                            if raw_bz_chk:
                                img_bz_chk = decode_screen_bytes(raw_bz_chk)
                                expanded_bz = _check_fieldmap_expanded(img_bz_chk, t_field_expanded_common, t_fieldmap_close_common)
                            if expanded_bz:
                                print("🗺️ [눈보라 판별] 필드맵이 정상 확장됨 - 눈보라가 아니라 커서가 아이콘에 가려진 상태입니다. 맵을 닫고 일반 절차로 진행합니다.")
                                cx_bz, cy_bz = FIELDMAP_CLOSE_TAP_COORDS
                                safe_device_shell(device, f"input tap {cx_bz} {cy_bz}")
                                time.sleep(1.0)
                                blizzard_state = "no"
                            else:
                                print("❄️ [눈보라 판별] 필드맵 확장이 되지 않음 - 눈보라 구간으로 확정합니다.")
                                blizzard_state = "yes"
                            transition_delay_count = 0
                            last_state_changed_time = time.time()
                            continue
                        elif blizzard_state == "yes":
                            now_bz2 = time.time()
                            # 🆕 [2026-09-15] 이 분기에 마지막으로 들어왔던 시각과 크게 벌어져 있으면(전투
                            # 등으로 몇 틱 이상 이탈했다 돌아온 것) 30초 타이머를 새로 시작한다 - 전투만
                            # 으로도 30초를 넘길 수 있는데 그 시간을 "재개가 안 풀린 시간"으로 합산하면
                            # 억울하게 나가기로 튕길 수 있다(사용자 확정: "전투가 끝나면 타이머를 다시 잰다").
                            if blizzard_resume_start_time is None or (now_bz2 - blizzard_last_tick_time) > 5.0:
                                blizzard_resume_start_time = now_bz2
                            blizzard_last_tick_time = now_bz2

                            if not blizzard_exit_tapped:
                                img_np_bz = img_np  # 재개 탭 실패/미검출 시 30초 판정에서도 쓸 폴백(구 화면)

                                # 🆕 [2026-09-16] 재개 버튼을 탭하기 "전"에 먼저 밝기로 활성/비활성을
                                # 확인한다 - 비활성이면 탭해봐야 반응이 없을 게 뻔하므로(실측:
                                # is_resume_button_active 주석 참고) 30초씩 기다리지 않고 바로 나가기로
                                # 직행한다.
                                if not is_resume_button_active(img_np):
                                    print("❄️ [눈보라구간] 재개 버튼 비활성 확인(밝기 판정) - 탭 생략하고 즉시 나가기로 전환합니다.")
                                    exit_coords = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                                    if exit_coords:
                                        print(f"❄️ [눈보라구간] 나가기 탭: {exit_coords}")
                                        safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                        blizzard_exit_tapped = True
                                        time.sleep(1.5)
                                    transition_delay_count = 0
                                    time.sleep(1.0)
                                    continue

                                resume_coords = find_checkpoint_btn_coords(img_np, t_move_resume_act, t_move_resume_deact, 0.70)
                                if resume_coords:
                                    print(f"❄️ [눈보라구간] 재개 버튼 탭: {resume_coords}")
                                    safe_device_shell(device, f"input tap {resume_coords[0]} {resume_coords[1]}")
                                    time.sleep(1.2)
                                    raw_bz = capture_screen_bytes(device)
                                    if raw_bz:
                                        img_np_bz = decode_screen_bytes(raw_bz)  # 재개 탭 직후 최신 화면으로 교체
                                        if check_template_present(img_np_bz, t_no_chest, 0.55):
                                            exit_coords = find_and_get_field_btn_coords(img_np_bz, t_move_exit, 0.70)
                                            if exit_coords:
                                                print(f"❄️ [눈보라구간] '없습니다' 감지 - 즉시 나가기 1회 탭: {exit_coords}")
                                                safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                                blizzard_exit_tapped = True
                                            time.sleep(1.5)
                                else:
                                    print("❄️ [눈보라구간] 재개 버튼 미검출 - 다음 틱 재시도.")

                                # 🆕 [2026-09-15] "없습니다" 토스트 없이도 30초 넘게 안 풀리면(재개 버튼이
                                # 실제로는 비활성인데 도장이 활성/비활성을 구분 못 해 계속 눌리기만 하고
                                # 게임 쪽 반응이 아예 없는 경우 - 실전 로그 2026-09-14 22:30~22:43, 13분+
                                # 무한 반복) 토스트 여부와 무관하게 강제로 나가기를 탭한다. 위에서 재개 탭
                                # 직후 새로 찍어둔 화면(img_np_bz)을 그대로 써서 판정한다.
                                if (not blizzard_exit_tapped) and (time.time() - blizzard_resume_start_time >= 30.0):
                                    exit_coords = find_and_get_field_btn_coords(img_np_bz, t_move_exit, 0.70)
                                    if exit_coords:
                                        print(f"❄️ [눈보라구간] 재개 30초 무반응 - 강제 나가기 탭: {exit_coords}")
                                        safe_device_shell(device, f"input tap {exit_coords[0]} {exit_coords[1]}")
                                        blizzard_exit_tapped = True
                                        time.sleep(1.5)

                            # 🚨 [2026-09-15] 여기서 last_state_changed_time을 더 이상 매 틱 무조건 리셋
                            # 하지 않는다 - 예전엔 여기서 매초 리셋해버려서, 이 분기에 갇힌 채 아무 진전이
                            # 없어도 300초 하드리밋(강제 재시작 안전장치)이 절대 안 걸리는 결함이 있었다
                            # (2026-08-21에 이미 "블라인드 포크는 정체 타이머를 건드리지 않는다"는 원칙이
                            # 확립됐는데 이 분기만 예외로 남아있었음 - 실전 사고: 2026-09-14 22:30~22:43+,
                            # 재개만 반복하다 결국 MuMu 자체가 죽을 때까지 13분+ 방치됨). 위 30초 자체
                            # 안전장치로 대부분 해결되지만, 혹시 그마저 실패해도(나가기도 안 먹는 등) 공용
                            # 300초 하드리밋이 최후 안전망으로 살아있도록 여기서는 건드리지 않는다.
                            transition_delay_count = 0
                            time.sleep(1.0)
                            continue
                        # blizzard_state == "no" 이면 아무것도 하지 않고 아래 일반 상자 시퀀스로 흘려보낸다.

                    # 이하 기존 상자 파밍 시퀀스
                    if check_field_anchor_present(img_np, t_field, 0.65):
                        coords = find_chest_btn_coords(img_np, t_move_chest_act, t_move_chest_deact, 0.70)
                    if coords:
                        cx, cy = coords
                        # 🚨 [2026-09-10 실전 확인 - 터치 먹통 3시간 정체 완치] prev_cursor_dir가
                        # start_main_macro 진입 시 딱 한 번만 초기화되고, 이 아래 이동감지 루프의
                        # moved=True 분기는 break로 곧장 빠져나가느라 그 값을 갱신하지 않는다 - 그래서
                        # 이 비교는 "방금 탭하기 전"이 아니라 훨씬 이전(심하면 몇 시간 전) 시점의 낡은
                        # 방향과 계속 비교되고 있었다. 실전 로그(2026-09-10 03:22~06:44, 3시간 넘게
                        # "이동 시작 확인"만 반복): MuMu 인스턴스의 터치 입력만 죽고 ADB 연결/화면 캡처는
                        # 멀쩡했던 상황(사용자가 MuMu 관리자 화면의 "실행이 중지됨" 표시로 직접 확인)에서,
                        # 캐릭터는 실제로 전혀 움직이지 못했는데도 "지금 방향"이 그 낡은 기준값과 우연히만
                        # 다르면 이동감지 루프 첫 프레임에서 곧장 moved=True로 오판됐다. 이 오판이
                        # last_state_changed_time까지 매번 리셋해버려, 진짜 정체를 잡아야 할 절대 워치독
                        # 조차 한 번도 발동하지 못했다(3시간 동안 재시작 0회). 탭 직전 화면(img_np, 아직
                        # 반응 전)에서 방향을 다시 찍어 "이번 탭 기준"으로 새로 세운다 - 비교 대상은 항상
                        # "방금 전"이어야지 임의의 과거 시점이면 안 된다.
                        if dungeon_name == "대설지대":
                            fresh_cursor_dir = get_minimap_cursor_direction(img_np, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right)
                            if fresh_cursor_dir is not None:
                                prev_cursor_dir = fresh_cursor_dir
                        # 🚨 [2026-08-28 상자 이동 대기시간 단축] 미니맵 이동 여부와 무관하게 항상 2연타부터
                        # 찍던 걸 1회 탭으로 변경 - 던전 필드에서 멈춰서 확인하는 시간 자체가 가장 위험한
                        # 구간(기습 위험)이라는 사용자 판단에 따라, 1차 탭으로 충분한 대부분의 경우 탭 간격
                        # 0.25초를 아낀다. 씹힘으로 진짜 반응이 없었던 경우는 아래 재시도(retry_cnt==1)에서
                        # 그대로 다시 1회 탭한다.
                        print(f"📦 [상자 이동 시도] '상자 자동 이동' ({cx}, {cy}) 터치합니다.")
                        safe_device_shell(device, f"input tap {cx} {cy}")
                        last_click_time = time.time()
                        last_target_coords = (cx, cy)

                        action_success = False
                        opened = False
                        toast_detected = False

                        for retry_cnt in range(2): # 최초 1회 + 씹힘 시 재시도 1회
                            if retry_cnt > 0:
                                print(f"🔄 [상자 터치 재시도] 터치 씹힘 감지되어 다시 누릅니다. ({cx}, {cy})")
                                safe_device_shell(device, f"input tap {cx} {cy}")
                                last_click_time = time.time()

                            time.sleep(0.5)
                            prev_mini = None
                            moved = False
                            
                            for step in range(3):
                                try:
                                    raw = capture_screen_bytes(device)
                                    if raw is None: continue
                                    img_np_sub = decode_screen_bytes(raw)
                                except:
                                    continue
                                
                                if check_template_present_multipass(img_np_sub, t_yeolda, 0.65):
                                    opened = True
                                    img_np = img_np_sub
                                    break
                                if check_template_present(img_np_sub, t_no_chest, 0.55):
                                    toast_detected = True
                                    img_np = img_np_sub
                                    break
                                
                                # 🆕 [2026-09-08 대설지대] 배경(눈보라 파티클 등)이 계속 흔들려 미니맵 픽셀
                                # diff 비교가 오작동하므로, 압축 미니맵 커서 방향이 바뀌는지로 판정한다
                                # (실측 근거는 get_minimap_cursor_direction() 주석 참고). 다른 던전은 기존
                                # diff 비교를 그대로 쓴다.
                                if dungeon_name == "대설지대":
                                    cursor_dir = get_minimap_cursor_direction(img_np_sub, t_cursor_up, t_cursor_down, t_cursor_left, t_cursor_right)
                                    if prev_cursor_dir is not None and cursor_dir is not None and cursor_dir != prev_cursor_dir:
                                        moved = True
                                        img_np = img_np_sub
                                        # 🚨 [2026-09-10] break 전에 기준값을 갱신 - 예전엔 여기서 그냥
                                        # break해 prev_cursor_dir이 이번에 감지한 새 방향으로 안 바뀌고
                                        # 계속 낡은 채로 남아있었다(위 탭 직전 갱신과 별개로, 다음 상자
                                        # 이동 시도에서도 계속 낡은 기준과 비교되지 않도록 이중 안전).
                                        prev_cursor_dir = cursor_dir
                                        break
                                    if cursor_dir is not None:
                                        prev_cursor_dir = cursor_dir
                                else:
                                    # 미니맵 스크롤 감지
                                    h, w = img_np_sub.shape[:2]
                                    scale_x, scale_y = w / 1440.0, h / 2560.0
                                    gray_sub = cv2.cvtColor(img_np_sub, cv2.COLOR_RGB2GRAY)
                                    mini = gray_sub[int(115 * scale_y):int(315 * scale_y), int(1117 * scale_x):int(1317 * scale_x)]

                                    if prev_mini is not None:
                                        diff = cv2.absdiff(mini, prev_mini)
                                        if (np.mean(diff) / 255.0) >= 0.05:
                                            moved = True
                                            img_np = img_np_sub
                                            break
                                    prev_mini = mini
                                time.sleep(0.4)
                            
                            if opened or toast_detected or moved:
                                # 🚨 [2026-09-09 실전 확인 - 정체 타이머 리셋 누락 완치] opened/toast_detected/
                                # moved 셋 다 진짜 화면 진행인데 last_state_changed_time 리셋이 하나도 없었다
                                # (같은 유형 재발 - CLAUDE.md 참고). 아래 최종 else(진짜 정체 - 상자없음 판정)는
                                # 이 조건에 안 걸리므로 리셋되지 않는다(의도한 대로).
                                last_state_changed_time = time.time()
                                action_success = True
                                break
                        
                        if opened:
                            if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                                state = "BRANCH_CHECK"
                            else:
                                state = "FIELD_WAIT"
                        elif toast_detected:
                            print("🎉 [상자 없음] 토스트 메시지를 확인하여 탈출 시퀀스로 이행합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            # 🚨 [v1.14.0-hotfix4] 진입 시 타이머 강제 초기화 제거
                            # 최초 스턱(정체) 발생 시점에만 타이머를 시작하도록 하여, 백스텝 동작 시 오리셋되는 루프 락을 원천 차단합니다.
                            # exit_first_start_time = time.time() <-- 제거됨
                            exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 출구 클릭 플래그 리셋
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                            exit_last_action_was_exit_tap = False  # 🚨 [2026-08-29] TRIGGER_EXIT 재진입 시 잔상 토스트 오판 방지
                            last_click_time = 0.0                 # 🚀 [v1.14.1-hotfix10] 탈출 탭 3초 쿨타임 파쇄
                        elif moved:
                            print("🏃 [이동 시작 확인] 미니맵이 움직이기 시작했습니다. AUTO_MOVING으로 이행.")
                            state = "AUTO_MOVING"
                        else:
                            print("📦🚫 [상자 없음 판정] 재시도 결과 미니맵 움직임과 '열다'가 모두 미검출되었습니다. 상자가 없는 것으로 논리적 판정하여 탈출로 전환합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            # 🚨 [v1.14.0-hotfix4] 진입 시 타이머 강제 초기화 제거
                            # 최초 스턱(정체) 발생 시점에만 타이머를 시작하도록 하여, 백스텝 동작 시 오리셋되는 루프 락을 원천 차단합니다.
                            # exit_first_start_time = time.time() <-- 제거됨
                            exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 출구 클릭 플래그 리셋
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                            exit_last_action_was_exit_tap = False  # 🚨 [2026-08-29] TRIGGER_EXIT 재진입 시 잔상 토스트 오판 방지
                            last_click_time = 0.0                 # 🚀 [v1.14.1-hotfix10] 탈출 탭 3초 쿨타임 파쇄

        elif state == "AUTO_MOVING":
            toast_detected = False
            for scan_step in range(5):
                if check_template_present_multipass(img_np, t_yeolda, 0.65): break
                if check_template_present(img_np, t_no_chest, 0.55):
                    toast_detected = True
                    break
                time.sleep(0.3)
                try: img_np = capture_screen(device)
                except: continue

            if toast_detected or state == "TRIGGER_EXIT":
                state = "TRIGGER_EXIT"
                exit_start_time = time.time()
                prev_minimap_zone = None
                last_click_time = 0
                exit_clicked_once = False
                exit_last_action_was_exit_tap = False  # 🚨 [2026-08-29] TRIGGER_EXIT 재진입 시 잔상 토스트 오판 방지
            else:
                if time.time() - last_click_time > 4.0: state = "FIELD_WAIT"

        if state == "TRIGGER_EXIT":
            # 🆕 [2026-09-07 대설지대] 나가기-버튼-도보 대신 필드맵 아이콘(캠핑/대하켄) 경유 귀환이 필요한
            # 던전은 여기서 완전히 별개의 경로로 분기 - 아래의 기존 정체감지/도보-나가기 로직은 전혀 타지
            # 않는다(return_to_town_via_fieldmap_icon()이 자체 타임아웃/재시도를 갖고 있음).
            if dungeon_name == "대설지대" and return_method != "exit_button":
                print(f"🚪 [TRIGGER_EXIT] 필드맵 아이콘 경유 귀환 루틴 진입 (return_method={return_method})")
                # 🚨 캠핑을 이미 마쳤는지는 루틴이 내부에서 is_camping_done()으로 직접 판단해 "나가기 버튼
                # → 하켄" 꼬리부터 이어간다(return_method를 바꿔치우면 안 된다 - 상세는 _return_after_camping 주석).
                fieldmap_return_result = return_to_town_via_fieldmap_icon(device, return_method, t_combat_in, t_combat_slow)
                if fieldmap_return_result == "returned":
                    return True, skill_mission_success_this_combat, need_pickaxe_refill
                if fieldmap_return_result == "combat":
                    # 🚨 [2026-09-08 실전 확인] 귀환 루틴은 전투를 스스로 기다리지 않고 여기로 돌려보낸다.
                    # 전투 처리(자동전투 재활성화/스킬/힐링/사망 감지)는 전부 IN_COMBAT 상태 기계에 있으므로,
                    # 예전처럼 루틴 안에서 "자동전투가 끝나길 기다리기"만 하면 자동전투가 한 번 깨졌을 때
                    # 아무도 전투를 몰지 않아 그대로 멈춘다. 전투가 끝나면 FIELD_WAIT로 복귀하고, 상자 없음
                    # 판정이 다시 나면 이 귀환 루틴을 처음부터 다시 탄다.
                    print("⚔️ [TRIGGER_EXIT] 필드맵 귀환 중 전투 조우 - 전투 모드로 전환합니다.")
                    exit_first_start_time = None
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time()
                    last_empty_shortcut_detected_time = 0
                    last_state_changed_time = time.time()
                    transition_delay_count = 0
                    continue
                if fieldmap_return_result == "retry":
                    # 자동이동이 멈췄고 재개/상자 사다리도 "없습니다"로 끝난 경우 - state를 TRIGGER_EXIT로
                    # 그대로 두면 다음 틱에 이 루틴을 처음부터(=필드맵 재확장부터) 다시 탄다.
                    fieldmap_return_retry_count += 1
                    if fieldmap_return_retry_count > FIELDMAP_RETURN_RETRY_LIMIT:
                        raise RuntimeError(f"필드맵 경유 귀환 재시도 {FIELDMAP_RETURN_RETRY_LIMIT}회 초과 - 프로세스 강제 재시작으로 복구를 시도합니다.")
                    print(f"🔁 [TRIGGER_EXIT] 필드맵 귀환 재시도 {fieldmap_return_retry_count}/{FIELDMAP_RETURN_RETRY_LIMIT} - 다음 틱에 필드맵을 다시 열어 명령을 새로 내립니다.")
                    transition_delay_count = 0
                    time.sleep(1.0)
                    continue
                raise RuntimeError("필드맵 아이콘 경유 귀환 루틴 실패 - 프로세스 강제 재시작으로 복구를 시도합니다.")

            # 🚨 [v1.14.0-hotfix4] 독립형 절대 Watchdog 가드 이식:
            # 백스텝 복구 드래그 동작 등으로 인해 미니맵이 강제로 움직여 exit_stuck_count가 0으로 도중에 초기화되더라도,
            # 최초 정체 발생 시점(exit_first_start_time) 기준으로 exit_watchdog_seconds 동안 필드를 벗어나지 못했다면 무조건 강제 앱 리셋 복구 프로세스를 작동시킵니다.
            # 🚨 [2026-08-12] 기준 시간을 고정 5분(300초)에서 farming_method별 단축값(exit_watchdog_seconds)으로 교체.
            if exit_first_start_time is not None:
                elapsed_exit_time = int(time.time() - exit_first_start_time)
                if elapsed_exit_time >= exit_watchdog_seconds:
                    raise RuntimeError(f"탈출 {exit_watchdog_seconds:.0f}초 초과 앱 강제 재시작: {elapsed_exit_time}초 동안 탈출하지 못하여 프로세스 강제 리셋을 수행합니다.")

            # 💡 [기습 방어 인터럽트] 탈출 중 전투 발생 즉시 0.1초 만에 전투 태세 전환
            if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                print("⚔️ [TRIGGER_EXIT 인터럽트] 탈출 행군 중 기습 포착! 즉시 전투 모드로 스위칭합니다.")
                # 🚨 [v1.14.0-hotfix4] 전투 돌입 시에는 탈출 정체 누적 타이머를 초기화하여, 전투 시간으로 인한 억울한 타임아웃 격발을 방지합니다.
                exit_first_start_time = None
                state = "IN_COMBAT"
                yuzuna_done = False
                milana_done = False
                guksu_done = False
                auto_combat_paused_for_skill = False
                combat_entry_start_time = time.time() 
                last_empty_shortcut_detected_time = 0
                continue

            # 🚨 [2026-08-27 TRIGGER_EXIT 하켄 메뉴 미처리 결함 완치 - 이제 대부분 위쪽 "공용 하켄 가드"에서
            # 먼저 잡힘] 원래 여기 있던 사유: TRIGGER_EXIT 루프가 check_and_handle_harken_menu()를 호출한
            # 적이 없어 하켄 메뉴가 뜬 채로 "화면 과도기" 폴링만 반복하다 엉뚱한 뒤로가기 폴백으로 빠지던 결함
            # (2026-08-27 20:17경 실전 확인). 이후 재확인 결과, "화면 과도기" 프린트 자체가 이 TRIGGER_EXIT
            # 분기보다 훨씬 앞쪽의 공용 전처리 블록(state 무관하게 매 틱 먼저 도는 코드, 1350행 부근)에서
            # 나오는 것이었고, 그 블록이 먼저 continue해버려서 아래 이 체크는 사실상 도달 못 하는 죽은 코드였음
            # (2026-08-27 21:06경 실전 로그로 재확인). 그래서 그 공용 전처리 블록에 동일 체크를 추가함 - 이제
            # 대부분의 경우 거기서 먼저 잡힌다. 여기는 혹시 모를 예외 경로(공용 블록을 우회해 TRIGGER_EXIT에
            # 진입하는 경우)를 위한 2차 안전망으로 남겨둔다.
            harken_menu_state_exit = check_and_handle_harken_menu(
                device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda
            )
            if harken_menu_state_exit in ("returned", "blessing"):
                print(f"   ➔ 🚪 [TRIGGER_EXIT 하켄 가드] 나가기 도중 하켄 메뉴 감지, '{harken_menu_state_exit}' 처리 완료.")
                time.sleep(2.0)
                last_click_time = time.time()
                exit_prev_minimap = None
                continue

            # 🚨 [2026-08-27 유령성 상자파밍 나가기 경로탐색 버그 완치] 실기 검증 완료(사용자와 라이브 ADB로 확인):
            # 4층 상자 소진 후 나가기로 3층 체크포인트 바로 앞까지 넘어온 상태에서 나가기를 다시 누르면 "목적지로
            # 가는 경로를 찾을 수 없습니다" 토스트가 뜨며 매번 실패한다(해당 타일에서의 경로탐색 버그로 추정).
            # 전진 스와이프 1회로 그 타일을 벗어난 뒤 나가기를 재탭하면 확실히 해소됨. exit_clicked_once 여부와
            # 무관하게(1차 탭이든 정체 재시도든) 이 토스트가 보이면 즉시 잡아서 처리한다.
            if dungeon_name == "북쪽의 유령선" and farming_method == "상자파밍" and exit_last_action_was_exit_tap:
                if check_template_present(img_np, t_no_chest, 0.55):
                    print("⚠️ [나가기 경로탐색 버그 감지] '경로를 찾을 수 없습니다' 토스트 확인 - 전진 스와이프 후 나가기를 재시도합니다.")
                    h_s, w_s = img_np.shape[:2]
                    scale_x_s, scale_y_s = w_s / 1440.0, h_s / 2560.0
                    safe_device_shell(device, f"input swipe {int(720*scale_x_s)} {int(1500*scale_y_s)} {int(720*scale_x_s)} {int(900*scale_y_s)} 300")
                    time.sleep(1.5)
                    coords_exit_retry = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                    if not coords_exit_retry:
                        coords_exit_retry = (1338, 461)
                    safe_device_shell(device, f"input tap {coords_exit_retry[0]} {coords_exit_retry[1]}")
                    time.sleep(0.2)
                    safe_device_shell(device, f"input tap {coords_exit_retry[0]} {coords_exit_retry[1]}")
                    exit_last_action_was_exit_tap = True
                    last_click_time = time.time()
                    exit_prev_minimap = None
                    exit_stuck_count = 0
                    continue

            exit_touched_this_loop = False
            # 출구 버튼 터치 (최초 1회 터치)
            if not exit_clicked_once:
                if time.time() - last_click_time > 3.0:
                    coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                    if coords_exit:
                        ex, ey = coords_exit
                        print(f"⏭️ [던전 탈출 시도] '출구 이동' ({ex}, {ey}) 터치합니다.")
                        safe_device_shell(device, f"input tap {ex} {ey}")
                        time.sleep(0.2)
                        safe_device_shell(device, f"input tap {ex} {ey}")
                        exit_last_action_was_exit_tap = True
                        last_click_time = time.time()
                        last_target_coords = (ex, ey)
                        exit_clicked_once = True
                        
                        # 터치 직후에는 캐릭터가 출발 연출을 수행하므로 미니맵 스턱 판정을 1턴 스킵
                        exit_prev_minimap = None
                        exit_stuck_count = 0
                        exit_touched_this_loop = True

            # 미니맵 정지 모니터링 (3초 간격 스캔 연계)
            h, w = img_np.shape[:2]
            scale_x, scale_y = w / 1440.0, h / 2560.0
            gray_current = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            # Y: 115~315, X: 1117~1317 화살표 관측 구역
            current_mini = gray_current[int(115 * scale_y):int(315 * scale_y), int(1117 * scale_x):int(1317 * scale_x)]

            is_real_field = check_field_anchor_present(img_np, t_field, 0.62)

            if exit_prev_minimap is not None and is_real_field:
                diff = cv2.absdiff(current_mini, exit_prev_minimap)
                mean_diff = np.mean(diff) / 255.0
                print(f"📊 [탈출 스턱 분석기] 미니맵 미세 움직임 변동 값: {mean_diff:.4f}")
                
                if mean_diff < 0.05:
                    exit_stuck_count += 1
                    
                    # 🚨 [v1.14.0-hotfix4] 최초 정체(스턱 1회차 이상)가 감지된 바로 그 시점에만 탈출 타이머를 개시합니다.
                    # 이후 백스텝 복구 드래그 등으로 인해 캐릭터가 움직여 exit_stuck_count가 0으로 리셋되어도,
                    # 이 최초 정체 발생 타임스탬프는 덮어쓰지 않고 엄격히 보존되어 절대적 5분 watchdog 카운트가 유효하게 유지됩니다.
                    if exit_first_start_time is None:
                        exit_first_start_time = time.time()
                        
                    exit_first_str = datetime.datetime.fromtimestamp(exit_first_start_time).strftime('%Y-%m-%d %H:%M:%S')
                    elapsed_exit_time = int(time.time() - exit_first_start_time)
                    print(f"⚠️ [탈출 정체 스택] 미니맵 정지 감지 ({exit_stuck_count}/5 회) (최초 탈출 시작: {exit_first_str}, 누적 경과: {elapsed_exit_time}초)")
                    
                    # 🚨 [2026-08-30 유령성4층 착지 스턱 즉시 스와이프] 재개버튼 신호로 "진짜 스턱인지"
                    # 미리 판별해보려 했으나(2026-08-29~30 시도) 활성/비활성 전환 창이 우리 스크린샷 폴링
                    # 주기보다 짧아 실전에서 매번 놓쳤음(다른 던전에서도 쓰려던 범용 아이디어라 완전히
                    # 폐기하지 않고 dev/ROADMAP.md로 이관). 대신 이 던전은 실전 로그로 "1회차 정체 = 예외
                    # 없이 항상 진짜 스턱, 결국 전진 스와이프 필요"임이 반복 확인됐으므로, 1~2회차의 범용
                    # 완충 연타(상자/출구 재탭)를 건너뛰고 1회차부터 곧장 전진 스와이프+출구 재탭(원래
                    # 5회차 전용 복구)을 실행한다. 특히 1회차의 범용 상자 버튼 연타는 이 착지 지점이 실제
                    # 3층 필드라 자칫 진짜 상자를 열어버려 "의도치 않은 3층 상자주회"로 새는 위험까지 있어
                    # (사용자 지적) 이 던전에서는 아예 건드리지 않는다.
                    if dungeon_name == "북쪽의 유령선" and farming_method == "상자파밍":
                        if elapsed_exit_time >= exit_watchdog_seconds:
                            raise RuntimeError(f"탈출 {exit_watchdog_seconds:.0f}초 초과 앱 강제 재시작: {elapsed_exit_time}초 동안 탈출하지 못하여 프로세스 강제 리셋을 수행합니다.")
                        exit_recovery_retry_count += 1
                        print(f"🚪🚨 [탈출 정체 복구 작동 - 유령성4층 전용 즉시발동] 1회차부터 곧바로 전진 스와이프(위로) 후 출구단추 0.1초 연사 터치를 단행합니다. (누적 경과: {elapsed_exit_time}초, 복구 시도 {exit_recovery_retry_count}회)")
                        sx = int(720 * scale_x)
                        sy1 = int(1500 * scale_y)
                        sy2 = int(900 * scale_y)
                        safe_device_shell(device, f"input swipe {sx} {sy1} {sx} {sy2} 300")
                        time.sleep(1.5)
                        coords_exit_immediate = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                        if not coords_exit_immediate:
                            coords_exit_immediate = (int(1338 * scale_x), int(462 * scale_y))
                        ex_immediate, ey_immediate = coords_exit_immediate
                        safe_device_shell(device, f"input tap {ex_immediate} {ey_immediate}")
                        time.sleep(0.1)
                        safe_device_shell(device, f"input tap {ex_immediate} {ey_immediate}")
                        time.sleep(2.0)

                        exit_last_action_was_exit_tap = True
                        exit_clicked_once = False
                        exit_stuck_count = 0
                        exit_prev_minimap = None
                        state = "FIELD_WAIT"
                        last_click_time = time.time()
                        continue

                    # 🚨 [v1.14.0-hotfix2] 정지 스택 1~2회차 신속 예비 연타 복구 작동 (유령성4층 상자파밍 외)
                    if exit_stuck_count == 1:
                        # 1회차: '상자 이동' 단추 5회 연타 주입
                        coords_chest = find_chest_btn_coords(img_np, t_move_chest_act, t_move_chest_deact, 0.70)
                        if coords_chest:
                            cx, cy = coords_chest
                            print(f"👉 [정체 1단계 복구] '상자 자동 이동' 단추 연타 5회 주입 ({cx}, {cy})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {cx} {cy}")
                                time.sleep(0.1)
                        else:
                            cx_fixed, cy_fixed = int(1338 * scale_x), int(577 * scale_y)
                            print(f"👉 [정체 1단계 복구] 상자 단추 미검출로 고정 좌표 연타 5회 주입 ({cx_fixed}, {cy_fixed})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {cx_fixed} {cy_fixed}")
                                time.sleep(0.1)
                        exit_last_action_was_exit_tap = False

                    elif exit_stuck_count == 2:
                        # 2회차: '출구 이동' 단추 5회 연타 주입
                        coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                        if coords_exit:
                            ex, ey = coords_exit
                            print(f"👉 [정체 2단계 복구] '출구 이동' 단추 연타 5회 주입 ({ex}, {ey})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {ex} {ey}")
                                time.sleep(0.1)
                        else:
                            ex_fixed, ey_fixed = int(1338 * scale_x), int(462 * scale_y)
                            print(f"👉 [정체 2단계 복구] 출구 단추 미검출로 고정 좌표 연타 5회 주입 ({ex_fixed}, {ey_fixed})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                                time.sleep(0.1)
                        exit_last_action_was_exit_tap = True
                else:
                    exit_stuck_count = 0
                
                if exit_stuck_count >= 5:
                    elapsed_exit_time = int(time.time() - exit_first_start_time)
                    if elapsed_exit_time >= exit_watchdog_seconds:
                        raise RuntimeError(f"탈출 {exit_watchdog_seconds:.0f}초 초과 앱 강제 재시작: {elapsed_exit_time}초 동안 탈출하지 못하여 프로세스 강제 리셋을 수행합니다.")
                    
                    exit_recovery_retry_count += 1

                    # 🚨 [2026-08-27 유령성 4층 나가기 무한루프 완치] 4층에서 3층으로 내려온 직후 착지 타일은
                    # 실기 확인 결과 "경로를 찾을 수 없습니다" 토스트조차 안 뜨고(위 나가기 경로탐색 버그 완치
                    # 블록의 토스트 감지 조건이 무효화됨) 그냥 미니맵이 정지된 채로만 잡힘. 이 상태에서 범용
                    # 백스텝(뒤로 후진, sy1→sy2가 아래 방향)으로는 같은 타일에 계속 갇혀 "출구 탭→정지 감지→
                    # 백스텝→다시 정지" 무한 루프에 빠짐(실전 로그로 확인: 2026-08-27 19:43~19:46, 3사이클 이상
                    # 반복하며 마을 복귀 실패). 사용자 확인: 이 지점은 뒤로가 아니라 "위로 한 발짝" 전진해야
                    # 실제로 타일을 벗어난다 - 3층→4층 진입 시 썼던 전진 스와이프와 동일 좌표를 재사용한다.
                    if dungeon_name == "북쪽의 유령선" and farming_method == "상자파밍":
                        print(f"🚪🚨 [탈출 정체 복구 작동 - 유령성4층 전용] 정지 감지로 전진 스와이프(위로) 후 출구단추 0.1초 연사 터치를 단행합니다. (누적 경과: {elapsed_exit_time}초, 복구 시도 {exit_recovery_retry_count}회)")
                        sx = int(720 * scale_x)
                        sy1 = int(1500 * scale_y)
                        sy2 = int(900 * scale_y)
                        safe_device_shell(device, f"input swipe {sx} {sy1} {sx} {sy2} 300")
                        time.sleep(1.5)
                    else:
                        print(f"🚪🚨 [탈출 정체 복구 작동] 정지 감지로 백스텝 후 출구단추 0.1초 연사 터치를 단행합니다. (누적 경과: {elapsed_exit_time}초, 복구 시도 {exit_recovery_retry_count}회)")
                        # 1. 백스텝 드래그 (뒤로 후진)
                        sx = int(720 * scale_x)
                        sy1 = int(1200 * scale_y)
                        sy2 = int(1600 * scale_y)
                        safe_device_shell(device, f"input swipe {sx} {sy1} {sx} {sy2} 300")
                        time.sleep(1.0)
                    
                    # 2. 출구 이동 단추 0.1초 간격 2회 탭핑
                    coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                    if coords_exit:
                        ex, ey = coords_exit
                        print(f"⏭️ [던전 탈출 복구] '출구 이동' 단추를 0.1초 텀 재클릭합니다. ({ex}, {ey})")
                        safe_device_shell(device, f"input tap {ex} {ey}")
                        time.sleep(0.1)
                        safe_device_shell(device, f"input tap {ex} {ey}")
                    else:
                        ex_fixed, ey_fixed = int(1338 * scale_x), int(462 * scale_y)
                        print(f"⏭️ [던전 탈출 복구] 출구 단추 미검출로 고정 좌표를 0.1초 텀 재클릭합니다. ({ex_fixed}, {ey_fixed})")
                        safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                        time.sleep(0.1)
                        safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                    time.sleep(2.0)

                    exit_last_action_was_exit_tap = True
                    exit_clicked_once = False
                    exit_stuck_count = 0
                    exit_prev_minimap = None
                    state = "FIELD_WAIT"
                    last_click_time = time.time()
                    continue
            
            exit_prev_minimap = current_mini
            
            if not check_field_anchor_present(img_np, t_field, 0.62):
                if check_template_present_multipass(img_np, t_yeolda, 0.65) or chest_opener.is_minigame_screen(img_np, height, width):
                    print("⚠️ [탈출 감시] 필드가 미검출되었으나, 상자 선택창('열다') 또는 미니게임 화면이 감지되었습니다. 탈출 복귀를 취소하고 상자 해제로 이행합니다.")
                else:
                    print("🎉 [탈출 무결점 성공] 던전 필드 화면이 완전히 소멸되었습니다! 사령탑 무대로 복귀합니다.")
                    exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 다음 판을 위한 변수 초기화
                    exit_first_start_time = None          # 🚨 [v1.14.0-hotfix2] 다음 판을 위한 변수 초기화
                    return True, skill_mission_success_this_combat, need_pickaxe_refill
            
            if exit_touched_this_loop or exit_clicked_once:
                time.sleep(3.0)
            else:
                time.sleep(0.3)
            continue

        elif state == "IN_COMBAT":
            if get_dead_match_score(img_np, t_anchor_dead) > 0.65 or check_template_present(img_np, t_btn_resurrect, 0.60):
                print("💀 [전투 중 주인공 사망] 전멸/주인공 사망 화면이 식별되었습니다. 부활을 집도합니다.")
                if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    safe_device_shell(device, "input tap 720 1200")
                time.sleep(1.0)
                safe_device_shell(device, "input tap 705 1241")
                print("⏳ 부활 암전 연출 대기... 무조건 10초간 제어를 홀딩합니다.")
                time.sleep(10.0)
                need_heal = True  # 부활 즉시 정비 플래그 작동
                continue

            yuzu_sc_coords = find_and_get_coords(img_np, t_sc_cheonja, 0.70)
            milana_sc_coords = find_and_get_coords(img_np, t_sc_jeongmil, 0.70)
            guksu_sc_coords = find_and_get_coords(img_np, t_sc_ttang, 0.70)

            if run_skill_logic and (not yuzuna_done) and (not milana_done) and (not guksu_done):
                if (not yuzu_sc_coords) and (not milana_sc_coords) and (not guksu_sc_coords):
                    print("🛡️ [Daphne 초입 가드 작동] 현재 화면은 전투실이 아니라 필드 오독입니다! 즉시 주도권을 FIELD_WAIT로 원상 반환합니다.")
                    state = "FIELD_WAIT"
                    time.sleep(0.5)
                    continue

            # 💡 [v1.14.1-hotfix9] 배속 및 자동 켜기 가드는 8.0초 간격으로 수행하여 자원 절약 및 로그 도배 방지
            now = time.time()
            if now - last_combat_color_check_time >= 8.0:
                last_combat_color_check_time = now
                if (not is_combat_speed_orange(img_np)) and check_combat_template_present(img_np, t_combat_slow, 0.70):
                    print("⚡ [속도 혁명] 전투 진입 확인! 배속이 회색(1배속)이므로 주황색 고속 기어로 먼저 올립니다.")
                    if find_and_click_combat_template(device, img_np, t_combat_slow, 0.65):
                        time.sleep(0.4) 
                        continue

                if run_skill_logic and skill_mission_success_this_combat:
                    if is_auto_combat_yellow(img_np):
                        print("🏆🛡️ [자동 감지] 자동전투가 이미 활성화되어 있으므로 수동 제어(수정)를 완료 처리합니다.")
                        run_skill_logic = False
                        continue
                    
                    print("🏆🛡️ [전술 이행망 작동] 핵심 광역기 가드 완수 상태 확인. 수동 모드를 즉시 해제하고 자동전투를 활성화합니다.")
                    auto_off_coords = find_and_get_auto_btn_coords(img_np, t_auto_off, 0.65)
                    if auto_off_coords: 
                        safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}")
                    else:
                        safe_device_shell(device, "input tap 1380 1720")
                    run_skill_logic = False 
                    time.sleep(1.5) 
                    continue

                if not is_auto_combat_yellow(img_np):
                    # 🚨 [2026-09-15 실전 확인] `t_auto_off` 도장은 자동전투 아이콘에 전투패턴 번호 배지가
                    # 붙기 전(로드맵 4번, 2026-08-30) 구형 모양이라, 배지가 붙은 지금 화면과는 실측 0.57
                    # 까지밖에 안 나와(임계값 0.65 미달) 좌표를 거의 못 찾는다. 그 결과 이 분기가
                    # "자동전투 꺼짐"까지는 맞게 판정하면서도 탭할 좌표를 못 찾아 아무 것도 안 하고
                    # 넘어가버려, 전투 시작 직후 자동전투가 영원히 안 켜진 채 정체하는 실전 사고가 있었다
                    # (2026-09-13/14 로그, 배속은 정상 주황인데 자동전투만 계속 꺼진 채 방치됨). 반면 이
                    # 버튼의 화면 위치 자체는 배지 숫자와 무관하게 고정(1380,1720, 1440x2560 기준 - 로드맵
                    # 4번에서 실기 확인됨)이므로, 도장 매칭이 실패해도 이 고정좌표로 바로 탭한다(바로 위
                    # 3863~3867줄의 기존 폴백과 동일 패턴).
                    auto_off_coords = find_and_get_auto_btn_coords(img_np, t_auto_off, 0.65)
                    if (not run_skill_logic) or (not auto_combat_paused_for_skill):
                        print("⚔️🛡️ [자동전투 비활성화 감지] 자동전투를 활성화하기 위해 터치합니다.")
                        if auto_off_coords:
                            safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}")
                        else:
                            safe_device_shell(device, "input tap 1380 1720")
                        time.sleep(1.0)
                        continue

            if run_skill_logic and (not skill_mission_success_this_combat):
                if time.time() - combat_entry_start_time > 35.0:
                    print("⚠️⏰ [비상 밸브 개방] 스킬 주입 제한시간 초과! 즉시 극하단 안전 좌표로 고속 자동전투 전환합니다.")
                    safe_device_shell(device, "input tap 1380 1720") 
                    run_skill_logic = False
                    continue

                if not auto_combat_paused_for_skill:
                    # 노란색(자동 온) 상태인지 컬러 판정!
                    # 만약 이미 꺼져 있다면(회색) 추가 클릭 없이 바로 auto_combat_paused_for_skill = True로 넘어감
                    if not is_auto_combat_yellow(img_np):
                        print("⚔️🛡️ [자동 감지] 자동 전투가 이미 꺼져(회색) 있습니다. 일시 중단을 확정합니다.")
                        auto_combat_paused_for_skill = True
                        continue
                        
                    # 🚨 [2026-09-15] t_auto_off 폴백과 동일 사유(도장이 배지 붙기 전 구형이라 매칭 실패
                    # 위험) - 고정좌표(1380,1720)로 폴백한다. 지금은 run_skill_logic이 항상 False라 죽은
                    # 경로지만, 다시 켜졌을 때 똑같은 함정에 빠지지 않도록 같이 고쳐둔다.
                    auto_on_coords = find_and_get_auto_btn_coords(img_np, t_auto_on, 0.65)
                    print("⚔️🛡️ [명함 센서 가동] 안전한 주황 배속 환경에서 '자동 전투'를 일시 중단합니다.")
                    if auto_on_coords:
                        safe_device_shell(device, f"input tap {auto_on_coords[0]} {auto_on_coords[1]}")
                    else:
                        safe_device_shell(device, "input tap 1380 1720")
                    auto_combat_paused_for_skill = True
                    time.sleep(0.5)
                    continue

                # ① 유즈나미키 턴
                if yuzu_sc_coords and not yuzuna_done:
                    print("🔮 [명함 포착] '천자만홍' 단축바 식별 ➔ 유즈나미키 턴 확정!!")
                    safe_device_shell(device, f"input tap {yuzu_sc_coords[0]} {yuzu_sc_coords[1]}")
                    time.sleep(0.7) 
                    
                    try: img_np_pop = capture_screen(device)
                    except: continue
                    lvl1_gray_coords = find_and_get_coords(img_np_pop, t_btn_lvl1, 0.68)
                    lvl1_atv_coords = find_and_get_coords(img_np_pop, t_btn_lvl1_atv, 0.68)
                    
                    target_lvl1_coords = lvl1_gray_coords if lvl1_gray_coords else lvl1_atv_coords
                    
                    if target_lvl1_coords:
                        print(f"      🎯 [레벨 선택] 도장 식별 성공 -> Lv1 구역 터치 시전! 좌표: {target_lvl1_coords}")
                        safe_device_shell(device, f"input tap {target_lvl1_coords[0]} {target_lvl1_coords[1]}")
                        time.sleep(0.4) 
                        
                        try: img_np_confirm = capture_screen(device)
                        except: continue
                        ok_coords = find_and_get_coords(img_np_confirm, t_btn_lvl_ok, 0.68)
                        if ok_coords:
                            safe_device_shell(device, f"input tap {ok_coords[0]} {ok_coords[1]}")
                            print("      ✅ [주입 대성공] 유즈나미키 '천자만홍 1레벨' 매칭 예약 완수!")
                            yuzuna_done = True
                            time.sleep(4.0) 
                    else:
                        print("      ⚠️ [세이프 가드] 레벨 단추 렌더링 대기... 다음 루프에서 즉시 재시도합니다.")
                    continue

                # ② 밀라나 턴
                elif milana_sc_coords and not milana_done:
                    print("🎯 [명함 포착] '정밀 공격' 단축바 식별 ➔ 밀라나 턴 확정!!")
                    safe_device_shell(device, f"input tap {milana_sc_coords[0]} {milana_sc_coords[1]}")
                    time.sleep(0.7) 
                    try: img_np_tgt = capture_screen(device)
                    except: continue
                    fire_target_monster_body(device, img_np_tgt, t_next, t_arrow)
                    print("      ✅ [주입 대성공] 밀라나 '정밀 사격' 몸통 조준 사격 완료!")
                    milana_done = True
                    time.sleep(1.5) 
                    last_empty_shortcut_detected_time = 0 
                    continue

                # ③ 격수 삼형제 턴
                elif guksu_sc_coords:
                    print("⚔️ [명함 포착] '땅 가르기 일격' 단축바 식별 ➔ 격수 형제 ➔ 전격 통과!")
                    safe_device_shell(device, f"input tap {guksu_sc_coords[0]} {guksu_sc_coords[1]}")
                    time.sleep(0.7) 
                    try: img_np_tgt = capture_screen(device)
                    except: continue
                    fire_target_monster_body(device, img_np_tgt, t_next, t_arrow)
                    print("      ✅ [주입 대성공] 격수군단 '땅 가르기 일격' 몸통 파쇄 완료!")
                    guksu_done = True 
                    time.sleep(1.5) 
                    last_empty_shortcut_detected_time = 0 
                    continue

                # ④ 앨리스 평타 턴
                elif auto_combat_paused_for_skill and (not yuzu_sc_coords) and (not milana_sc_coords) and (not guksu_sc_coords):
                    if last_empty_shortcut_detected_time == 0:
                        last_empty_shortcut_detected_time = time.time()
                        continue
                        
                    if time.time() - last_empty_shortcut_detected_time > 1.5:
                        if check_template_present(img_np, t_next, 0.55) or check_template_present(img_np, t_arrow, 0.55):
                            print("🏹 [명함 추론 완료] 단축바 정체 공백 1.5초 유지 ➔ 앨리스 평타 ➔ 전투 확정 사격!")
                            fire_target_monster_body(device, img_np, t_next, t_arrow)
                            time.sleep(1.0) 
                            last_empty_shortcut_detected_time = 0 
                            continue

                if yuzuna_done and guksu_done:
                    print("🏆🎉 [대성공!!] 핵심 전술 체인(천자만홍+땅가르기) 주입 만족 확인!! 즉시 판정 완료 후 자동 복구 대기 처리.")
                    skill_mission_success_this_combat = True
                    continue



            if not check_combat_template_present(img_np, t_combat_in, 0.65) and not check_combat_template_present(img_np, t_combat_slow, 0.65):
                print("🎉 배속마크 소멸! 필드로 주도권 복구 수순 가동. (연출 마진 확보를 위해 3.0초 슬로우 브레이크 가동)")
                came_from_combat = True
                last_target_coords = None  # 🚨 [2026-08-28] 위 IN_COMBAT 종료 지점과 동일 사유로 초기화
                # 🚨 [2026-08-28 hotfix] 위 전투 종료 지점과 동일 사유 - came_from_combat 소비를 건너뛰지
                # 않도록 곧장 TRIGGER_EXIT로 넘기지 않고 항상 FIELD_WAIT로 보낸다.
                if farming_method == "상자파밍":
                    resume_or_confirm_chest(
                        device, img_np, t_move_resume_act, t_move_resume_deact,
                        t_move_chest_act, t_move_chest_deact, t_no_chest
                    )
                    last_click_time = 0.0  # 🚀 [2026-08-30] FIELD_WAIT 상자탭 4초 쿨타임 파쇄
                state = "FIELD_WAIT"
                time.sleep(3.0)
            else: time.sleep(0.3)

        elif state == "BRANCH_CHECK":
            if chest_opener.is_minigame_screen(img_np, height, width): state = "PLAY_MINIGAME"
            elif check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75): state = "CLEAR_CHECK"
            else: time.sleep(0.2)

        elif state == "PLAY_MINIGAME":
            chest_opener.solve_trap_game(device, img_np)
            try: img_np_post = capture_screen(device)
            except: continue
            if chest_opener.is_minigame_screen(img_np_post, height, width): state = "PLAY_MINIGAME"
            else: state = "CLEAR_CHECK"
            continue

        elif state == "CLEAR_CHECK":
            if check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75):
                safe_device_shell(device, "input tap 701 333")
                time.sleep(0.8)
            else:
                if check_field_anchor_present(img_np, t_field, 0.65):
                    print("✨ [상자깡 완료 및 필드 안착] 다음 탐색으로 정상 복귀합니다.")
                    state = "FIELD_WAIT"
                    came_from_chest = True
                    time.sleep(1.0)
                else:
                    time.sleep(0.3)

        time.sleep(0.001)