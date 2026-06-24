import sys
import os
import datetime
import time

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.11.8 (Stable)
# - 최근 수정일: 2026-06-24 17:10
# - 수정 기록:
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
# ==============================================================================

# ==============================================================================
# ⚙️ [Daphne 마스터 글로벌 제어 세팅 변수 구역 - 진짜 최상단 제어판]
# ==============================================================================
# 💡 앞으로 주행 설정을 바꾸실 때는 오직 여기 "최상단 마디 1"의 숫자만 수정하시면 됩니다!
LIMIT_DUNGEON_LOOPS = 2             # 🔄 [마을 회군 기준] 던전을 몇 바퀴 돌지 설정
START_RUN_COUNT_OFFSET = 2          # 🚀 [초기 부팅 주회 카운트] 
ENABLE_FIRST_COMBAT_SKILL = False   # ⚔️ [초기 전투 스킬 제어] (⚠️ 현재 미구현으로 추후 구현 예정이니 무조건 False로 고정해 주세요)
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
    from datetime import datetime as dt_class
    
    screenshot_dir = find_screenshot_dir()
    if not screenshot_dir:
        print("⚠️ [스크린샷 동기화] 뮤뮤 스크린샷 폴더(기본/원드라이브 문서 후보군)를 찾지 못해 동기화 기능이 비활성화됩니다.")
        return
        
    print(f"📸 [스크린샷 동기화] 백그라운드 동기화 감시 스레드 기동 완료 (경로: {screenshot_dir}, 주기: 30초)")
    
    copied_files = set()
    
    while True:
        try:
            if os.path.exists(screenshot_dir):
                for item in os.listdir(screenshot_dir):
                    item_path = os.path.join(screenshot_dir, item)
                    if os.path.isfile(item_path) and item.lower().endswith(('.png', '.jpg', '.jpeg')):
                        mtime = os.path.getmtime(item_path)
                        if mtime >= session_start_ts and item_path not in copied_files:
                            dt_shot = dt_class.fromtimestamp(mtime)
                            time_str = dt_shot.strftime("%Y-%m-%d-%H%M%S")
                            
                            _, ext = os.path.splitext(item.lower())
                            clean_name = f"{time_str}_Screenshot{ext}"
                            dst_path = os.path.join(log_dir, clean_name)
                            
                            shutil.copy(item_path, dst_path)
                            copied_files.add(item_path)
                            print(f"📸 [스크린샷 동기화] 새 스크린샷이 감지되어 로그 폴더로 카피되었습니다: {clean_name}")
        except Exception:
            pass
        time.sleep(30)

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

    now = datetime.datetime.now()
    base_name = now.strftime("%Y-%m-%d-%H%M")
    
    sequence_num = 0
    while True:
        log_filename = os.path.join(log_dir, f"{base_name}-{sequence_num:03d}.txt")
        if not os.path.exists(log_filename):
            break
        sequence_num += 1
        
    sys.stdout = DoubleWriter(log_filename)
    print(f"🚀 [사령탑 로그 엔진 가동] 초기 부팅부터 모든 대순환 루프 기록이 동시 백업됩니다: {log_filename}")
    
    # [스크린샷 동기화 스레드 시작]
    try:
        import threading
        session_start_ts = get_session_start_time()
        threading.Thread(
            target=sync_screenshots_loop, 
            args=(session_start_ts, log_dir), 
            daemon=True
        ).start()
    except Exception as thread_err:
        print(f"⚠️ [스크린샷 동기화 스레드 기동 실패] {thread_err}")

def timestamped_print(*args, **kwargs):
    current_time = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    sys.stdout.terminal.write(f"{current_time} ")
    msg = " ".join(map(str, args)) + kwargs.get('end', '\n')
    sys.stdout.terminal.write(msg)
    if sys.stdout.log:
        sys.stdout.log.write(f"{current_time} {msg}")
        sys.stdout.log.flush()

init_main_logger()
print = timestamped_print

# ==============================================================================
# 🔄 [마디 3] 로그 가드 인쇄 영역 (평생 건드릴 필요 없는 고정 파이프라인)
# ==============================================================================
def print_daphne_global_settings():
    print("====================================================")
    print("⚙️ [Daphne 마스터 글로벌 제어 세팅 변수 구역 - 최상단 제어판 연동 완료]")
    print(f" -> 목표 주회 설정 수치: {LIMIT_DUNGEON_LOOPS}회 안전 고정")
    print(f" -> 숏컷기반 스킬 예약 시스템 가동 여부: {ENABLE_FIRST_COMBAT_SKILL}")
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

global_device = None

def restart_process(reason):
    print(f"\n🔄 [프로세스 자가 복구 가동] 사유: {reason}")
    
    # 📸 [재시작 직전 자동 스샷] 오류 발생 시점의 화면 스냅샷 촬영
    global global_device
    if global_device:
        try:
            print("📸 [자가 복구 스크린샷] 리셋 직전 에뮬레이터 화면 캡처 F9 신호를 전송합니다.")
            global_device.shell("input keyevent KEYCODE_F9")
            time.sleep(1.5) # 에뮬레이터가 스샷 파일을 디스크에 다 쓸 때까지 1.5초 대기 마진
        except Exception as f9_err:
            print(f"⚠️ [자가 복구 스샷 실패] {f9_err}")
            
    print("      ➔ 🛠️ 윈도우 ADB 서버 리셋 후 5초 뒤 파이썬 프로세스를 전격 재시작합니다.")
    os.system("adb kill-server")
    time.sleep(1.0)
    os.system("adb start-server")
    time.sleep(4.0)
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

def start_grand_orchestrator():
    device = connect_mumu()
    if not device: return
    
    # 📸 [초기 구동 스샷 자동화] 수동 시작 시점의 화면 스크린샷 촬영
    try:
        print("📸 [초기 구동 스크린샷] 시작 화면 캡처 F9 신호를 에뮬레이터에 전송합니다.")
        device.shell("input keyevent KEYCODE_F9")
    except Exception as f9_err:
        print(f"⚠️ [초기 구동 스샷 실패] {f9_err}")

    print("\n=======================================")
    print("🎨 [마스터 마스킹] 대순환 루프 전용 모든 코어 도장들을 로드합니다...")
    t_village = load_template("templates/village_anchor.png")
    t_world_map = load_template("templates/world_map_anchor.png")
    t_dungeon_sel = load_template("templates/dungeon_select_anchor.png")
    t_inn_title = load_template("templates/inn_title.png")
    
    t_enter_dungeon = load_template("templates/enter_dungeon_btn.png")
    t_open_world = load_template("templates/open_world_map_btn.png")
    t_go_village = load_template("templates/go_to_village_btn.png")
    t_go_dungeon = load_template("templates/go_to_dungeon_btn.png")
    t_village_to_inn = load_template("templates/village_to_inn_btn.png")
    
    t_field = load_template("templates/field_anchor.png")
    t_yeolda = load_template("templates/yeolda_clean.png")
    t_get_item = load_template("templates/get_item.png")
    
    t_heal_close = load_template("templates/close_panel.png") 
    t_combat_in = load_template("templates/combat_in.png")
    t_combat_slow = load_template("templates/combat_slow.png") 
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    t_cha_anchor = load_template("templates/cha_panel_anchor.png")
    
    t_popup_levelup = load_template("templates/popup_levelup_title.png") 
    t_popup_skill = load_template("templates/popup_skill_title.png")     
    t_skillget_anchor = load_template("templates/skillget_anchor.png")   
    
    t_lvl_next = load_template("templates/levelup_next_btn.png")   
    t_lvl_close = load_template("templates/levelup_close_btn.png") 
    t_skill_close_btn = load_template("templates/skill_close_btn.png")
    
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_arrow_clean = load_template("templates/arrow_clean.png")
    t_passport_anchor = load_template("templates/anchor_passport_popup.png")
    t_passport_close = load_template("templates/close_passport_popup.png")
    t_disarmer_templates = chest_opener.load_multiple_templates("templates", "disarmer_")
    print("=======================================")

    dungeon_run_count = START_RUN_COUNT_OFFSET  
    is_fully_healed = False 
    waiting_for_village_dialogue = False 

    force_first_analysis = True
    last_action_time = time.time()
    last_logged_status = ""
    first_stuck_time_str = ""
    global_skill_setup_completed = False

    # 🛑 [Daphne 마스터 섀도우 통화면 동결 감지 엔진 변수]
    last_full_screen_shadow = None
    last_freeze_check_time = time.time()

    print("\n====================================================")
    print("위저드리 다프네 [그랜드 마스터 순환 컨트롤러 v17.45 통판동결파쇄판] 가동")
    print(f" -> 목표 주회 설정 수치: {LIMIT_DUNGEON_LOOPS}회 안전 고정")
    print(f" -> 숏컷기반 스킬 예약 시스템 가동 여부: {ENABLE_FIRST_COMBAT_SKILL}")
    print("====================================================")

    cap_fail_counter = 0
    while True:
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
        if height < 2560 or width < 1440:
            print(f"⚠️ [main 해상도 미달 가드] 현재 화면 크기({width}x{height})가 기준 해상도(1440x2560) 미만입니다. 1.0초 대기합니다.")
            time.sleep(1.0)
            continue

        mean_brightness = np.mean(img_np)
        if mean_brightness < 5.0:
            print("⏳ [로딩 가드] 화면 전환/로딩 중(암전) 포착! 0.5초 대기 후 재스캔합니다.")
            time.sleep(0.5)
            continue

        current_time = time.time()

        # ======================================================================
        # 👑 [Daphne 완성형 엔진: 1분 30초 전체 화면 동결 시 인지 복구 레이더 강제 부팅]
        # ======================================================================
        if current_time - last_freeze_check_time > 90.0:
            current_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            current_shadow = cv2.resize(current_gray, (int(width/4), int(height/4)))
            
            if last_full_screen_shadow is not None:
                frame_diff = cv2.absdiff(current_shadow, last_full_screen_shadow)
                pixel_alteration = np.count_nonzero(frame_diff > 30)
                
                if pixel_alteration < 200:
                    if not first_stuck_time_str:
                        first_stuck_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n🚨💀 [사령탑 통화면 동결 감지!!] 1분 30초간 프레임 변화 없음 (동결 판정).")
                    print(f"      -> 최초 정체 유발 시각: {first_stuck_time_str} / 미세 변동률: {pixel_alteration} px")
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
                    
            last_full_screen_shadow = current_shadow
            last_freeze_check_time = current_time
        # ======================================================================

        # ======================================================================
        # 👑 [대화창 저격 구역 - 극하단 대화 전용 스팟 완벽 격리 가드]
        # ======================================================================
        dialogue_zone = img_np[2200:2560, 1100:1440]
        
        # 📦 [상자 조우 예외 가드] 화면에 '열다'가 감지되는 경우 대화창 저격을 하지 않고 건너뜁니다.
        is_box_menu_present = check_template_present(img_np, t_yeolda, 0.65)
        
        # [차원 안전 가드] dialogue_zone의 크기가 t_arrow_clean 템플릿 크기보다 작은 경우 매칭 생략
        has_dialogue_size_ok = True
        if t_arrow_clean is not None:
            hz, wz = dialogue_zone.shape[:2]
            ha, wa = t_arrow_clean.shape[:2]
            if hz < ha or wz < wa:
                has_dialogue_size_ok = False
        
        if t_arrow_clean is not None and not is_box_menu_present and has_dialogue_size_ok:
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
                if not first_stuck_time_str:
                    first_stuck_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n⚠️ [🚨 사령탑 블랙박스 경고] 아웃게임 상태 무반응 정체 중... (최초 정체 발생 시각: {first_stuck_time_str})")
                
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
            
            score_village = get_match_score(img_np, t_village)
            score_world = get_match_score(img_np, t_world_map)
            score_dung_sel = get_match_score(img_np, t_dungeon_sel)
            score_inn = get_match_score(img_np, t_inn_title)
            
            score_field = get_match_score(img_np, t_field)
            score_yeolda = get_match_score(img_np, t_yeolda)
            score_loot = get_match_score(img_np, t_get_item)
            score_heal_close = get_match_score(img_np, t_heal_close)
            
            score_combat_in = get_match_score(img_np, t_combat_in)
            score_combat_slow = get_match_score(img_np, t_combat_slow)
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
                print(f"   ➔ 🏠 [엔진 최종 판정] 리얼 아웃게임 스팟 안착 확인: '{best_status}' 구역으로 확정합니다. (신뢰도: {scores[best_status]:.2f})")
                first_stuck_time_str = "" 
                global_skill_setup_completed = False
                
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
                
                last_action_time = time.time()
                continue

            # 👤 [따개 강제 검출 가드] 캐릭터 선택창("누가 열 거야?")이 이미 열려 있는 경우 던전 판정 보정
            has_disarmer_visible = False
            if len(t_disarmer_templates) > 0:
                for file_name, thresh_disarmer in t_disarmer_templates:
                    coords = chest_opener.find_template_coords(img_np, thresh_disarmer, 0.75)
                    if coords:
                        has_disarmer_visible = True
                        print(f"   ➔ 👤 [사령탑 캐릭터 감지] '{file_name}' 캐릭터 따개 도장 검출로 던전 진입 판정 보정!")
                        break

            if is_mini_screen or score_loot > 0.65 or score_field > 0.60 or score_yeolda > 0.65 or score_heal_close > 0.65 or score_combat > 0.80 or has_disarmer_visible:
                print(f"   ➔ 🤖 [엔진 최종 판정] 아웃게임 부재 및 던전 조건 충족, '던전 내부' 상태로 확정합니다.")
                last_action_time = time.time()
                
                run_skill_logic = ENABLE_FIRST_COMBAT_SKILL and (not global_skill_setup_completed)
                try:
                    exit_by_user, skill_ok = dungeon_bot.start_main_macro(device, run_skill_logic)
                    if skill_ok:
                        global_skill_setup_completed = True  
                    if exit_by_user: last_action_time = time.time() + 30.0 
                except Exception as bot_err:
                    restart_process(f"던전 내부 동작 중 ADB 통신 치명적 예외 발생: {bot_err}")
                continue
            else:
                close_coords_main = find_and_get_coords_main(img_np, t_heal_close, 0.70)
                if close_coords_main:
                    device.shell(f"input tap {close_coords_main[0]} {close_coords_main[1]}")
                else:
                    mag_coords_main = find_and_get_coords_main(img_np, t_exit_mag, 0.70)
                    if mag_coords_main: device.shell(f"input tap {mag_coords_main[0]} {mag_coords_main[1]}")
                    else: device.shell("input tap 713 273")
                time.sleep(2.0)

            last_action_time = time.time()
            continue

        if check_template_present(img_np, t_dungeon_sel, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "DUNGEON_SEL":
                last_action_time = time.time()
                last_logged_status = "DUNGEON_SEL"
            if dungeon_run_count < LIMIT_DUNGEON_LOOPS:
                print(f"📋 [던전선택] 현재 주회 카운트 ({dungeon_run_count}/{LIMIT_DUNGEON_LOOPS}). 지하 1층으로 진입합니다.")
                if find_and_click_template(device, img_np, t_enter_dungeon, 0.70):
                    time.sleep(5.0)
                    run_skill_logic = ENABLE_FIRST_COMBAT_SKILL and (not global_skill_setup_completed)
                    try:
                        exit_by_user, skill_ok = dungeon_bot.start_main_macro(device, run_skill_logic)
                        if skill_ok: global_skill_setup_completed = True
                        if exit_by_user: last_action_time = time.time() + 30.0
                        else: last_action_time = time.time() 
                        dungeon_run_count += 1
                        is_fully_healed = False 
                    except Exception as bot_err:
                        restart_process(f"던전 진입 시퀀스 중 ADB 통신 치명적 예외 발생: {bot_err}")
            else:
                if find_and_click_template(device, img_np, t_open_world, 0.70):
                    print("      ✅ 't_open_world' 도장 추적 정밀 타격 성공.")
                    last_action_time = time.time()
                    time.sleep(2.5)
                else:
                    print("      ⚠️ [세계지도 단추 은폐 감지] 알림 레이어 방해 포착! '세계지도를 연다' 텍스트 바 중앙(720, 1160) 강제 파쇄 점사!!")
                    device.shell("input tap 720 1160")
                    last_action_time = time.time()
                    time.sleep(3.0)
            continue

        if check_template_present(img_np, t_world_map, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "WORLDMAP":
                last_action_time = time.time()
                last_logged_status = "WORLDMAP"
            if dungeon_run_count >= LIMIT_DUNGEON_LOOPS and not is_fully_healed:
                if find_and_click_template(device, img_np, t_go_village, 0.70):
                    waiting_for_village_dialogue = True
                    last_action_time = time.time()
                    time.sleep(3.0)
            else:
                if find_and_click_template(device, img_np, t_go_dungeon, 0.70):
                    last_action_time = time.time()
                    time.sleep(3.0)
            continue

        if check_template_present(img_np, t_village, 0.83):
            first_stuck_time_str = ""
            if last_logged_status != "VILLAGE":
                last_action_time = time.time()
                last_logged_status = "VILLAGE"
            if waiting_for_village_dialogue:
                waiting_for_village_dialogue = False
                last_action_time = time.time()
            if not is_fully_healed:
                if find_and_click_template(device, img_np, t_village_to_inn, 0.70):
                    last_action_time = time.time()
                    time.sleep(2.5)
                else: time.sleep(1.0)
            else:
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
        raise err