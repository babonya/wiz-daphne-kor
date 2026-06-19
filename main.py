import sys
import os
import datetime

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 18.11.1 (Stable)
# - 최근 수정일: 2026-06-17 10:15
# - 수정 기록:
#   v18.00: 3시간 전 안정 버전 기반 롤백 (Base)
#   v18.01: 뇌절 좌표 회피용 안전 스팟 수정 (950, 1900 -> 713, 273)
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
# ==============================================================================

# ==============================================================================
# ⚙️ [KONURI 마스터 글로벌 제어 세팅 변수 구역 - 진짜 최상단 제어판]
# ==============================================================================
# 💡 앞으로 주행 설정을 바꾸실 때는 오직 여기 "최상단 마디 1"의 숫자만 수정하시면 됩니다!
LIMIT_DUNGEON_LOOPS = 2             # 🔄 [마을 회군 기준] 던전을 몇 바퀴 돌지 설정
START_RUN_COUNT_OFFSET = 2          # 🚀 [초기 부팅 주회 카운트] 
ENABLE_FIRST_COMBAT_SKILL = False   # ⚔️ [초기 전투 스킬 제어 스위치] True=수동예약 / False=일반자동
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
            self.log.flush() # 시스템 팅김 발생 시에도 실시간 강제 저장 보장

    def flush(self):
        self.terminal.flush()
        if self.log:
            self.log.flush()

def init_main_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
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
def print_konuri_global_settings():
    print("====================================================")
    print("⚙️ [KONURI 마스터 글로벌 제어 세팅 변수 구역 - 최상단 제어판 연동 완료]")
    print(f" -> 목표 주회 설정 수치: {LIMIT_DUNGEON_LOOPS}회 안전 고정")
    print(f" -> 숏컷기반 스킬 예약 시스템 가동 여부: {ENABLE_FIRST_COMBAT_SKILL}")
    print("====================================================")

print_konuri_global_settings()

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
    sys.stdout.terminal.write(f"\n💀💀 [🚨 시스템 치명적 크래시 발생 시간: {error_time}] 💀💀\n")
    sys.stdout.terminal.flush()
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

def restart_process(reason):
    print(f"\n🔄 [프로세스 자가 복구 가동] 사유: {reason}")
    print("      ➔ 🛠️ 윈도우 ADB 서버 리셋 후 5초 뒤 파이썬 프로세스를 전격 재시작합니다.")
    os.system("adb kill-server")
    time.sleep(1.0)
    os.system("adb start-server")
    time.sleep(4.0)
    os.execv(sys.executable, [sys.executable] + sys.argv)

def connect_mumu():
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
    if thresh_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def get_match_score(img_np, thresh_temp):
    if thresh_temp is None: return 0.0
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def find_and_get_coords_main(img_np, thresh_temp, threshold_val=0.68):
    if thresh_temp is None: return None
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def find_and_click_template(device, img_np, thresh_temp, threshold_val=0.70):
    if thresh_temp is None: return False
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
    print("=======================================")

    dungeon_run_count = START_RUN_COUNT_OFFSET  
    is_fully_healed = False 
    waiting_for_village_dialogue = False 

    force_first_analysis = True
    last_action_time = time.time()
    last_logged_status = ""
    first_stuck_time_str = ""
    global_skill_setup_completed = False

    # 🛑 [KONURI 마스터 섀도우 통화면 동결 감지 엔진 변수]
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
        current_time = time.time()

        # ======================================================================
        # 👑 [KONURI 완성형 엔진: 1분 30초 전체 화면 동결 시 인지 복구 레이더 강제 부팅]
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
        
        if t_arrow_clean is not None:
            gray_zone = cv2.cvtColor(dialogue_zone, cv2.COLOR_RGB2GRAY)
            _, thresh_zone = cv2.threshold(gray_zone, 160, 255, cv2.THRESH_BINARY)
            result_arrow = cv2.matchTemplate(thresh_zone, t_arrow_clean, cv2.TM_CCOEFF_NORMED)
            _, score_arrow_clean, _, arrow_loc = cv2.minMaxLoc(result_arrow)
            
            if score_arrow_clean > 0.70:
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
                    inn_manager.run_inn_sleep_sequence(device)
                    is_fully_healed = True
                    dungeon_run_count = 0
                
                last_action_time = time.time()
                continue

            if is_mini_screen or score_loot > 0.65 or score_field > 0.60 or score_yeolda > 0.65 or score_heal_close > 0.65 or score_combat > 0.80:
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
            inn_manager.run_inn_sleep_sequence(device)
            is_fully_healed = True  
            dungeon_run_count = 0   
            last_action_time = time.time()
            time.sleep(1.0)
            continue

        time.sleep(0.1)

if __name__ == "__main__":
    start_grand_orchestrator()