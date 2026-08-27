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

# 💡 [v1.13.18 신설] 통합 힐링 필요 플래그 및 상자 복귀 감시 전역 변수
# 💡 [v1.17.0] FFXI 콜라보 던전("북쪽의 유령선") 지원, 3채널 BGR 컬러 매칭 수렴 루프 하켄 스턱 완치, 체크포인트 1회 제한 + Redo 연동, 최초 기동 던전 직진입 안전 탈출
need_heal = False
came_from_chest = False

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.17.1-hotfix10
# - 최근 수정일: 2026-08-26
# - 수정 기록:
#   1.17.1-hotfix10: (이 파일 자체는 변경 없음, 버전 동기화용) 유령성 던전선택 '2nd' 층 버튼 미인식 결함 완치.
#     상세는 main.py 참고.
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

def check_dialogue_indicator_present(img_np, template, threshold=0.75):
    if img_np is None or template is None:
        return False
    h, w = img_np.shape[:2]
    if h < 2433 or w < 1377:
        return False
    roi = img_np[2349:2433, 1293:1377]
    return check_template_present(roi, template, threshold)

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
# 'no_chest' | 'none'.
def try_resume_move(device, img_np, t_move_resume_act, t_move_resume_deact, t_no_chest=None):
    resume_coords = find_checkpoint_btn_coords(img_np, t_move_resume_act, t_move_resume_deact, 0.70)
    if not resume_coords:
        return 'not_found'
    rx, ry = resume_coords
    print(f"⏭️ [이동 재개] '재개(1번 Redo)' ({rx}, {ry}) 터치 주입")
    safe_device_shell(device, f"input tap {rx} {ry}")

    time.sleep(0.5)
    prev_mini = None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    for _step in range(2):
        try:
            raw = device.screencap()
            if raw is None: continue
            img_np_sub = np.array(Image.open(io.BytesIO(raw)))
        except Exception:
            continue

        if t_no_chest is not None and check_template_present(img_np_sub, t_no_chest, 0.55):
            return 'no_chest'

        gray_sub = cv2.cvtColor(img_np_sub, cv2.COLOR_RGB2GRAY)
        mini = gray_sub[int(115 * scale_y):int(315 * scale_y), int(1117 * scale_x):int(1317 * scale_x)]
        if prev_mini is not None:
            diff = cv2.absdiff(mini, prev_mini)
            if (np.mean(diff) / 255.0) >= 0.05:
                return 'moved'
        prev_mini = mini
        time.sleep(0.3)

    return 'none'

# 🚨 [2026-08-28 재개 오진 방지 - 사용자 확정 설계] 재개 버튼이 이미 도착한 예전 목적지를 다시 가리켜서
# "없습니다" 토스트가 뜰 수 있다. 이걸 곧바로 던전 나가기 신호로 오인하지 않도록, 상자 버튼(4번)으로 한
# 번 더 확인한 뒤에도 없을 때만 진짜 "상자 없음"으로 판정한다. 반환값: True면 진짜 상자 없음(나가기로
# 전환), False면 정상(다음 FIELD_WAIT 사이클에 맡김).
def resume_or_confirm_chest(device, img_np, t_move_resume_act, t_move_resume_deact,
                             t_move_chest_act, t_move_chest_deact, t_no_chest):
    outcome = try_resume_move(device, img_np, t_move_resume_act, t_move_resume_deact, t_no_chest)
    if outcome != 'no_chest':
        return False

    print("⚠️ [재개 오진 방지] 재개 중 '없습니다' 감지 - 상자 버튼으로 1회 재확인합니다.")
    try:
        raw = device.screencap()
        img_check = np.array(Image.open(io.BytesIO(raw))) if raw else img_np
    except Exception:
        img_check = img_np
    coords = find_chest_btn_coords(img_check, t_move_chest_act, t_move_chest_deact, 0.70)
    if not coords:
        return False
    cx, cy = coords
    safe_device_shell(device, f"input tap {cx} {cy}")
    time.sleep(0.5)
    try:
        raw2 = device.screencap()
        img_check2 = np.array(Image.open(io.BytesIO(raw2))) if raw2 else img_check
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
            raw = device.screencap()
            if raw is None: continue
            img = np.array(Image.open(io.BytesIO(raw)))
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
            raw = device.screencap()
            if not raw:
                return "not_present"
            img_np = np.array(Image.open(io.BytesIO(raw)))
        if not check_template_present(img_np, t_harken_blessing_donothing, 0.70):
            return "not_present"

        # 🚨 [2026-08-16 상자 오판 완치] 상자 대화창("열다" / "아무것도 안 한다")에도 "아무것도 안 한다"가
        # 그대로 있어서, donothing=True & 귀환=False 조건이 성립해 상자 화면을 가호 팝업으로 오판하고 있었음
        # (실전 확인: 2026-08-16 20:26~20:27 2분 사이에만 상자 화면을 찍은 harken 증거 스샷 10장 발생,
        # 실제로는 가호 줄 좌표를 엉뚱하게 탭하고 있었음). 상자 화면에는 "열다"가 같이 있고 가호 팝업에는
        # 없다는 차이로 구분해 차단한다.
        if t_yeolda is not None and check_template_present_multipass(img_np, t_yeolda, 0.65):
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
            raw_h = device.screencap()
            if raw_h:
                img_np_h = np.array(Image.open(io.BytesIO(raw_h)))

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
            raw_verify = device.screencap()
            if raw_verify:
                img_np_v = np.array(Image.open(io.BytesIO(raw_verify)))
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



def start_main_macro(device, run_skill_logic=False, healing_loops=1, heal_after_chest=True, healer_slot=5, masked_adventurer_slot=5, chest_opener_slot=6, farming_method="상자파밍", dungeon_name="일반 던전", from_dungeon_select=False):
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
    
    t_heal_auto = load_template("templates/healer_auto_btn.png")
    t_heal_confirm = load_template("templates/confirm_recover.png")
    t_heal_close = load_template("templates/close_panel.png")

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
    
    # 💡 [반응형 이동 및 즉시 복귀 상태 변수]
    last_target_coords = None
    exit_stuck_count = 0
    exit_prev_minimap = None

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
            raw_cap = device.screencap()
            if raw_cap is None: raise RuntimeError("Screencap returned None")
            img_np = np.array(Image.open(io.BytesIO(raw_cap)))
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
                    need_heal = True
                    low_threshold_active_until = current_time + 60.0
                    if low_threshold_reset_count < 3:
                        last_state_changed_time = current_time  # 정체 타이머 리셋
                        low_threshold_reset_count += 1
                        print(f"🔴 빈사(딸피) 장막 간섭 판정: 완화 모드 리셋 적용 ({low_threshold_reset_count}/3)")
                    else:
                        print("🔴 빈사(딸피) 완화 리셋 한계(3회) 도달! 진성 정체 상태일 가능성이 있으므로 타이머 리셋을 건너뜁니다.")
                    
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
                            state = "FIELD_WAIT"
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
                            state = "FIELD_WAIT"
                            continue
                        state = "FIELD_WAIT"
                else:
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
                            raw_cap = device.screencap()
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
                if not need_heal:
                    danger_px = count_danger_hp_pixels(img_np)
                    if danger_px >= DANGER_HP_PIXEL_LIMIT:
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
                                    last_click_time = 0.0
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
                                raw = device.screencap()
                                if raw:
                                    img_np = np.array(Image.open(io.BytesIO(raw)))
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
                                        raw_mine = device.screencap()
                                        if raw_mine is None: continue
                                        img_np_mine = np.array(Image.open(io.BytesIO(raw_mine)))
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

                    # 이하 기존 상자 파밍 시퀀스
                    if check_field_anchor_present(img_np, t_field, 0.65):
                        coords = find_chest_btn_coords(img_np, t_move_chest_act, t_move_chest_deact, 0.70)
                    if coords:
                        cx, cy = coords
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
                                    raw = device.screencap()
                                    if raw is None: continue
                                    img_np_sub = np.array(Image.open(io.BytesIO(raw)))
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
                            last_click_time = 0.0                 # 🚀 [v1.14.1-hotfix10] 탈출 탭 3초 쿨타임 파쇄

        elif state == "AUTO_MOVING":
            toast_detected = False
            for scan_step in range(5):
                if check_template_present_multipass(img_np, t_yeolda, 0.65): break
                if check_template_present(img_np, t_no_chest, 0.55):
                    toast_detected = True
                    break
                time.sleep(0.3)
                try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
                except: continue

            if toast_detected or state == "TRIGGER_EXIT": 
                state = "TRIGGER_EXIT"
                exit_start_time = time.time()
                prev_minimap_zone = None
                last_click_time = 0
                exit_clicked_once = False
            else:
                if time.time() - last_click_time > 4.0: state = "FIELD_WAIT"

        if state == "TRIGGER_EXIT":
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
            if dungeon_name == "북쪽의 유령선" and farming_method == "상자파밍":
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
                    
                    # 🚨 [v1.14.0-hotfix2] 정지 스택 1~2회차 신속 예비 연타 복구 작동
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
                    auto_off_coords = find_and_get_auto_btn_coords(img_np, t_auto_off, 0.65)
                    if (not run_skill_logic) or (not auto_combat_paused_for_skill):
                        if auto_off_coords:
                            print("⚔️🛡️ [자동전투 비활성화 감지] 자동전투를 활성화하기 위해 터치합니다.")
                            safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}") 
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
                        
                    auto_on_coords = find_and_get_auto_btn_coords(img_np, t_auto_on, 0.65)
                    if auto_on_coords:
                        print("⚔️🛡️ [명함 센서 가동] 안전한 주황 배속 환경에서 '자동 전투'를 일시 중단합니다.")
                        safe_device_shell(device, f"input tap {auto_on_coords[0]} {auto_on_coords[1]}")
                        auto_combat_paused_for_skill = True
                        time.sleep(0.5)
                        continue
                    else: auto_combat_paused_for_skill = True

                # ① 유즈나미키 턴
                if yuzu_sc_coords and not yuzuna_done:
                    print("🔮 [명함 포착] '천자만홍' 단축바 식별 ➔ 유즈나미키 턴 확정!!")
                    safe_device_shell(device, f"input tap {yuzu_sc_coords[0]} {yuzu_sc_coords[1]}")
                    time.sleep(0.7) 
                    
                    try: img_np_pop = np.array(Image.open(io.BytesIO(device.screencap())))
                    except: continue
                    lvl1_gray_coords = find_and_get_coords(img_np_pop, t_btn_lvl1, 0.68)
                    lvl1_atv_coords = find_and_get_coords(img_np_pop, t_btn_lvl1_atv, 0.68)
                    
                    target_lvl1_coords = lvl1_gray_coords if lvl1_gray_coords else lvl1_atv_coords
                    
                    if target_lvl1_coords:
                        print(f"      🎯 [레벨 선택] 도장 식별 성공 -> Lv1 구역 터치 시전! 좌표: {target_lvl1_coords}")
                        safe_device_shell(device, f"input tap {target_lvl1_coords[0]} {target_lvl1_coords[1]}")
                        time.sleep(0.4) 
                        
                        try: img_np_confirm = np.array(Image.open(io.BytesIO(device.screencap())))
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
                    try: img_np_tgt = np.array(Image.open(io.BytesIO(device.screencap())))
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
                    try: img_np_tgt = np.array(Image.open(io.BytesIO(device.screencap())))
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
                state = "FIELD_WAIT"
                time.sleep(3.0)
            else: time.sleep(0.3)

        elif state == "BRANCH_CHECK":
            if chest_opener.is_minigame_screen(img_np, height, width): state = "PLAY_MINIGAME"
            elif check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75): state = "CLEAR_CHECK"
            else: time.sleep(0.2)

        elif state == "PLAY_MINIGAME":
            chest_opener.solve_trap_game(device, img_np)
            try: img_np_post = np.array(Image.open(io.BytesIO(device.screencap())))
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