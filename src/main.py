import sys
import os
import datetime
import time
import json

CURRENT_VERSION = "1.17.1-hotfix7" # 📋 [시스템 버전 변수] 업데이트 시 이 버전 수치만 수정하시면 일괄 동기화됩니다.

# ==============================================================================
# ⚙️ [Daphne 마스터 글로벌 제어 세팅 변수 구역 - 진짜 최상단 제어판]
# ==============================================================================

# 📂 [프리셋 자동 로딩 엔진 - 가장 자주 바꾸는 설정]
# 💡 [프리셋 선택 방법 - 아래 두 줄 중 사용할 프리셋 줄만 남기고, 사용하지 않는 줄의 맨 앞에 # 을 붙여 비활성화하세요]
#   (오타 방지를 위해 프리셋명을 직접 타이핑하지 마시고, 아래 두 줄의 # 위치만 바꿔서 전환하는 걸 권장합니다)

ACTIVE_PRESET_NAME = "유령성 2층 채굴"  # 이 프리셋을 쓰시려면 이 줄은 그대로 두세요 (백아1층을 쓰려면 이 줄 맨 앞에 # 을 붙여 비활성화)
#ACTIVE_PRESET_NAME = "백아1층 파밍"    # 백아1층을 쓰시려면 이 줄 맨 앞의 # 을 지우고, 위 줄 맨 앞에는 # 을 붙여주세요

LIMIT_DUNGEON_LOOPS = 2             # 🔄 [마을 회군 기준] 던전을 몇 바퀴 돌고 마을(여관)로 복귀할지 설정
                                    #    0으로 설정 시 상자파밍은 회군 없이 무한 주회합니다. (광석파밍은 이 값과 무관하게 곡괭이가 소진될 때까지 항상 무한 재진입하므로, 광석파밍 프리셋에서는 이 값이 아무 영향도 없습니다.)
START_RUN_COUNT_OFFSET = 1          # 🚀 [초기 부팅 주회 카운트] 매크로 시작 시 초기 주회 offset 수치 (초기값=던전루프와 같은 수치, 던전에서 시작하면 해당 주회 후 복귀, 마을이면 숙박 후 주회 시작)
ENABLE_FIRST_COMBAT_SKILL = 0       # ⚔️ [초기 전투 스킬 제어] (⚠️ 현재 미구현으로 추후 구현 예정이니 무조건 0으로 고정해 주세요) (0: Off, 1: On)
ENABLE_HEAL_AFTER_CHEST = 0         # 📦 [상자 개방 후 힐링] 상자 해제/개방 성공 후 긴급 파티 치료(정비)를 작동할지 설정 (0: Off, 1: On)
HEALING_LOOPS = 1                   # 💊 [전투 후 정비 주기] 몇 회의 전투마다 파티 힐링 정비를 수행할지 설정
                                    #    - 1: 매 전투 종료 시 필드 복귀 직후 즉시 힐링 시퀀스 실행
                                    #    - 2: 2회 전투 치를 때마다 힐링 시퀀스 실행 (누적 카운트 기준)
                                    #    - 0: 전투 후 자동 힐링 정비 비활성화 (체력 소진 시까지 계속 전투 진행)

# 🏥 [힐러 및 주인공 슬롯 설정]
HEALER_SLOT = 5                         # 💊 [힐러 캐릭터 슬롯 번호] 1번~6번 슬롯 중 주 힐러(스켈톤 등)의 배치 슬롯
MASKED_ADVENTURER_SLOT = 6              # 👤 [주인공 캐릭터 슬롯 번호] 1번~6번 슬롯 중 주인공의 배치 슬롯 (2번 사망 시 주인공이 앞으로 밀릴 수 있음)
CHEST_OPENER_SLOT = 6                   # 🔑 [상자 해제 따개 슬롯] 1번~6번 슬롯 중 상자 따기(함정 해제)를 기본 담당할 캐릭터 슬롯

# 🖥️ [MuMu 에뮬레이터 콜드 리부트 자동 제어 세팅]
ENABLE_EMULATOR_REBOOT = True       # 🔄 [에뮬레이터 리부트] 디바이스 오프라인/5분 정체 지속 시 에뮬레이터 자체를 강제 재시작할지 설정
MUMU_EXECUTABLE_PATH = r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuNxMain.exe"  # 뮤뮤 실행 파일 경로
MUMU_VM_INDEX = "0"                  # 실행할 가상머신 번호 인덱스 (기본값 "0")

# 🚨 [최후 안전망 전용 - 직접 수정 금지] presets.json이 없거나 지정한 프리셋을 못 찾은 극단적 예외 상황에서만 쓰이는 비상 기본값입니다.
# 정상적인 상황에서는 아래 4개 값이 항상 presets.json 내용으로 자동 교체됩니다.
TOWN_NAME = "이스벨크"
DUNGEON_NAME = "백아의 동굴"
DUNGEON_FLOOR_NAME = "백아1층"
FARMING_METHOD = "상자파밍"

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
# - 현재 버전: 1.17.1-hotfix7
# - 최근 수정일: 2026-08-14
# - 수정 기록:
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
                copied_files = set(json.load(f))
            print(f"📸 [스크린샷 동기화] 디스크 캐시에서 기존 복사 이력 {len(copied_files)}건 복원 완료.")
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

def write_pid_file():
    # 💡 [v1.17.1 원격 제어 연동] remote_control/server.py가 이 파일을 읽어 매크로 프로세스를 식별합니다.
    # 모듈 최상단(재시작마다 항상 재실행되는 위치)에 있어서, os.execv 자기재시작 시에도(윈도우는 PID가 바뀌므로)
    # 매번 자동으로 최신 PID로 갱신됩니다. remote_control을 안 쓰면 이 파일은 그냥 무시하셔도 됩니다.
    try:
        pid_path = os.path.join(os.path.dirname(script_dir), "macro.pid")
        with open(pid_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
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

import dungeon_bot
import inn_manager
import chest_opener

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
    
    # 3. 뮤뮤 실행 파일 백그라운드로 실행
    print(f"      ➔ 🚀 MuMu Player를 백그라운드 구동합니다: \"{MUMU_EXECUTABLE_PATH}\" -v {MUMU_VM_INDEX}")
    try:
        import subprocess
        # 백그라운드로 실행하여 파이썬 스레드가 블락되지 않게 처리
        subprocess.Popen([MUMU_EXECUTABLE_PATH, "-v", MUMU_VM_INDEX])
    except Exception as ex_err:
        print(f"❌ [에뮬레이터 실행 실패] {ex_err}")
        
    # 4. ADB 포트 연결 및 대기 루프 (최대 60초)
    print("      ➔ ⏳ 에뮬레이터 부팅 및 ADB 포트 활성화를 대기합니다 (최대 60초)...")
    start_wait = time.time()
    connected = False
    target_ports = ["16384", "16385", "5555"]
    
    while time.time() - start_wait < 60.0:
        for port in target_ports:
            os.system(f"adb connect 127.0.0.1:{port} > nul 2>&1")
        time.sleep(5.0)
        
        try:
            from ppadb.client import Client as AdbClient
            client = AdbClient(host="127.0.0.1", port=5037)
            devices = client.devices()
            valid_device = None
            for d in devices:
                if d.get_state() == "device":
                    valid_device = d
                    break
            if valid_device:
                print(f"      ✅ ADB 연결 수립 완료! 디바이스 부팅 상태: {valid_device.get_state()}")
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
            devices = client.devices()
            valid_device = None
            for d in devices:
                if d.get_state() == "device":
                    valid_device = d
                    break
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
    t_combat_in = load_template("templates/combat_in.png")
    t_combat_slow = load_template("templates/combat_slow.png")
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_error_to_title = load_template("templates/Error_to_title.png")
    
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    t_incombat_dead = load_template("templates/InCombat_dead.png")
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    
    t_inn_title = load_template("templates/inn_sleep/inn_title.png")
    t_world_map = load_grayscale_template("templates/Worldmap/world_map_anchor.png")

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

    while counter < max_try:
        try:
            raw_cap = device.screencap()
            if raw_cap is None:
                time.sleep(0.5)
                continue
            img_np = np.array(Image.open(io.BytesIO(raw_cap)))
        except:
            time.sleep(0.5)
            continue

        # 🖥️ [가로 화면/안드로이드 홈 복구 가드] 에뮬레이터가 가로 상태로 기동된 경우 앱을 실행해 세로 모드 회전을 유도
        height, width = img_np.shape[:2]
        if height < width:
            startup_landscape_fail_counter += 1
            print(f"🖥️ [기동 복구 - 가로 화면 감지] 현재 화면이 가로 상태({width}x{height})입니다. 위저드리 다프네 앱 기동(Relaunch)을 강제 주입하여 세로 화면 전환을 시도합니다. ({startup_landscape_fail_counter}/30)")
            if startup_landscape_fail_counter >= 30:
                print("      🚨 [기동 복구 - 가로화면 탈출 실패] 30회 연속 가로 화면 정체! MuMu 자체 이상으로 판단해 자가 복구 절차로 넘어갑니다.")
                restart_process(f"기동 복구(recover_app_startup) 중 가로 화면 30회 연속 정체 (화면 크기: {width}x{height})")
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
                import dungeon_bot
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
                import dungeon_bot
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
            continue
            
        if check_template_present(img_np, t_re_download, 0.70):
            print("📥 [리소스 다운로드] 다운로드 확인 버튼 감지! 즉시 터치합니다.")
            find_and_click_template(device, img_np, t_re_download, 0.70)
            time.sleep(5.0)
            continue
            
        if check_template_present(img_np, t_re_retry, 0.70):
            print("🌐 [네트워크 재시도] 에러 재시도 버튼 감지! 즉시 터치합니다.")
            find_and_click_template(device, img_np, t_re_retry, 0.70)
            time.sleep(3.0)
            continue

        if check_template_present(img_np, t_title_notice, 0.75):
            print("📢 [공지 가드] 기동 중 공지사항 팝업 포착! '닫기' 단추를 터치합니다.")
            if find_and_click_template(device, img_np, t_title_notice_close, 0.70):
                print("      🎯 'title_notice_close' 앵커 좌표 조준 타격 성공.")
            else:
                device.shell("input tap 540 2360")
            time.sleep(3.0)
            continue

        if check_template_present(img_np, t_title_warning, 0.75):
            print("⚠️ [주의 가드] 게임 최초 기동 '주의' 경고 화면 포착! 구석 터치로 진행을 격발합니다.")
            device.shell("input tap 10 10")
            time.sleep(3.0)
            continue

        if check_template_present(img_np, t_error_to_title, 0.70):
            print("👉 [타이틀 복귀 확인] 'Error_to_title.png' 감지! 즉시 탭합니다.")
            find_and_click_template(device, img_np, t_error_to_title, 0.70)
            time.sleep(3.0)
            continue

        if check_template_present(img_np, t_net_error, 0.75):
            print("🌐 [인게임 통신 에러] 기존 네트워크 에러 감지! 재시도 클릭.")
            net_coords = find_and_get_coords_main(img_np, t_net_retry, 0.70)
            if net_coords: device.shell(f"input tap {net_coords[0]} {net_coords[1]}")
            else: device.shell("input tap 1380 1720")
            time.sleep(4.0)
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
            check_grayscale_template_present(img_np, t_village_anchor, 0.65)):
            print("✨ [앱 기동 복구 성공] 인게임 화면(필드/전투/던전선택/상자/여관/세계지도/마을 등) 진입 성공! 매크로를 복구합니다.")
            return True

        if counter >= 4:
            print(f"💤 [스킵 가드] 로딩/타이틀 정체 감지 ({counter}/{max_try}). [1, 1] 터치를 주입합니다.")
            device.shell("input tap 1 1")
            time.sleep(3.5)
        else:
            time.sleep(2.0)
            
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

    # 조건 A: 연속 2회 이상 재시작 시도 시 즉시 에뮬레이터 콜드 리부트 단행
    if ENABLE_EMULATOR_REBOOT and consecutive_restart_count >= 2:
        print(f"      🚨 [연속 재시작 한계 도달] 재시작 시도가 {consecutive_restart_count}회 연속 격발되었습니다. 에뮬레이터 완전 재시작으로 강제 극복합니다.")
        reboot_emulator()
        clear_restart_counter()
        print("      ➔ 🚀 파이썬 프로세스를 전격 재시작합니다.")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    # 일반 자가 복구 전개 (카운트 1회차인 경우)
    print("      ➔ 🛠️ 윈도우 ADB 서버 리셋 후 연결 재수립을 개시합니다...")
    os.system("adb kill-server")
    time.sleep(1.0)
    os.system("adb start-server")
    os.system("adb connect 127.0.0.1:16384")
    os.system("adb connect 127.0.0.1:16385")
    os.system("adb connect 127.0.0.1:5555")
    time.sleep(4.0)
    
    # 디바이스 온라인 상태 검증
    device_online = False
    device = None
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device = client.device("127.0.0.1:5555")
        if not device: device = client.device("127.0.0.1:16384")
        if not device: device = client.device("127.0.0.1:16385")
        if device and device.get_state() == "device":
            device_online = True
    except:
        pass
        
    # 조건 B: ADB 연결을 뚫었음에도 디바이스가 존재하지 않거나 오프라인인 경우 즉각 리부트
    if ENABLE_EMULATOR_REBOOT and not device_online:
        print("      🚨 [디바이스 오프라인 감지] ADB 연결 수립 결과 디바이스가 오프라인이거나 감지되지 않습니다. 즉시 에뮬레이터 콜드 리부트를 수행합니다.")
        reboot_emulator()
        clear_restart_counter()
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
    print("🚀 [ADB 메인 연결] 사령탑 시스템 가동... 3중 포트 자동 스위칭 터널을 개설합니다.")
    os.system("adb start-server")
    os.system("adb connect 127.0.0.1:16384")
    os.system("adb connect 127.0.0.1:16385")
    os.system("adb connect 127.0.0.1:5555")
    time.sleep(1.0)
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        device = client.device("127.0.0.1:5555")
        if not device: device = client.device("127.0.0.1:16384")
        if not device: device = client.device("127.0.0.1:16385")
        if device:
            print("✅ [ADB 메인 연결 성공] 하이브리드 자동 포트 제어 레이더 가동 완료.")
            global_device = device
            return device
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
    if template is None or img_np is None: return 0.0
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return 0.0
    crop = img_np[y1:y2, x1:x2]
    return get_match_score(crop, template)

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
        t_go_village = load_template("templates/Worldmap/Vill_isbelk_btn.png")

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

    # 🚨 [2026-08-18 하켄 메뉴 시작 인식 결함 완치] 매크로를 하켄 메뉴(귀환목록/가호팝업)가 떠 있는 상태에서
    # (재)시작하면, 아래 스캐너가 마을/세계지도/던전선택/여관/필드/상자 등 알려진 앵커 어느 것과도 안 맞아
    # "아웃게임 무반응 정체"만 무한 반복하며 아무 행동도 못 하던 실전 결함 확인(2026-08-18 01:16~, 5분 절대
    # 워치독이 걸릴 때까지 방치됨). dungeon_bot.py가 이미 갖고 있는 하켄 메뉴 판정 함수를 그대로 재사용한다.
    t_harken_blessing_donothing = dungeon_bot.load_grayscale_template("templates/Field/harken_blessing_donothing.png")
    t_harken_return = dungeon_bot.load_color_template("templates/FFXI/harken_return.png")

    t_field = load_grayscale_template("templates/Field/field_anchor.png")
    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_get_item = load_template("templates/chestopening/get_item.png")
    t_app_exit = load_template("templates/app_exit.png")
    
    t_heal_close = load_template("templates/close_panel.png") 
    t_combat_in = load_template("templates/combat_in.png")
    t_combat_slow = load_template("templates/combat_slow.png") 
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
            raw_cap = device.screencap()
            if raw_cap is None:
                raise RuntimeError("Screencap returned None")
            cap_img = Image.open(io.BytesIO(raw_cap))
            img_np = np.array(cap_img)
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
            print(f"🖥️ [가로 화면 감지] 현재 화면이 가로 상태({width}x{height})입니다. 위저드리 다프네 앱 기동(Relaunch)을 강제 주입하여 세로 화면 전환을 시도합니다. ({resolution_fail_counter}/30)")
            if resolution_fail_counter >= 30:
                restart_process(f"main 내 가로 화면 정체 30초 지속 감지 (화면 크기: {width}x{height})")
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
                    exit_by_user, skill_ok, need_pickaxe_result = dungeon_bot.start_main_macro(device, run_skill_logic, HEALING_LOOPS, bool(ENABLE_HEAL_AFTER_CHEST), healer_slot=HEALER_SLOT, masked_adventurer_slot=MASKED_ADVENTURER_SLOT, chest_opener_slot=CHEST_OPENER_SLOT, farming_method=FARMING_METHOD, dungeon_name=DUNGEON_NAME, from_dungeon_select=False)
                    if FARMING_METHOD == "광석파밍":
                        need_pickaxe_refill = need_pickaxe_result
                    if skill_ok:
                        global_skill_setup_completed = True  
                    if exit_by_user: 
                        last_action_time = time.time() - 20.0 
                    else: 
                        last_action_time = time.time()
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
                    print(f"📋 [던전선택 - FFXI] '{DUNGEON_FLOOR_NAME}' 층 버튼 도장 정밀 조준을 시도합니다.")
                    if find_and_click_template(device, img_np, t_enter_dungeon, 0.88):
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
                            raw_poll = device.screencap()
                            if raw_poll:
                                img_np_poll = np.array(Image.open(io.BytesIO(raw_poll)))
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
                        exit_by_user, skill_ok, need_pickaxe_result = dungeon_bot.start_main_macro(device, run_skill_logic, HEALING_LOOPS, bool(ENABLE_HEAL_AFTER_CHEST), healer_slot=HEALER_SLOT, masked_adventurer_slot=MASKED_ADVENTURER_SLOT, chest_opener_slot=CHEST_OPENER_SLOT, farming_method=FARMING_METHOD, dungeon_name=DUNGEON_NAME, from_dungeon_select=True)
                        if skill_ok: global_skill_setup_completed = True
                        if exit_by_user: last_action_time = time.time() - 20.0
                        else: last_action_time = time.time()
                        if FARMING_METHOD == "광석파밍":
                            need_pickaxe_refill = need_pickaxe_result
                        else:
                            dungeon_run_count += 1
                        clear_restart_counter()
                        is_fully_healed = False
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

            is_ffxi_worldmap = (TOWN_NAME == "노던할로우" if should_go_town else DUNGEON_NAME == "북쪽의 유령선")
            
            if is_ffxi_worldmap:
                # 3초마다 걸레질 지그재그 탐색 단계(worldmap_drag_step)를 가동
                if time.time() - worldmap_last_drag_time > 3.0:
                    print(f"🗺️ [세계지도 - 걸레질 탐색] FFXI 타겟 수색 중 (현재 단계: Step {worldmap_drag_step})")
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
                        raw_cap_w = device.screencap()
                        if raw_cap_w:
                            img_np = np.array(Image.open(io.BytesIO(raw_cap_w)))
                    except: pass
            
            if should_go_town:
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