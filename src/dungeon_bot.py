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
# - 현재 버전: 1.12.3
# - 최근 수정일: 2026-06-27 00:25
# - 수정 기록:
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

def find_chest_button_coords(img_np, template, threshold=0.70):
    """
    우측 상단 2x2 격자의 4번째 단추(상자이동) 영역(X: 1250~1440, Y: 530~630)만 잘라내어 매칭을 수행합니다.
    이를 통해 1번, 2번, 3번 단추와의 오검출을 100% 차단합니다.
    """
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    if h < 630 or w < 1440: return None
    
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 4번째 단추 Bounding Box (원본 해상도 기준 X: 1250~1440, Y: 530~630)
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(530 * scale_y), int(630 * scale_y)
    
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    
    crop = img_np[y1:y2, x1:x2]
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
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
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    if h < 520 or w < 1440: return None
    
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 2번째 단추 Bounding Box (원본 해상도 기준 X: 1250~1440, Y: 410~520)
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(410 * scale_y), int(520 * scale_y)
    
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    
    crop = img_np[y1:y2, x1:x2]
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
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
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    if h < 630 or w < 1280: return None
    
    scale_x = w / 1440.0
    scale_y = h / 2560.0
    
    # 3번째 단추 Bounding Box (원본 해상도 기준 X: 1150~1280, Y: 530~630)
    x1, x2 = int(1150 * scale_x), int(1280 * scale_x)
    y1, y2 = int(530 * scale_y), int(630 * scale_y)
    
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    
    crop = img_np[y1:y2, x1:x2]
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
    coords = find_and_get_coords(crop, template, threshold)
    if coords:
        # 크롭 영역 상대 좌표를 전체 화면 좌표로 복원
        return x1 + coords[0], y1 + coords[1]
    return None


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

def detect_poison_flash_6way(img_np):
    """
    6인 캐릭터 슬롯 각각의 전체 영역을 스캔하여, 슬롯 전체가 보라색(독 데미지 플래시/광원)으로 번쩍이는지 정밀 판정합니다.
    - 기존의 아이콘 스캔 방식은 압축 노이즈(JPG 열화) 및 타 아이콘 간섭으로 무한 힐 루프를 유발할 수 있음.
    - 슬롯 영역 내 보라색 픽셀 비율이 15% 이상일 때만 진짜 독 플래시로 판정하여 오작동을 차단합니다.
    """
    if img_np is None: return False, 0
    h, w = img_np.shape[:2]
    if h < 2560 or w < 1440: return False, 0
    try:
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
    if img_np is None: return False
    h, w = img_np.shape[:2]
    if h < 2560 or w < 1440: return False
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
    t_get_item = load_template("templates/get_item.png")
    
    t_heal_auto = load_template("templates/healer_auto_btn.png")
    t_heal_confirm = load_template("templates/confirm_recover.png")
    t_heal_close = load_template("templates/close_panel.png")

    t_combat_in = load_template("templates/combat_in.png")   
    t_combat_slow = load_template("templates/combat_slow.png") 
    t_auto_off = load_template("templates/auto_off.png")     
    t_auto_on = load_template("templates/auto_on.png")       
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    t_dungeon_sel = load_template("templates/WolfCave/dungeon_select.png")
    
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
    t_disarmer_templates = chest_opener.load_multiple_templates("templates/!!Character", "disarmer_")
    print("=======================================")

    state = "FIELD_WAIT"
    last_click_time = 0 
    came_from_combat = False 
    event_counter = 0
    
    last_state_changed_time = time.time()
    previous_state = "FIELD_WAIT"
    exit_start_time = 0
    prev_minimap_zone = None
    
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
    
    last_empty_shortcut_detected_time = 0
    continuous_heal_retry_count = 0
    yeolda_stuck_retry_count = 0
    exit_clicked_once = False

    cap_fail_counter = 0
    while True:
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
            print(f"⚠️ [dungeon_bot 해상도 미달 가드] 현재 화면 크기({width}x{height})가 기준 해상도(1440x2560) 미만입니다. 1.0초 대기합니다.")
            time.sleep(1.0)
            continue

        mean_brightness = np.mean(img_np)
        if mean_brightness < 5.0:
            print("⏳ [dungeon_bot 로딩 가드] 화면 전환/로딩 중(암전) 포착! 0.5초 대기 후 재스캔합니다.")
            time.sleep(0.5)
            continue
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
                if state == "TRIGGER_EXIT":
                    last_state_changed_time = time.time()
                    continue
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
                    heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                    continuous_heal_retry_count += 1
                    event_counter = 0
                    last_state_changed_time = time.time()
                    if heal_success and last_target_coords:
                        print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                        safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                        last_click_time = time.time()
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
                    if yeolda_stuck_retry_count < 3:
                        yeolda_stuck_retry_count += 1
                        print(f"⚠️ [블랙박스 상자 해제 갇힘 복구] '열다'가 보이나 진입 실패 상태입니다. 상자 오프닝을 재시도합니다. ({yeolda_stuck_retry_count}/3)")
                        if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda):
                            state = "BRANCH_CHECK"
                        last_state_changed_time = time.time()
                    else:
                        print("⚠️ [블랙박스 상자 해제 갇힘 복구] '열다' 재시도 3회 초과! '아무것도 안 한다' 강제 터치로 상자창을 확실히 탈출합니다.")
                        safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.855)}")
                        time.sleep(1.0)
                        yeolda_stuck_retry_count = 0
                        state = "FIELD_WAIT"
                elif chest_opener.is_minigame_screen(img_np, height, width):
                    state = "PLAY_MINIGAME"
                elif check_template_present(img_np, t_get_item, 0.65):
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
            yeolda_stuck_retry_count = 0
        # 🎮 [미니게임 즉각 돌입 가드] 화면이 미니게임 해제 창인 경우 30초 정체 대기 없이 즉시 전이
        if state in ["FIELD_WAIT", "AUTO_MOVING"] and chest_opener.is_minigame_screen(img_np, height, width):
            print("🎮 [dungeon_bot] 미니게임 화면 포착! 즉각 PLAY_MINIGAME 상태로 진입합니다.")
            state = "PLAY_MINIGAME"
            last_state_changed_time = time.time()
            continue

        # 👤 [따개 강제 검출 가드] 캐릭터 선택창("누가 열 거야?")이 이미 열려 있는 경우
        if state in ["FIELD_WAIT", "AUTO_MOVING"] and len(t_disarmer_templates) > 0:
            found_disarmer = False
            for file_name, thresh_disarmer in t_disarmer_templates:
                coords = chest_opener.find_template_coords(img_np, thresh_disarmer, 0.75)
                if coords:
                    dx, dy = coords
                    print(f"👤 [dungeon_bot] 갇힘 복구 가드 작동: '{file_name}' 도장 검출! 좌표 ({dx}, {dy}) 터치합니다.")
                    safe_device_shell(device, f"input tap {dx} {dy}")
                    time.sleep(1.5) # 미니게임 혹은 정산창 전환 대기
                    state = "BRANCH_CHECK"
                    found_disarmer = True
                    break
            if found_disarmer:
                continue

        if is_poisoned and state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if continuous_heal_retry_count < 2:
                print(f"🔮🚨 [6인 총괄 독 레이더 포착!] 하단 슬롯 보라색 플래시 폭발 검출!! 제자리 즉각 치유를 전개합니다.")
                heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                continuous_heal_retry_count += 1
                if heal_success:
                    print("✅ 제자리 일괄 해독 성공! 즉각 이동을 재개합니다.")
                    event_counter = 0
                    if last_target_coords:
                        print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                        safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                        last_click_time = time.time()
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
                if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda):
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
                    heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                    continuous_heal_retry_count += 1
                    if heal_success:
                        event_counter = 0
                        if last_target_coords:
                            print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                            safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                            last_click_time = time.time()
                    continue 
                elif continuous_heal_retry_count >= 2:
                    print("⚠️⏰ [치유 폭주 해제] 무한 루프를 깨고 강제 파밍 기어를 올립니다.")
                    continuous_heal_retry_count = 0 

                if is_low_hp_dark_mode and came_from_combat:
                    print(f"🩸🚨 [전투 직후 대위기!] 주인공 빈사 피안개 장막 감지. 제자리 긴급 치유 정비를 주입합니다!")
                    heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                    if heal_success:
                        event_counter = 0
                        if last_target_coords:
                            print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                            safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                            last_click_time = time.time()
                    came_from_combat = False
                    continue
                
                if came_from_combat:
                    print("⏳ [정산 대기 브레이크] 경험치창 및 필드 완전 복귀를 위해 3.0초간 연산 대기...")
                    time.sleep(3.0)
                    
                    event_counter += 1
                    print(f"🎉 [전투 일괄 정산 완료] 전투 종료 필드 복귀 성공! 현재 누적 순수 전투 수: ({event_counter}/{LIMIT_COMBAT_EVENTS})")
                    if event_counter >= LIMIT_COMBAT_EVENTS:
                        heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                        if heal_success:
                            event_counter = 0 
                            if last_target_coords:
                                print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                                safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                                last_click_time = time.time()
                        else:
                            event_counter = LIMIT_COMBAT_EVENTS
                    came_from_combat = False 
                    continuous_heal_retry_count = 0
                    continue
                
                if time.time() - last_click_time > 4.0:
                    coords = find_chest_button_coords(img_np, t_chest_btn, 0.70)
                    if coords:
                        cx, cy = coords
                        print(f"📦 [상자 이동 시도] '상자 자동 이동' ({cx}, {cy}) 1회 터치합니다.")
                        safe_device_shell(device, f"input tap {cx} {cy}")
                        last_click_time = time.time()
                        last_target_coords = (cx, cy)
                        
                        action_success = False
                        opened = False
                        toast_detected = False
                        
                        for retry_cnt in range(2): # 최초 1회 + 씹힘 시 재시도 1회
                            if retry_cnt > 0:
                                print(f"🔄 [상자 터치 재시도] 터치 씹힘 감지되어 1회 다시 누릅니다. ({cx}, {cy})")
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
                                
                                current_target_thresh = 65 if is_low_hp_dark_mode else 160
                                if check_template_present_dynamic(img_np_sub, t_yeolda, 0.65, current_target_thresh):
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
                            if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda):
                                state = "BRANCH_CHECK"
                            else:
                                state = "FIELD_WAIT"
                        elif toast_detected:
                            print("🎉 [상자 없음] 토스트 메시지를 확인하여 탈출 시퀀스로 이행합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                        elif moved:
                            print("🏃 [이동 시작 확인] 미니맵이 움직이기 시작했습니다. AUTO_MOVING으로 이행.")
                            state = "AUTO_MOVING"
                        else:
                            print("📦🚫 [상자 없음 판정] 재시도 결과 미니맵 움직임과 '열다'가 모두 미검출되었습니다. 상자가 없는 것으로 논리적 판정하여 탈출로 전환합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            exit_stuck_count = 0
                            exit_prev_minimap = None

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
                last_click_time = 0
                exit_clicked_once = False
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

            exit_touched_this_loop = False
            # 출구 버튼 터치 (최초 1회 터치이거나, 미니맵이 멈춰서 정체 스택이 쌓였을 때만 재시도 터치)
            if (not exit_clicked_once) or (exit_stuck_count >= 1):
                if time.time() - last_click_time > 3.0:
                    coords_exit = find_exit_button_coords(img_np, t_exit_btn, 0.70)
                    if coords_exit:
                        ex, ey = coords_exit
                        print(f"⏭️ [던전 탈출 시도] '출구 이동' 단추를 터치합니다. ({ex}, {ey})")
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

            is_real_field = check_template_present(img_np, t_field, 0.62) or is_low_hp_dark_mode
            if exit_prev_minimap is not None and is_real_field:
                diff = cv2.absdiff(current_mini, exit_prev_minimap)
                mean_diff = np.mean(diff) / 255.0
                print(f"📊 [탈출 스턱 분석기] 미니맵 미세 움직임 변동 값: {mean_diff:.4f}")
                
                if mean_diff < 0.05:
                    exit_stuck_count += 1
                    print(f"⚠️ [탈출 정체 스택] 미니맵 정지 감지 ({exit_stuck_count}/3 회)")
                else:
                    exit_stuck_count = 0
                
                if exit_stuck_count >= 3:
                    print("🚪🚨 [탈출 정체 복구 시스템 작동] 출구 주변에서 9초간 누적 정체 감지! 즉시 회군을 단행합니다.")
                    chk_coords = find_checkpoint_button_coords(img_np, t_move_chk, 0.70)
                    if chk_coords:
                        cx, cy = chk_coords
                        print(f"📍 [체크포인트] 3번 버튼 검출 성공 ({cx}, {cy}) 터치하여 안전 지대로 회군합니다.")
                        safe_device_shell(device, f"input tap {cx} {cy}")
                    else:
                        print("📍 [체크포인트] 3번 버튼 미검출. 물리 복구 스위프 및 고정 좌표 강제 사격.")
                        safe_device_shell(device, "input swipe 400 800 400 1200 600")
                        time.sleep(1.0)
                        safe_device_shell(device, "input swipe 1200 400 1200 800 600")
                        time.sleep(1.5)
                        safe_device_shell(device, "input tap 1215 572")
                    
                    print("⏳ 회군 연출 및 위치 재조정을 위해 4.0초간 제어를 홀딩합니다...")
                    time.sleep(4.0)
                    
                    state = "FIELD_WAIT"
                    last_click_time = time.time()
                    exit_stuck_count = 0
                    exit_prev_minimap = None
                    continue
            
            exit_prev_minimap = current_mini
            
            if not check_template_present(img_np, t_field, 0.62) and not is_low_hp_dark_mode:
                current_target_thresh = 65 if is_low_hp_dark_mode else 160
                if check_template_present_dynamic(img_np, t_yeolda, 0.65, current_target_thresh) or chest_opener.is_minigame_screen(img_np, height, width):
                    print("⚠️ [탈출 감시] 필드가 미검출되었으나, 상자 선택창('열다') 또는 미니게임 화면이 감지되었습니다. 탈출 복귀를 취소하고 상자 해제로 이행합니다.")
                else:
                    print("🎉 [탈출 무결점 성공] 던전 필드 화면이 완전히 소멸되었습니다! 사령탑 무대로 복귀합니다.")
                    return True, skill_mission_success_this_combat
            
            if exit_touched_this_loop or exit_clicked_once:
                time.sleep(3.0)
            else:
                time.sleep(0.3)
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
                    print("🛡️ [Daphne 초입 가드 작동] 현재 화면은 전투실이 아니라 필드 오독입니다! 즉시 주도권을 FIELD_WAIT로 원상 반환합니다.")
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
            elif check_template_present(img_np, t_get_item, 0.65): state = "CLEAR_CHECK"
            else: time.sleep(0.2)

        elif state == "PLAY_MINIGAME":
            chest_opener.solve_trap_game(device, img_np)
            try: img_np_post = np.array(Image.open(io.BytesIO(device.screencap())))
            except: continue
            if chest_opener.is_minigame_screen(img_np_post, height, width): state = "PLAY_MINIGAME"
            else: state = "CLEAR_CHECK"
            continue

        elif state == "CLEAR_CHECK":
            if check_template_present(img_np, t_get_item, 0.65):
                safe_device_shell(device, "input tap 701 333")
                time.sleep(0.8)
            else:
                if is_low_hp_dark_mode:
                    print("🩸🎁 [빈사형 상자깡 정산 완료] 즉각 피안개 장막 파쇄를 위해 힐러를 전격 소환합니다.")
                    party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close)
                print("✨ [상자 오프닝 완료] 다음 파밍 탐색으로 복귀합니다.")
                state = "FIELD_WAIT" 
                time.sleep(1.0)

        time.sleep(0.001)