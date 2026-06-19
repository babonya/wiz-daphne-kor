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

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 18.11.1 (Stable)
# - 최근 수정일: 2026-06-17 10:15
# - 수정 기록:
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
# ==============================================================================

# ==============================================================================
# 🕒 [KONURI 던전봇 실시간 타임스탬프 미러링 필터 가드 전격 장착]
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
# ⚙️ [KONURI 마스터 인게임 제어 세팅 변수 구역]
# ==============================================================================
LIMIT_COMBAT_EVENTS = 2      
# ==============================================================================

# 🌐 [KONURI 특허: ADB 통신 거부 WinError 10061 원천 차단 심폐소생 장치 - 예외 전파 사양]
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
            safe_device_shell(device, f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
            return True
        return False
    except: return False

def check_template_present_dynamic(img_np, thresh_temp, threshold_val=0.68, min_brightness_thresh=160):
    if thresh_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, min_brightness_thresh, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_template_present(img_np, thresh_temp, threshold_val=0.68):
    return check_template_present_dynamic(img_np, thresh_temp, threshold_val, 160)

def find_and_get_coords_dynamic(img_np, thresh_temp, threshold_val=0.68, min_brightness_thresh=160):
    if thresh_temp is None: return None
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

def find_chest_button_coords(img_np, template, threshold=0.70):
    """
    우측 상단 2x2 격자의 4번째 단추(상자이동) 영역(X: 1250~1440, Y: 530~630)만 잘라내어 매칭을 수행합니다.
    이를 통해 1번, 2번, 3번 단추와의 오검출을 100% 차단합니다.
    """
    if template is None: return None
    h, w = img_np.shape[:2]
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 4번째 단추 Bounding Box (원본 해상도 기준 X: 1250~1440, Y: 530~630)
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(530 * scale_y), int(630 * scale_y)
    
    crop = img_np[y1:y2, x1:x2]
    coords = find_and_get_coords(crop, template, threshold)
    if coords:
        # 크롭 영역 상대 좌표를 전체 화면 좌표로 복원
        return x1 + coords[0], y1 + coords[1]
    return None

def find_exit_button_coords(img_np, template, threshold=0.70):
    """
    우측 상단 2x2 격자의 2번째 단추(출구이동/탈출) 영역(X: 1250~1440, Y: 410~520)만 잘라내어 매칭을 수행합니다.
    이를 통해 X축이 다른 1번(속도), Y축이 다른 3번, 4번 단추와의 오검출을 100% 차단합니다.
    """
    if template is None: return None
    h, w = img_np.shape[:2]
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 2번째 단추 Bounding Box (원본 해상도 기준 X: 1250~1440, Y: 410~520)
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(410 * scale_y), int(520 * scale_y)
    
    crop = img_np[y1:y2, x1:x2]
    coords = find_and_get_coords(crop, template, threshold)
    if coords:
        # 크롭 영역 상대 좌표를 전체 화면 좌표로 복원
        return x1 + coords[0], y1 + coords[1]
    return None

def find_checkpoint_button_coords(img_np, template, threshold=0.70):
    """
    우측 상단 2x2 격자의 3번째 단추(체크포인트) 영역(X: 1150~1280, Y: 530~630)만 잘라내어 매칭을 수행합니다.
    이를 통해 위에 붙은 1번(속도), 우측의 4번(상자) 단추와의 오검출을 100% 차단합니다.
    """
    if template is None: return None
    h, w = img_np.shape[:2]
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 3번째 단추 Bounding Box (원본 해상도 기준 X: 1150~1280, Y: 530~630)
    x1, x2 = int(1150 * scale_x), int(1280 * scale_x)
    y1, y2 = int(530 * scale_y), int(630 * scale_y)
    
    crop = img_np[y1:y2, x1:x2]
    coords = find_and_get_coords(crop, template, threshold)
    if coords:
        # 크롭 영역 상대 좌표를 전체 화면 좌표로 복원
        return x1 + coords[0], y1 + coords[1]
    return None




def find_and_click_template_in_bot(device, img_np, thresh_temp, threshold_val=0.68):
    if thresh_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        safe_device_shell(device, f"input tap {max_loc[0] + int(w / 2)} {max_loc[1] + int(h / 2)}")
        return True
    return False

def detect_poison_flash_6way(img_np):
    """
    6인 캐릭터 슬롯 각각의 전체 영역을 스캔하여, 슬롯 전체가 보라색(독 데미지 플래시/광원)으로 번쩍이는지 정밀 판정합니다.
    - 기존의 아이콘 스캔 방식은 압축 노이즈(JPG 열화) 및 타 아이콘 간섭으로 무한 힐 루프를 유발할 수 있음.
    - 슬롯 영역 내 보라색 픽셀 비율이 15% 이상일 때만 진짜 독 플래시로 판정하여 오작동을 차단합니다.
    """
    try:
        h, w = img_np.shape[:2]
        scale_x = w / 1440.0
        scale_y = h / 2560.0
        
        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV) if len(img_np.shape) == 3 else img_np
        
        # 보라색 범위 (H: 130~160, S: 40~255, V: 40~255)
        lower_purple = np.array([130, 40, 40])
        upper_purple = np.array([160, 255, 255])
        
        poisoned_detected = False
        max_purple_pixels = 0
        
        for slot_idx in range(1, 7):
            col = (slot_idx - 1) % 3
            row = (slot_idx - 1) // 3
            
            orig_left = col * 480
            orig_top = 1950 if row == 0 else 2250
            orig_right = orig_left + 480
            orig_bottom = 2250 if row == 0 else 2560
            
            # 해상도 비율 적용 좌표
            rx1, rx2 = int(orig_left * scale_x), int(orig_right * scale_x)
            ry1, ry2 = int(orig_top * scale_y), int(orig_bottom * scale_y)
            
            crop = hsv[ry1:ry2, rx1:rx2]
            mask = cv2.inRange(crop, lower_purple, upper_purple)
            purple_pixel_count = np.sum(mask > 0)
            
            # 슬롯 전체 면적 대비 보라색 비율 계산
            slot_area = (rx2 - rx1) * (ry2 - ry1)
            purple_ratio = (purple_pixel_count / slot_area) if slot_area > 0 else 0
            
            # 디버깅용 모니터링 로그 (5% 초과 검출 시에만 출력)
            if purple_ratio > 0.05:
                print(f"🟣 [독 감지 모니터링] {slot_idx}번 슬롯 보라색 영역 검출: {purple_pixel_count}px ({purple_ratio*100:.1f}%)")
                
            # 15% 이상 면적이 보라색으로 덮였을 때만 진성 독 플래시로 판정
            if purple_ratio >= 0.15:
                print(f"🏥 [독 플래시 확정] {slot_idx}번 슬롯 캐릭터 독 데미지 피격 감지! (비율: {purple_ratio*100:.1f}%)")
                poisoned_detected = True
                if purple_pixel_count > max_purple_pixels:
                    max_purple_pixels = purple_pixel_count
                    
        return poisoned_detected, max_purple_pixels
    except Exception as e:
        print(f"⚠️ [독 플래시 감지 오류] {e}")
        return False, 0

def detect_orange_danger_hp(img_np):
    try:
        party_zone = img_np[1900:2560, :]
        hsv = cv2.cvtColor(party_zone, cv2.COLOR_RGB2HSV)
        lower_orange = np.array([0, 210, 210])    
        upper_orange = np.array([6, 255, 255])    
        orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)
        orange_pixel_count = np.sum(orange_mask > 0)
        if orange_pixel_count > 30:
            print(f"    [레이더 정밀 진단] 검출된 빈사 핏빛 픽셀수: {orange_pixel_count} -> 진성 빈사 확정!!")
            return True
        return False
    except: return False

def fire_target_monster_body(device, img_np, t_next, t_arrow):
    target_coords = find_and_get_coords(img_np, t_next, 0.65)
    if target_coords:
        body_x = target_coords[0]
        body_y = target_coords[1] + 260
        print(f"      🎯 [몸통 저격] 적 'NEXT' 마크 기반 KONURI 공식 사격! 수치: ({body_x}, {body_y})")
        safe_device_shell(device, f"input tap {body_x} {body_y}")
        return True
        
    target_coords = find_and_get_coords(img_np, t_arrow, 0.60)
    if target_coords:
        body_x = target_coords[0]
        body_y = target_coords[1] + 130
        print(f"      🎯 [몸통 저격] '▼(적 화살표)' 마크 기반 KONURI 공식 사격! 수치: ({body_x}, {body_y})")
        safe_device_shell(device, f"input tap {body_x} {body_y}")
        return True
        
    print("      ⚠️ 타깃 인디케이터 인식 지연! 적 배치 중앙 안전 가드 스팟 강제 사격.")
    safe_device_shell(device, "input tap 720 1300") 
    return True

def start_main_macro(device, run_skill_logic=False):
    if not device: return False, False

    print("\n=======================================")
    print("🎨 [dungeon_bot] 코어 마스크 도장을 로드합니다...")
    t_field = load_template("templates/field_anchor.png") 
    t_chest_btn = load_template("templates/move_chest.png")
    t_exit_btn = load_template("templates/move_exit.png")
    t_move_chk = load_template("templates/move_check.png")
    t_no_chest = load_template("templates/no_chest.png") 
    t_yeolda = load_template("templates/yeolda_clean.png")
    t_milana = load_template("templates/milana_clean.png")
    t_get_item = load_template("templates/get_item.png")
    
    t_healer_name = load_template("templates/healer_name.png")
    t_heal_auto = load_template("templates/healer_auto_btn.png")
    t_heal_confirm = load_template("templates/confirm_recover.png")
    t_heal_close = load_template("templates/close_panel.png")

    t_combat_in = load_template("templates/combat_in.png")   
    t_combat_slow = load_template("templates/combat_slow.png") 
    t_auto_off = load_template("templates/auto_off.png")     
    t_auto_on = load_template("templates/auto_on.png")       
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    t_dungeon_sel = load_template("templates/dungeon_select_anchor.png")
    
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    
    t_sc_cheonja = load_template("templates/shortcut_cheonja_core.png") 
    t_btn_lvl_ok = load_template("templates/btn_level_confirm.png")      
    t_btn_lvl1 = load_template("templates/btn_level_1.png")         
    t_btn_lvl1_atv = load_template("templates/btn_level_1_atv.png") 
    
    t_sc_jeongmil = load_template("templates/shortcut_jeongmil.png")    
    t_sc_ttang = load_template("templates/shortcut_ttang.png")          
    
    t_next = load_template("templates/indicator_next.png")              
    t_arrow = load_template("templates/indicator_arrow.png")            
    print("=======================================")

    print("⏳ [로딩 마진 확보] 던전 필드 스트리밍 안정화를 위해 3.0초간 제어를 홀딩합니다...")
    time.sleep(3.0)

    state = "FIELD_WAIT"
    last_click_time = 0 
    came_from_combat = False 
    event_counter = 0
    
    last_state_changed_time = time.time()
    previous_state = "FIELD_WAIT"
    exit_start_time = 0
    prev_minimap_zone = None

    yuzuna_done = False
    milana_done = False
    guksu_done = False 
    
    auto_combat_paused_for_skill = False
    skill_mission_success_this_combat = False
    combat_entry_start_time = time.time()
    
    last_empty_shortcut_detected_time = 0
    continuous_heal_retry_count = 0

    while True:
        try:
            raw_cap = device.screencap()
            if raw_cap is None: raise RuntimeError("Screencap returned None")
            img_np = np.array(Image.open(io.BytesIO(raw_cap)))
        except Exception as cap_err:
            print(f"\n🌐⚠️ [dungeon_bot 캡처 실패] 실시간 캡처 유실!! 오류: {cap_err}")
            raise cap_err

        height, width = img_np.shape[:2]
        mean_brightness = np.mean(img_np)
        is_low_hp_dark_mode = mean_brightness < 85.0
        is_poisoned, purple_pixels = detect_poison_flash_6way(img_np)

        if check_template_present(img_np, t_dungeon_sel, 0.70):
            print("🚪 [dungeon_bot] 현실 화면이 '던전 선택창'으로 식별되었습니다! 사령탑으로 즉시 퇴장합니다.")
            return False, skill_mission_success_this_combat

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
            if stuck_duration > 30.0:
                print(f"\n⚠️ [🚨 블랙박스 경고] 현재 던전봇이 '{state}' 상태로 정체 중...")
                
                if state == "TRIGGER_EXIT":
                    print("🚪🚨 [탈출 정체 복구 시스템 작동] 던전 출구에서 30초간 정체 감지! 회군을 시작합니다.")
                    chk_coords = find_checkpoint_button_coords(img_np, t_move_chk, 0.70)
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
                
                if (detect_orange_danger_hp(img_np) or is_poisoned) and (continuous_heal_retry_count < 2):
                    print("🚨 [블랙박스 긴급 구호] 검증된 파티원 진성 빈사/독 포착!! 제자리 치료를 단행합니다.")
                    party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                    continuous_heal_retry_count += 1
                    event_counter = 0
                    last_state_changed_time = time.time()
                    continue
                elif continuous_heal_retry_count >= 2:
                    print("⚠️⏰ [폭주 방지 안전 벨브 개방] 무한 루프를 파쇄하고 행군을 강제 허용합니다!")
                    continuous_heal_retry_count = 0 

                if check_template_present(img_np, t_dungeon_sel, 0.70): return False, skill_mission_success_this_combat
                
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

                if check_template_present(img_np, t_combat_in, 0.80) or check_template_present(img_np, t_combat_slow, 0.80):
                    state = "IN_COMBAT"
                    last_state_changed_time = time.time()
                    continue

                if check_template_present_dynamic(img_np, t_yeolda, 0.65, 65 if is_low_hp_dark_mode else 160):
                    print("⚠️ [블랙박스 상자 해제 갇힘 복구] '열다'가 보이나 진입 실패 상태입니다. '아무것도 안 한다' 강제 터치로 상자창을 탈출합니다.")
                    safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.855)}")
                    time.sleep(1.0)
                    state = "FIELD_WAIT"
                elif chest_opener.is_minigame_screen(img_np, height, width):
                    state = "PLAY_MINIGAME"
                elif check_template_present(img_np, t_get_item, 0.80):
                    state = "CLEAR_CHECK"
                elif check_template_present(img_np, t_field, 0.65):
                    state = "FIELD_WAIT"
                else:
                    mag_coords_bot = find_exit_button_coords(img_np, t_exit_mag, 0.70)
                    if mag_coords_bot: safe_device_shell(device, f"input tap {mag_coords_bot[0]} {mag_coords_bot[1]}")
                    else: safe_device_shell(device, "input tap 1380 2400")
                    time.sleep(1.5)
                    state = "FIELD_WAIT"
                
                last_state_changed_time = time.time()
                continue
        else:
            previous_state = state
            last_state_changed_time = time.time()

        if is_poisoned and state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if continuous_heal_retry_count < 2:
                print(f"🔮🚨 [6인 총괄 독 레이더 포착!] 하단 슬롯 보라색 플래시 폭발 검출!! 제자리 즉각 치유를 전개합니다.")
                heal_success = party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                continuous_heal_retry_count += 1
                if heal_success:
                    print("✅ 제자리 일괄 해독 성공!")
                    event_counter = 0
                state = "FIELD_WAIT"
                continue
            else:
                print("⚠️ [독 레이더 세이프 가드] 연속 치유 한도 초과! 강제 해독 루프 탈출.")
                continuous_heal_retry_count = 0

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            current_target_thresh = 65 if is_low_hp_dark_mode else 160
            if check_template_present_dynamic(img_np, t_yeolda, 0.65, current_target_thresh):
                if is_low_hp_dark_mode:
                    print(f"🩸⚠️ [빈사형 암전상자 포착!] 현재 화면 평균 밝기 {mean_brightness:.1f} 야간 투시경 가동.")
                else:
                    print("📦 [메인] '열다' 감지! 상자 해제 시퀀스로 진입.")
                if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, t_milana):
                    state = "BRANCH_CHECK"
                continue

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if not check_template_present(img_np, t_field, 0.62) or is_low_hp_dark_mode:
                if check_template_present(img_np, t_combat_in, 0.80) or check_template_present(img_np, t_combat_slow, 0.80):
                    print("⚔️ [메인] 배속 고정 UI 포착,적 인카운터 확정! 전투 대기(`IN_COMBAT`) 진입.")
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time() 
                    last_empty_shortcut_detected_time = 0 
                    continue

        if state == "FIELD_WAIT":
            if check_template_present(img_np, t_field, 0.62) or is_low_hp_dark_mode:
                if detect_orange_danger_hp(img_np) and (continuous_heal_retry_count < 2):
                    print("🚨🚨 [철벽 빈사 레이더 발동] 파티원 중 핏빛 주황색 이름 발견!! 즉각 행군을 멈추고 강제 치유 시퀀스를 전개합니다.")
                    heal_success = party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                    continuous_heal_retry_count += 1
                    if heal_success:
                        event_counter = 0
                    continue 
                elif continuous_heal_retry_count >= 2:
                    print("⚠️⏰ [치유 폭주 해제] 무한 루프를 깨고 강제 파밍 기어를 올립니다.")
                    continuous_heal_retry_count = 0 

                if is_low_hp_dark_mode and came_from_combat:
                    print(f"🩸🚨 [전투 직후 대위기!] 주인공 빈사 피안개 장막 감지. 제자리 긴급 치유 정비를 주입합니다!")
                    heal_success = party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                    if heal_success: event_counter = 0
                    came_from_combat = False
                    continue
                
                if came_from_combat:
                    print("⏳ [정산 대기 브레이크] 경험치창 및 필드 완전 복귀를 위해 3.0초간 연산 대기...")
                    time.sleep(3.0)
                    
                    event_counter += 1
                    print(f"🎉 [전투 일괄 정산 완료] 전투 종료 필드 복귀 성공! 현재 누적 순수 전투 수: ({event_counter}/{LIMIT_COMBAT_EVENTS})")
                    if event_counter >= LIMIT_COMBAT_EVENTS:
                        heal_success = party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                        if heal_success: event_counter = 0 
                        else: event_counter = LIMIT_COMBAT_EVENTS
                    came_from_combat = False 
                    continuous_heal_retry_count = 0
                    continue
                
                if time.time() - last_click_time > 4.0:
                    coords = find_chest_button_coords(img_np, t_chest_btn, 0.70)
                    if coords:
                        cx, cy = coords
                        print(f"🔥 [인터리빙 탭] '상자 자동 이동' ({cx}, {cy}) 10연타 시전")
                        toast_detected = False
                        for click_count in range(1, 11):
                            safe_device_shell(device, f"input tap {cx} {cy}")
                            time.sleep(0.2) 
                            try: raw_cap_inter = device.screencap()
                            except: continue
                            img_np_inter = np.array(Image.open(io.BytesIO(raw_cap_inter)))
                            
                            current_target_thresh = 65 if is_low_hp_dark_mode else 160
                            if check_template_present_dynamic(img_np_inter, t_yeolda, 0.65, current_target_thresh):
                                img_np = img_np_inter 
                                break
                            if check_template_present(img_np_inter, t_no_chest, 0.55):
                                print(f"✨ 토스트 실시간 포착!")
                                toast_detected = True
                                img_np = img_np_inter
                                break
                        
                        last_click_time = time.time()
                        if toast_detected: 
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            prev_minimap_zone = None
                        else: state = "AUTO_MOVING"

        elif state == "AUTO_MOVING":
            toast_detected = False
            for scan_step in range(5):
                current_target_thresh = 65 if is_low_hp_dark_mode else 160
                if check_template_present_dynamic(img_np, t_yeolda, 0.65, current_target_thresh): break
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
            else:
                if time.time() - last_click_time > 4.0: state = "FIELD_WAIT"

        if state == "TRIGGER_EXIT":
            # 💡 [기습 방어 인터럽트] 탈출 중 전투 발생 즉시 0.1초 만에 전투 태세 전환
            if check_template_present(img_np, t_combat_in, 0.80) or check_template_present(img_np, t_combat_slow, 0.80):
                print("⚔️ [TRIGGER_EXIT 인터럽트] 탈출 행군 중 기습 포착! 즉시 전투 모드로 스위칭합니다.")
                state = "IN_COMBAT"
                yuzuna_done = False
                milana_done = False
                guksu_done = False
                auto_combat_paused_for_skill = False
                combat_entry_start_time = time.time() 
                last_empty_shortcut_detected_time = 0 
                continue

            coords_exit = find_exit_button_coords(img_np, t_exit_btn, 0.70)
            if coords_exit:
                ex, ey = coords_exit
                print(f"⏭️ [던전 탈출 시도] '출구 이동' 단추를 터치합니다. ({ex}, {ey})")
                safe_device_shell(device, f"input tap {ex} {ey}")
            
            elapsed_exit_time = time.time() - exit_start_time
            if elapsed_exit_time > 90.0:
                print(f"🔍 [출구 락앤롤 모니터] 이동 시작 후 {elapsed_exit_time:.1f}초 경과. 우상단 미니맵 동결 상태 정밀 대조를 시작합니다...")
                current_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                current_minimap = current_gray[0:170, 370:576]
                
                if prev_minimap_zone is not None:
                    diff = cv2.absdiff(current_minimap, prev_minimap_zone)
                    non_zero_count = np.count_nonzero(diff > 25)
                    print(f"📊 [스턱 분석기] 미니맵 미세 움직임 프레임 변동 값: {non_zero_count} 픽셀")
                    
                    if non_zero_count < 50:
                        print("🚨💀 [문앞 물리 스턱 발생 검증 확정!!] 캐릭터가 제자리걸음 중입니다!")
                        safe_device_shell(device, "input swipe 400 800 400 1200 600")
                        time.sleep(1.0)
                        safe_device_shell(device, "input swipe 1200 400 1200 800 600")
                        exit_start_time = time.time() - 10.0 
                        prev_minimap_zone = None
                        time.sleep(2.5)
                        continue
                prev_minimap_zone = current_minimap
            
            if not check_template_present(img_np, t_field, 0.62) and not is_low_hp_dark_mode:
                print("🎉 [탈출 무결점 성공] 던전 필드 화면이 완전히 소멸되었습니다! 사령탑 무대로 복귀합니다.")
                return True, skill_mission_success_this_combat
            time.sleep(2.0)
            continue

        elif state == "IN_COMBAT":
            if get_dead_match_score(img_np, t_anchor_dead) > 0.65:
                if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    safe_device_shell(device, "input tap 720 1200")
                time.sleep(2.0)
                continue

            yuzu_sc_coords = find_and_get_coords(img_np, t_sc_cheonja, 0.70)
            milana_sc_coords = find_and_get_coords(img_np, t_sc_jeongmil, 0.70)
            guksu_sc_coords = find_and_get_coords(img_np, t_sc_ttang, 0.70)

            if run_skill_logic and (not yuzuna_done) and (not milana_done) and (not guksu_done):
                if (not yuzu_sc_coords) and (not milana_sc_coords) and (not guksu_sc_coords):
                    print("🛡️ [KONURI 초입 가드 작동] 현재 화면은 전투실이 아니라 필드 오독입니다! 즉시 주도권을 FIELD_WAIT로 원상 반환합니다.")
                    state = "FIELD_WAIT"
                    time.sleep(0.5)
                    continue

            if check_template_present(img_np, t_combat_slow, 0.82):
                print("⚡ [속도 혁명] 전투 진입 확인! 배속이 회색(1배속)이므로 주황색 고속 기어로 먼저 올립니다.")
                if find_and_click_template_in_bot(device, img_np, t_combat_slow, 0.75):
                    time.sleep(0.4) 
                    continue

            if run_skill_logic and skill_mission_success_this_combat:
                print("🏆🛡️ [전술 이행망 작동] 핵심 광역기 가드 완수 상태 확인. 수동 모드를 즉시 해제하고 극하단 자동전투 안전 기지(1380, 1720) 강제 격타!!")
                auto_off_coords = find_and_get_coords(img_np, t_auto_off, 0.75)
                if auto_off_coords: 
                    safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}")
                else:
                    safe_device_shell(device, "input tap 1380 1720")
                run_skill_logic = False 
                time.sleep(1.5) 
                continue

            if run_skill_logic and (not skill_mission_success_this_combat):
                if time.time() - combat_entry_start_time > 35.0:
                    print("⚠️⏰ [비상 밸브 개방] 스킬 주입 제한시간 초과! 즉시 극하단 안전 좌표로 고속 자동전투 전환합니다.")
                    safe_device_shell(device, "input tap 1380 1720") 
                    run_skill_logic = False
                    continue

                if not auto_combat_paused_for_skill:
                    auto_on_coords = find_and_get_coords(img_np, t_auto_on, 0.75)
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

            auto_off_coords = find_and_get_coords(img_np, t_auto_off, 0.80)
            if auto_off_coords and (not auto_combat_paused_for_skill): 
                safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}") 
                time.sleep(0.3)
                continue

            if not check_template_present(img_np, t_combat_in, 0.70) and not check_template_present(img_np, t_combat_slow, 0.70):
                print("🎉 배속마크 소멸! 필드로 주도권 복구 수순 가동. (연출 마진 확보를 위해 3.0초 슬로우 브레이크 가동)")
                came_from_combat = True 
                state = "FIELD_WAIT"
                time.sleep(3.0) 
            else: time.sleep(0.3)

        elif state == "BRANCH_CHECK":
            if chest_opener.is_minigame_screen(img_np, height, width): state = "PLAY_MINIGAME"
            elif check_template_present(img_np, t_get_item, 0.80): state = "CLEAR_CHECK"
            else: time.sleep(0.2)

        elif state == "PLAY_MINIGAME":
            chest_opener.solve_trap_game(device, img_np)
            try: img_np_post = np.array(Image.open(io.BytesIO(device.screencap())))
            except: continue
            if chest_opener.is_minigame_screen(img_np_post, height, width): state = "PLAY_MINIGAME"
            else: state = "CLEAR_CHECK"
            continue

        elif state == "CLEAR_CHECK":
            if check_template_present(img_np, t_get_item, 0.80):
                safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.5)}")
                time.sleep(0.8)
            else:
                if is_low_hp_dark_mode:
                    print("🩸🎁 [빈사형 상자깡 정산 완료] 즉각 피안개 장막 파쇄를 위해 힐러를 전격 소환합니다.")
                    party_manager.run_party_healing_sequence(device, t_healer_name, t_heal_auto, t_heal_confirm, t_heal_close)
                print("✨ [상자 오프닝 완료] 다음 파밍 탐색으로 복귀합니다.")
                state = "FIELD_WAIT" 
                time.sleep(1.0)

        time.sleep(0.001)