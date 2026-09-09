import sys
import os
import datetime
import time
import json

CURRENT_VERSION = "1.21.2" # 📋 [시스템 버전 변수] 업데이트 시 이 버전 수치만 수정하시면 일괄 동기화됩니다.

# ==============================================================================
# ⚙️ [Daphne 마스터 글로벌 제어 세팅 변수 구역 - 진짜 최상단 제어판]
#    던전 주회 방식(어떤 던전을 돌지)은 아래가 아니라 프로젝트 루트의 .bat 파일 선택으로 정합니다.
#    이 구역은 "어떤 프리셋을 쓰든 공통으로 적용되는" 설정값만 모아둔 곳입니다.
# ==============================================================================

LIMIT_DUNGEON_LOOPS = 5             # 🔄 [마을 회군 기준] 던전을 몇 바퀴 돌고 마을(여관)로 복귀할지 설정
                                    #    0으로 설정 시 상자파밍은 회군 없이 무한 주회합니다. (광석파밍은 이 값과 무관하게 곡괭이가 소진될 때까지 항상 무한 재진입하므로, 광석파밍 프리셋에서는 이 값이 아무 영향도 없습니다.)
START_RUN_COUNT_OFFSET = 1          # 🚀 [초기 부팅 주회 카운트] 매크로 시작 시 초기 주회 offset 수치 (초기값=던전루프와 같은 수치, 던전에서 시작하면 해당 주회 후 복귀, 마을이면 숙박 후 주회 시작)
ENABLE_FIRST_COMBAT_SKILL = 0       # ⚔️ [초기 전투 스킬 제어] (⚠️ 현재 미구현으로 추후 구현 예정이니 무조건 0으로 고정해 주세요) (0: Off, 1: On)
ENABLE_HEAL_AFTER_CHEST = 0         # 📦 [상자 개방 후 힐링] 상자 해제/개방 성공 후 긴급 파티 치료(정비)를 작동할지 설정 (0: Off, 1: On)
HEALING_LOOPS = 5                   # 💊 [전투 후 정비 주기] 몇 회의 전투마다 파티 힐링 정비를 수행할지 설정
                                    #    - 1: 매 전투 종료 시 필드 복귀 직후 즉시 힐링 시퀀스 실행
                                    #    - 2: 2회 전투 치를 때마다 힐링 시퀀스 실행 (누적 카운트 기준)
                                    #    - 0: 전투 후 자동 힐링 정비 비활성화 (체력 소진 시까지 계속 전투 진행)

# 🏥 [힐러 및 주인공 슬롯 설정]
HEALER_SLOT = 5                         # 💊 [힐러 캐릭터 슬롯 번호] 1번~6번 슬롯 중 주 힐러(스켈톤 등)의 배치 슬롯
MASKED_ADVENTURER_SLOT = 2              # 👤 [주인공 캐릭터 슬롯 번호] 1번~6번 슬롯 중 주인공의 배치 슬롯 (2번 사망 시 주인공이 앞으로 밀릴 수 있음)
CHEST_OPENER_SLOT = 6                   # 🔑 [상자 해제 따개 슬롯] 1번~6번 슬롯 중 상자 따기(함정 해제)를 기본 담당할 캐릭터 슬롯

# 🖥️ [MuMu 에뮬레이터 콜드 리부트 자동 제어 세팅]
ENABLE_EMULATOR_REBOOT = True       # 🔄 [에뮬레이터 리부트] 디바이스 오프라인/5분 정체 지속 시 에뮬레이터 자체를 강제 재시작할지 설정
MUMU_EXECUTABLE_PATH = r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuNxMain.exe"  # 뮤뮤 실행 파일 경로
MUMU_VM_INDEX = "2"                  # 🚨 [v1.20.0] 안드15 전용화에 맞춰 기본값을 인스턴스 #2(안드15)로 변경. 아직 한
                                    #    번도 ADB 연결에 성공하지 못한 상태에서 콜드 리부트가 걸릴 때만 쓰이는
                                    #    폴백입니다. 평소엔 마지막으로 실제 연결됐던 포트를 보고 자동으로
                                    #    인스턴스 번호를 골라 재실행하므로(MUMU_PORT_TO_INDEX), 인스턴스 번호가
                                    #    #0이 아니어도 이 값을 직접 고칠 필요가 없습니다.

# ------------------------------------------------------------------------------
# 📂 [프리셋 자동 로딩 엔진] - ⚠️ 신버전부터는 이 구역을 직접 수정/선택하지 않는 것을 권장합니다.
#    어떤 던전을 돌릴지는 프로젝트 루트의 .bat 파일(예: "유령성4층 상자파밍.bat")을 실행하는 것으로
#    선택하세요 - 로컬에서 더블클릭하든 원격 대시보드에서 선택하든 동일하게 작동합니다. 아래
#    ACTIVE_PRESET_NAME 하드코딩 값은 .bat 없이 `python src/main.py`를 직접 실행할 때만 쓰이는
#    비상용 로컬 폴백입니다.
# ------------------------------------------------------------------------------

# 🚨 [2026-08-27 원격 프리셋 전환 지원 - 파일 기반으로 전환] 배치파일이 프로젝트 루트에
# `daphne_preset_id.txt` 파일을 써두면 그 내용(영문 ID 한 줄)을 아래 매핑표로 실제 프리셋명(한글)으로
# 변환해서 우선 사용하고, 파일이 없으면(기존처럼 직접 python main.py 실행 등) 아래 하드코딩 기본값을
# 그대로 씁니다 - 기존 사용 방식은 전혀 안 바뀝니다.
# ⚠️ 환경변수(`set DAPHNE_PRESET_ID=...`) 방식은 실측 결과 신뢰할 수 없어서 폐기했습니다 - 실제 원인은
# 배치파일의 `title` 줄(한글+긴 문자열 조합)이 cmd.exe의 배치파일 파싱을 깨뜨려서, 그 여파로 완전히 무관해
# 보이는 앞쪽의 `set` 줄까지 통째로 무시되는 결함이었음(2026-08-27 실기 이분탐색으로 확인 - `title`을 짧은
# 영문으로 바꾸니 해결, 반대로 `set` 줄 자체는 순수 영문 값이면 `title` 없이는 항상 정상 작동했음). 파일
# 쓰기/읽기는 이런 배치파일 파싱 취약점과 완전히 무관해 안정적으로 재현됨 - 그래도 안전하게 새 배치파일의
# `title` 줄은 항상 짧고 영문으로만 쓸 것.
# 배치파일에는 영문 ID 리터럴을 그대로 파일에 echo(변수 전개 없이 고정 문자열로) - 아래 PRESET_ID_MAP에서
# 한글 프리셋명으로 변환합니다. 새 프리셋을 원격으로 켜고 싶으면: (1) presets.json에 프리셋 추가, (2) 아래
# PRESET_ID_MAP에 영문ID: 프리셋명 한 줄 추가, (3) 새 .bat 파일에
# `echo 영문ID> daphne_preset_id.txt` 한 줄만 추가(remote_control/server.py가 루트의 모든 .bat을 자동으로
# 원격 대시보드 드롭다운에 올려주므로 서버 쪽은 손댈 필요 없음).
PRESET_ID_MAP = {
    "GHOST_2F_MINE": "유령성 2층 채굴",
    "GHOST_4F_CHEST": "유령성 4층 상자파밍",
    "WOLF_1F_CHEST": "백아1층 파밍",
    "ISBERG_HEAVYSNOW_6F_CHEST": "이스벨크 대설지대 6층 상자파밍",
    "ISBERG_HEAVYSNOW_CHURCH_CHEST": "이스벨크 대설지대 교회구역 상자파밍",
}
_preset_id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "daphne_preset_id.txt")
_preset_id_from_file = None
try:
    if os.path.exists(_preset_id_file):
        with open(_preset_id_file, "r", encoding="utf-8") as _f:
            _preset_id_from_file = _f.read().strip()
except Exception:
    _preset_id_from_file = None
ACTIVE_PRESET_NAME = PRESET_ID_MAP.get(_preset_id_from_file, "유령성 2층 채굴")  # .bat 없이 직접 실행할 때만 쓰이는 비상용 로컬 폴백 - 이 줄은 그대로 두세요

# 🚨 [최후 안전망 전용 - 직접 수정 금지] presets.json이 없거나 지정한 프리셋을 못 찾은 극단적 예외 상황에서만 쓰이는 비상 기본값입니다.
# 정상적인 상황에서는 아래 4개 값이 항상 presets.json 내용으로 자동 교체됩니다.
TOWN_NAME = "이스벨크"
DUNGEON_NAME = "백아의 동굴"
DUNGEON_FLOOR_NAME = "백아1층"
FARMING_METHOD = "상자파밍"
# 🆕 [대설지대 전용, 2026-09-07] 캠핑/하켄 있는 던전에서만 쓰는 3개 필드 - 다른 던전은 기본값(기존 동작)
RETURN_METHOD = "exit_button"
RESUPPLY_MODE = "items_only"
INN_VISIT_LOOP_INTERVAL = 0

# main.py 파일이 위치한 src/ 폴더를 기준으로 presets.json의 물리 절대 경로를 도출합니다. (v1.17.0-hotfix1부터 presets.json이 src/ 안으로 이동)
script_dir = os.path.dirname(os.path.abspath(__file__))
presets_path = os.path.join(script_dir, "presets.json")

if os.path.exists(presets_path):
    try:
        with open(presets_path, "r", encoding="utf-8") as f:
            preset_data = json.load(f)
            sel_preset = ACTIVE_PRESET_NAME if ACTIVE_PRESET_NAME else preset_data.get("active_preset")
            if sel_preset and sel_preset in preset_data.get("presets", {}):
                p_info = preset_data["presets"][sel_preset]
                TOWN_NAME = p_info.get("town", TOWN_NAME)
                DUNGEON_NAME = p_info.get("dungeon", DUNGEON_NAME)
                DUNGEON_FLOOR_NAME = p_info.get("floor", DUNGEON_FLOOR_NAME)
                FARMING_METHOD = p_info.get("farming_method", FARMING_METHOD)
                RETURN_METHOD = p_info.get("return_method", RETURN_METHOD)
                RESUPPLY_MODE = p_info.get("resupply_mode", RESUPPLY_MODE)
                INN_VISIT_LOOP_INTERVAL = p_info.get("inn_visit_loop_interval", INN_VISIT_LOOP_INTERVAL)
                print(f"📂 [프리셋 로드 성공] 활성화된 프리셋: {sel_preset}")
                print(f"   - 마을: {TOWN_NAME} | 던전: {DUNGEON_NAME} | 층: {DUNGEON_FLOOR_NAME} | 방식: {FARMING_METHOD}")
            else:
                print(f"⚠️ [프리셋 경고] 지정된 프리셋 '{sel_preset}'을 presets.json에서 찾지 못했습니다. 기본 설정을 적용합니다.")
    except Exception as pr_err:
        print(f"⚠️ [프리셋 로드 에러] {pr_err}. 기본 설정을 적용합니다.")
else:
    print(f"⚠️ [프리셋 경고] presets.json 파일이 존재하지 않습니다. ({presets_path}) 기본 설정을 적용합니다.")

if DUNGEON_FLOOR_NAME == "백아2층":
    DUNGEON_FLOOR = 2
else:
    DUNGEON_FLOOR = 1
# ==============================================================================

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.21.1
# - 최근 수정일: 2026-09-09
# - 수정 기록:
#   1.21.2: 🚨 필드맵 귀환 루틴이 캠핑 화면("쉰다")을 전혀 모르던 결함 완치(dungeon_bot.py 상세
#     참고). 캐릭터가 상자를 찾아 이동하다 마침 캠프 지점(우물) 위에 서면 맵을 열지 않아도 게임이
#     자동으로 캠핑 선택창을 띄우는데, 이 루틴은 그걸 "커서 미검출"로만 인식해 미니맵 확장 좌표만
#     계속 눌러대며 정체했다(실전 로그: TRIGGER_EXIT 진입 직후부터 캠핑 화면이 떠 있었는데도 확장
#     탭 1/3, 2/3을 헛되이 반복).
#     추가 완치(같은 세션, 실측 확정): 자동이동 대기 루프에서는 도착 판정(쉰다/우물말랐다)이
#     _handle_dungeon_interrupt() "뒤"에 있어서, "생명의 우물이 말라버렸다" 화면이 화살표 도장과
#     0.985로 매칭돼(임계값 0.82 초과) 화살표 폴백이 먼저 대화를 넘겨버리는 바람에 도착 체크가 그
#     프레임에서 아예 실행되지 못했다. 캐릭터는 이미 도착해 있으니 재개 버튼이 같은 자리를 다시
#     트리거해 "우물말랐다"가 또 뜨고, 화살표→재개 사이클이 무한 반복됐다(실전 로그: 8회 연속).
#     도착 판정을 인터럽트 처리보다 먼저 체크하도록 순서를 바꿔 완치 - "도착했는가"가 "화살표니까
#     넘긴다"보다 우선순위가 높아야 한다는 원칙.
#     추가 완치(같은 세션, 사용자 지적 - 비대칭 완치): 필드맵 귀환 루틴이 스와이프 탐색 끝까지 목표
#     아이콘을 못 찾았을 때 캠핑 분기만 나가기 버튼 폴백이 있고 하켄 분기(harken_only)는 없었다.
#     사용자 지적: "교회구역 외에 다른 구역에 캐릭을 두고 매크로를 실행하면 하켄 없는 맵에서는 나갈
#     수가 없다." 하켄 분기도 아이콘 미검출 시 나가기 버튼을 눌러 도보 탈출/하켄 귀환 중 먼저 뜨는
#     쪽을 따라가도록 완치. 상세는 dungeon_bot.py 참고.
#   1.21.1: 🚨 정체 타이머(last_state_changed_time) 리셋 누락 2건 완치(dungeon_bot.py, 상세는 그
#     파일 참고). v1.21.0 실전 운용 중 발견 - 힐링 완료 직후와 상자 재개-이동 결과 처리 두 자리에서
#     명백한 화면 진행이 일어났는데도 리셋이 안 돼, 힐링/상자 처리가 끝난 직후 곧바로 "30초 정체"로
#     오판되어 비상 뒤로가기가 주입되고, 그게 마침 새로 뜬 상자 화면을 건드려 정상 처리 기회를 날렸다
#     (실전 로그: 힐링 27초 소요 → 재개 탭 완료 → 4초 뒤 "31초 정체" 오판정).
#   1.21.0: 🚀 ADB 화면 캡처를 원시(raw) 방식으로 전환 - 캡처 1회 평균 1.60초→0.63초(약 2.5배).
#     기존 screencap -p(PNG 인코딩) + PIL 디코드 대신, 원시 screencap(비압축) + 헤더 파싱 +
#     numpy reshape을 쓴다(에뮬레이터가 PNG로 압축하는 CPU 비용이 전송량 증가보다 훨씬 컸음 -
#     같은 게임의 다른 매크로 WVD도 이 방식을 씀). src/screen_capture.py 신설
#     (capture_screen_bytes/decode_screen_bytes/capture_screen) - 원시 실패 시 자동으로 기존 PNG
#     방식 폴백, 반환 shape/dtype은 기존과 완전히 동일(H,W,4 uint8 RGBA)해 호출부 코드는 안 바꿔도
#     된다. 매 루프 틱·모든 폴링 단계마다 캡처하므로 전 구간 체감 지연이 줄어든다(사용자 지적:
#     "열다 반응이 8초쯤 걸려 답답하다"). 호출부 6개 파일 46곳 전수 치환(dungeon_bot 29, main 7,
#     combat_manager 4, party_manager 4, chest_opener 1, inn_manager 1) - take_screencap_backup()
#     (로그용 실제 PNG 파일 저장)만 원본 방식 유지. chest_opener.py는 유일하게 3채널 RGB를
#     cv2.imdecode+BGR2RGB로 직접 만들던 특수 경로였는데, 합성 이미지로 채널 순서 일치를 결정적
#     테스트로 확인 후 decode_screen_bytes()의 4채널 결과에서 [:,:,:3]으로 안전하게 대체했다.
#     검증: 알파 채널 값 차이(PNG 항상 255 vs 원시 0/255 혼재)가 COLOR_RGB2GRAY 변환에 전혀 영향
#     없음을 결정적 테스트로 확인, 라이브 캡처로 shape/dtype 동일 확인, 153개 함수 AST 미정의 참조
#     전수검사(오탐 1건 - 중첩 클로저, 실결함 없음) + 전체 컴파일/임포트 확인.
#   1.20.0 (2026-09-09 후속): 🚨 대설지대 실전 완주 검증 중 발견된 결함 4건 완치. (1) [30초 정체
#     함정 완치] 아웃게임 화면 분류의 30초 정체 분기 중 heal_close/exit_mag/고정좌표 폴백 탭 경로만
#     유일하게 last_action_time을 갱신하지 않아, 마을/세계지도/던전선택/여관 어디에도 안 걸리는 화면을
#     만나면 영원히 그 분기에 갇혀 바로 아래 있는 is_any_dungeon_sel(공용 세계지도 이탈 버튼) 판정에
#     도달조차 못했다(실전 로그 2026-09-09 14:03~14:05, 유령성 던전선택 화면에서 대설지대 프리셋을
#     켰을 때 재현). 다른 분기와 동일하게 last_action_time 갱신을 추가해 완치 - 던전별 코드가 아니라
#     모든 던전이 공유하는 공용 루프라 유령성/백아에도 잠재하던 결함이었다. (2) [세계지도 목표 아이콘
#     오지정 완치] "if DUNGEON_NAME == 북쪽의 유령선: ... else: (백아 전용 도장)" 이분법이 대설지대
#     추가로 깨져, t_go_dungeon이 대설지대에서도 백아 아이콘(Cave_Wolf_btn.png)으로 로드됐다.
#     대설지대는 세계지도 직행 아이콘이 없는 마을경유형이라 이 아이콘이 세계지도에 있을 리 없어 클릭이
#     조용히 실패하고 'WORLDMAP 확정'만 반복하며 정체했다 - should_go_town 값과 무관하게 대설지대는
#     항상 마을(이스벨크) 아이콘을 목표로 하도록 완치. (3) [세계지도 스와이프 탐색 범용화] 목표 아이콘을
#     찾는 지그재그 스와이프 탐색이 is_ffxi_worldmap(유령성/노던할로우 목표일 때만)으로 게이트돼 있어,
#     유령성 던전선택에서 대설지대로 이탈했을 때 목표 아이콘(이스벨크)이 화면 밖에 있으면 스와이프
#     자체가 안 걸려 정체했다(라이브 화면 실측으로 확인: 노던할로우 지역 뷰엔 이스벨크 아이콘이 없음).
#     게이트를 제거해 모든 목표가 동일한 탐색을 쓰도록 통일 - 아이콘이 이미 보이면 스와이프 타이머(3초)
#     전에 클릭+continue로 빠져나가므로 기존 동작(백아 등)엔 영향 없음. 실전 검증: 유령성 던전선택
#     시작 → 세계지도 이탈 → 스와이프 탐색 → 이스벨크 진입까지 확인 완료. (4) [기동 복구 마을외곽 인식
#     누락 완치] recover_app_startup()의 "인게임 진입 성공" 앵커 목록에 마을외곽/대설지대 경로목록
#     화면이 빠져 있어 그 화면에서 매크로를 켜면 빈 (1,1) 탭만 35회 반복했다 - 메인 루프가 쓰는 것과
#     동일한 도장으로 추가. 이 과정에서 HEAVYSNOW_FLOOR_FILE_MAP을 지역변수에서 모듈 전역으로 승격.
#     (5) [대설지대 귀환/전투/캠핑 로직 대폭 개선, 상세는 dungeon_bot.py 참고] 전투를 메인 루프
#     IN_COMBAT으로 인계(자동전투 재활성화 보장), 캠핑을 공용 전처리 블록에서도 처리, 재정비 예약을
#     start_main_macro 호출부 3곳으로 통일, 눈보라 판별을 미니맵 확장 가능 여부로 교체, 필드 버튼
#     활성/비활성 픽셀 판별 추가, 하켄 대/소 구분 없는 탐색, 캠핑 완료("생명의 우물이 말라버렸다")
#     감지 추가. 대설지대 6층 1주회 완주(진입→상자파밍→상자없음→귀환→인벤정리→재진입) 실전 검증 완료.
#   1.20.0: 🚨 뮤뮤 안드로이드 15 전용화 + 안드15 화면 캡처 전면 실패 완치. (1) 근본 원인은 뮤뮤의
#     '앱 상주' 기능(디바이스 설정 - 기타 - "애플리케이션이 실행 중입니다", 중국어 원문 应用保活)이었다.
#     이게 켜져 있으면 뮤뮤가 앱마다 별도의 안드로이드 디스플레이를 만드는데, 그러면 (a) screencap이
#     PNG 앞에 347바이트 경고문("[Warning] Multiple displays were found...")을 평문으로 뱉어
#     Image.open()이 첫 바이트부터 실패하고(실측: 연속 10회 100% 실패), (b) 게임이 별도 디스플레이로
#     밀려나는데 input tap은 기본 디스플레이(안드로이드 홈)로 가서 클릭이 전부 엉뚱한 화면으로 샌다
#     (실측: 탭 한 번에 뮤뮤 스토어 검색창이 열림). 설정을 끄면 디스플레이가 1개로 돌아오고 캡처/입력이
#     모두 정상화된다(실측 확인). (2) 그래서 우회하지 않고 진단만 한다 - mumu_display_check.py 신설:
#     check_display_configuration()이 연결 직후(connect_mumu) 디스플레이 개수를 세어 2개 이상이면
#     원인과 해결법(설정 경로까지)을 찍고 매크로를 즉시 정지시킨다. ⚠️ 경고문을 잘라내 캡처만 되게
#     우회하는 안전망도 만들어봤다가 폐기했다 - 그러면 "화면은 제대로 읽으면서 클릭은 홈 화면으로
#     나가는" 더 위험한 상태로 계속 돌게 된다. 우회하지 않으면 캡처 실패 → 기존 실패 카운터가 재시작
#     → 재시작 시 이 점검이 잡아내고 멈추는 안전한 경로가 된다(같은 게임의 다른 매크로 WVD도 우회 없이
#     정지시킨다 - wvd-master/src/script.py:639,691). (3) 안드12 인스턴스는 그래픽 렌더러 에러(901)로
#     사실상 못 쓰게 돼 이 버전부터 지원 중단 - pick_supported_device()가 포트 번호가 아니라
#     getprop ro.build.version.release로 안드15 이상만 선별한다(인스턴스를 다시 만들어 포트가 바뀌어도
#     안 깨짐). MUMU_VM_INDEX 기본값 "0"→"2", 포트 스캔 순서도 안드15 우선으로 통일.
#   1.19.2: 대설지대 던전 추가 전 마지막 안정화 릴리즈 - (1) adb connect 시도마다 CLI가 성공/실패를 줄줄이
#     찍어 오류처럼 보이던 문제 완치: 출력을 nul로 죽이고 최종 연결된 인스턴스 번호+포트만 한 줄로 출력
#     (connect_all_mumu_ports_quietly() 신설, connect_mumu()/restart_process() 양쪽 적용). (2) 원격 정지
#     시 콘솔창이 잔존하는 결함 완치: capture_root_cmd_pid()의 PowerShell/tasklist 캡처가 부팅 시 시스템
#     부하로 1회 실패하면 그대로 영구 비활성화되던 걸 3회 재시도(1초 간격)로 보강. (3) .copied_screenshots.json
#     스크린샷 동기화 캐시가 삭제된 원본을 계속 들고 있어 무한 증식하던 결함 완치(로드 시 실존 파일만 남기고
#     정리). (4) 미사용 toastmsg_noway 도장 삭제(toastmsg_nochest와 내용 겹쳐 애초에 코드에서 참조된 적 없음).
#     (5) 정체(stuck) 복구 30초 메가블록 내 사망감지 분기가 "공식" 사망감지 분기와 동일한 체크를 하면서도
#     transition_delay_count 리셋만 빠뜨린 쌍둥이 결함 완치(같은 유형이 하루 전 유령성4층 진입 카운터
#     미리셋 버그로 이미 한 번 확인돼, 재발 방지 컨벤션을 CLAUDE.md/AGENTS.md에 추가). 상세는 각 커밋
#     참고 - 이 버전은 신규 던전(대설지대) 로직은 포함하지 않은 순수 안정화 릴리즈.
#   1.19.1: 재부팅 로그 파일명이 "reboot2" 이상으로 절대 안 올라가던 결함 완치 - 에뮬레이터 콜드 리부트
#     분기(조건 A/B) 직후 clear_restart_counter()를 호출해 카운터를 0으로 지운 채로 다음 프로세스를
#     띄우고 있었음(사용자 지적: "분명 2번 이상 리붓인데 reboot2를 본 적이 없다" - 정확한 관찰이었음).
#     리부트 카운트가 2 이상 되는 바로 그 시점에 매번 스스로 지워버리는 구조라 reboot2 이상 표기가
#     구조적으로 불가능했음. 리부트 직전 clear 2곳을 제거해 카운터가 다음 프로세스로 그대로 이어지도록
#     완치(정상 주행 돌입 시 클리어되는 다른 지점은 그대로 유지 - "회복되면 리셋" 취지 보존). 아울러
#     "수동/원격 시작만 start로 표기"를 보장하기 위해 던전별 `.bat` 3종 맨 앞에 restart_counter.txt 삭제를
#     추가(원격 시작도 같은 `.bat`를 실행하는 구조라 자동 적용됨). 상세는 dungeon_bot.py/chest_opener.py 참고.
#   1.19.0: MuMu 멀티 인스턴스(0/1/2번) 자동 감지 지원(포트→인덱스 매핑, 재부팅 시 마지막 접속 포트 기준
#     자동 재선택) 및 재부팅 시 뮤뮤 설정 파일이 프로젝트 루트에 잘못 쓰이던 결함 완치(subprocess.Popen에
#     cwd 미지정 → 정품 설치 루트로 명시). 앱 재시작 우선 정책 복원(뮤뮤 재부팅 직행에서 원복) 및 가로화면
#     정체 캡 30→3회 단축(과잉 대기 완화). 원격 정지(/stop) 시 콘솔창이 "가끔" 안 닫히던 결함 완치 -
#     os.execv 자기재시작을 한 번이라도 거치면 직계 부모가 이미 죽은 이전 python.exe가 되어 진짜 cmd.exe를
#     못 찾던 구조적 결함이었음(1.18.0의 콘솔창 종료 기능 자체는 정상이었으나 재시작 후엔 무력화됐음).
#     최초 부팅 시점에만 cmd.exe PID를 캡처해 환경변수(재시작에도 안 끊김)/파일(macro_cmd.pid)로 전달하도록
#     전환. 유령성4층 상자파밍 나가기 관련 결함은 dungeon_bot.py, 콘솔창 관련 상세는 remote_control/server.py 참고.
#   1.18.0: 유령성 4층 상자먹튀파밍 신규 던전 주회 추가(3층 하켄 진입 → 체크포인트+스와이프로 4층 진입 →
#     기존 상자파밍 루프 재사용 → 나가기 경로탐색 버그/4층→3층 하강 무한루프 우회) 및 다수 결함 완치.
#     TRIGGER_EXIT 하켄 메뉴 미처리(공용 전처리 블록으로 이동해 완치), harken_blessing_donothing/전투
#     인식(combat_in/slow) 이진화 불일치로 판정 여유가 얇던 문제, last_target_coords가 상자/출구 버튼을
#     공유해 정비 후 엉뚱한 버튼을 재탭하던 결함, came_from_combat/chest 플래그가 소비되지 못하고 지연돼
#     힐링이 뜬금없이 발동하던 결함을 완치. 상자 버튼 단일탭화, 힐/전투/상자 직후 "재개(1번)" 버튼 도입,
#     재개 오진 방지(상자 버튼 재확인)로 던전 필드 정지 시간을 단축. 원격 대시보드 프리셋 전환을 파일
#     기반(daphne_preset_id.txt)으로 전환하고, 원격 정지 시 부모 콘솔창까지 함께 종료하도록 개선. 던전
#     주회 방식별 `.bat` 3종(백아1층/유령성2층/유령성4층)을 분리하고, `main.py` 상단을 "공통 글로벌
#     설정값 → 프리셋 로딩 엔진" 순서로 재배치해 프리셋을 직접 수정/선택하지 않는 것을 표준으로 전환.
#   1.17.1-hotfix10: 유령성 던전선택 '2nd' 층 버튼 미인식 결함 완치 - 유령성 3회차 엔딩(진엔딩) 이후
#     던전선택 화면 배경이 바뀌면서(사용자 확인: 2회차→3회차 진입 시 진엔딩 진행에 따라 배경 그래픽
#     자체가 교체됨), 고정 이진화 문턱 160에서 매칭 점수가 0.72까지 떨어져(임계값 0.88 미달) 밤새
#     (2026-08-26 00:03~10:23, 7시간+) 단 한 번도 던전에 진입하지 못하고 2초 간격 무한 재시도만
#     반복하던 실전 결함 완치. 신규 `find_and_click_template_multipass()`로 교체해 문턱 160(기존 배경)/
#     150(진엔딩 이후 배경)을 순차 시도(신뢰도 임계값 0.88은 그대로 유지) - 실측 검증 결과 문턱 150에서
#     점수 0.90으로 회복, 다른 구역 버튼과의 오탐 여유도 0.10 이상 확보. 이 계기로 "배경이 바뀔 수 있는
#     선택지형 화면은 멀티패스를 기본으로" 컨벤션을 CLAUDE.md/AGENTS.md에 문서화.
#   1.17.1-hotfix9: (1) 목요일 콘텐츠 추가 점검 후 리소스 다운로드가 기가바이트 단위로 나오면 recover_app_startup()의
#     35회(약 2분) 스킵가드 예산이 그대로 소진돼 다운로드 도중 에뮬레이터가 강제 리부트되던 결함 완치 - 알려진 팝업
#     처리 시마다 예산 리셋 + 다운로드 확인 버튼 클릭 시점부터 20분(DOWNLOAD_GRACE_SECONDS) 유예 추가.
#     (2) 던전봇의 일반 정체(30초) 복구용 비상 뒤로가기가 주입 직후 정체 타이머 자체를 리셋해버려서, 뮤뮤가 진짜
#     동결돼도 5분 하드 리밋(강제 재시작)이 영원히 도달 못 하던 구조적 결함 완치(실전 확인: 2026-08-21 03:38~07:15,
#     3시간 37분 무한 방치). 상세는 dungeon_bot.py 참고.
#     (3) recover_app_startup()이 하켄 메뉴(귀환목록/이동목록/가호팝업) 화면을 전혀 검사하지 않아, 하켄 메뉴가 떠
#     있는 상태에서 매크로를 재시작하면 35회 예산을 빈 탭으로 허비하고 실패하던 결함 완치 - 아웃게임 스캐너에
#     이미 있던 하켄 판정 함수를 기동 복구 루프에도 재사용. 이 과정에서 함수 내부에 남아있던 불필요한 지역
#     `import dungeon_bot`가 파이썬 스코프 규칙상 UnboundLocalError 크래시를 유발하던 결함도 같이 완치.
#   1.17.1-hotfix8: (1) 피장막(딸피 연출) 관통 인식 - 붉은 안개가 씌워지면 흰 글씨 이진화 문턱(160)에서
#     텍스트가 사실상 지워지던 결함을 다중 이진화 패스(160/100/85)로 완치, 상자 대화창을 하켄 가호로
#     오판하던 결함 완치, 파티창 빈사색 픽셀 감지로 안개 원인(빈사 상태)을 직접 잡아 힐 시퀀스 자동 격발.
#     (2) 하켄 메뉴(귀환목록/가호팝업) 화면에서 매크로를 시작/재시작하면 어떤 아웃게임 앵커와도 안 맞아
#     무한 정체하던 결함 완치 - dungeon_bot.py의 하켄 판정 함수를 main.py 아웃게임 스캐너에도 재사용.
#     (3) 유령성 하켄 가호 색상 등급이 실제 유용도와 안 맞는 사례(녹색 "오드"가 파란색 "민첩"보다 낮게
#     판정) 확인 - 이름 도장(데몬족 헌터/오드의 가호) 우선 인식 후 색상 등급 폴백으로 개선.
#     상세는 dungeon_bot.py 참고. (main.py 자체 변경분은 (1)-일부/(2))
#   1.17.1-hotfix7: 실전(2026-08-14 뮤뮤 완전 행) 사고에서 발견된 재시작 카운터 미기록 결함 완치 -
#     restart_process()가 launch_daphne_app()/recover_app_startup() 등 ADB 통신을 거치는 위험한 복구
#     단계까지 다 끝난 뒤에야 연속 재시작 카운터를 저장했는데, 정작 뮤뮤가 완전히 먹통이면 그 복구 단계
#     자체가 멈춰버려 카운터가 기록될 기회가 없었음 - 그 결과 Watchdog이 뒤이어 재시작을 걸어도 여전히
#     "1회차"로 보여 에뮬레이터 강제 리부트(연속 2회 조건)로 승격이 안 됨. 카운트 계산 직후, 위험한 작업
#     시도 전에 즉시 저장하도록 완치 - 최악의 경우(처음부터 완전 먹통)에도 늦어도 Watchdog 주기(4분) 안에는
#     ADB를 거치지 않는 taskkill 기반 에뮬레이터 강제 재시작으로 확실히 이어짐. 광석파밍 한정으로 main.py의
#     범용 90초 동결감지도 비활성화(채굴 사이클이 빨라지며 재발한 구조적 오탐 - dungeon_bot.py 내부의 더
#     정확한 자체 워치독에 위임, 상세는 dungeon_bot.py 참고).
#   1.17.1-hotfix6: 실전(뮤뮤 완전 동결 6시간 방치 사고)에서 발견된 자가복구 결함 2건 완치 + 그 여파로
#     드러난 동결감지 구조적 오탐 3건 완치.
#     (1) restart_process()의 증거 스크린샷 캡처(device.shell)가 자가복구를 격발시킨 원인(ADB 소켓 블로킹)에
#     똑같이 걸려 진짜 복구 절차에 도달 못 하던 결함 - daemon 스레드로 fire-and-forget 처리해 완치.
#     (2) "통화면 동결 감지" 엔진이 진짜 동결을 정확히 감지하고도 보정 터치+재스캔만 반복하고 restart_process()로
#     승격되는 경로가 없던 구조적 결함 - consecutive_freeze_count 2회 연속 시 자가복구로 승격하도록 완치.
#     (3) [2026-08-11] 위 (2) 배포 직후 재시작이 하루 70건 이상(약 10분 간격)으로 폭증. 원인 규명 결과, 동결감지가
#     사는 바깥 대순환 루프는 dungeon_bot.start_main_macro() 안에 있는 동안(채굴/귀환/재진입 사이클 전체) 아예 돌지
#     않는데, 그 블로킹이 끝나고 귀환으로 던전을 빠져나와 루프가 재개되는 순간 "최근 90초 변화"를 체크하면서 비교
#     기준이 몇 분 전(이번 던전 사이클 시작 전)에 찍힌 스냅샷이었음 - 귀환 직후 화면은 매번 똑같이 생긴 "던전선택"
#     화면으로 복귀하므로 그 사이 실제 활동이 다 있었어도 픽셀 차이가 0에 가깝게 나와 필연적 오탐. 마지막 점검 후
#     경과가 150초를 넘으면(=루프가 다른 작업으로 오래 비어있었다는 뜻) 비교를 생략하고 조용히 기준만 재설정하도록
#     완치, 임계값도 정황 추정으로 올렸던 6회 연속(9분)에서 원래 의도인 2회 연속(3분)으로 원복.
#     (4) take_screencap_backup()이 device.shell()로 기기에 저장 후 sync_screenshots_loop()의 30초 폴링에 의존하던
#     경로에 무결성 검증이 전혀 없어, 실전 stuck 증거 스샷 74개 중 거의 전부가 완전히 새까만 빈 이미지였음(확인됨).
#     메인 루프가 쓰던 신뢰도 높은 방식(device.screencap() 직접 pull + 즉시 디코드 검증)으로 교체해 완치.
#     (5) dungeon_bot.py의 하켄 앵커 로직을 "귀환" 1차 앵커 + 별도 가호 재확인의 이중 구조에서, "아무것도 안 한다"
#     (귀환목록/가호팝업 공통 앵커) 1차 확인 후 "귀환" 유무로 분기하는 단일 구조로 재구성(check_and_handle_harken_menu).
#     상세는 dungeon_bot.py 참고.
#   1.17.1-hotfix5: 실전에서 하켄의 가호 오탐지(구역 이동 목록 화면을 가호 팝업으로 오인식, 잘못된 구역 텔레포트 유발)
#     확인 및 완치는 dungeon_bot.py에서 처리. main.py 자체는 sync_screenshots_loop()가 "screencap_harken" 접미사를
#     인식 못 해 하켄 증거 스샷이 로그 폴더에 뭉뚱그려 저장되던 결함만 완치. 상세는 dungeon_bot.py 참고.
#   1.17.1-hotfix4: (main.py 자체는 변경 없음, 버전 동기화용) dungeon_bot.py에 하켄의 가호(연 1회 3지선다 팝업)
#     대응 신설. 상세는 dungeon_bot.py 참고.
#   1.17.1-hotfix3: (main.py 자체는 변경 없음, 버전 동기화용) remote_control/server.py에 백그라운드(pythonw) 실행
#     지원(시작/종료 배치파일, PID 자기기록) 및 대시보드 URL 줄바꿈/콘솔 창 깜빡임 결함 완치. 상세는 remote_control/server.py 참고.
#   1.17.1-hotfix2: (main.py 자체는 변경 없음, 버전 동기화용) remote_control/server.py에 실시간 로그+버튼식 대시보드
#     웹페이지(/dashboard, /api/state) 신설 및 마지막 실행 배치 기억 기능 추가. 상세는 remote_control/server.py 참고.
#   1.17.1-hotfix1:
#     - 갱신 데이터 확인("타이틀로") 팝업이 village_common/inn.png와 오탐되어 여관 도장을 무한 반복 터치하던 결함 완치
#     - retry.png(네트워크/서버 재시도 팝업)도 메인 루프 미체크 상태였던 것 발견 및 완치
#     - "타이틀로" 감지 시 앱 재기동 대신 매크로(파이썬 프로세스) 자체를 재시작하도록 강화 (스킬 설정 등 세션 상태 초기화 대응)
#     - 재시작 직전 스크린샷 보존 및 restart_counter 연동으로 로그가 "_rebootN"으로 남도록 완치
#   1.17.1: 테일스케일 기반 원격 시작/정지 기능 추가 (macro.pid 자기기록, remote_control/ 신설)
#   1.17.0-hotfix2:
#     - dumpsys 기반 위저드리 앱 최상단 실행 여부 사전 점검 (MuMu만 켜진 상태 부팅 시 5분 정체 방지)
#     - 던전선택 층버튼 클릭 후 고정 5초 대기를 최대 10초 필드안착 폴링으로 교체 (하켄 귀환 무한루프 완치)
#     - recover_app_startup 인게임 진입 판정 순서 재배치 (리소스 다운로드 화면 인식 누락 완치)
#   1.17.0-hotfix1:
#     - 세계지도 버튼 그레이스케일 매칭 전환 (유령성 스턱 완치)
#     - 던전선택 로그 던전명 표시
#     - 월드맵 지그재그 Step1 스케일 보정
#     - 광석파밍 회군을 need_pickaxe 전용 플래그로 전면 재설계 (N주회 카운터 미참조 + 무한 재진입)
#     - LIMIT_DUNGEON_LOOPS=0 무한주회 지원
#     - village_common 공용 도장(여관/캐릭터창닫기/월드맵아이콘)으로 마을 상태 판별 체계 전환
#     - t_world_map 그레이스케일 전환 및 텍스트 크롭
#     - recover_app_startup 가로화면 무한루프(탈출구 부재) 완치
#     - 월드맵 분기 should_go_town을 need_pickaxe_refill과 동기화, 지그재그 상태 재진입 시 초기화
#     - worldmap_icon 야간 배경 이진화 오탐(0,0 좌표) 완치 (그레이스케일 전환) 및 마을 이탈 로그 보강
#     - 프리셋 불일치 던전선택 화면 범용 인식 (open_world_map_btn ROI 공용 판별) 및 자동 세계지도 이탈
#     - 재시작 직전 스턱 화면 증거 보존용 screencap(prefix=stuck) 캡처 및 로그 동기화 접미사 인식
#   1.17.0: FFXI 콜라보 북쪽의 유령선 2층 광석파밍(마이닝) 주회 상태 머신 및 presets.json 동적 가변 프리셋 로딩 엔진 구축, 층 매칭 오검출 방지 임계치 0.88 상향 튜닝
#   1.16.0: 상자 대화창 우하단 화살표(dialogue_indicator.png) 감지 터치 개편, 공포 상태이상 캐릭 선택 시 "열 수 없다" 대화 팝업 복구 루프 추가, templates/chestopening/ 하위로 상자 관련 템플릿 폴더 정돈
#   1.15.0: 지정 슬롯 따개(CHEST_OPENER_SLOT) 터치 개편, 상자공포 상태이상(chestfear.png) 자동 감지 및 주인공/타 슬롯 우회 회피 시퀀스 추가, whowillopenit 템플릿 의존성 제거 및 '열다' 버튼 소멸 기반 진입 판정 최적화
#   1.14.1-hotfix10: 전투 중 배속/자동 8초 가드 단일 블록 통합(상하단 동일 타이머 충돌로 인한 자동전투 8초 감지 영구 스킵 결함 완치), 정비 즉시 재사격 및 상자 없음 인지 시 터치 쿨타임(last_click_time = 0) 파쇄(정비 직후 7초 지연 및 출구 탭 3초 지연 제거)
#   1.14.1-hotfix9: 상자깡 완료 연출 마진 sleep(1.0초) 탈거를 통한 딜레이 차감, 전투 중 배속/자동 켜기 가드 8초 쿨타임 주기 검사 도입, 화면 과도기 대기 한계 상향(5회 ➔ 10회)으로 연출 대기 stuck 복구 안정화
#   1.14.1-hotfix8: 전투 중 딸피 피장막 상황 앵커 소실 버그 완치(배속/자동 앵커 그레이스케일 매치 전환 및 컬러 픽셀 R-B 가드 결합으로 핑퐁 연타 박멸), 백아 던전 층수 분기 제어(DUNGEON_FLOOR 추가 및 2층 활성화 유무에 따른 물리 좌표 분기 적용)
#   1.14.1-hotfix7: 고비용 독 감지 모니터링(HSV 변환 및 6개 슬롯 픽셀 감지) 함수 및 분기 완전 삭제 (CPU 사용량 대폭 경감 및 프레임 렉 근절 최적화)
#   1.14.1-hotfix6: 힐러 도장 이진화 매칭/캐싱 최적화, 스캔 하단 ROI(2000~2540) 지정 및 1차 정상/2차 red 분리 이중 격리 검출 패치, red 진입 렉 대기(1.5초) 주입, 전투/상자 종료 후 힐링 누수 버그 완치
#   1.14.1-hotfix5: 여관 루프 정체 방지 45초 Watchdog 가드 탑재 및 1:1 이진화 매치 적용
#   1.14.1-hotfix4: OpenCV 픽셀 번짐 방지를 위해 동적 리사이저 배제 및 원본 1:1 그레이스케일 매칭 롤백, dungeon_bot 내 load_grayscale_template 정의 유실 NameError 수정 완료
#   1.14.1-hotfix3: 템플릿 크기 및 ROI 정밀 분석 대조를 통한 여백 마진 보강, 그레이스케일 매칭 및 동적 템플릿 축소 스케일러 적용
#   1.14.1: 신규 필드 템플릿 연동, 미니맵 오토-오픈 가드 구축 및 전투/자동전투 앵커 ROI 한정 이식
#   1.14.0-hotfix4: 탈출 복구 드래그 동작에 의한 타이머 오초기화 방지 (최초 정체 시점 타이머 보존 및 5분 절대 Watchdog 가드 이식)
#   1.14.0-hotfix3: 바탕화면 튕김/가로 화면 30초 정체 시 예외 격발 및 에뮬레이터 자동 2단계 리부팅 복구 가드 탑재
#   1.14.0-hotfix2: 탈출 5분 리셋 누적 버그/출구 클릭 건너뜀 수정 및 정체 1~2회 시점 예비 연타 기능 이식 (동기화)
#   1.14.0-hotfix1: README 안내 보강에 따른 핫픽스 빌드 반영 (동기화)
#   1.14.0: 스크린샷 동기화 디스크 캐시(.copied_screenshots.json) 및 60초 정체 완화 임계값(0.45) 힐링 연동 가드 추가
#   1.13.20-hotfix3: 전투 진행 중 필드 앵커 오검출 및 과도기 감지 대기(else: continue)에 갇혀 자동전투 버튼 클릭이 무산되던 결함 수정
#   1.13.20-hotfix2: 2배속 전환 이후 무한 루프에 갇혀 자동전투 버튼 클릭이 유실되던 인덴트 오류(continue 제어문) 해결
#   1.13.20-hotfix1: 탈출 정지 감지 5회 상향 및 백스텝 후 출구 이동 단추 0.1초 간격 2회 탭핑 복구 시퀀스 도입
#   1.13.20: 자동전투 켜기 씹힘 방지(auto_combat_paused_for_skill 가드 우회) 보완
#   1.13.19-hotfix2: 최상단 전투 가드 변수 리셋, 렉 보호 가드 주입, 탈출 앵커 임계치 상향 및 안전지대(700, 150) 터치 조율
#   1.13.19-hotfix1: 던전 최초 탈출 시 출구 이동 버튼 0.2초 간격 2회 터치(더블 탭) 보완
#   1.13.19: 사망/부활(InCombat_dead, btn_resurrect) 흐름 및 기동 복구(recover_app_startup) 연동 고도화
#   1.13.18: 통합 힐링 플래그 need_heal 도입, 상자 완료 필드 앵커 2차 검증 가드 주입, 임의 빈사 힐링 제거 및 임계치 완화
#   1.13.17: 전투 후 상자 획득 시 중복 힐링 충돌 차단
#   1.13.16: 상자 탐색 무한 루프 방어, On/Off 1/0 치환, 버전 전역 변수화 및 상자 개방 정비 추가
#   1.13.15: dungeon_bot.py 주행 실행 차단 continue 구문 제거 및 통상 주행/토스트 인식 복원
#   1.13.14: 던전 상태 감지 코드 인덴트 교정 및 실시간 전투/필드 인식 복원
#   1.13.13: 전투(IN_COMBAT) 상태 정체 시간 리셋 결함 해결 및 최상단 예외 크래시 복구 가드 탑재
#   1.13.12: 화면 분석 실패 예외 탭핑 분기(else) 내부의 무의미한 last_action_time 업데이트 제거 핫픽스
#   1.13.11: 최초 기동 경고 화면 자동 돌파 및 최초 가동 무인 안심 가드(recover_app_startup 선행 실행) 탑재
#   1.13.10: 기동 중 공지사항 팝업 감지 시 자동 닫기 타격 가드 보강
#   1.13.9: 상자 자동 이동 터치 및 씹힘 재시도 시 0.25초 텀 2회 더블 탭 연사 기법 주입
#   1.13.8: 복구 로직 사령탑(main.py) 이관 및 에뮬레이터 최초 기동/리부트 직후 인게임 로딩 완전 돌파 연동
#   1.13.7: 최초 실행 시 에뮬레이터 미기동 감지 및 자동 콜드 기동 무인화 피처 추가
#   1.13.6: 에뮬레이터 콜드 리부트(Emulator Reboot) 기능 및 디스크 파일 연동 연속 오류 방지 가드 도입
#   1.13.5: 일반 필드 상태 정체 시간 리셋 버그 수정 및 5분 필드 정체 시 앱 리셋 재시작 가드 장착
#   1.13.4: 프로세스 자가 복구 시 게임 앱 강제 종료 및 Relaunch 세이프티 가드 도입
#   1.13.3: 5분 타임아웃 세이프티 가드 도입 및 백스텝-전진/2번단추 사격 무한 교대식 복구 시퀀스 개편
#   1.13.2: 범용 탈출 물리 백스텝-전진 복구 도입, 최후의 5회차 앱 리셋 가드 탑재, 최초 탈출 시간 누적 보존 패치
#   1.13.1: 정식 릴리즈 - watchdog_monitor_loop 선언부 NameError 버그 해결 및 1.13.1 버전 일괄 동기화
#   1.13.0-hotfix4: 핫픽스 적용 - 글로벌 제어판에 HEALING_LOOPS 변수 추가 및 제어판 최상단 이동, 상자 발견 시 힐링 유예 가드 장착
#   1.13.0-hotfix3: 핫픽스 적용 - 던전 탈출 복귀 시 지연시간을 60초에서 안전 마진 10초로 최적화 단축
#   1.13.0-hotfix2: 핫픽스 적용 - 기동 복구 진입 조건 판정에 상자, 여관, 세계지도, 마을 광장 앵커 보강
#   1.13.0-hotfix1: 핫픽스 적용 - 로딩 정체 뒤로가기 생략 및 에러 팝업 시 클릭 스킵 후 즉각 재시작
#   1.13.0: 마이너 버전업 - 게임 앱 자동 재시작 및 로딩/점검 복구 피처(restart_game_app, recover_app_startup) 구현 완료
#   1.12.6: 여관 정비 시 멀티 레벨업 '다음' 팝업 처리 구현 및 실시간 타임스탬프 로깅 래퍼 함수 도입
#   1.12.5: 탈출 정체 복구 카운트 리셋 오류 패치, 블랙박스 및 탈출 정지 최초 정체 시각 표기 추가 및 버전업
#   1.12.4: 힐러방 딸피 암전 시 블라인드 고정좌표 힐 시퀀스 핫픽스 적용 및 버전 동기화
#   1.12.3: 상자 자동 이동 완료 후 '열다' 발견 시 즉시 해제 함수 직접 호출하도록 정체 로직 버그 패치 및 버전업
#   1.12.2: 4대 예외 패치, 자연 정렬(Natural Sort) 도입, 리드미 가이드 정정 및 버전 업그레이드
#   1.12.1: 마이너 버전업 - 템플릿 디렉토리 구조 다각화(Worldmap, WolfCave, Vill_Isbelg, inn_sleep) 분리 및 동적 파일명 최적화
#   v18.00: 3시간 전 안정 버전 기반 롤백 (Base)
#   v18.01: 메인 좌표 스팟 대응 동기화
#   v18.02: ADB 통신 장애 시 os.execv 프로세스 강제 재시작 가드 장착
#   v18.03: trap_minigame_anchor.png 및 해제 좌표 보정 대응 (동기화)
#   v18.04: dungeon_bot 독 감지 필터 개편 대응 (동기화)
#   v18.05: 독 감지 필터 개편 대응 (동기화)
#   v18.06: dungeon_bot 4번째 단추 크롭 검색 대응 (동기화)
#   v18.07: dungeon_bot 힐러/따개 멀티 템플릿 대응 (동기화)
#   v18.08: dungeon_bot 상자/출구 매칭 영역 분화 대응 (동기화)
#   v18.09: dungeon_bot 힐러/따개 템플릿 정렬 및 우선순위 대응 (동기화)
#   v18.10: dungeon_bot 힐러 시스템 예약 파일 제외 필터링 대응 (동기화)
#   18.11.0: dungeon_bot 3번 체크포인트 정체 복구 대응 및 SemVer 표기 도입 (동기화)
#   18.11.1: dungeon_bot '열다' 터치 씹힘 재시도 및 갇힘 복구 대응 (동기화)
#   18.11.2: 부팅 및 재시작 시 캐릭터 선택창('누가 열 거야?') 정체 복구 가드 탑재 (동기화)
#   18.11.3: 여관 정비 시퀀스 중 ADB 통신 장애 크래시 자가 복구 가드 추가 (동기화)
#   18.11.4: 미니게임 화면 중 재시작 시 30초 정체 대기 없이 즉각 전이 복구 가드 추가 (동기화)
#   18.11.5: 대화창 화살표 저격 임계값 상향 및 '열다' 감지 시 대화저격 스킵 예외 가드 추가 (동기화)
#   18.11.6: 여권 만료 팝업에 의한 아웃게임 정체 해결용 이중 앵커 닫기 가드 탑재 (동기화)
#   1.11.7: 로딩 암전 가드, 해상도 크래시 가드, 예외 트레이스백 실시간 로깅 및 Dimension Guard 탑재 (동기화)
#   1.11.8: 4일 경과 로그 파일 자동 청소기 장착, 메인 루프 전체 이중 감시 예외 처리 보강 및 리드미 설명 개정 (동기화)
#   1.11.9: 최초 기동/재시작 자동 스샷 촬영, 스샷 동기화 스레드, 다중 사용자 경로 탐색 가드 탑재 (동기화)
#   1.11.10: 자동캡쳐 스샷 파일 네이밍 형식 개선(초단위 3자리 패딩 YYYY-MM-DD-HHMM-0SS), 기동/재시작/수동 캡쳐 접미사(start/restart/screenshot) 분기 및 중복 넘버링 처리 추가 (동기화)
#   1.11.11: 프로젝트 구조 개편으로 인한 순수 소스코드 src/ 폴더 격리 이행 및 배치 파일 경로 고도화 (동기화)
#   1.11.16: 미니게임 앵커 국소 크롭 스캔 범위(X: 57~187, Y: 227~317 마진 적용) 지정 및 임계값 0.70 상향 (동기화)
#   1.11.16-hotfix1: 핫픽스 버전 동기화
# ==============================================================================

# ==============================================================================
# 📂 [마디 2] 파일 분할형 이중 로그 스트리밍 엔진 가동 (0층 기저 레이어)
# ==============================================================================
class DoubleWriter:
    def __init__(self, filename):
        self.terminal = sys.stdout
        try:
            self.log = open(filename, "a", encoding="utf-8")
        except:
            self.log = None

    def write(self, message):
        self.terminal.write(message)
        if self.log:
            self.log.write(message)
            self.log.flush()

    def flush(self):
        self.terminal.flush()
        if self.log:
            self.log.flush()

def get_session_start_time():
    raw_val = os.environ.get('MACRO_SESSION_START')
    if not raw_val:
        return time.time()
    try:
        import re
        from datetime import datetime as dt_class
        nums = re.findall(r'\d+', raw_val)
        if len(nums) >= 5:
            year = int(nums[0])
            month = int(nums[1])
            day = int(nums[2])
            
            is_pm = "오후" in raw_val or "PM" in raw_val.upper()
            hour = int(nums[3])
            if is_pm and hour < 12:
                hour += 12
            elif not is_pm and hour == 12 and ("오전" in raw_val or "AM" in raw_val.upper()):
                hour = 0
                
            minute = int(nums[4])
            second = int(nums[5]) if len(nums) > 5 else 0
            
            dt = dt_class(year, month, day, hour, minute, second)
            return dt.timestamp()
    except Exception:
        pass
    return time.time()

def find_screenshot_dir():
    user_home = os.path.expanduser("~")
    candidates = [
        os.path.join(user_home, "Documents", "MuMuSharedFolder", "Screenshots"),
        os.path.join(user_home, "OneDrive", "Documents", "MuMuSharedFolder", "Screenshots"),
        os.path.join(user_home, "OneDrive", "문서", "MuMuSharedFolder", "Screenshots"),
        os.path.join(user_home, "Documents", "MuMu12SharedFolder", "Screenshots"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def sync_screenshots_loop(session_start_ts, log_dir):
    import shutil
    import json
    from datetime import datetime as dt_class
    
    screenshot_dir = find_screenshot_dir()
    if not screenshot_dir:
        print("⚠️ [스크린샷 동기화] 뮤뮤 스크린샷 폴더(기본/원드라이브 문서 후보군)를 찾지 못해 동기화 기능이 비활성화됩니다.")
        return
        
    print(f"📸 [스크린샷 동기화] 백그라운드 동기화 감시 스레드 기동 완료 (경로: {screenshot_dir}, 주기: 30초)")
    
    copied_files = set()
    cache_file = os.path.join(log_dir, ".copied_screenshots.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                loaded = set(json.load(f))
            # 🚨 [2026-09-03 무한 증식 완치] 이 캐시는 "복사 완료" 이력을 영원히 누적만 하고 정리하는 로직이
            # 없었음(실측: 860건 중 426건이 이미 원본이 삭제된 죽은 항목) - 새 스크린샷 감지마다 집합 전체를
            # JSON으로 다시 쓰는 구조라(아래 참고) 커질수록 매 주기 쓰기 비용도 계속 늘어남. 원본이 이미
            # 없는 경로는 다시 복사될 일도 없으므로(같은 경로에 파일이 재생성되지 않는 한) 안전하게 제거.
            copied_files = {p for p in loaded if os.path.exists(p)}
            pruned = len(loaded) - len(copied_files)
            msg = f"📸 [스크린샷 동기화] 디스크 캐시에서 기존 복사 이력 {len(copied_files)}건 복원 완료."
            if pruned > 0:
                msg += f" (원본 삭제된 죽은 항목 {pruned}건 정리)"
            print(msg)
            if pruned > 0:
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(list(copied_files), f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ [스크린샷 동기화] 캐시 로드 실패 (새로 생성): {e}")
            
    while True:
        try:
            if os.path.exists(screenshot_dir):
                for item in os.listdir(screenshot_dir):
                    item_path = os.path.join(screenshot_dir, item)
                    if os.path.isfile(item_path) and item.lower().endswith(('.png', '.jpg', '.jpeg')):
                        mtime = os.path.getmtime(item_path)
                        if mtime >= session_start_ts and item_path not in copied_files:
                            dt_shot = dt_class.fromtimestamp(mtime)
                            
                            # 날짜 및 시간 정보 분리
                            date_str = dt_shot.strftime("%Y-%m-%d")
                            hour_min = dt_shot.strftime("%H%M")
                            sec_str = dt_shot.strftime("%S")
                            
                            # 파일명 분석을 통한 접미사(suffix) 설정
                            item_lower = item.lower()
                            if "screencap_stuck" in item_lower:
                                suffix = "stuck"
                            elif "screencap_start" in item_lower:
                                suffix = "start"
                            elif "screencap_reboot" in item_lower:
                                import re
                                match = re.search(r"screencap_(reboot\d+)", item_lower)
                                suffix = match.group(1) if match else "reboot"
                            elif "screencap_restart" in item_lower:
                                suffix = "restart"
                            elif "screencap_harken" in item_lower:
                                suffix = "harken"
                            else:
                                suffix = "screenshot"
                                
                            _, ext = os.path.splitext(item.lower())
                            
                            # 초 단위 앞에 0을 붙여 3자리로 맞춤 (0SS 형태)
                            clean_name = f"{date_str}-{hour_min}-0{sec_str}_{suffix}{ext}"
                            dst_path = os.path.join(log_dir, clean_name)
                            
                            # 동일 시간(초)에 파일이 겹칠 경우 넘버링 추가
                            if os.path.exists(dst_path):
                                counter = 1
                                while True:
                                    clean_name_numbered = f"{date_str}-{hour_min}-0{sec_str}_{suffix}_{counter}{ext}"
                                    dst_path_numbered = os.path.join(log_dir, clean_name_numbered)
                                    if not os.path.exists(dst_path_numbered):
                                        clean_name = clean_name_numbered
                                        dst_path = dst_path_numbered
                                        break
                                    counter += 1
                                    
                            shutil.copy(item_path, dst_path)
                            copied_files.add(item_path)
                            try:
                                with open(cache_file, "w", encoding="utf-8") as f:
                                    json.dump(list(copied_files), f, ensure_ascii=False, indent=2)
                            except Exception as cache_err:
                                pass
                            print(f"📸 [스크린샷 동기화] 새 스크린샷이 감지되어 로그 폴더로 카피되었습니다: {clean_name}")
        except Exception:
            pass
        time.sleep(30)

# 🛡️ [Watchdog 락 감시 변수 및 함수 정의]
last_heartbeat_time = time.time()

def update_heartbeat():
    global last_heartbeat_time
    last_heartbeat_time = time.time()

def watchdog_monitor_loop():
    global last_heartbeat_time
    print("🛡️ [Watchdog 감시자] 백그라운드 락(Lock) 감시 센서 기동 완료 (주기: 15초, 한계치: 240초)")
    while True:
        time.sleep(15)
        try:
            inactive_duration = time.time() - last_heartbeat_time
            if inactive_duration > 240:
                print(f"\n🚨🚨 [Watchdog 감시자 경보] 메인 스레드가 {int(inactive_duration)}초 동안 무반응 정체(락) 상태에 빠진 것을 인지했습니다.")
                restart_process("Watchdog 감시자에 의한 메인 스레드 무반응(ADB 소켓 블로킹 등) 검출")
        except Exception as watchdog_err:
            print(f"⚠️ [Watchdog 오류] {watchdog_err}")

def read_restart_counter():
    flag_path = "restart_counter.txt"
    if not os.path.exists(flag_path):
        return 0
    try:
        with open(flag_path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except:
        return 0

def write_restart_counter(val):
    flag_path = "restart_counter.txt"
    try:
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(str(val))
    except:
        pass

def clear_restart_counter():
    flag_path = "restart_counter.txt"
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
            print("💾 [카운터 클리어] 정상 주행 돌입으로 연속 재시작 카운터 플래그 파일이 삭제되었습니다.")
        except:
            pass

def init_main_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # [로그 청소 가드] 4일(96시간) 지난 로그 및 스크린샷 자동 청소
    try:
        now_ts = time.time()
        cutoff_ts = now_ts - (4 * 24 * 60 * 60)
        for item in os.listdir(log_dir):
            item_path = os.path.join(log_dir, item)
            if os.path.isfile(item_path) and (item.endswith(".txt") or item.endswith(".png") or item.endswith(".jpg") or item.endswith(".jpeg")):
                mtime = os.path.getmtime(item_path)
                if mtime < cutoff_ts:
                    os.remove(item_path)
                    print(f"🧹 [로그 청소기] 4일 경과 구형 파일 자동 삭제: {item}")
    except Exception as clean_err:
        print(f"⚠️ [로그 청소기 오류] {clean_err}")

    reboot_cnt = read_restart_counter()
    suffix = "start" if reboot_cnt == 0 else f"reboot{reboot_cnt}"
    
    now = datetime.datetime.now()
    base_name = now.strftime("%Y-%m-%d-%H%M")
    
    sequence_num = 0
    while True:
        log_filename = os.path.join(log_dir, f"{base_name}-{sequence_num:03d}_{suffix}.txt")
        if not os.path.exists(log_filename):
            break
        sequence_num += 1
        
    sys.stdout = DoubleWriter(log_filename)
    if sys.stdout.log:
        sys.stdout.log.write("====================================================\n")
        sys.stdout.log.write(f" Wizardry Daphne Antigravity Bot - Version {CURRENT_VERSION}\n")
        sys.stdout.log.write(f" Log Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sys.stdout.log.write("====================================================\n\n")
        sys.stdout.log.flush()
    print(f"🚀 [사령탑 로그 엔진 가동] 초기 부팅부터 모든 대순환 루프 기록이 동시 백업됩니다: {log_filename}")
    
    # [스크린샷 동기화 스레드 및 Watchdog 락 감시 스레드 시작]
    try:
        import threading
        session_start_ts = get_session_start_time()
        threading.Thread(
            target=sync_screenshots_loop, 
            args=(session_start_ts, log_dir), 
            daemon=True
        ).start()
        
        threading.Thread(
            target=watchdog_monitor_loop,
            daemon=True
        ).start()
    except Exception as thread_err:
        print(f"⚠️ [백그라운드 스레드 기동 실패] {thread_err}")

def timestamped_print(*args, **kwargs):
    current_time = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    sys.stdout.terminal.write(f"{current_time} ")
    msg = " ".join(map(str, args)) + kwargs.get('end', '\n')
    sys.stdout.terminal.write(msg)
    if sys.stdout.log:
        sys.stdout.log.write(f"{current_time} {msg}")
        sys.stdout.log.flush()

def capture_root_cmd_pid():
    # 💡 [2026-08-29 원격 정지 콘솔창 안 닫힘 "랜덤" 재발 완치] remote_control의 find_parent_cmd_pid()는
    # /stop 호출 그 순간의 라이브 프로세스 트리에서 "직계 부모가 cmd.exe인지"만 확인하는데, os.execv 자기
    # 재시작은 윈도우에서 매번 새 PID를 만들며(위 write_pid_file 주석 참고) 그 직계 부모는 원래의 cmd.exe가
    # 아니라 "방금 종료된 이전 python.exe"가 된다. 그 이전 python.exe는 이미 죽어서 프로세스 테이블에서
    # 사라졌으므로(윈도우는 죽은 프로세스의 부모 기록을 보존하지 않음) 더 위로 거슬러 올라갈 방법이 없다.
    # 그래서 재시작을 한 번이라도 거친 뒤 /stop 하면 콘솔창이 안 닫히고, 재시작 전이면 닫히는 "랜덤"처럼
    # 보이는 증상이 있었다(사용자 실전 확인). 해결: 최초 부팅 시점(아직 진짜 cmd.exe가 직계 부모일 때) 딱
    # 한 번만 캡처해서 환경변수에 저장한다 - os.execv는 현재 프로세스의 환경변수를 그대로 물려주므로, 이후
    # 몇 번을 재시작하든 이 값은 계속 살아남는다.
    if "DAPHNE_ROOT_CMD_PID" in os.environ:
        return os.environ["DAPHNE_ROOT_CMD_PID"]
    # 🚨 [2026-09-03 콘솔창 안 닫힘 잔존 사례 완치] 이 캡처는 딱 한 번(최초 부팅, 아직 진짜 cmd.exe가 직계
    # 부모일 때)만 기회가 있는데, 부팅 직후는 ADB 연결/화면 분석 등으로 시스템이 바쁜 시점이라 powershell
    # 기동(자체 오버헤드 있음)이나 tasklist 호출이 5초 타임아웃을 넘겨 실패할 수 있음. 예전엔 이 실패를
    # 재시도 없이 빈 문자열("")로 환경변수에 영구 캐싱해버려서, 그 세션이 끝날 때까지(재시작을 몇 번
    # 거치든) 콘솔창 종료 기능이 통째로 비활성화됐음(사용자 재보고: "여전히 남는 경우가 있다"). 단발성
    # 타임아웃/일시적 지연에 당하지 않도록, 실패 시 최대 3회까지 짧은 간격으로 재시도한다.
    import subprocess
    root_pid = ""
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'(Get-CimInstance Win32_Process -Filter "ProcessId={os.getpid()}").ParentProcessId'],
                capture_output=True, text=True, timeout=5
            )
            ppid_str = result.stdout.strip()
            if ppid_str.isdigit():
                check = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {ppid_str}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                out = check.stdout.strip()
                if out and not out.upper().startswith("INFO:") and out.split(",")[0].strip('"').lower() == "cmd.exe":
                    root_pid = ppid_str
                    break
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.0)
    os.environ["DAPHNE_ROOT_CMD_PID"] = root_pid
    return root_pid

def write_pid_file():
    # 💡 [v1.17.1 원격 제어 연동] remote_control/server.py가 이 파일을 읽어 매크로 프로세스를 식별합니다.
    # 모듈 최상단(재시작마다 항상 재실행되는 위치)에 있어서, os.execv 자기재시작 시에도(윈도우는 PID가 바뀌므로)
    # 매번 자동으로 최신 PID로 갱신됩니다. remote_control을 안 쓰면 이 파일은 그냥 무시하셔도 됩니다.
    try:
        pid_path = os.path.join(os.path.dirname(script_dir), "macro.pid")
        with open(pid_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        # 💡 [2026-08-29] 재시작에도 안 끊기는 콘솔창 PID(위 capture_root_cmd_pid 참고)를 같이 기록합니다.
        cmd_pid_path = os.path.join(os.path.dirname(script_dir), "macro_cmd.pid")
        with open(cmd_pid_path, "w", encoding="utf-8") as f:
            f.write(capture_root_cmd_pid())
    except Exception:
        pass  # 원격 제어를 안 쓰는 환경에서는 실패해도 매크로 동작에 지장 없음

init_main_logger()
print = timestamped_print
write_pid_file()

# ==============================================================================
# 🔄 [마디 3] 로그 가드 인쇄 영역 (평생 건드릴 필요 없는 고정 파이프라인)
# ==============================================================================
def print_daphne_global_settings():
    print("====================================================")
    print("⚙️ [Daphne 마스터 글로벌 제어 세팅 변수 구역 - 최상단 제어판 연동 완료]")
    print(f" -> 목표 주회 설정 수치: {LIMIT_DUNGEON_LOOPS}회 안전 고정")
    print(f" -> 숏컷기반 스킬 예약 시스템 가동 여부: {bool(ENABLE_FIRST_COMBAT_SKILL)}")
    print(f" -> 상자 개방 후 긴급 힐링 가동 여부: {bool(ENABLE_HEAL_AFTER_CHEST)}")
    print("====================================================")

print_daphne_global_settings()

# ==============================================================================
# 📦 [마디 4] 서브 모듈 안전 수입 (메인 변수가 메모리에 완벽 적재된 후 로드)
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image
from ppadb.client import Client as AdbClient
import traceback

# 🚨 [v1.20.0] 뮤뮤 '앱 상주' 설정 점검용 (연결 직후 connect_mumu()에서 호출)
from mumu_display_check import check_display_configuration

import dungeon_bot
import inn_manager
import chest_opener
from screen_capture import capture_screen_bytes, decode_screen_bytes

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    err_msg = f"\n💀💀 [🚨 시스템 치명적 크래시 발생 시간: {error_time}] 💀💀\n"
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    err_msg += "".join(tb_lines)
    
    # DoubleWriter를 통해 콘솔과 로그파일 양쪽에 실시간 플러시 기입
    sys.stdout.write(err_msg)
    sys.stdout.flush()

sys.excepthook = handle_exception

def is_daphne_app_foreground(device):
    # 💡 이미지 매칭(가로화면 감지 등) 없이 ADB dumpsys로 직접 "지금 위저드리 다프네가 최상단 앱인가"를 확인합니다.
    # 이미지 기반 판정은 안드로이드 홈 화면처럼 낯선(가로도 아니고 인게임도 아닌) 상태를 놓칠 수 있어, 앱 자체가 아예 안 켜져 있는
    # 상황에서는 여기서 즉시 잡아내 launch_daphne_app을 곧바로 격발할 수 있도록 하는 빠른 사전 점검용입니다.
    try:
        # 💡 안드로이드 버전에 따라 이 항목의 키 이름이 mResumedActivity(구버전) 또는 topResumedActivity(신버전)로 다르게 출력되어,
        # "mResumedActivity"로만 grep하면 신버전에서 항상 빈 결과가 나와 매번 "최상단 아님"으로 오판하는 결함이 있었음.
        # 접두어를 떼고 "ResumedActivity"로 grep하면 양쪽 버전 모두, 그리고 요약용 "ResumedActivity:" 라인까지 안전하게 포착됨.
        result = device.shell("dumpsys activity activities | grep ResumedActivity") or ""
        return "jp.co.drecom.wizardry.daphne" in result
    except Exception:
        return False

def launch_daphne_app(device):
    print("      ➔ 🛑 jp.co.drecom.wizardry.daphne 게임 앱 강제 종료 및 Relaunch를 실행합니다.")
    try:
        device.shell("am force-stop jp.co.drecom.wizardry.daphne")
        time.sleep(2.0)
    except Exception as stop_err:
        print(f"      ⚠️ am force-stop 실패: {stop_err}")

    # 동적 액티비티 런칭 적용
    launched = False
    try:
        act_brief = device.shell("cmd package resolve-activity --brief jp.co.drecom.wizardry.daphne")
        if act_brief and "No activity found" not in act_brief:
            main_act = act_brief.strip().split("\n")[-1]
            print(f"      ➔ 🚀 동적 런처 엑티비티 식별 성공: {main_act} - am start 기동을 전개합니다.")
            device.shell(f"am start -n {main_act}")
            launched = True
    except Exception as brief_err:
        print(f"      ⚠️ 동적 런처 엑티비티 식별 실패: {brief_err}")

    if not launched:
        print("      ➔ 🚀 monkey 런칭으로 폴백하여 기동을 주입합니다.")
        try:
            device.shell("monkey -p jp.co.drecom.wizardry.daphne -c android.intent.category.LAUNCHER 1")
        except Exception as monkey_err:
            print(f"      ⚠️ monkey 폴백 런칭 실패: {monkey_err}")

# 🚨 [2026-08-29 MuMu 인스턴스 자동 감지] 배포판을 받는 다른 사용자들은 대부분 MuMu 기본 인스턴스(#0)를
# 쓰지만, 개인 환경에 따라 #1/#2... 등 다른 인스턴스를 쓸 수도 있다(예: 안드로이드15 업글로 새 인스턴스가
# 추가된 경우). MUMU_VM_INDEX를 특정 값으로 하드코딩해버리면 그 값이 다른 사용자 환경에선 아예 존재하지
# 않는 인스턴스일 수 있어 콜드 리부트가 깨진다. 그래서 실제로 마지막에 ADB 연결이 성공했던 포트를 계속
# 기억해뒀다가, 콜드 리부트 시 그 포트에 해당하는 인스턴스 번호를 자동으로 골라 재실행한다 - 아직 한 번도
# 연결 성공 이력이 없으면(최초 부팅 등) 위 MUMU_VM_INDEX 기본값으로 안전하게 폴백한다.
# 🚨 [2026-08-29] 실측 확보: 0번(16384/16385/5555)과 2번(16448/5559) 두 인스턴스 값을 사용자가 직접 확인.
# 1번(16416/5557)은 사용자가 해당 인스턴스를 이미 삭제해 직접 실측이 불가능했음 - 대신 두 실측값에서
# 역산한 공식(5555 + 2×인덱스, 16384 + 32×인덱스)에 인덱스=1을 대입한 추정값이다(1번을 실제로 쓰는
# 환경에서 어긋나면 실측값으로 교체 필요 - 추측 금지 원칙에 따라 이 사실을 남겨둔다).
MUMU_PORT_TO_INDEX = {
    "16384": "0", "16385": "0", "5555": "0",
    "16416": "1", "5557": "1",  # ⚠️ 공식 역산 추정값 (직접 실측 못 함)
    "16448": "2", "5559": "2",
}
_last_connected_mumu_port = None

# 🚨 [v1.20.0 안드15 전용화] 이 버전부터 MuMu Player 안드로이드 15 인스턴스만 지원한다.
#    배경: 안드12 인스턴스는 그래픽 렌더러 에러(901)가 반복돼 사실상 못 쓰게 됐고, 안드15 인스턴스가
#    OpenGL + 30fps 조합에서 안정적으로 도는 것을 확인했다. 문제는 아래 포트 스캔이 예전엔 5555(안드12)를
#    가장 먼저 시도해서, 안드12 인스턴스가 켜져 있으면 그쪽에 붙어버렸다는 것.
#    ⚠️ 인스턴스 "번호"가 아니라 디바이스가 직접 보고하는 "안드로이드 버전"으로 판정한다 - 나중에
#    인스턴스를 지웠다 다시 만들어 번호(=포트)가 바뀌어도 안 깨지게 하기 위함.
# 🚨 [2026-09-08] 원래 start_grand_orchestrator() 안의 지역변수였는데, recover_app_startup()도 대설지대
# 경유 화면(마을외곽/경로 목록)을 인식해야 해서 모듈 전역으로 승격했다(두 함수가 같은 매핑을 써야 함).
HEAVYSNOW_FLOOR_FILE_MAP = {"6층": "Heavysnow_6F", "교회구역": "Heavysnow_church", "4층": "Heavysnow_4F"}

MIN_ANDROID_VERSION = 15
MUMU_ADB_PORTS = ["16448", "5559", "16384", "16385", "5555", "16416", "5557"]  # 안드15(2번) 포트 우선

def get_device_android_version(device):
    """디바이스가 보고하는 안드로이드 메이저 버전(int). 조회 실패 시 0."""
    try:
        raw_ver = (device.shell("getprop ro.build.version.release") or "").strip()
        return int(raw_ver.split(".")[0])
    except Exception:
        return 0

def pick_supported_device(client, verbose=True):
    """붙어 있는 MuMu 포트 중 안드15 이상인 첫 디바이스를 고른다.

    반환: (device, port, android_version). 지원 대상이 없으면 (None, None, 0).
    verbose=False면 미지원 안내를 찍지 않는다 - 에뮬레이터 부팅 대기 루프처럼 5초마다 반복 호출되는
    자리에서 아직 부팅 중인 디바이스를 두고 경고문이 도배되는 걸 막기 위함.
    """
    rejected = []
    for port in MUMU_ADB_PORTS:
        try:
            device = client.device(f"127.0.0.1:{port}")
            if not device or device.get_state() != "device":
                continue
            android_version = get_device_android_version(device)
            if android_version >= MIN_ANDROID_VERSION:
                return device, port, android_version
            rejected.append((port, android_version))
        except Exception:
            continue

    if rejected and verbose:
        detail = ", ".join(f"{p}포트=안드{v if v else '?'}" for p, v in rejected)
        print(f"❌ [미지원 에뮬레이터] 연결된 인스턴스가 전부 안드로이드 {MIN_ANDROID_VERSION} 미만입니다({detail}).")
        print(f"   이 버전부터는 MuMu Player 안드로이드 {MIN_ANDROID_VERSION} 인스턴스만 지원합니다. 해당 인스턴스를 켜주세요.")
    return None, None, 0

def record_mumu_port(port_str):
    global _last_connected_mumu_port
    if port_str in MUMU_PORT_TO_INDEX:
        _last_connected_mumu_port = port_str

def get_reboot_vm_index():
    if _last_connected_mumu_port and _last_connected_mumu_port in MUMU_PORT_TO_INDEX:
        return MUMU_PORT_TO_INDEX[_last_connected_mumu_port]
    return MUMU_VM_INDEX

def connect_all_mumu_ports_quietly():
    # 🚨 [2026-09-06 연결 스팸 완치] adb connect CLI 자체가 포트마다 성공/실패 문구를 줄줄이 찍어
    # 실제 오류처럼 보인다는 지적 - 출력을 nul로 죽이고, 호출부가 최종 결과만 한 줄로 알린다.
    for port in MUMU_ADB_PORTS:
        os.system(f"adb connect 127.0.0.1:{port} > nul 2>&1")

def reboot_emulator():
    print("\n🖥️🚨 [에뮬레이터 콜드 리부트 작동] MuMu Player가 정지했거나 오프라인 상태입니다. 완전 리셋을 수행합니다!")
    # 1. 윈도우 taskkill을 통해 모든 뮤뮤 플레이어 프로세스 강제 킬
    print("      ➔ 🛑 MuMu Player 프로세스를 윈도우 상에서 강제 종료합니다...")
    os.system("taskkill /f /im MuMuPlayer.exe")
    os.system("taskkill /f /im MuMuNxMain.exe")
    os.system("taskkill /f /im MuMuNxDevice.exe")
    time.sleep(3.0)
    
    # 2. 윈도우 ADB 서버 리셋
    os.system("adb kill-server")
    time.sleep(1.0)
    os.system("adb start-server")
    
    # 3. 뮤뮤 실행 파일 백그라운드로 실행 (마지막으로 실제 연결됐던 포트 기준 인스턴스 자동 선택)
    reboot_vm_index = get_reboot_vm_index()
    print(f"      ➔ 🚀 MuMu Player를 백그라운드 구동합니다: \"{MUMU_EXECUTABLE_PATH}\" -v {reboot_vm_index}")
    try:
        import subprocess
        # 🚨 [2026-08-29] cwd 미지정 결함 완치: MuMu 실행 파일이 일부 설정(vm_config.json 등)을 자기
        # 설치 경로가 아니라 "실행 당시의 현재 작업 디렉토리" 기준 상대경로로 쓰는 것으로 보임(실전 확인:
        # 뮤뮤 재시작을 거칠 때마다 이 매크로 프로젝트 루트 폴더 안에 configs/ 폴더가 생겨있었음 - .bat이
        # 항상 프로젝트 루트를 cwd로 고정해두는데 여기서 cwd를 안 넘겨줘서 그대로 물려받은 것). 뮤뮤 설치
        # 폴더 자체를 cwd로 명시해 원래 있어야 할 자리(C:\Program Files\Netease\MuMuPlayer\configs\)에
        # 쓰도록 고정한다.
        # 💡 실측 확인: 진짜 configs/ 폴더는 nx_main 폴더가 아니라 그 한 단계 위(MuMuPlayer 설치 루트)에
        # 있음(C:\Program Files\Netease\MuMuPlayer\configs\) - cwd를 nx_main으로 잘못 잡으면 엉뚱한
        # 위치에 또 새 configs/가 생기므로 반드시 한 단계 위로 잡는다.
        mumu_install_root = os.path.dirname(os.path.dirname(MUMU_EXECUTABLE_PATH))
        # 백그라운드로 실행하여 파이썬 스레드가 블락되지 않게 처리
        subprocess.Popen([MUMU_EXECUTABLE_PATH, "-v", reboot_vm_index], cwd=mumu_install_root)
    except Exception as ex_err:
        print(f"❌ [에뮬레이터 실행 실패] {ex_err}")
        
    # 4. ADB 포트 연결 및 대기 루프 (최대 60초)
    print("      ➔ ⏳ 에뮬레이터 부팅 및 ADB 포트 활성화를 대기합니다 (최대 60초)...")
    start_wait = time.time()
    connected = False
    target_ports = MUMU_ADB_PORTS  # 🚨 [v1.20.0] 안드15 포트 우선 순서로 통일 (MUMU_ADB_PORTS 주석 참고)
    
    while time.time() - start_wait < 60.0:
        for port in target_ports:
            os.system(f"adb connect 127.0.0.1:{port} > nul 2>&1")
        time.sleep(5.0)
        
        try:
            from ppadb.client import Client as AdbClient
            client = AdbClient(host="127.0.0.1", port=5037)
            # 🚨 [v1.20.0] 아무 디바이스나 잡지 않고 안드15 인스턴스가 올라올 때까지 기다린다.
            #    (부팅 초반엔 getprop이 아직 안 떠서 버전 0으로 걸러지므로 자연스럽게 재시도된다)
            valid_device, valid_port, valid_ver = pick_supported_device(client, verbose=False)
            if valid_device:
                print(f"      ✅ ADB 연결 수립 완료! 인스턴스 {MUMU_PORT_TO_INDEX.get(valid_port, '?')}번 ({valid_port}포트, 안드로이드 {valid_ver})")
                record_mumu_port(valid_port)
                connected = True
                break
        except:
            pass
        print(f"      ⏳ 대기 중... ({int(time.time() - start_wait)}초 경과)")
        
    if not connected:
        print("⚠️ [에뮬레이터 리부트 경고] 60초 내에 디바이스가 온라인 상태로 전환되지 않았습니다. 자가 재시작으로 제어를 계속합니다.")
    else:
        # 5. 게임 앱 Relaunch 격발
        try:
            from ppadb.client import Client as AdbClient
            client = AdbClient(host="127.0.0.1", port=5037)
            valid_device, _valid_port, _valid_ver = pick_supported_device(client, verbose=False)
            if valid_device:
                launch_daphne_app(valid_device)
                time.sleep(5.0)
        except Exception as app_err:
            print(f"⚠️ [에뮬레이터 리부트 앱 실행 실패] {app_err}")

def recover_app_startup(device):
    print("🔮 [앱 기동 복구 시스템 작동] 로딩 및 인트로 팝업 극복 절차를 시작합니다.")
    
    t_re_retry = load_template("templates/reboot/retry.png")
    t_re_download = load_template("templates/reboot/start_download.png")
    t_re_maintenance = load_template("templates/reboot/maintenance.png")
    t_re_maintain_title = load_template("templates/reboot/maintain_to_title.png")
    t_title_notice = load_template("templates/reboot/title_notice.png")
    t_title_notice_close = load_template("templates/reboot/title_notice_close.png")
    t_title_warning = load_template("templates/reboot/title_warning.png")

    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_combat_in = load_grayscale_template("templates/combat_in.png")
    t_combat_slow = load_grayscale_template("templates/combat_slow.png")
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_error_to_title = load_template("templates/Error_to_title.png")
    
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    t_incombat_dead = load_template("templates/InCombat_dead.png")
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    
    t_inn_title = load_template("templates/inn_sleep/inn_title.png")
    t_world_map = load_grayscale_template("templates/Worldmap/world_map_anchor.png")

    # 🚨 [2026-08-25 기동 복구 하켄 인식 결함 완치] 실전 확인: 하켄 메뉴(귀환목록/이동목록/가호팝업)가 떠 있는
    # 상태에서 매크로를 원격으로 재시작하면, 이 함수는 아래 known-popup 목록과 인게임 앵커 OR 판정 어디에도
    # 하켄 관련 앵커가 없어 35회 예산을 전부 빈 (1,1) 탭으로 허비하고 실패함 - 아웃게임 스캐너(1369행 부근)에는
    # 이미 이식됐던 check_and_handle_harken_menu()를 여기 기동 복구 루프에도 동일하게 재사용한다.
    # 🚨 [2026-08-27 하켄 메뉴 판정 여유 확보] dungeon_bot.py의 동일 수정과 같은 사유 -
    # check_template_present()가 라이브 화면만 이진화(160)하고 도장은 그대로 비교해 판정 여유가
    # 얇았음(실측 0.786/여유 0.086 vs 이진화 통일 시 0.997/여유 0.30). 다른 도장들과 동일하게 통일.
    t_harken_blessing_donothing = dungeon_bot.load_template("templates/Field/harken_blessing_donothing.png")
    t_harken_return = dungeon_bot.load_color_template("templates/FFXI/harken_return.png")

    # 💡 [항목5] 마을별 개별 앵커(!!vill_FFXI.png 등) 대신 어떤 마을에나 있는 공용 여관 도장으로 통일
    t_village_anchor = load_grayscale_template("templates/village_common/inn.png")

    if DUNGEON_NAME == "북쪽의 유령선":
        t_dungeon_sel = load_template("templates/FFXI/FFXI_dungeon_Anchor.png")
    else:
        t_dungeon_sel = load_template("templates/WolfCave/dungeon_select.png")

    # 💡 [던전선택 범용 인식] 프리셋과 다른 던전의 셀렉창에서 부팅돼도 "세계지도를 연다" 공용 버튼(5개 던전 전수 0.957+ 검증)으로
    # "여기가 어떤 던전이든 던전선택 화면이다"를 판별. ROI(800~1200, 1480~1650)로 제한해 오탐 방지.
    t_open_world = load_grayscale_template("templates/open_world_map_btn.png")

    t_field = load_grayscale_template("templates/Field/field_anchor.png")
    t_get_item = load_template("templates/chestopening/get_item.png")
    t_app_exit = load_template("templates/app_exit.png")

    # 🚨 [2026-09-08 실전 확인] 대설지대 경유 화면(마을외곽 / 대설지대 경로 목록)은 아래 "인게임 진입 성공"
    # 앵커 목록 어디에도 없어서, 그 화면에서 매크로를 시작하면 아는 화면이 하나도 없다고 판단해 빈 (1,1)
    # 탭만 반복하다 35회 예산을 통째로 날렸다(실전 로그 23:09, 마을외곽에서 기동). 메인 루프가 이 두 화면을
    # 구분할 때 쓰는 것과 완전히 같은 도장/임계값(0.80)을 그대로 재사용한다.
    t_heavysnow_outskirts = None
    t_heavysnow_route = None
    if DUNGEON_NAME == "대설지대":
        t_heavysnow_outskirts = load_template("templates/Vill_Isberg/dungeon_Heavysnow.png")
        t_heavysnow_route = load_template(f"templates/Vill_Isberg/{HEAVYSNOW_FLOOR_FILE_MAP.get(DUNGEON_FLOOR_NAME, 'Heavysnow_6F')}.png")
    
    # 🎮 [앱 실행 여부 사전 점검] MuMu는 켜져있지만 위저드리 다프네 앱 자체가 안 켜져 있는 경우(예: 안드로이드 홈 화면),
    # 가로화면도 아니고 아는 인게임 화면도 아니라서 아래 루프가 (1,1) 공허 탭만 반복하다 5분 정체 타이머까지 기다리던 결함을 완치.
    # dumpsys로 빠르게 확인해서 즉시 앱을 실행합니다.
    if not is_daphne_app_foreground(device):
        print("🎮 [앱 상태 점검] 위저드리 다프네 앱이 최상단에 있지 않은 것으로 확인되었습니다. 즉시 앱 기동을 시도합니다.")
        try:
            launch_daphne_app(device)
            time.sleep(4.0)
        except Exception as launch_err:
            print(f"⚠️ [앱 상태 점검] 앱 실행 시도 실패: {launch_err}")

    counter = 0
    max_try = 35
    startup_landscape_fail_counter = 0  # 🚨 [v1.17.0-hotfix1] 가로화면 무한루프 완치용 전용 카운터 (기존 counter는 이 분기의 continue로 인해 증가하지 않아 탈출구가 없었음)
    # 🚨 [2026-08-20 대용량 다운로드 타임아웃 완치] 목요일 콘텐츠 추가 점검 등으로 리소스 다운로드가 기가바이트
    # 단위로 나오면, 다운로드 확인 버튼을 눌러도 그 뒤 진행률 화면엔 아는 앵커가 하나도 없어 빈 [1,1] 탭만
    # 반복하며 35회(약 2분) 예산을 그대로 소진 - 실전 확인(2026-08-20 13시): 다운로드 버튼을 누르고도 카운터가
    # 안 줄어들어 5분 뒤 "아웃게임 정체" 절대 워치독까지 걸려 다운로드 도중 에뮬레이터 강제 리부트가 발생함.
    # 다운로드 확인 버튼을 감지한 시점을 기록해두고, 그 뒤 일정 시간(DOWNLOAD_GRACE_SECONDS) 동안은 35회 예산이
    # 소진되지 않도록 유예한다 - 진행률 화면처럼 아는 앵커가 없는 정적 화면이 계속 떠도 시간만으로 강제 실패
    # 처리되지 않게 함. 유예 시간이 다 지나도록 인게임 진입을 못 하면 그때는 원래대로 실패 처리(원인 불명 정체와
    # 구분 못 할 이유가 없으므로 무한정 봐주지는 않음).
    download_started_at = None
    DOWNLOAD_GRACE_SECONDS = 1200.0  # 20분 - 기가바이트급 다운로드도 넉넉히 커버, 필요시 조정 가능

    # 🚨 [2026-09-08 무한 정체 완치] 이 루프의 캡처 실패 경로 2개(None 반환 / Image.open 예외)는 원래
    # counter를 증가시키지 않고 조용히 continue만 했다 - 그래서 screencap이 계속 깨진 데이터를 돌려주면
    # (실전 로그: "cannot identify image file <_io.BytesIO ...>") while 조건이 영원히 안 끝나고, 로그도
    # 한 줄 안 남아서 "🔮 앱 기동 복구 시스템 작동" 직후 아무 출력 없이 멈춘 것처럼 보였음(사용자 확인:
    # 이삼일에 한 번 꼴로 재현). 240초 Watchdog이 결국 구해주긴 하지만 그때까지 아무 진단 정보도 없다.
    # 메인 루프(start_grand_orchestrator)가 이미 쓰고 있는 검증된 패턴(연속 실패 카운터 + 매 실패마다 사유
    # 로그 + 한계 도달 시 restart_process)을 이식하되, 한계치는 메인 루프의 5회(2.5초)보다 넉넉한 20회(10초)로
    # 잡는다 - 실전 로그(2026-09-08 20:51)에서 캡처가 깨진 시점이 ADB 연결 성공 겨우 2초 뒤였다. 즉 에뮬레이터가
    # 막 뜬 직후 화면 서브시스템이 아직 준비되지 않은 과도기일 가능성이 높아, 조금만 기다리면 저절로 회복될
    # 상황에서 2.5초 만에 앱/에뮬레이터 재시작을 걸어버리면 오히려 손해다(메인 루프는 이미 정상 주행 중이라
    # 같은 실패가 진짜 이상 신호지만, 이 함수는 부팅 직후 구간이라 성격이 다르다).
    startup_cap_fail_counter = 0
    STARTUP_CAP_FAIL_LIMIT = 20  # 0.5초 간격 × 20회 = 약 10초 유예 (240초 워치독보다 24배 빠름)
    while counter < max_try:
        try:
            raw_cap = capture_screen_bytes(device)
            if raw_cap is None:
                raise RuntimeError("Screencap returned None")
            img_np = decode_screen_bytes(raw_cap)
            if startup_cap_fail_counter:
                print(f"✅ [기동 복구 캡처 회복] {startup_cap_fail_counter}회 실패 후 화면 캡처가 정상화되었습니다.")
            startup_cap_fail_counter = 0
        except Exception as cap_err:
            startup_cap_fail_counter += 1
            print(f"⚠️ [기동 복구 캡처 실패] 화면 캡처 유실! 오류: {cap_err} ({startup_cap_fail_counter}/{STARTUP_CAP_FAIL_LIMIT})")
            if startup_cap_fail_counter >= STARTUP_CAP_FAIL_LIMIT:
                restart_process(f"기동 복구(recover_app_startup) 중 화면 캡처 {STARTUP_CAP_FAIL_LIMIT}회 연속 실패: {cap_err}")
                return True
            time.sleep(0.5)
            continue

        # 🖥️ [가로 화면/안드로이드 홈 복구 가드] 에뮬레이터가 가로 상태로 기동된 경우 앱을 실행해 세로 모드 회전을 유도
        height, width = img_np.shape[:2]
        if height < width:
            startup_landscape_fail_counter += 1
            print(f"🖥️ [기동 복구 - 가로 화면 감지] 현재 화면이 가로 상태({width}x{height})입니다. 위저드리 다프네 앱 기동(Relaunch)을 강제 주입하여 세로 화면 전환을 시도합니다. ({startup_landscape_fail_counter}/3)")
            # 🚨 [2026-08-29] 30회는 너무 관대해서 뮤뮤가 진짜 먹통일 때 탈출까지 몇 분씩 걸렸음(실전 로그로
            # 확인: 8분 넘게 10/30까지만 진행됨) - 3회로 줄여 가벼운 문제는 여전히 앱 재시작으로 해결하되,
            # 뮤뮤 자체가 먹통인 경우 빠르게 다음 단계(2회차 재시작 → 에뮬레이터 완전 재시작)로 넘어가게 한다.
            if startup_landscape_fail_counter >= 3:
                print("      🚨 [기동 복구 - 가로화면 탈출 실패] 3회 연속 가로 화면 정체! MuMu 자체 이상으로 판단해 자가 복구 절차로 넘어갑니다.")
                restart_process(f"기동 복구(recover_app_startup) 중 가로 화면 3회 연속 정체 (화면 크기: {width}x{height})")
                return True
            try:
                launch_daphne_app(device)
                time.sleep(4.0)
            except Exception as launch_err:
                print(f"⚠️ 기동 복구 중 가로 화면 앱 실행 실패: {launch_err}")
            continue
            
        # 🚪 [앱 종료 방지 가드]
        if check_template_present(img_np, t_app_exit, 0.75):
            print("⏰ [앱 종료 방지 가드] 종료 확인 팝업 감지! 즉각 '취소' 버튼(880, 1450)을 터치하여 파쇄합니다.")
            device.shell("input tap 880 1450")
            time.sleep(1.0)
            continue
            
        # 💀 [주인공 사망 부활 복구]
        if check_template_present(img_np, t_btn_resurrect, 0.60) or (check_template_present(img_np, t_anchor_dead, 0.65) if t_anchor_dead is not None else False):
            print("💀 [기동 복구 가드] 전멸/주인공 사망 화면이 식별되었습니다. 부활을 집도합니다.")
            if find_and_click_template(device, img_np, t_btn_resurrect, 0.60):
                time.sleep(1.0)
            else:
                device.shell("input tap 720 1200")
                time.sleep(1.0)
            device.shell("input tap 705 1241")
            print("⏳ 부활 암전 연출 대기... 무조건 10초간 제어를 홀딩합니다.")
            time.sleep(10.0)
            
            try:
                dungeon_bot.need_heal = True
                print("💊 [기동 복구 가드] 부활 성공. dungeon_bot.need_heal = True 설정 완료.")
            except Exception as e:
                print(f"⚠️ [기동 복구 가드] need_heal 설정 실패: {e}")
            continue

        # 💀 [아군 사망 부활 복구]
        if check_template_present(img_np, t_incombat_dead, 0.75):
            print("💀 [기동 복구 가드] 아군 사망 앵커가 포착되었습니다. 1초 간격 5회 부활 연타를 주입합니다.")
            time.sleep(1.0)
            import random
            for i in range(5):
                rx = 640 + random.randint(0, 160)
                ry = 1200 + random.randint(0, 160)
                print(f"  👉 부활 시도 ({i+1}/5) - 터치 좌표: ({rx}, {ry})")
                device.shell(f"input tap {rx} {ry}")
                time.sleep(1.0)
                
            try:
                dungeon_bot.need_heal = True
                print("💊 [기동 복구 가드] 부활 성공. dungeon_bot.need_heal = True 설정 완료.")
            except Exception as e:
                print(f"⚠️ [기동 복구 가드] need_heal 설정 실패: {e}")
            continue
            
        if check_template_present(img_np, t_re_maintenance, 0.70):
            print("🚨 [점검 경고] 점검 메시지 감지! 5분(300초) 대기 모드로 돌입합니다.")
            time.sleep(300.0)
            print("⏳ 5분 대기 완료. 타이틀 이동 버튼 터치를 시도합니다.")
            find_and_click_template(device, img_np, t_re_maintain_title, 0.70)
            time.sleep(5.0)
            counter = 0
            continue
            
        if check_template_present(img_np, t_re_maintain_title, 0.70):
            print("👉 [점검 경고] 타이틀 이동(점검) 버튼 감지! 즉시 클릭합니다.")
            find_and_click_template(device, img_np, t_re_maintain_title, 0.70)
            time.sleep(3.0)
            counter = 0  # 🚨 [2026-08-20] 실제 진행이 있었으니 정체 예산 리셋 (사용자 제안)
            continue

        if check_template_present(img_np, t_re_download, 0.70):
            print("📥 [리소스 다운로드] 다운로드 확인 버튼 감지! 즉시 터치합니다.")
            find_and_click_template(device, img_np, t_re_download, 0.70)
            time.sleep(5.0)
            counter = 0
            # 🚨 [2026-08-20 대용량 다운로드 타임아웃 완치] 다운로드 시작 시점 기록 - 아래 예산 소진 로직이
            # 이 시점 이후 DOWNLOAD_GRACE_SECONDS 동안은 진행률 화면(아는 앵커 없음)이 계속 떠도 예산을
            # 안 깎도록 참조한다.
            download_started_at = time.time()
            continue

        if check_template_present(img_np, t_re_retry, 0.70):
            print("🌐 [네트워크 재시도] 에러 재시도 버튼 감지! 즉시 터치합니다.")
            find_and_click_template(device, img_np, t_re_retry, 0.70)
            time.sleep(3.0)
            counter = 0
            continue

        if check_template_present(img_np, t_title_notice, 0.75):
            print("📢 [공지 가드] 기동 중 공지사항 팝업 포착! '닫기' 단추를 터치합니다.")
            if find_and_click_template(device, img_np, t_title_notice_close, 0.70):
                print("      🎯 'title_notice_close' 앵커 좌표 조준 타격 성공.")
            else:
                device.shell("input tap 540 2360")
            time.sleep(3.0)
            counter = 0
            continue

        if check_template_present(img_np, t_title_warning, 0.75):
            print("⚠️ [주의 가드] 게임 최초 기동 '주의' 경고 화면 포착! 구석 터치로 진행을 격발합니다.")
            device.shell("input tap 10 10")
            time.sleep(3.0)
            counter = 0
            continue

        if check_template_present(img_np, t_error_to_title, 0.70):
            print("👉 [타이틀 복귀 확인] 'Error_to_title.png' 감지! 즉시 탭합니다.")
            find_and_click_template(device, img_np, t_error_to_title, 0.70)
            time.sleep(3.0)
            counter = 0
            continue

        if check_template_present(img_np, t_net_error, 0.75):
            print("🌐 [인게임 통신 에러] 기존 네트워크 에러 감지! 재시도 클릭.")
            net_coords = find_and_get_coords_main(img_np, t_net_retry, 0.70)
            if net_coords: device.shell(f"input tap {net_coords[0]} {net_coords[1]}")
            else: device.shell("input tap 1380 1720")
            time.sleep(4.0)
            counter = 0
            continue

        # 🚨 [2026-08-25 기동 복구 하켄 인식 결함 완치] 하켄 메뉴가 떠 있으면 처리하고 카운터를 리셋한다.
        # "returned"(귀환목록/이동목록 화면)는 함수 내부에서 이미 귀환 버튼을 클릭까지 완료한 상태로 반환된다.
        harken_state = dungeon_bot.check_and_handle_harken_menu(
            device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda
        )
        if harken_state in ("returned", "blessing"):
            print(f"🚪 [기동 복구 하켄 가드] 하켄 메뉴 화면에서 재시작된 것을 인지, '{harken_state}' 처리 완료.")
            counter = 0
            time.sleep(2.0)
            continue

        # 💡 [순서 재배치] "인게임 진입 성공" 판정을 모든 구체적 팝업(점검/다운로드/재시도/공지/주의/에러) 체크보다 뒤로 이동.
        # village_common/inn.png("여관")가 리소스 다운로드 확인 화면 등 타이틀 팝업에서 0.65 문턱을 살짝 넘는 오탐(실측 0.686)이
        # 있었는데, 이 판정이 맨 위에 있으면 오탐 즉시 return True로 함수가 끝나버려서 정작 필요한 다운로드 버튼 클릭 등
        # 구체적 팝업 대응 코드에 도달하지도 못하는 결함이 있었음. 구체적 팝업들을 전부 먼저 걸러낸 뒤에만 범용 판정을 내리도록 완치.
        if (check_field_anchor_present(img_np, t_field, 0.62) or
            check_template_present(img_np, t_dungeon_sel, 0.70) or
            check_grayscale_template_present_in_roi(img_np, t_open_world, 800, 1200, 1480, 1650, 0.85) or
            get_combat_match_score(img_np, t_combat_in) > 0.80 or
            get_combat_match_score(img_np, t_combat_slow) > 0.80 or
            check_template_present(img_np, t_yeolda, 0.65) or
            check_template_present(img_np, t_get_item, 0.65) or
            check_template_present(img_np, t_inn_title, 0.83) or
            check_grayscale_template_present(img_np, t_world_map, 0.70) or
            check_grayscale_template_present(img_np, t_village_anchor, 0.65) or
            (t_heavysnow_outskirts is not None and check_template_present(img_np, t_heavysnow_outskirts, 0.80)) or
            (t_heavysnow_route is not None and check_template_present(img_np, t_heavysnow_route, 0.80))):
            print("✨ [앱 기동 복구 성공] 인게임 화면(필드/전투/던전선택/상자/여관/세계지도/마을/마을외곽 등) 진입 성공! 매크로를 복구합니다.")
            return True

        if counter >= 4:
            print(f"💤 [스킵 가드] 로딩/타이틀 정체 감지 ({counter}/{max_try}). [1, 1] 터치를 주입합니다.")
            device.shell("input tap 1 1")
            time.sleep(3.5)
        else:
            time.sleep(2.0)

        # 🚨 [2026-08-20 대용량 다운로드 타임아웃 완치] 다운로드 확인 버튼을 누른 뒤 DOWNLOAD_GRACE_SECONDS(20분)
        # 이내라면, 진행률 화면에 아는 앵커가 하나도 없어도 예산을 깎지 않는다 - 그래야 while 루프가 시간만으로
        # 조기 실패 처리되지 않고 다운로드가 실제로 끝날 때까지 버틸 수 있다. 유예 시간이 지나면 그대로 정상 소진 재개.
        if download_started_at is not None and (time.time() - download_started_at) < DOWNLOAD_GRACE_SECONDS:
            pass
        else:
            counter += 1

    print("⚠️ [앱 기동 복구 실패] 제한 시간 내 인게임 진입에 실패했습니다. 강제 앱 재시작을 다시 시도합니다.")
    return False

global_device = None

def take_screencap_backup(device, prefix="start"):
    # 🚨 [2026-08-11 증거 스샷 신뢰성 완치] 예전엔 device.shell()로 기기에 파일로만 저장해두고
    # sync_screenshots_loop()가 30초마다 폴링해서 나중에 복사해오는 구조였는데, 이 경로엔 무결성
    # 검증이 전혀 없어 실전 stuck 증거 스샷 74개 중 거의 전부가 완전히 새까만 빈 이미지였음(확인됨).
    # 메인 루프 자체가 쓰는 신뢰도 높은 방식(device.screencap() 직접 pull)으로 교체해, 지연/폴링
    # 없이 즉시 로컬 logs/ 폴더에 저장하고 디코드까지 검증한다.
    try:
        reboot_cnt = read_restart_counter()
        if prefix in ["start", "restart"]:
            prefix = "start" if reboot_cnt == 0 else f"reboot{reboot_cnt}"

        raw = device.screencap()
        if not raw:
            print(f"⚠️ [{prefix.upper()} 스크린샷 실패] screencap이 빈 데이터를 반환함")
            return
        img = Image.open(io.BytesIO(raw))
        img.load()  # 즉시 디코드 검증 - 손상된 데이터면 여기서 예외 발생
        os.makedirs("logs", exist_ok=True)
        time_str = datetime.datetime.now().strftime("%Y-%m-%d-%H%M-%S")
        out_path = os.path.join("logs", f"{time_str}_{prefix}.png")
        img.save(out_path)
        print(f"📸 [{prefix.upper()} 스크린샷] 저장 완료: {out_path}")
    except Exception as err:
        print(f"⚠️ [{prefix.upper()} 스크린샷 실패] {err}")

def restart_process(reason):
    print(f"\n🔄 [프로세스 자가 복구 가동] 사유: {reason}")

    # 📸 [스턱 증거 보존] 재시작/리부팅으로 화면이 바뀌기 전, 마지막으로 연결됐던 디바이스 기준으로 현재 화면을 캡처합니다.
    # NPC 대화 선택창 등 아직 대응 도장이 없는 미지의 정체 상황을 나중에 분석해 새 도장을 채집할 수 있도록 남겨두는 용도입니다.
    # 🚨 [2026-08-10 실전 사고 완치] 이 캡처(device.shell)가 정확히 자가복구를 격발시킨 원인(ADB 소켓
    # 블로킹)에 그대로 다시 걸려서, 복구 로직이 진짜 조치(adb 재시작/에뮬레이터 리부트)에 도달하지 못하고
    # 통째로 멈춰버린 사고 발생(뮤뮤 동결 후 6시간 넘게 방치됨). 별도 스레드로 fire-and-forget 처리해서
    # 이게 멈추더라도 아래 진짜 복구 절차는 반드시 진행되도록 함 - 실패해도 증거 스샷 하나 못 남기는 것뿐,
    # 복구 자체가 막히는 일은 없어야 함.
    if global_device is not None:
        import threading
        threading.Thread(
            target=take_screencap_backup, args=(global_device,), kwargs={"prefix": "stuck"}, daemon=True
        ).start()

    # 💾 디스크 파일 연동 연속 재시작 횟수 누적
    consecutive_restart_count = read_restart_counter() + 1
    print(f"      ➔ 💾 [연속 재시작 누적 카운트]: {consecutive_restart_count}회")
    # 🚨 [2026-08-14 카운터 미기록 결함 완치] 예전엔 이 카운터를 launch_daphne_app()/recover_app_startup() 등
    # ADB 통신을 거치는 위험한 복구 단계까지 다 끝난 뒤에야 저장했음 - 그런데 정작 뮤뮤가 완전히 먹통이면
    # 바로 그 복구 단계 자체가 멈춰버려서 카운터가 기록될 기회조차 없었음(실전 확인: 첫 재시작 시도가
    # recover_app_startup()에서 멈춘 채 4분 뒤 Watchdog이 두 번째 재시작을 걸었는데도 카운터가 여전히
    # "1회"로 남아있어 에뮬레이터 강제 리부트(>=2 조건)로 못 넘어감). 이제 어떤 위험한 작업도 시도하기 전,
    # 카운트를 계산한 직후 즉시 저장한다 - 이 시도 자체가 멈추더라도 다음 시도(Watchdog 등)는 정확한
    # 누적 횟수를 보고 판단할 수 있음.
    write_restart_counter(consecutive_restart_count)

    # 🚨 [2026-08-29 정책 재조정] 한때 앱 재시작을 완전히 생략하고 매번 곧바로 에뮬레이터 완전 재시작으로
    # 갔었는데(뮤뮤가 화면만 죽고 ADB는 살아있는 경우 앱 재시작이 무의미하게 시간을 허비한다는 실전 사고
    # 때문), 정작 대부분의 재시작 사유는 앱만 문제인 가벼운 경우가 많아 매번 완전 재시작하면 그만큼 항상
    # 느려짐. 그래서 앱 재시작을 다시 살리되, recover_app_startup()의 가로 화면 정체 캡(예전 30회, 너무
    # 관대해서 뮤뮤가 진짜 먹통일 때 탈출까지 너무 오래 걸림)을 3회로 크게 줄여서, 가벼운 문제는 앱
    # 재시작으로 빠르게 해결하고 뮤뮤 자체가 먹통인 경우는 몇 초 안에 바로 다음 단계(2회차 재시작 →
    # 에뮬레이터 완전 재시작)로 넘어가도록 균형을 맞춘다.

    # 조건 A: 연속 2회 이상 재시작 시도 시 즉시 에뮬레이터 콜드 리부트 단행
    if ENABLE_EMULATOR_REBOOT and consecutive_restart_count >= 2:
        print(f"      🚨 [연속 재시작 한계 도달] 재시작 시도가 {consecutive_restart_count}회 연속 격발되었습니다. 에뮬레이터 완전 재시작으로 강제 극복합니다.")
        reboot_emulator()
        # 🚨 [2026-09-02 로그 파일명 reboot2+ 미표기 결함 완치] 여기서 clear_restart_counter()를 호출하면
        # restart_counter.txt가 0으로 리셋된 채로 다음 프로세스가 부팅되어, init_main_logger()가 그 값을
        # 읽어 로그 파일명을 "reboot2"가 아니라 "start"로 잘못 붙였음(실전 확인: 연속 자동 재부팅이 실제로
        # 여러 번 있었는데도 로그에는 매번 reboot1 아니면 start만 찍히고 reboot2 이상을 본 적이 없다는
        # 사용자 지적). 카운터를 여기서 지우지 않고 그대로 넘기면, 다음 프로세스의 init_main_logger()가
        # 정확한 누적 횟수(2, 3, ...)로 로그 파일명을 붙인다 - "정상 주행 돌입"(던전 1주회/여관 숙박 성공)
        # 시점에 이미 별도로 클리어되므로, 진짜 안정화된 뒤엔 여전히 카운터가 자연스럽게 리셋된다. "수동/원격
        # 시작만 start로, 그 이후 자동 재시작은 reboot로 누적"은 대신 각 .bat 파일이 기동 직전에
        # restart_counter.txt를 지우는 방식으로 보장한다(진짜 새 시작인지는 .bat/원격시작 지점에서만 확실히
        # 알 수 있고, os.execv 자가재시작은 이 파일을 거치지 않으므로 값이 그대로 보존됨).
        print("      ➔ 🚀 파이썬 프로세스를 전격 재시작합니다.")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    # 일반 자가 복구 전개 (카운트 1회차인 경우)
    print("      ➔ 🛠️ 윈도우 ADB 서버 리셋 후 연결 재수립을 개시합니다...")
    os.system("adb kill-server")
    time.sleep(1.0)
    os.system("adb start-server")
    connect_all_mumu_ports_quietly()
    time.sleep(4.0)

    # 디바이스 온라인 상태 검증
    device_online = False
    device = None
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device, port, android_version = pick_supported_device(client)
        if device:
            device_online = True
            print(f"      ✅ 인스턴스 {MUMU_PORT_TO_INDEX.get(port, '?')}번 ({port}포트, 안드로이드 {android_version})에 연결 성공했습니다.")
            record_mumu_port(port)  # 🚨 [2026-08-29] 콜드 리부트 시 같은 인스턴스를 재실행하기 위한 기록
    except:
        pass

    # 조건 B: ADB 연결을 뚫었음에도 디바이스가 존재하지 않거나 오프라인인 경우 즉각 리부트
    if ENABLE_EMULATOR_REBOOT and not device_online:
        print("      🚨 [디바이스 오프라인 감지] ADB 연결 수립 결과 디바이스가 오프라인이거나 감지되지 않습니다. 즉시 에뮬레이터 콜드 리부트를 수행합니다.")
        reboot_emulator()
        # 🚨 [2026-09-02] 위 조건 A와 동일 사유로 clear_restart_counter() 제거 - 로그 파일명 reboot2+ 표기를
        # 위해 카운터를 다음 프로세스로 그대로 넘긴다.
        print("      ➔ 🚀 파이썬 프로세스를 전격 재시작합니다.")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    # 정상 복구 시나리오 진행 (온라인 디바이스 확보)
    if device_online:
        try:
            # 🛑 [안전 가드]: 파이썬 리셋 전 먹통이 된 게임 앱을 강제 종료 후 런처 재기동
            launch_daphne_app(device)

            # 🖥️ [v1.13.8 연동] 앱 신규 실행 완료 대기 및 기동 복구 수행
            print("⏳ 초기 로딩을 위해 15초간 대기합니다...")
            time.sleep(15.0)
            print("👉 초기 로딩 대기 완료. 최초 [1, 1] 터치를 격발합니다.")
            device.shell("input tap 1 1")
            time.sleep(2.0)

            # recover_app_startup을 가동하여 안전 진입
            recover_app_startup(device)

            take_screencap_backup(device, "restart")
            time.sleep(1.5) # 디스크 동기화 대기 마진
        except Exception as f9_err:
            print(f"⚠️ [자가 복구 기동/스샷 실패] {f9_err}")
        # 💾 카운터는 함수 상단에서 이미 저장했으므로 여기선 재저장 불필요.
    else:
        print("⚠️ [자가 복구 실패] 리셋 후 디바이스 객체 획득 불가")

    print("      ➔ 🚀 파이썬 프로세스를 전격 재시작합니다.")
    os.execv(sys.executable, [sys.executable] + sys.argv)

def connect_mumu():
    global global_device
    os.system("adb start-server")
    connect_all_mumu_ports_quietly()
    time.sleep(1.0)
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device, port, android_version = pick_supported_device(client)
        if device:
            print(f"✅ 인스턴스 {MUMU_PORT_TO_INDEX.get(port, '?')}번 ({port}포트, 안드로이드 {android_version})에 연결 성공했습니다.")
            # 🚨 [v1.20.0] 뮤뮤 '앱 상주'가 켜져 있으면 앱마다 별도 디스플레이가 생겨서, 매크로가 읽는
            #    화면과 클릭이 나가는 화면이 서로 달라진다(실측: 탭이 안드로이드 홈으로 새어 뮤뮤 스토어
            #    검색창이 열림). 이 상태로 계속 돌면 게임 대신 홈 화면을 마구 누르므로 여기서 멈춘다.
            if not check_display_configuration(device):
                sys.exit(1)
            record_mumu_port(port)  # 🚨 [2026-08-29] 콜드 리부트 시 같은 인스턴스를 재실행하기 위한 기록
            global_device = device
            return device
        print(f"⚠️ [ADB 연결 실패] 안드로이드 {MIN_ANDROID_VERSION} 이상인 MuMu 인스턴스를 찾지 못했습니다.")
        return None
    except Exception as e:
        print(f"❌ ADB 연결 치명적 실패: {e}")
        return None

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
    if thresh_temp is None: return 0.0
    try:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 65, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val
    except: return 0.0

def click_dead_template(device, img_np, thresh_temp, threshold_val=0.65):
    if thresh_temp is None: return False
    try:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 65, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            h, w = thresh_temp.shape[:2]
            device.shell(f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
        return False
    except: return False

def check_template_present(img_np, thresh_temp, threshold_val=0.70):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_grayscale_template_present(img_np, thresh_temp, threshold_val=0.65):
    # 이진화 없이 순수 그레이스케일 매칭 (village_common 공용 도장용, load_grayscale_template와 짝을 이룸)
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_template_present_in_roi(img_np, thresh_temp, x1, x2, y1, y2, threshold_val=0.70):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    
    scale_x, scale_y = w_img / 1440.0, h_img / 2560.0
    rx1, rx2 = int(x1 * scale_x), int(x2 * scale_x)
    ry1, ry2 = int(y1 * scale_y), int(y2 * scale_y)
    
    if rx2 <= rx1 or ry2 <= ry1 or rx2 > w_img or ry2 > h_img: return False
    crop = img_np[ry1:ry2, rx1:rx2]
    
    h_crop, w_crop = crop.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    _, thresh_crop = cv2.threshold(gray_crop, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_crop, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_grayscale_template_present_in_roi(img_np, thresh_temp, x1, x2, y1, y2, threshold_val=0.70):
    # 이진화 없이 순수 그레이스케일 ROI 매칭 (던전 구분 없이 공용인 open_world_map_btn.png용)
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]

    scale_x, scale_y = w_img / 1440.0, h_img / 2560.0
    rx1, rx2 = int(x1 * scale_x), int(x2 * scale_x)
    ry1, ry2 = int(y1 * scale_y), int(y2 * scale_y)

    if rx2 <= rx1 or ry2 <= ry1 or rx2 > w_img or ry2 > h_img: return False
    crop = img_np[ry1:ry2, rx1:rx2]

    h_crop, w_crop = crop.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False

    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def get_match_score_in_roi(img_np, thresh_temp, x1, x2, y1, y2):
    if thresh_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    
    scale_x, scale_y = w_img / 1440.0, h_img / 2560.0
    rx1, rx2 = int(x1 * scale_x), int(x2 * scale_x)
    ry1, ry2 = int(y1 * scale_y), int(y2 * scale_y)
    
    if rx2 <= rx1 or ry2 <= ry1 or rx2 > w_img or ry2 > h_img: return 0.0
    crop = img_np[ry1:ry2, rx1:rx2]
    h_crop, w_crop = crop.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return 0.0
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    _, thresh_crop = cv2.threshold(gray_crop, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_crop, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def get_grayscale_match_score(img_np, thresh_temp):
    # 이진화 없이 순수 그레이스케일 매칭 점수 (village_common 공용 도장용)
    if thresh_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return 0.0

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def get_match_score(img_np, thresh_temp):
    if thresh_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return 0.0

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

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

def get_field_match_score(img_np, thresh_temp):
    if thresh_temp is None or img_np is None: return 0.0
    h_img, w_img = img_np.shape[:2]
    scale_x, scale_y = w_img / 1440.0, h_img / 2560.0
    x1, x2 = int(1250 * scale_x), int(1420 * scale_x)
    y1, y2 = int(380 * scale_y), int(530 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w_img or y2 > h_img: return 0.0
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return 0.0
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def get_combat_match_score(img_np, template):
    # 🚨 [2026-08-27 부팅 복구 전투 미인식 결함 완치] 기존엔 get_match_score(이진화 160 매칭)를 그대로 썼는데,
    # 스킬 메뉴가 펼쳐진 수동 턴 대기 상태에서 배속 버튼의 미세 명암이 이진화로 뭉개져 점수가 0.3~0.55까지
    # 떨어져 임계값 0.80을 못 넘는 실전 사고 확인(라이브 스크린샷 실측). dungeon_bot.py는 이미 hotfix8에서
    # 같은 영역/도장을 원본 그레이스케일 매칭(check_gray_template_present_specific)으로 바꿔 검증까지 끝난
    # 상태였는데 main.py 쪽엔 반영이 안 돼있었음 - 그 검증된 방식을 그대로 이식(같은 스크린샷 재현 시 0.86~0.92로 통과 확인).
    if template is None or img_np is None: return 0.0
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return 0.0
    crop = img_np[y1:y2, x1:x2]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def get_auto_btn_match_score(img_np, template):
    if template is None or img_np is None: return 0.0
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return 0.0
    crop = img_np[y1:y2, x1:x2]
    return get_match_score(crop, template)

def find_and_get_coords_main(img_np, thresh_temp, threshold_val=0.68):
    if thresh_temp is None or img_np is None: return None
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return None
    
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def find_and_click_template(device, img_np, thresh_temp, threshold_val=0.70):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        device.shell(f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
        return True
    return False

# 🚨 [2026-08-26 유령성 던전선택 '2nd' 층 버튼 미인식 결함 완치] 실전 확인: 유령성 3회차 엔딩(진엔딩)
# 이후 던전선택 화면 배경이 바뀌면서(사용자 확인: 2회차→3회차 진입 시 진엔딩 진행에 따라 배경 그래픽
# 자체가 교체됨), 고정 이진화 문턱 160에서 매칭 점수가 0.72까지 떨어짐(원래 0.88 임계값은 이 정도 여유를
# 두고 튜닝된 값이었음) - 밤새(00:03~10:23, 7시간+) 단 한 번도 진입하지 못하고 2초 간격으로 무한 재시도만
# 반복함. 실측 결과 바뀐 배경에서는 이진화 문턱을 150으로 살짝만 낮추면 점수가 0.90까지 회복되고(다른 구역
# 행과의 오탐 여유도 0.10 이상 유지), 문턱 160(기존 배경)과 150(진엔딩 이후 배경) 두 패스를 순차 시도하면
# 양쪽 다 커버된다. 신뢰도 임계값 자체는 건드리지 않고 이진화 문턱만 다르게 시도 - 상자/피안개 대응 때 쓴
# 것과 동일한 원칙(check_template_present_multipass).
def find_and_click_template_multipass(device, img_np, thresh_temp, threshold_val=0.70, bin_passes=(160, 150)):
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    for bin_th in bin_passes:
        _, thresh_img = cv2.threshold(gray_img, bin_th, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            h, w = thresh_temp.shape[:2]
            device.shell(f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
    return False

def find_and_click_grayscale_template(device, img_np, thresh_temp, threshold_val=0.70):
    # 이진화 없이 순수 그레이스케일 매칭 (마을/던전마다 조명 차이가 큰 도장용, load_grayscale_template와 짝을 이룸)
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        device.shell(f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
        return True
    return False

def start_grand_orchestrator():
    device = connect_mumu()
    if not device:
        if ENABLE_EMULATOR_REBOOT:
            print("⚠️ [ADB 연결 실패] 에뮬레이터가 구동 중이지 않은 것으로 식별되었습니다. 에뮬레이터 자동 실행 가드를 격발합니다.")
            reboot_emulator()
            device = connect_mumu()
            if not device:
                print("❌ [초기 부팅 실패] 에뮬레이터 자동 실행 후에도 연결 수립에 실패했습니다. 프로그램을 종료합니다.")
                return
            
            # 🖥️ [v1.13.8 연동] 에뮬레이터 콜드 부팅 성공 직후 인게임 완전 복구 진입 시퀀스 가동
            print("🔄 [에뮬레이터 콜드 부팅 완료] 인게임 완전 진입을 위해 초기 로딩 대기 및 복구 시퀀스를 수행합니다.")
            time.sleep(15.0)
            device.shell("input tap 1 1")
            time.sleep(2.0)
            recover_app_startup(device)
        else:
            print("❌ [초기 부팅 실패] 에뮬레이터 연결에 실패하였으며, 자동 재기동 옵션이 비활성화 상태라 프로그램을 종료합니다.")
            return
    
    # 📸 [초기 구동 스샷 자동화] 수동 시작 시점의 화면 스크린샷 촬영
    take_screencap_backup(device, "start")

    print("\n=======================================")
    print("🎨 [마스터 마스킹] 대순환 루프 전용 모든 코어 도장들을 로드합니다...")
    t_world_map = load_grayscale_template("templates/Worldmap/world_map_anchor.png")
    t_inn_title = load_template("templates/inn_sleep/inn_title.png")
    t_open_world = load_grayscale_template("templates/open_world_map_btn.png")
    
    # 📂 [v1.17.0 프리셋별 템플릿 동적 교체 로딩]
    # 💡 [항목5] "마을에 있다" 판별 및 여관 진입은 마을별 개별 앵커 대신 village_common 공용 도장으로 통일.
    # 캐릭터창이 펼쳐져 월드맵 아이콘이 가려질 수 있어 worldmap_icon은 앵커로 쓰지 않고 클릭 전용으로만 사용.
    t_village = load_grayscale_template("templates/village_common/inn.png")
    t_char_down = load_template("templates/village_common/char_down.png")
    # 💡 [항목5 후속수정] 이진화(160) 매칭이 밤 배경(넓은 검은 하늘 영역)에서 (0,0) 좌표로 완벽 오탐(1.000)하는 결함 발견 → 그레이스케일로 전환
    t_worldmap_icon = load_grayscale_template("templates/village_common/worldmap_icon.png")

    if TOWN_NAME == "노던할로우":
        t_go_village = load_template("templates/Worldmap/FFXI_village.png")
    else:
        t_go_village = load_template("templates/Worldmap/Vill_isberg_btn.png")

    if DUNGEON_NAME == "북쪽의 유령선":
        t_dungeon_sel = load_template("templates/FFXI/FFXI_dungeon_Anchor.png")
        t_go_dungeon = load_template("templates/Worldmap/FFXI_dungeon.png")
        
        # 반투명 층 선택 도장 이진화 로딩
        floor_img_path = f"templates/FFXI/{DUNGEON_FLOOR_NAME}.png"
        t_enter_dungeon = load_template(floor_img_path)
    else:
        t_dungeon_sel = load_template("templates/WolfCave/dungeon_select.png")
        t_go_dungeon = load_template("templates/Worldmap/Cave_Wolf_btn.png")
        
        if DUNGEON_FLOOR == 2:
            t_enter_dungeon = load_template("templates/WolfCave/Wolf_B2_btn.png")
        else:
            t_enter_dungeon = load_template("templates/WolfCave/Wolf_B1_btn.png")

    # 🆕 [2026-09-07 대설지대] "마을경유형" 진입(town → 마을외곽 → 던전 목록) - village_common/README.md가
    # 예고해뒀던 첫 연동. 이 값들은 항상 로드해두고, 실제 사용(클릭 시도)만 DUNGEON_NAME == "대설지대"로
    # 제한한다(다른 던전은 아래 화면분류 루프에서 이 도장들을 아예 참조하지 않으므로 영향 없음).
    t_go_outside = load_grayscale_template("templates/village_common/go_outside.png")
    t_dungeon_heavysnow = load_template("templates/Vill_Isberg/dungeon_Heavysnow.png")
    t_heavysnow_floor = load_template(f"templates/Vill_Isberg/{HEAVYSNOW_FLOOR_FILE_MAP.get(DUNGEON_FLOOR_NAME, 'Heavysnow_6F')}.png")
    t_inven_cleanup_btn = load_template("templates/Dungeon_select/inven_cleanup_btn.png")
    t_inven_cleanup_refill = load_template("templates/Dungeon_select/inven_cleanup_refill.png")
    t_back_to_village = load_template("templates/Vill_Isberg/back_to_village.png")

    # 🚨 [2026-08-18 하켄 메뉴 시작 인식 결함 완치] 매크로를 하켄 메뉴(귀환목록/가호팝업)가 떠 있는 상태에서
    # (재)시작하면, 아래 스캐너가 마을/세계지도/던전선택/여관/필드/상자 등 알려진 앵커 어느 것과도 안 맞아
    # "아웃게임 무반응 정체"만 무한 반복하며 아무 행동도 못 하던 실전 결함 확인(2026-08-18 01:16~, 5분 절대
    # 워치독이 걸릴 때까지 방치됨). dungeon_bot.py가 이미 갖고 있는 하켄 메뉴 판정 함수를 그대로 재사용한다.
    # 🚨 [2026-08-27 하켄 메뉴 판정 여유 확보] dungeon_bot.py의 동일 수정과 같은 사유 -
    # check_template_present()가 라이브 화면만 이진화(160)하고 도장은 그대로 비교해 판정 여유가
    # 얇았음(실측 0.786/여유 0.086 vs 이진화 통일 시 0.997/여유 0.30). 다른 도장들과 동일하게 통일.
    t_harken_blessing_donothing = dungeon_bot.load_template("templates/Field/harken_blessing_donothing.png")
    t_harken_return = dungeon_bot.load_color_template("templates/FFXI/harken_return.png")

    t_field = load_grayscale_template("templates/Field/field_anchor.png")
    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_get_item = load_template("templates/chestopening/get_item.png")
    t_app_exit = load_template("templates/app_exit.png")
    
    t_heal_close = load_template("templates/close_panel.png")
    t_combat_in = load_grayscale_template("templates/combat_in.png")
    t_combat_slow = load_grayscale_template("templates/combat_slow.png")
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    t_cha_anchor = load_template("templates/cha_panel_anchor.png")
    
    t_popup_levelup = load_template("templates/inn_sleep/popup_levelup_title.png") 
    t_popup_skill = load_template("templates/inn_sleep/popup_skill_title.png")     
    t_skillget_anchor = load_template("templates/skillget_anchor.png")   
    
    t_lvl_next = load_template("templates/inn_sleep/levelup_next_btn.png")   
    t_lvl_close = load_template("templates/inn_sleep/levelup_close_btn.png") 
    t_skill_close_btn = load_template("templates/inn_sleep/skill_close_btn.png")
    
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_arrow_clean = load_template("templates/inn_sleep/arrow_clean.png")
    t_passport_anchor = load_template("templates/anchor_passport_popup.png")
    t_passport_close = load_template("templates/close_passport_popup.png")
    t_error_to_title = load_template("templates/Error_to_title.png")
    t_re_retry = load_template("templates/reboot/retry.png")

    print("=======================================")

    dungeon_run_count = START_RUN_COUNT_OFFSET
    is_fully_healed = False
    need_pickaxe_refill = False  # 💡 [광석파밍 전용] True면 다음 던전선택 도달 시 재진입 대신 마을로 회군
    waiting_for_village_dialogue = False
    heavysnow_resupply_pending = False  # 🆕 [2026-09-07 대설지대] 귀환 직후 마을외곽에서 인벤정리/여관 후처리가 필요한지
    heavysnow_resupply_attempts = 0     # 🆕 후처리가 막혔을 때 주회 자체가 멈추지 않도록 하는 포기 카운터
    heavysnow_force_inn_this_cycle = False  # 🆕 [2026-09-08] inn_visit_loop_interval 조건으로 이번 주회만 여관 강제

    def mark_heavysnow_resupply_pending():
        """대설지대 던전 1회차가 끝났을 때 마을외곽 후처리(인벤정리/여관)를 예약한다.

        🚨 [2026-09-08 실전 확인] 예전엔 이 예약을 "대설지대 진입 경로"의 호출부 한 곳에서만, 그것도
        exit_by_user가 True일 때만 했다. 그런데 start_main_macro() 호출부는 3곳이다 - (1) 부팅 시 이미
        던전 안이었던 경로, (2) 일반 던전선택 경로, (3) 대설지대 진입 경로. 실전 로그(23:37 세션)에서
        매크로가 던전 안에 있는 채로 재시작돼 (1)번으로 들어갔고, 귀환은 정상이었는데 예약이 안 걸려
        인벤정리를 통째로 건너뛰고 곧장 재진입했다. 게다가 하켄 탈출처럼 exit_by_user가 False로 끝나는
        경로도 마을외곽에 도착하므로, 반환값과 무관하게 "던전 1회차가 끝났으면 무조건 예약"으로 바꾼다
        (후처리 블록 자체가 화면이 안 맞으면 조용히 흘려보내고 25회 상한도 있어 과예약은 무해하다).
        """
        nonlocal heavysnow_resupply_pending, heavysnow_resupply_attempts, heavysnow_force_inn_this_cycle
        if DUNGEON_NAME != "대설지대":
            return
        heavysnow_resupply_pending = True
        heavysnow_resupply_attempts = 0
        # 캠핑은 HP/MP만 회복하고 레벨업은 여관 취침으로만 적용되므로, N주회마다 한 번은
        # resupply_mode와 무관하게 여관을 강제로 들르게 한다(0=비활성).
        heavysnow_force_inn_this_cycle = (
            INN_VISIT_LOOP_INTERVAL > 0 and dungeon_run_count % INN_VISIT_LOOP_INTERVAL == 0
        )
        if heavysnow_force_inn_this_cycle:
            print(f"🏠 [주회 카운터] {dungeon_run_count}주회 도달 - inn_visit_loop_interval={INN_VISIT_LOOP_INTERVAL} 조건으로 이번엔 여관을 경유합니다.")

    force_first_analysis = True
    last_action_time = time.time()
    last_logged_status = ""
    first_stuck_time_str = ""
    first_stuck_start_time = None
    first_outgame_stuck_time_str = ""
    first_outgame_stuck_start_time = None
    global_skill_setup_completed = False

    # 🛑 [Daphne 마스터 섀도우 통화면 동결 감지 엔진 변수]
    last_full_screen_shadow = None
    last_freeze_check_time = time.time()
    consecutive_freeze_count = 0  # 🚨 [2026-08-10 실전 사고 완치] 연속 동결 감지 시 진짜 복구로 승격시키기 위한 카운터

    print("\n====================================================")
    print(f"위저드리 다프네 [그랜드 마스터 순환 컨트롤러 v{CURRENT_VERSION}] 가동")
    print(f" -> 목표 주회 설정 수치: {LIMIT_DUNGEON_LOOPS}회 안전 고정")
    print(f" -> 숏컷기반 스킬 예약 시스템 가동 여부: {bool(ENABLE_FIRST_COMBAT_SKILL)}")
    print("====================================================")
    is_worldmap_swiped = False
    worldmap_drag_step = 0
    worldmap_last_drag_time = 0.0

    # 🔮 [최초 구동 무인 안심 가드] 에뮬리부트/초기실행 후 타이틀/공지사항/주의 화면 돌파 강제 가동
    recover_app_startup(device)

    cap_fail_counter = 0
    resolution_fail_counter = 0  # 🚨 [v1.14.0-hotfix3] 해상도 미달 가드 연속 카운터 추가
    while True:
        update_heartbeat()
        try:
            raw_cap = capture_screen_bytes(device)
            if raw_cap is None:
                raise RuntimeError("Screencap returned None")
            img_np = decode_screen_bytes(raw_cap)
            cap_fail_counter = 0
        except Exception as cap_err:
            cap_fail_counter += 1
            print(f"⚠️ [main 캡처 실패] 실시간 캡처 유실!! 오류: {cap_err} ({cap_fail_counter}/5)")
            if cap_fail_counter >= 5:
                restart_process("아웃게임 화면 캡처 5회 연속 실패")
            time.sleep(0.5)
            continue

        height, width = img_np.shape[:2]
        
        # 🖥️ [가로 화면/안드로이드 홈 복구 가드] 에뮬레이터가 가로 상태로 기동된 경우 앱을 실행해 세로 모드 회전을 유도
        if height < width:
            resolution_fail_counter += 1
            print(f"🖥️ [가로 화면 감지] 현재 화면이 가로 상태({width}x{height})입니다. 위저드리 다프네 앱 기동(Relaunch)을 강제 주입하여 세로 화면 전환을 시도합니다. ({resolution_fail_counter}/3)")
            # 🚨 [2026-08-29] 30회는 너무 관대해서 뮤뮤가 진짜 먹통일 때 탈출까지 너무 오래 걸림 - 3회로 단축
            if resolution_fail_counter >= 3:
                restart_process(f"main 내 가로 화면 정체 3회 연속 감지 (화면 크기: {width}x{height})")
                resolution_fail_counter = 0
            try:
                launch_daphne_app(device)
                time.sleep(4.0)
            except Exception as launch_err:
                print(f"⚠️ 가로 화면 앱 실행 실패: {launch_err}")
            continue

        if height < 2560 or width < 1440:
            resolution_fail_counter += 1
            print(f"⚠️ [main 해상도 미달 가드] 현재 화면 크기({width}x{height})가 기준 해상도(1440x2560) 미만입니다. 1.0초 대기합니다. ({resolution_fail_counter}/30)")
            if resolution_fail_counter >= 30:
                restart_process(f"main 내 해상도 미달 상태 30초 지속 감지 (화면 크기: {width}x{height})")
                resolution_fail_counter = 0
            time.sleep(1.0)
            continue
        else:
            resolution_fail_counter = 0  # 정상 해상도 검출 시 카운터 리셋

        mean_brightness = np.mean(img_np)
        if mean_brightness < 5.0:
            print("⏳ [로딩 가드] 화면 전환/로딩 중(암전) 포착! 0.5초 대기 후 재스캔합니다.")
            time.sleep(0.5)
            continue

        current_time = time.time()
        
        # 정체 해소 감지 시 타임아웃 초기화
        if current_time - last_action_time <= 30.0:
            first_stuck_time_str = ""
            first_stuck_start_time = None
            first_outgame_stuck_time_str = ""
            first_outgame_stuck_start_time = None

        # ======================================================================
        # 👑 [Daphne 완성형 엔진: 1분 30초 전체 화면 동결 시 인지 복구 레이더 강제 부팅]
        # ======================================================================
        # 🚨 [2026-08-12 광석파밍 한정 비활성화] 이 바깥 루프 동결감지는 dungeon_bot.start_main_macro() 안에
        # 있는 동안 아예 안 도는 구조적 한계(2026-08-11 완치 시도) 때문에, 채굴 사이클이 짧아지면(30~100초) 여러
        # 성공 사이클이 150초 재기준 문턱 안에 다 들어가버려 "몇 사이클 전 던전선택 화면"과 "지금 던전선택 화면"을
        # 비교하는 격 - 문턱값을 더 늘려도 근본적으로 해소가 안 되는 구조적 오탐(실전 확인: 하켄 메뉴는 매번
        # 1~2회차에 정상 성공했는데도 귀환 직후 반복 오탐). 광석파밍은 이제 dungeon_bot.py 내부에 훨씬 정확한
        # 자체 워치독이 2개(trigger_harken_escape 60초, TRIGGER_EXIT 90초) 있으므로, 이 범용 감지는 광석파밍에서만
        # 끄고 상자파밍 등 다른 방식에서는 그대로 유지한다. 문제가 재발하면 그때 다시 검토.
        if FARMING_METHOD != "광석파밍" and current_time - last_freeze_check_time > 90.0:
            freeze_check_gap = current_time - last_freeze_check_time
            current_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            current_shadow = cv2.resize(current_gray, (int(width/4), int(height/4)))

            # 🚨 [2026-08-11 구조적 오탐 완치] 이 바깥 루프는 dungeon_bot.start_main_macro() 안에 있는 동안은
            # 아예 돌지 않는다(채굴/귀환/재진입 사이클 전체가 그 블로킹 호출 하나에서 처리됨, 실전 로그로 확인:
            # 몇 분씩 이 루프가 완전히 멈춰있다가 귀환으로 던전을 빠져나온 직후 딱 1번 재개됨). 그 순간 last_full_screen_shadow는
            # 이번 던전 사이클이 시작되기 전(최대 수 분 전)에 찍힌 스냅샷인데, 귀환 직후 화면은 항상 똑같이 생긴
            # "던전선택" 화면으로 복귀하므로 그 사이 실제로는 채굴/전투/이동이 다 있었어도 픽셀 차이가 0에 가깝게
            # 나와 필연적으로 오탐이 발생하던 구조였음(하루 70건 이상, 전부 귀환 성공 로그 직후·간격이 90초를
            # 훨씬 초과). 간격이 150초를 넘으면 "루프가 다른 작업으로 오래 비어있었다"는 뜻이므로 비교 자체를
            # 생략하고 조용히 기준만 재설정한다. 90~150초 구간은 루프가 계속 초 단위로 돌던 정상적인 아웃게임
            # 정체 상황이므로 기존 로직 그대로 유지해 진짜 동결(2026-08-10 6시간 방치 사고 같은 경우)은 계속 잡아낸다.
            if last_full_screen_shadow is not None and freeze_check_gap <= 150.0:
                frame_diff = cv2.absdiff(current_shadow, last_full_screen_shadow)
                pixel_alteration = np.count_nonzero(frame_diff > 30)

                if pixel_alteration < 200:
                    consecutive_freeze_count += 1
                    frozen_seconds_min = consecutive_freeze_count * 90
                    freeze_started_estimate = (datetime.datetime.now() - datetime.timedelta(seconds=frozen_seconds_min)).strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n🚨💀 [사령탑 통화면 동결 감지!!] 최근 90초간 프레임 변화 없음 (동결 판정, 연속 {consecutive_freeze_count}회차).")
                    print(f"      -> 최소 동결 지속: {frozen_seconds_min}초 (추정 시작: {freeze_started_estimate} 경) / 미세 변동률: {pixel_alteration} px")

                    # 🚨 [2026-08-10 실전 사고 완치] 예전엔 이 감지 이후 그냥 보정 터치 + 재스캔만 반복해서,
                    # 뮤뮤가 진짜로 완전히 멈췄을 땐(다음 90초 뒤에도 여전히 0px 변화) 똑같은 얼어붙은 화면을
                    # 영원히 재확인만 하고 진짜 복구(adb 재시작/에뮬레이터 리부트)로 못 넘어가던 결함이 있었음
                    # (뮤뮤 동결 후 6시간 넘게 방치된 실제 사고로 확인). 연속 2회(3분)에서 승격.
                    # (참고: 8/11에 관측된 대량 오탐/재시작은 이 임계값이 아니라 위 freeze_check_gap 가드가
                    # 없어서 생긴 구조적 결함이었음 - 원인 규명 후 완치, 임계값은 원래 의도대로 2 유지)
                    if consecutive_freeze_count >= 2:
                        restart_process(f"화면 동결이 {consecutive_freeze_count}회 연속(약 {consecutive_freeze_count * 90}초) 감지되어 보정 터치로도 해소되지 않음")
                        return

                    print("      🔄 [사령탑 인지 복구] 엇박자 교정을 위해 강제 전수조사 감별 시퀀스를 전격 유도합니다!!")

                    # 1. 아웃게임 상태 조건문 타이밍 강제 오픈 및 해제
                    force_first_analysis = True
                    last_action_time = current_time - 40.0

                    # 2. 렉 유실 가드를 위한 화면 정중앙 보정 터치 가동
                    device.shell("input tap 720 1280")
                    time.sleep(1.0)

                    last_freeze_check_time = time.time()
                    last_full_screen_shadow = None
                    continue
                else:
                    consecutive_freeze_count = 0
            else:
                # 🚨 [2026-08-12 무한루프 완치] last_full_screen_shadow가 None인 경우(바로 위에서 동결 1회차를
                # 감지한 직후 재시도를 위해 일부러 None으로 초기화한 상태)까지 여기서 매번 count=0으로 되돌리면,
                # 진짜로 계속 멈춰있는 화면조차 다음 재기준 사이클마다 카운터가 리셋되어 영원히 2회차에 도달하지
                # 못해 restart_process()로 승격이 안 되는 결함이 있었음(실전 확인: 동결 1회차만 반복 감지하며
                # 하켄탈출→실패→재검증→하켄탈출을 몇 분씩 무한 반복, 승격 없음). "간격이 비정상적으로 커서
                # 비교 자체가 무의미한" 경우(last_full_screen_shadow가 있는데도 gap>150)에만 리셋한다.
                if last_full_screen_shadow is not None and freeze_check_gap > 150.0:
                    print(f"ℹ️ [사령탑 동결감지 재기준] 마지막 점검 후 {freeze_check_gap:.0f}초 경과(던전 등 다른 작업으로 바깥 루프가 오래 비어있었음) - 비교 기준이 낡아 동결판정을 건너뛰고 현재 화면으로 기준을 새로 잡습니다.")
                    consecutive_freeze_count = 0

            last_full_screen_shadow = current_shadow
            last_freeze_check_time = current_time
        # ======================================================================

        # ======================================================================
        # 👑 [대화창 저격 구역 - 극하단 대화 전용 스팟 완벽 격리 가드]
        # ======================================================================
        dialogue_zone = img_np[2200:2560, 1100:1440]
        
        # 📦 [상자 조우 예외 가드] 화면에 '열다'가 감지되는 경우 대화창 저격을 하지 않고 건너뜁니다.
        is_box_menu_present = check_template_present(img_np, t_yeolda, 0.65)
        is_get_item_present = check_template_present(img_np, t_get_item, 0.70)
        
        # [차원 안전 가드] dialogue_zone의 크기가 t_arrow_clean 템플릿 크기보다 작은 경우 매칭 생략
        has_dialogue_size_ok = True
        if t_arrow_clean is not None:
            hz, wz = dialogue_zone.shape[:2]
            ha, wa = t_arrow_clean.shape[:2]
            if hz < ha or wz < wa:
                has_dialogue_size_ok = False
        
        if t_arrow_clean is not None and not is_box_menu_present and not is_get_item_present and has_dialogue_size_ok:
            gray_zone = cv2.cvtColor(dialogue_zone, cv2.COLOR_RGB2GRAY)
            _, thresh_zone = cv2.threshold(gray_zone, 160, 255, cv2.THRESH_BINARY)
            result_arrow = cv2.matchTemplate(thresh_zone, t_arrow_clean, cv2.TM_CCOEFF_NORMED)
            _, score_arrow_clean, _, arrow_loc = cv2.minMaxLoc(result_arrow)
            
            # 임계값을 기존 0.70에서 0.82로 대폭 상향하여 지형 오탐을 억제합니다.
            if score_arrow_clean > 0.82:
                print(f"💬 [🗣️ 대화창 저격 성공] 격리구역 내 진짜 대화 화살표 포착 (신뢰도: {score_arrow_clean:.2f}). 즉각 파쇄!!")
                real_x = 1100 + arrow_loc[0] + int(t_arrow_clean.shape[1] / 2)
                real_y = 2200 + arrow_loc[1] + int(t_arrow_clean.shape[0] / 2)
                device.shell(f"input tap {real_x} {real_y}")
                time.sleep(1.0)
                last_action_time = time.time()
                last_full_screen_shadow = None
                last_freeze_check_time = time.time()
                continue
        # ======================================================================

        if (current_time - last_action_time > 30.0) or force_first_analysis:
            if force_first_analysis:
                print(f"\n🚀 [초기 부팅 오토 세트] 시스템이 가동되었습니다. 즉시 현재 에뮬레이터 화면 감별을 시작합니다!")
                force_first_analysis = False
            else:
                if not first_outgame_stuck_time_str:
                    first_outgame_stuck_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    first_outgame_stuck_start_time = time.time()
                
                stuck_duration = time.time() - first_outgame_stuck_start_time
                print(f"\n⚠️ [🚨 사령탑 블랙박스 경고] 아웃게임 상태 무반응 정체 중... (최초 정체 발생 시각: {first_outgame_stuck_time_str}, 경과: {int(stuck_duration)}초)")
                
                # 🖥️ [v1.13.7 추가] 사령탑 아웃게임 5분 이상 정체 시 자동 재부팅 세이프티 가드
                if stuck_duration >= 300.0:
                    raise RuntimeError(f"사령탑 아웃게임 정체 한계 초과: {int(stuck_duration)}초 동안 아웃게임 상태에 머물러 강제 앱/에뮬레이터 리셋을 수행합니다.")
                
            print("🔍 [화면 분석 엔진] 보유 중인 모든 마스터 앵커의 매칭 신뢰도를 전수조사합니다...")
            
            if check_template_present(img_np, t_passport_anchor, 0.80) and check_template_present(img_np, t_passport_close, 0.80):
                print("🎫 [사령탑 팝업 가드] 여권 만료 안내 팝업이 확실하게 감지되었습니다. 'X 닫기'를 터치합니다.")
                if find_and_click_template(device, img_np, t_passport_close, 0.75):
                    print("      🎯 'close_passport_popup' 앵커 좌표 조준 타격 성공.")
                else:
                    device.shell("input tap 720 1625")
                time.sleep(2.5)
                last_action_time = time.time()
                continue

            if check_template_present(img_np, t_net_error, 0.75):
                print("🌐 [사령탑 통신 가기] 기습적인 네트워크 오류 팝업 감지!! 재시도를 주입합니다.")
                if find_and_click_template(device, img_np, t_net_retry, 0.70):
                    print("      🎯 'btn_network_retry'(재시도) 앵커 좌표 조준 타격 성공.")
                else:
                    device.shell("input tap 540 1100")
                time.sleep(4.0)
                last_action_time = time.time()
                continue

            # 💡 [갱신 데이터 확인 팝업 가드] 이 팝업이 village_common/inn.png와 그레이스케일 0.72로 오탐되어
            # "VILLAGE"로 오판정되고 여관 도장을 무한 반복 터치하던 결함 발견(실사용 로그로 확인). recover_app_startup()
            # 에서만 체크하던 Error_to_title.png를 메인 루프에도 동일하게 추가해, 점검류 팝업 체크보다 먼저 걸러냅니다.
            # ⚠️ "타이틀로"가 뜨면 게임이 로그인/로딩부터 다시 시작되어 자동전투 스킬 설정 등 세션 상태가 초기화되므로,
            # 매크로도 같이 완전히 새로 시작합니다(파이썬 프로세스 자체를 재시작 - 새 프로세스의 recover_app_startup이
            # 이 화면을 다시 감지해 탭까지 처리하므로 여기서 직접 탭할 필요 없음).
            if check_template_present(img_np, t_error_to_title, 0.70):
                print("👉 [타이틀 복귀 확인] 'Error_to_title.png' 감지! 매크로를 완전히 재시작합니다.")
                take_screencap_backup(device, prefix="stuck")
                write_restart_counter(read_restart_counter() + 1)
                os.execv(sys.executable, [sys.executable] + sys.argv)

            # 💡 [재시도 팝업 가드] Error_to_title.png와 동일한 사유(recover_app_startup() 전용으로만 체크되고
            # 메인 루프엔 없었음)로 같이 추가. 언제든 뜰 수 있는 일반 네트워크/서버 재시도 팝업.
            if check_template_present(img_np, t_re_retry, 0.70):
                print("🌐 [네트워크 재시도] 'retry.png' 감지! 즉시 터치합니다.")
                find_and_click_template(device, img_np, t_re_retry, 0.70)
                time.sleep(3.0)
                last_action_time = time.time()
                continue

            score_village = get_grayscale_match_score(img_np, t_village)
            score_world = get_grayscale_match_score(img_np, t_world_map)
            score_dung_sel = get_match_score(img_np, t_dungeon_sel)
            score_inn = get_match_score(img_np, t_inn_title)
            
            score_field = get_field_match_score(img_np, t_field)
            score_yeolda = get_match_score(img_np, t_yeolda)
            score_loot = get_match_score(img_np, t_get_item)
            score_heal_close = get_match_score(img_np, t_heal_close)
            
            score_combat_in = get_combat_match_score(img_np, t_combat_in)
            score_combat_slow = get_combat_match_score(img_np, t_combat_slow)
            score_combat = max(score_combat_in, score_combat_slow)
            
            is_mini_screen = chest_opener.is_minigame_screen(img_np, height, width)
            score_cha_panel = get_match_score(img_np, t_cha_anchor)
            score_popup_lvl = get_match_score(img_np, t_popup_levelup) 
            score_popup_sk = get_match_score(img_np, t_popup_skill) 
            score_sk_get_text = get_match_score(img_np, t_skillget_anchor) 
            score_dead_screen = get_dead_match_score(img_np, t_anchor_dead)

            print(f"📊 [분석 리포트] 마을:{score_village:.2f} | 세계지도:{score_world:.2f} | 던전선택:{score_dung_sel:.2f} | 여관:{score_inn:.2f}")

            if score_dead_screen > 0.65:
                print("   ➔ 💀 [사령탑 사망 가드] 붉은 안개/회색조 전멸 구역 검증 확정!!")
                if click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    print("         🎯 [안개 관통 저격] 'btn_resurrect'(부활한다) 실시간 뼈대 추적 격파 완료.")
                else:
                    device.shell("input tap 540 930")
                time.sleep(2.5)
                last_action_time = time.time()
                continue

            # 🚨 [2026-08-18 하켄 메뉴 시작 인식 결함 완치] 위 4개 아웃게임 앵커 판정 전에 먼저 확인 -
            # "아무것도 안 한다"는 상자 대화창에도 있지만 t_yeolda를 같이 넘겨 상자는 여기서 걸러진다.
            harken_menu_state = dungeon_bot.check_and_handle_harken_menu(
                device, t_harken_blessing_donothing, t_harken_return, img_np=img_np, t_yeolda=t_yeolda
            )
            if harken_menu_state in ("returned", "blessing"):
                print(f"   ➔ 🚪 [사령탑 하켄 가드] 하켄 메뉴 화면에서 시작/정체된 것을 인지, '{harken_menu_state}' 처리 완료.")
                first_outgame_stuck_time_str = ""
                first_outgame_stuck_start_time = None
                time.sleep(2.0)
                last_action_time = time.time()
                continue

            if score_popup_lvl > 0.75:
                print("   ➔ 📈 [사령탑 롤백가드] 정통 레벨업 마스터 앵커 식별 성공!! 하단 버튼 매칭 검증을 돌립니다.")
                if find_and_click_template(device, img_np, t_lvl_next, 0.65):
                    print("         ➔ ✨ 'levelup_next_btn'(다음) 이미지 검출 및 실시간 격파 완료.")
                elif find_and_click_template(device, img_np, t_lvl_close, 0.60):
                    print("         ➔ ✨ 'levelup_close_btn'(닫기) 이미지 검출 및 최종 여관 탈출 성공.")
                else:
                    device.shell("input tap 250 1920")
                time.sleep(1.5)
                last_action_time = time.time()
                continue

            if score_popup_sk > 0.75 or score_sk_get_text > 0.75:
                print("   ➔ 🔮 [사령탑 롤백가드] 스킬/마법 배움 연출 마스터 앵커 식별 성공!! 'skill_close_btn' 조준경을 가동합니다.")
                if find_and_click_template(device, img_np, t_skill_close_btn, 0.65):
                    print("         ➔ ✨ 'skill_close_btn'(탭으로 닫기) 이미지 인식 저격 점사 완벽 성공.")
                else:
                    device.shell("input tap 540 1450")
                time.sleep(1.5)
                last_action_time = time.time()
                continue

            if score_cha_panel > 0.78:
                print("   ➔ 🛡️ [사령탑 이미지 레이더] 아웃게임 캐릭터 상세 정보창 감지 성공!!")
                close_coords = find_and_get_coords_main(img_np, t_heal_close, 0.70)
                if close_coords:
                    device.shell(f"input tap {close_coords[0]} {close_coords[1]}")
                else:
                    device.shell("input tap 75 1940")
                time.sleep(1.5)
                last_action_time = time.time()
                continue

            scores = {
                "VILLAGE": score_village,
                "WORLDMAP": score_world,
                "DUNGEON_SEL": score_dung_sel,
                "INN": score_inn
            }
            best_status = max(scores, key=scores.get)

            if scores[best_status] > 0.65:
                status_label = f"{best_status}({DUNGEON_NAME})" if best_status == "DUNGEON_SEL" else best_status
                print(f"   ➔ 🏠 [엔진 최종 판정] 리얼 아웃게임 스팟 안착 확인: '{status_label}' 구역으로 확정합니다. (신뢰도: {scores[best_status]:.2f})")
                first_stuck_time_str = "" 
                global_skill_setup_completed = False
                if best_status != "WORLDMAP":
                    is_worldmap_swiped = False
                    worldmap_drag_step = 0
                
                if best_status == "VILLAGE":
                    waiting_for_village_dialogue = False
                    last_logged_status = "VILLAGE"
                elif best_status == "WORLDMAP":
                    last_logged_status = "WORLDMAP"
                elif best_status == "DUNGEON_SEL":
                    last_logged_status = "DUNGEON_SEL"
                elif best_status == "INN":
                    try:
                        inn_manager.run_inn_sleep_sequence(device)
                    except Exception as inn_err:
                        restart_process(f"여관 숙박 동작 중 ADB 통신 치명적 예외 발생: {inn_err}")
                    is_fully_healed = True
                    dungeon_run_count = 0
                    need_pickaxe_refill = False
                
                last_action_time = time.time()
                continue

            if is_mini_screen or score_loot > 0.65 or score_field > 0.60 or score_yeolda > 0.65 or score_heal_close > 0.65 or score_combat > 0.80:
                print(f"   ➔ 🤖 [엔진 최종 판정] 아웃게임 부재 및 던전 조건 충족, '던전 내부' 상태로 확정합니다.")
                last_action_time = time.time()
                
                run_skill_logic = ENABLE_FIRST_COMBAT_SKILL and (not global_skill_setup_completed)
                try:
                    exit_by_user, skill_ok, need_pickaxe_result = dungeon_bot.start_main_macro(device, run_skill_logic, HEALING_LOOPS, bool(ENABLE_HEAL_AFTER_CHEST), healer_slot=HEALER_SLOT, masked_adventurer_slot=MASKED_ADVENTURER_SLOT, chest_opener_slot=CHEST_OPENER_SLOT, farming_method=FARMING_METHOD, dungeon_name=DUNGEON_NAME, from_dungeon_select=False, dungeon_floor_name=DUNGEON_FLOOR_NAME, return_method=RETURN_METHOD)
                    if FARMING_METHOD == "광석파밍":
                        need_pickaxe_refill = need_pickaxe_result
                    if skill_ok:
                        global_skill_setup_completed = True  
                    if exit_by_user: 
                        last_action_time = time.time() - 20.0 
                    else: 
                        last_action_time = time.time()
                    mark_heavysnow_resupply_pending()
                except Exception as bot_err:
                    restart_process(f"던전 내부 동작 중 ADB 통신 치명적 예외 발생: {bot_err}")
                continue
            else:
                if check_template_present(img_np, t_app_exit, 0.75):
                    print("⏰ [사령탑 안전 가드] 앱 종료 팝업 감지! 즉각 '취소'(880, 1450)를 터치하여 파쇄합니다.")
                    device.shell("input tap 880 1450")
                    time.sleep(1.0)
                    last_action_time = time.time()
                    continue
                close_coords_main = find_and_get_coords_main(img_np, t_heal_close, 0.70)
                if close_coords_main:
                    device.shell(f"input tap {close_coords_main[0]} {close_coords_main[1]}")
                else:
                    mag_coords_main = find_and_get_coords_main(img_np, t_exit_mag, 0.70)
                    if mag_coords_main: device.shell(f"input tap {mag_coords_main[0]} {mag_coords_main[1]}")
                    else: device.shell("input tap 713 273")
                # 🚨 [2026-09-09 실전 확인] 이 경로만 유일하게 last_action_time을 안 건드려서, 다음 틱에도
                # "current_time - last_action_time > 30.0"이 계속 참이 되어 영원히 이 30초 정체 분기로만
                # 되돌아왔다. 그 아래에 있는 is_any_dungeon_sel(공용 "세계지도를 연다" 버튼)/t_dungeon_sel/
                # 세계지도/마을외곽 등 "매 틱 상시 판정" 코드가 전부 그 뒤에 있어서 한 번도 실행되지 못했다
                # - 실전 로그(2026-09-09 14:03~14:05)에서 마을/세계지도/던전선택/여관 점수가 몇 분간 완전히
                # 똑같은 패턴으로 반복된 게 이 함정에 갇힌 증거. 다른 함수와 동일하게 여기도 last_action_time을
                # 갱신해야 다음 틱에 상시 판정으로 빠져나가 세계지도 이탈/재이동 로직에 도달할 수 있다.
                last_action_time = time.time()
                time.sleep(2.0)

            continue

        # 💡 [갱신 데이터 확인 팝업 가드 - 상시 체크] 위쪽 30초 정체 감지 블록은 last_action_time이 최근이면(예: 던전에서
        # 막 돌아온 직후) 통째로 스킵되어, 그 다음 줄부터 시작되는 상시 판별 로직(마을/월드맵/던전선택)이 이 팝업을 못 보고
        # village_common/inn.png와 오탐(0.72)될 수 있음(실사용 중 하켄 귀환 직후 발생 확인). 여기서도 동일하게 최우선 체크.
        if check_template_present(img_np, t_error_to_title, 0.70):
            print("👉 [타이틀 복귀 확인] 'Error_to_title.png' 감지! 매크로를 완전히 재시작합니다.")
            take_screencap_backup(device, prefix="stuck")
            write_restart_counter(read_restart_counter() + 1)
            os.execv(sys.executable, [sys.executable] + sys.argv)

        if check_template_present(img_np, t_re_retry, 0.70):
            print("🌐 [네트워크 재시도] 'retry.png' 감지! 즉시 터치합니다.")
            find_and_click_template(device, img_np, t_re_retry, 0.70)
            time.sleep(3.0)
            last_action_time = time.time()
            continue

        # 💡 [던전선택 범용 인식] "세계지도를 연다" 공용 버튼(ROI 제한)으로 "여기가 어떤 던전이든 던전선택 화면이다"를 우선 판별.
        # 프리셋 전용 도장(t_dungeon_sel)이 안 맞아도 이걸로 "던전선택 화면인데 내 던전이 아니다"를 구분할 수 있다.
        is_any_dungeon_sel = check_grayscale_template_present_in_roi(img_np, t_open_world, 800, 1200, 1480, 1650, 0.85)

        if check_template_present(img_np, t_dungeon_sel, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "DUNGEON_SEL":
                last_action_time = time.time()
                last_logged_status = "DUNGEON_SEL"
                print(f"🚪 [던전선택 도달] '{DUNGEON_NAME}' 던전선택창 확인.")

            # 💡 [항목4] 파밍 방식별 재진입 여부 완전 분리
            # - 광석파밍: N주회 카운터를 아예 참조하지 않고, 곡괭이 부족(need_pickaxe_refill)일 때만 마을 회군
            # - 상자파밍(기존 백아): 기존 N주회 카운터 유지 + LIMIT_DUNGEON_LOOPS=0이면 무한 주회
            if FARMING_METHOD == "광석파밍":
                should_reenter = not need_pickaxe_refill
            else:
                should_reenter = (LIMIT_DUNGEON_LOOPS == 0) or (dungeon_run_count < LIMIT_DUNGEON_LOOPS)

            if should_reenter:
                click_success = False
                
                if DUNGEON_NAME == "북쪽의 유령선":
                    # 파판 던전 층계 버튼 이진화 매치 터치 (오검출 방지를 위해 임계값을 0.88로 대폭 상향 튜닝)
                    # 🚨 [2026-08-26] 유령성 3회차 진엔딩 이후 배경 교체로 문턱 160만으로는 밤새 매칭 실패하던 결함 완치 -
                    # 문턱 160/150 순차 시도로 교체(신뢰도 임계값 0.88은 그대로 유지).
                    print(f"📋 [던전선택 - FFXI] '{DUNGEON_FLOOR_NAME}' 층 버튼 도장 정밀 조준을 시도합니다.")
                    if find_and_click_template_multipass(device, img_np, t_enter_dungeon, 0.88, bin_passes=(160, 150)):
                        print(f"👉 [던전선택 - FFXI] '{DUNGEON_FLOOR_NAME}' 진입 버튼 격파 성공!")
                        click_success = True
                    else:
                        print(f"⚠️ [던전선택 - FFXI] '{DUNGEON_FLOOR_NAME}' 층 버튼 매칭 실패. 재스캔 대기...")
                else:
                    # 2층 활성화 감지를 위해 위쪽 격리 ROI 내 지하 1층 버튼 유무 판정 (Y:1200~1320)
                    is_b2_active = check_template_present_in_roi(img_np, t_enter_dungeon, 1100, 1380, 1200, 1320, 0.75)
                    target_floor = DUNGEON_FLOOR
                    
                    if is_b2_active:
                        print(f"📋 [던전선택] 현재 지하 2층 버튼이 활성화되어 있습니다. (목표: {target_floor}층)")
                        if target_floor == 2:
                            print("👉 [던전선택] 지하 2층 고정 좌표 (1239, 1411) 터치 주입")
                            device.shell("input tap 1239 1411")
                            click_success = True
                        else:
                            print("👉 [던전선택] 지하 1층 고정 좌표 (1239, 1267) 터치 주입")
                            device.shell("input tap 1239 1267")
                            click_success = True
                    else:
                        print("📋 [던전선택] 현재 지하 1층만 활성화되어 있습니다.")
                        print("👉 [던전선택] 지하 1층 고정 좌표 (1239, 1411) 터치 주입")
                        device.shell("input tap 1239 1411")
                        click_success = True
                
                if click_success:
                    # 💡 [진입 폴링 대기] 고정 5초 대기가 유령성 등 로딩이 느린 던전에서 부족해, 아직 던전선택 화면인데
                    # dungeon_bot을 호출 → 즉시 되돌아옴 → from_dungeon_select 컨텍스트 유실 → 뒤늦게 재진입 시
                    # "최초 기동 감지" 안전장치가 오작동하며 계속 하켄 탈출을 반복하던 결함을 완치.
                    # 최대 10초까지 0.8초 간격으로 필드 안착을 직접 폴링하고, 로딩이 일찍 끝나면 그만큼 빨리 진입한다.
                    print("⏳ [던전 진입 대기] 필드 안착을 최대 10초간 폴링합니다...")
                    poll_start = time.time()
                    entered = False
                    while time.time() - poll_start < 10.0:
                        time.sleep(0.8)
                        try:
                            raw_poll = capture_screen_bytes(device)
                            if raw_poll:
                                img_np_poll = decode_screen_bytes(raw_poll)
                                if check_field_anchor_present(img_np_poll, t_field, 0.65):
                                    print(f"      ✅ [던전 진입 확인] 필드 안착 확인 (대기 {time.time()-poll_start:.1f}초)")
                                    entered = True
                                    break
                        except Exception:
                            pass
                    if not entered:
                        print("      ⚠️ [던전 진입 대기 초과] 10초 내 필드 안착 미확인. 일단 진입 시퀀스를 시도합니다.")

                    run_skill_logic = ENABLE_FIRST_COMBAT_SKILL and (not global_skill_setup_completed)
                    try:
                        exit_by_user, skill_ok, need_pickaxe_result = dungeon_bot.start_main_macro(device, run_skill_logic, HEALING_LOOPS, bool(ENABLE_HEAL_AFTER_CHEST), healer_slot=HEALER_SLOT, masked_adventurer_slot=MASKED_ADVENTURER_SLOT, chest_opener_slot=CHEST_OPENER_SLOT, farming_method=FARMING_METHOD, dungeon_name=DUNGEON_NAME, from_dungeon_select=True, dungeon_floor_name=DUNGEON_FLOOR_NAME, return_method=RETURN_METHOD)
                        if skill_ok: global_skill_setup_completed = True
                        if exit_by_user: last_action_time = time.time() - 20.0
                        else: last_action_time = time.time()
                        if FARMING_METHOD == "광석파밍":
                            need_pickaxe_refill = need_pickaxe_result
                        else:
                            dungeon_run_count += 1
                        clear_restart_counter()
                        is_fully_healed = False
                        mark_heavysnow_resupply_pending()
                    except Exception as bot_err:
                        restart_process(f"던전 진입 시퀀스 중 ADB 통신 치명적 예외 발생: {bot_err}")
            else:
                if find_and_click_grayscale_template(device, img_np, t_open_world, 0.70):
                    print(f"      ✅ 't_open_world' 도장 추적 정밀 타격 성공. ({DUNGEON_NAME})")
                    last_action_time = time.time()
                    time.sleep(2.5)
                else:
                    print("      ⚠️ [세계지도 단추 은폐 감지] 뒤로가기(ESC) 입력을 주입해 세계지도로 안전 탈출을 유도합니다.")
                    device.shell("input keyevent 4")
                    last_action_time = time.time()
                    time.sleep(3.0)
            continue

        elif is_any_dungeon_sel:
            # 💡 [던전선택 불일치] 던전선택 화면은 맞는데 지금 프리셋(DUNGEON_NAME)의 던전이 아님 → 층 진입 시도하지 않고 즉시 세계지도로 이탈
            if last_logged_status != "DUNGEON_SEL_WRONG":
                last_action_time = time.time()
                last_logged_status = "DUNGEON_SEL_WRONG"
                print(f"🚪⚠️ [던전선택 불일치] 현재 화면이 '{DUNGEON_NAME}' 던전선택창이 아닙니다. 세계지도로 이탈을 시도합니다.")
            if find_and_click_grayscale_template(device, img_np, t_open_world, 0.70):
                print("      ✅ 't_open_world' 도장 추적 정밀 타격 성공. (불일치 던전 이탈)")
                last_action_time = time.time()
                time.sleep(2.5)
            else:
                print("      ⚠️ [세계지도 단추 은폐 감지] 뒤로가기(ESC) 입력을 주입해 세계지도로 안전 탈출을 유도합니다.")
                device.shell("input keyevent 4")
                last_action_time = time.time()
                time.sleep(3.0)
            continue

        # 🆕 [2026-09-07 대설지대] 귀환 직후 인벤정리 후처리 - ⚠️ 반드시 아래 "마을외곽 화면 분류"보다
        # 먼저, 그리고 그 화면 앵커에 종속되지 않는 최상위 블록으로 둬야 한다. 소지품 보충 팝업이 열리면
        # 화면 전체를 덮어 "대설 지대" 행이 가려지기 때문(실측: 팝업 화면에서 대설지대 앵커 1.000 → 0.134).
        # 마을외곽 앵커 안에 넣어두면 팝업을 연 순간 이 블록이 더 이상 안 돌아 '보충한다'를 영원히 못 누른다.
        if DUNGEON_NAME == "대설지대" and heavysnow_resupply_pending:
            heavysnow_resupply_attempts += 1
            resupply_handled = True

            if RESUPPLY_MODE == "inn" or heavysnow_force_inn_this_cycle:
                # 🆕 [2026-09-08] 여관 경유: 캠핑이 없어 HP/MP를 여관에 의존하는 던전(교회구역 기본값) 또는
                # inn_visit_loop_interval 조건으로 이번 주회만 강제된 경우.
                # 마을로 돌아가기 -> town square -> 여관(체력회복+아이템정리 동시 처리, inn_manager가
                # 이미 소지품 정리 팝업까지 다 처리해주므로 인벤정리 버튼은 따로 누르지 않는다).
                if check_grayscale_template_present(img_np, t_village, 0.65):
                    print("🏠 [마을외곽 후처리] town square 도착 확인 - 여관 숙박을 실행합니다.")
                    try:
                        inn_manager.run_inn_sleep_sequence(device)
                    except Exception as inn_err:
                        restart_process(f"대설지대 여관 경유 후처리 중 ADB 통신 치명적 예외 발생: {inn_err}")
                    is_fully_healed = True
                    heavysnow_resupply_pending = False
                    heavysnow_resupply_attempts = 0
                    heavysnow_force_inn_this_cycle = False
                elif find_and_click_template(device, img_np, t_back_to_village, 0.70):
                    print("🏠 [마을외곽 후처리] '마을로 돌아가기' 터치 성공.")
                    time.sleep(2.0)
                else:
                    resupply_handled = False
            else:
                # items_only: 인벤정리 버튼만(6층 기본값 - 캠핑으로 이미 회복했을 때)
                # 순서 주의: 팝업이 열려 있으면 그 아래 인벤정리 버튼은 못 누르므로 '보충한다'를 먼저 본다.
                if find_and_click_template(device, img_np, t_inven_cleanup_refill, 0.70):
                    print("🎒 [마을외곽 후처리] '보충한다' 버튼 터치 성공.")
                    time.sleep(1.5)
                elif dungeon_bot.find_and_click_dialogue_advance_arrow(device, img_np, t_arrow_clean):
                    print("🎒 [마을외곽 후처리] 정리 완료 토스트 확인 - 후처리 종료, 재진입을 재개합니다.")
                    heavysnow_resupply_pending = False
                    heavysnow_resupply_attempts = 0
                    time.sleep(1.0)
                elif find_and_click_template(device, img_np, t_inven_cleanup_btn, 0.70):
                    print("🎒 [마을외곽 후처리] 인벤정리 버튼 터치 성공.")
                    time.sleep(1.5)
                else:
                    resupply_handled = False

            # 🚨 후처리가 어떤 이유로든 막히면 주회 자체가 멈추면 안 되므로, 일정 횟수 뒤엔 포기하고
            # 재진입을 계속한다(인벤정리/여관은 실패해도 주회는 계속 도는 게 낫다는 판단).
            if heavysnow_resupply_attempts >= 25:
                print("⚠️ [마을외곽 후처리] 후처리 절차가 25회 시도 내에 끝나지 않아 이번 주회는 건너뜁니다.")
                heavysnow_resupply_pending = False
                heavysnow_resupply_attempts = 0
            if resupply_handled:
                last_action_time = time.time()
                continue
            time.sleep(1.0)
            # 후처리 화면이 아직 아니면(로딩 중 등) 아래 일반 화면분류로 흘려보낸다.

        # 🆕 [2026-09-07 대설지대] 마을외곽 진입 목록 화면("대설 지대"/"마을로 돌아가기" 두 줄)
        if DUNGEON_NAME == "대설지대" and check_template_present(img_np, t_dungeon_heavysnow, 0.80):
            if last_logged_status != "VILLAGE_OUTSKIRTS":
                last_action_time = time.time()
                last_logged_status = "VILLAGE_OUTSKIRTS"
                print("🌲 [마을외곽 도달] 대설지대 진입 목록 화면 확인.")

            if find_and_click_template(device, img_np, t_dungeon_heavysnow, 0.80):
                print("👉 [마을외곽] '대설 지대' 목록 터치 성공.")
                last_action_time = time.time()
                time.sleep(2.0)
            else:
                print("⚠️ [마을외곽] '대설 지대' 목록 매칭 실패. 재스캔 대기...")
                time.sleep(1.0)
            continue

        # 🆕 [2026-09-07 대설지대] 대설지대 내부 경로 목록 화면(경로1~9 + 교회구역 + 돌아간다) - 목표 층
        # 행을 클릭해 진입한다. 화면 구조가 유령성 하켄 귀환목록과 사실상 동일해 dungeon_bot.py 내부의
        # check_and_handle_harken_menu()가 던전 안에서의 귀환 처리를 그대로 담당할 수 있다.
        if DUNGEON_NAME == "대설지대" and check_template_present(img_np, t_heavysnow_floor, 0.80):
            if last_logged_status != "HEAVYSNOW_ROUTE_SEL":
                last_action_time = time.time()
                last_logged_status = "HEAVYSNOW_ROUTE_SEL"
                print(f"🚪 [대설지대 경로선택 도달] '{DUNGEON_FLOOR_NAME}' 경로 목록 확인.")

            should_reenter = (LIMIT_DUNGEON_LOOPS == 0) or (dungeon_run_count < LIMIT_DUNGEON_LOOPS)
            if not should_reenter:
                print("      ⚠️ [주회 한도 도달] 대설지대 재진입을 보류하고 뒤로가기로 마을외곽으로 복귀합니다.")
                device.shell("input keyevent 4")
                last_action_time = time.time()
                time.sleep(2.0)
                continue

            if find_and_click_template(device, img_np, t_heavysnow_floor, 0.80):
                print(f"👉 [대설지대 경로선택] '{DUNGEON_FLOOR_NAME}' 행 터치 성공.")
                print("⏳ [던전 진입 대기] 필드 안착을 최대 10초간 폴링합니다...")
                poll_start = time.time()
                entered = False
                while time.time() - poll_start < 10.0:
                    time.sleep(0.8)
                    try:
                        raw_poll = capture_screen_bytes(device)
                        if raw_poll:
                            img_np_poll = decode_screen_bytes(raw_poll)
                            if check_field_anchor_present(img_np_poll, t_field, 0.65):
                                print(f"      ✅ [던전 진입 확인] 필드 안착 확인 (대기 {time.time()-poll_start:.1f}초)")
                                entered = True
                                break
                    except Exception:
                        pass
                if not entered:
                    print("      ⚠️ [던전 진입 대기 초과] 10초 내 필드 안착 미확인. 일단 진입 시퀀스를 시도합니다.")

                run_skill_logic = ENABLE_FIRST_COMBAT_SKILL and (not global_skill_setup_completed)
                try:
                    exit_by_user, skill_ok, need_pickaxe_result = dungeon_bot.start_main_macro(device, run_skill_logic, HEALING_LOOPS, bool(ENABLE_HEAL_AFTER_CHEST), healer_slot=HEALER_SLOT, masked_adventurer_slot=MASKED_ADVENTURER_SLOT, chest_opener_slot=CHEST_OPENER_SLOT, farming_method=FARMING_METHOD, dungeon_name=DUNGEON_NAME, from_dungeon_select=True, dungeon_floor_name=DUNGEON_FLOOR_NAME, return_method=RETURN_METHOD)
                    if skill_ok: global_skill_setup_completed = True
                    last_action_time = time.time()
                    dungeon_run_count += 1
                    clear_restart_counter()
                    is_fully_healed = False
                    mark_heavysnow_resupply_pending()
                except Exception as bot_err:
                    restart_process(f"대설지대 진입 시퀀스 중 ADB 통신 치명적 예외 발생: {bot_err}")
            else:
                print("⚠️ [대설지대 경로선택] 목표 경로 행 매칭 실패. 재스캔 대기...")
                time.sleep(1.0)
            continue

        if check_grayscale_template_present(img_np, t_world_map, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "WORLDMAP":
                last_action_time = time.time()
                last_logged_status = "WORLDMAP"
                # 💡 [항목4 후속수정] 세계지도에 신규 진입할 때마다 지그재그 탐색을 원점(Step 0)부터 새로 시작하도록 초기화.
                # 이전 방문의 중간 단계(Step 3~7 등)에서 이어가면 실제 화면 위치와 안 맞아 엉뚱한 곳을 스와이프하게 됨.
                # worldmap_last_drag_time도 지금 시각으로 맞춰서, 첫 스와이프 전에 이미 보이는 목표 아이콘을
                # 클릭 시도할 3초의 여유를 먼저 준다.
                worldmap_drag_step = 0
                worldmap_last_drag_time = time.time()

            # 💡 [항목4 후속수정] 광석파밍은 dungeon_run_count가 아니라 need_pickaxe_refill로만 마을행 여부 판단
            if FARMING_METHOD == "광석파밍":
                should_go_town = need_pickaxe_refill
            else:
                should_go_town = (dungeon_run_count >= LIMIT_DUNGEON_LOOPS and not is_fully_healed)

            # 🚨 [2026-09-09 실전 확인] 예전엔 이 스와이프 탐색이 is_ffxi_worldmap(유령성/노던할로우 목표일
            # 때만)로 잠겨 있었다. 그런데 이 스와이프 방향/좌표 자체는 유령성 전용이 아니라 지도 전체를
            # 훑는 범용 패턴이고, 각 스텝의 클릭 대상도 이미 should_go_town 기준 범용으로 짜여 있었다 -
            # "언제 스와이프를 시작할지"만 유령성 전용으로 게이트돼 있었을 뿐. 백아는 세계지도가 열리자마자
            # 아이콘이 바로 보이는 경우가 많아 이 게이트가 없어도 티가 안 났지만, 유령성 던전선택에서
            # 대설지대(이스벨크)로 이탈한 경우처럼 목표 아이콘이 처음부터 화면 밖에 있으면 스와이프 자체가
            # 아예 안 걸려 영원히 같은 자리에서 빈 클릭만 반복했다(실전 로그 2026-09-09 16:20~16:21, 라이브
            # 화면으로 확인: 노던할로우 지역이 보이고 이스벨크/대설지대 아이콘은 화면 밖). 아래 블록 진입
            # 조건을 제거해 모든 목표(유령성/백아/대설지대)가 똑같이 스와이프 탐색을 쓰도록 통일한다.
            # 안전성: 이 블록 자체는 3초 경과 후에만 스와이프하고, 그 아래 클릭 시도는 매 틱 먼저 실행되므로
            # 아이콘이 이미 보이는 기존 케이스(백아 등)는 스와이프 타이머가 돌기 전에 클릭+continue로
            # 빠져나가 기존 동작이 그대로 유지된다.
            # 3초마다 걸레질 지그재그 탐색 단계(worldmap_drag_step)를 가동
            if time.time() - worldmap_last_drag_time > 3.0:
                print(f"🗺️ [세계지도 - 걸레질 탐색] 목표 아이콘 수색 중 (현재 단계: Step {worldmap_drag_step})")
                worldmap_last_drag_time = time.time()
                
                if worldmap_drag_step == 0:
                    print("🗺️ [Step 0] 맵을 좌상단 원점으로 강력히 리셋합니다 (캘리브레이션 2회).")
                    device.shell("input swipe 200 200 1200 2000 300")
                    time.sleep(0.8)
                    device.shell("input swipe 200 200 1200 2000 300")
                    time.sleep(0.8)
                    worldmap_drag_step = 1
                    
                elif worldmap_drag_step == 1:
                    # 💡 [항목3] wvd(900x1600) 좌표를 1.6배 환산 없이 그대로 옮겨써서 이동거리가 이웃 스텝(700~1800px) 대비
                    # 1/7~1/18 수준(100px)이던 결함을 보정. 이웃 스텝과 비슷한 규모(약 600px)로 상향.
                    # 최종 이동량은 실제 구동 화면을 보며 미세조정이 필요할 수 있음.
                    if should_go_town:
                        print("🗺️ [Step 1] 1번 라인 마을 기본 뷰 정밀 드래그(400, 450 ➔ 800, 50) 주입")
                        device.shell("input swipe 400 450 800 50 800")
                    else:
                        print("🗺️ [Step 1] 1번 라인 던전 기본 뷰 정밀 드래그(650, 430 ➔ 50, 1030) 주입")
                        device.shell("input swipe 650 430 50 1030 800")
                    worldmap_drag_step = 2
                    
                elif worldmap_drag_step == 2:
                    print("🗺️ [Step 2] 1번 라인 가로 추가 탐색 (화면 왼쪽으로 쓸기 ➔ 맵 우측 노출)")
                    device.shell("input swipe 1000 1200 300 1200 500")
                    worldmap_drag_step = 3
                    
                elif worldmap_drag_step == 3:
                    print("🗺️ [Step 3] 세로 1단 하강 (세로 1000px 맵 끌어올리기)")
                    device.shell("input swipe 600 1600 600 600 500")
                    worldmap_drag_step = 4
                    
                elif worldmap_drag_step == 4:
                    print("🗺️ [Step 4] 2번 라인 가로 탐색 (화면 오른쪽으로 쓸기 ➔ 맵 좌측 노출)")
                    device.shell("input swipe 300 1200 1000 1200 500")
                    worldmap_drag_step = 5
                    
                elif worldmap_drag_step == 5:
                    print("🗺️ [Step 5] 2번 라인 가로 추가 탐색 (화면 오른쪽으로 쓸기 ➔ 맵 좌측 추가 노출)")
                    device.shell("input swipe 300 1200 1000 1200 500")
                    worldmap_drag_step = 6
                    
                elif worldmap_drag_step == 6:
                    print("🗺️ [Step 6] 세로 2단 하강 (세로 1000px 맵 한 칸 더 끌어올리기)")
                    device.shell("input swipe 600 1600 600 600 500")
                    worldmap_drag_step = 7
                    
                elif worldmap_drag_step == 7:
                    print("🗺️ [Step 7] 3번 라인 가로 탐색 (화면 다시 왼쪽으로 쓸기 ➔ 맵 우측 노출)")
                    device.shell("input swipe 1000 1200 300 1200 500")
                    worldmap_drag_step = 8
                    
                elif worldmap_drag_step == 8:
                    print("🗺️ [Step 8] 수색 한계 도달! 원점(Step 0)으로 캘리브레이션 롤백합니다.")
                    worldmap_drag_step = 0
                
                time.sleep(1.5)
                try:
                    raw_cap_w = capture_screen_bytes(device)
                    if raw_cap_w:
                        img_np = decode_screen_bytes(raw_cap_w)
                except: pass
            
            # 🚨 [2026-09-09 실전 확인] 이 should_go_town 이분법은 "세계지도에 던전 직행 아이콘이 있는"
            # 백아/유령성 기준으로 짜여 있다. 대설지대는 마을경유형(town → 마을외곽 → 던전 목록)이라
            # 세계지도에 직행 아이콘이 아예 없다 - t_go_dungeon이 여기선 백아 전용 Cave_Wolf_btn.png로
            # 잘못 로드되는데(위 "if DUNGEON_NAME == 북쪽의 유령선: ... else: (백아 전용)" 이분법이
            # 대설지대 추가로 깨졌음), 세계지도에 그 아이콘이 있을 리 없어 클릭이 조용히 실패하고 아무
            # 동작 없이 'WORLDMAP 확정'만 30초마다 반복하며 정체했다(실전 로그 2026-09-09 14:21~14:23).
            # 대설지대는 should_go_town 값과 무관하게 항상 마을(이스벨크) 아이콘을 목표로 한다.
            if should_go_town or DUNGEON_NAME == "대설지대":
                if find_and_click_template(device, img_np, t_go_village, 0.70):
                    waiting_for_village_dialogue = True
                    last_action_time = time.time()
                    time.sleep(3.0)
            else:
                if find_and_click_template(device, img_np, t_go_dungeon, 0.70):
                    last_action_time = time.time()
                    time.sleep(3.0)
            continue


        if check_grayscale_template_present(img_np, t_village, 0.65):
            first_stuck_time_str = ""
            if last_logged_status != "VILLAGE":
                last_action_time = time.time()
                last_logged_status = "VILLAGE"
            if waiting_for_village_dialogue:
                waiting_for_village_dialogue = False
                last_action_time = time.time()
            if not is_fully_healed:
                if find_and_click_grayscale_template(device, img_np, t_village, 0.65):
                    print("🏠 [마을] 여관 도장 인식 및 진입 터치 성공.")
                    last_action_time = time.time()
                    time.sleep(2.5)
                else:
                    print("⚠️ [마을] 여관 도장 미검출. 재스캔 대기...")
                    time.sleep(1.0)
            else:
                # 💡 [항목5] 캐릭터창이 펼쳐져 있으면(월드맵 아이콘이 가려짐) 먼저 접기부터 처리
                if check_template_present(img_np, t_char_down, 0.65):
                    print("🔽 [마을] 캐릭터창 펼침 감지! 접기 버튼을 눌러 월드맵 아이콘을 노출시킵니다.")
                    find_and_click_template(device, img_np, t_char_down, 0.65)
                    last_action_time = time.time()
                    time.sleep(1.0)
                # 🆕 [2026-09-07 대설지대] "마을경유형" 진입 - 힐 완료 후에는 월드맵 이탈 대신 마을외곽으로.
                elif DUNGEON_NAME == "대설지대" and find_and_click_grayscale_template(device, img_np, t_go_outside, 0.75):
                    print("🌲 [마을] '마을외곽' 도장 인식 및 터치 성공. 대설지대 진입 목록으로 이동합니다.")
                    last_action_time = time.time()
                    time.sleep(2.0)
                elif find_and_click_grayscale_template(device, img_np, t_worldmap_icon, 0.80):
                    print("🗺️ [마을] 월드맵 아이콘 인식 및 터치 성공. 세계지도로 이탈합니다.")
                    last_action_time = time.time()
                    time.sleep(2.5)
                else:
                    # 도장 매칭 실패 시 안전망 폴백 (기존 고정좌표)
                    print("⚠️ [마을] 월드맵 아이콘 미검출. 고정좌표 폴백 터치를 주입합니다.")
                    target_x = int(width * 0.93)
                    target_y = int(height * 0.93)
                    device.shell(f"input tap {target_x} {target_y}")
                    last_action_time = time.time()
                    time.sleep(2.5)
            continue

        if check_template_present(img_np, t_inn_title, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "INN":
                last_action_time = time.time()
                last_logged_status = "INN"
            try:
                inn_manager.run_inn_sleep_sequence(device)
            except Exception as inn_err:
                restart_process(f"여관 루프 숙박 중 ADB 통신 치명적 예외 발생: {inn_err}")
            is_fully_healed = True
            dungeon_run_count = 0
            need_pickaxe_refill = False
            clear_restart_counter()
            last_action_time = time.time()
            time.sleep(1.0)
            continue

        time.sleep(0.1)

if __name__ == "__main__":
    try:
        start_grand_orchestrator()
    except Exception as err:
        import traceback
        error_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_lines = traceback.format_exception(type(err), err, err.__traceback__)
        err_msg = f"\n💀💀 [🚨 메인 오케스트레이터 치명적 예외 감지 시간: {error_time}] 💀💀\n" + "".join(tb_lines)
        sys.stdout.write(err_msg)
        sys.stdout.flush()
        
        print("🔄 [크래시 복구 가드] 프로그램 종료를 차단하고 10초 대기 후 자가 복구 프로세스를 격발합니다.")
        time.sleep(10.0)
        try:
            restart_process(f"시스템 최상단 크래시 복구 격발: {err}")
        except Exception as rst_err:
            print(f"❌ [복구 프로세스 격발 실패] {rst_err}. 강제 프로세스 전격 재시작을 단행합니다.")
            import os, sys
            os.execv(sys.executable, [sys.executable] + sys.argv)