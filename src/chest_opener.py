# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.15.0
# - 최근 수정일: 2026-07-28 01:28
# - 수정 기록:
#   1.15.0: 지정 슬롯 따개 선택 도입, 상자공포(chestfear) 그레이스케일/컬러 감지 및 우회 알고리즘 추가
#           (whowillopenit 템플릿 의존성 제거 및 '열다' 버튼 소멸 기반 진입 판정 전격 전환)
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image

# 1440x2560 기준 정밀 카드 ROI 영역 (좌상X, 좌상Y, 우하X, 우하Y)
SLOT_ROIS = {
    1: (107, 1727, 507, 1992),
    2: (527, 1727, 927, 1992),
    3: (947, 1727, 1347, 1992),
    4: (107, 2020, 507, 2285),
    5: (527, 2020, 927, 2285),
    6: (947, 2020, 1347, 2285)
}

def load_template(file_path):
    import os
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
        return thresh
    except: return None

def load_grayscale_template(file_path):
    import os
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        return gray
    except: return None

def load_color_template(file_path):
    """ RGB 채널 싱크를 맞춘 컬러 템플릿 로드 함수 """
    import os
    if not os.path.exists(file_path): return None
    try:
        # cv2.imread는 BGR로 읽으므로 RGB로 강제 변환하여 screencap 포맷과 통일
        img = cv2.imread(file_path)
        if img is None: return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except:
        return None

def check_text_by_user_template(img_np, thresh_temp, threshold_val=0.68):
    """ 도장 뼈대 대조 공통 함수 """
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_gray_template_present(img_np, gray_temp, threshold_val=0.70):
    if gray_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = gray_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False
    
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_color_template_present_in_roi(img_np, color_temp, x1, y1, x2, y2, threshold_val=0.80):
    """ 지정된 ROI(카드 영역) 안에서 컬러 템플릿(상자공포 등) 매칭 수행 """
    if color_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    
    # Boundary Guard (경계 보호)
    x1 = max(0, min(x1, w_img))
    y1 = max(0, min(y1, h_img))
    x2 = max(0, min(x2, w_img))
    y2 = max(0, min(y2, h_img))
    
    if x2 <= x1 or y2 <= y1: return False
    
    # ROI 크롭
    crop = img_np[y1:y2, x1:x2]
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = color_temp.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    result = cv2.matchTemplate(crop, color_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def get_slot_center(slot_idx):
    """ 슬롯 번호(1~6)에 매칭되는 카드의 정밀 중심 터치 좌표 반환 """
    roi = SLOT_ROIS.get(slot_idx)
    if not roi:
        return (733, 2390)  # 기본값
    x1, y1, x2, y2 = roi
    return (x1 + x2) // 2, (y1 + y2) // 2

def is_minigame_screen(img_np, height, width):
    """ 미니게임 상단 붉은상자+해골마크 앵커 존재 여부 감지 """
    t_trap_anchor = load_grayscale_template("templates/trap_minigame_anchor.png")
    if t_trap_anchor is not None and img_np is not None:
        h_img, w_img = img_np.shape[:2]
        
        scale_x = w_img / 1440.0
        scale_y = h_img / 2560.0
        
        x1, x2 = int(37 * scale_x), int(207 * scale_x)
        y1, y2 = int(207 * scale_y), int(337 * scale_y)
        
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w_img, x2)
        y2 = min(h_img, y2)
        
        crop = img_np[y1:y2, x1:x2]
        h_crop, w_crop = crop.shape[:2]
        h_temp, w_temp = t_trap_anchor.shape[:2]
        if h_crop < h_temp or w_crop < w_temp: return False
        
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        result = cv2.matchTemplate(gray_crop, t_trap_anchor, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val > 0.65
    return False

def solve_trap_game(device, img_np):
    """ 미니게임 정중앙 하단 해제 난사 """
    print("🔮 [chest_opener] 미니게임 인카운터! 게이트 스캔을 스킵하고 0.1초 간격 15연타 초고속 폭격을 주입합니다.")
    height, width = img_np.shape[:2]
    
    release_x = int(width * 0.503)
    release_y = int(height * 0.611)
    
    for _ in range(15):
        device.shell(f"input tap {release_x} {release_y}")
        time.sleep(0.1)
        
    print("⏳ 15연타 난사 완료. 정산창 연출 진입을 위해 1.0초간 충분히 대기합니다...")
    time.sleep(1.0)
    return True

def open_and_disarm_chest(device, img_np, thresh_yeolda, chest_opener_slot=6, masked_adventurer_slot=4):
    """
    [dungeon_bot 연동용 핵심 함수]
    '열다' 터치부터 상자공포 상태이상 회피 및 지정 슬롯 클릭까지 진행합니다.
    """
    height, width = img_np.shape[:2]
    
    # [1단계] '열다' 버튼을 발견 즉시 터치
    print("🔥 [chest_opener] '열다' 버튼 포착! 상자 오픈을 시도합니다.")
    open_x = int(width * 0.5)
    open_y = int(height * 0.795) 
    device.shell(f"input tap {open_x} {open_y}")
    time.sleep(1.0) # 캐릭터 선택창 애니메이션 대기
    
    # 템플릿 로딩
    t_chestfear = load_color_template("templates/chestfear.png")
        
    # '열다' 버튼이 사라질 때까지 최대 5초간 대기하며 진입 판정 진행
    start_time = time.time()
    last_click_yeolda_time = time.time()
    while time.time() - start_time < 5.0:
        try:
            import sys
            if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'update_heartbeat'):
                sys.modules['__main__'].update_heartbeat()
        except:
            pass

        try:
            raw_cap = device.screencap()
            img_np_current = cv2.imdecode(np.frombuffer(raw_cap, np.uint8), cv2.IMREAD_COLOR)
            img_np_current = cv2.cvtColor(img_np_current, cv2.COLOR_BGR2RGB)
        except Exception as cap_err:
            print(f"⚠️ [chest_opener] Screencap 버퍼 렉 감지: {cap_err}")
            time.sleep(0.1)
            continue
            
        # 여전히 '열다' 버튼이 보인다면 터치 씹힘 재시도
        if check_text_by_user_template(img_np_current, thresh_yeolda, 0.70):
            if time.time() - last_click_yeolda_time > 1.5:
                print("⚠️ [chest_opener] '열다' 터치 씹힘 감지! 재클릭을 주입합니다.")
                device.shell(f"input tap {open_x} {open_y}")
                last_click_yeolda_time = time.time()
            time.sleep(0.1)
            continue
            
        # [2단계] '열다' 버튼이 화면에서 사라졌으므로 캐릭터 선택창 진입 완료로 판정!
        print("👤 [chest_opener] '열다' 버튼 소멸 확인! 캐릭터 선택창 진입 확정 판정 진행.")
        
        chosen_slot = None
        fear_on_primary = False
        
        # 1. 1순위: 지정 따개 슬롯에 상자공포 상태이상 검사
        if t_chestfear is not None:
            x1, y1, x2, y2 = SLOT_ROIS[chest_opener_slot]
            if check_color_template_present_in_roi(img_np_current, t_chestfear, x1, y1, x2, y2, 0.78):
                print(f"⚠️ [chest_opener] 1순위 따개({chest_opener_slot}번)에 '상자 공포' 상태이상이 발견되었습니다!")
                fear_on_primary = True
            else:
                print(f"✅ [chest_opener] 1순위 따개({chest_opener_slot}번) 상태 정상.")
                chosen_slot = chest_opener_slot
        else:
            print("⚠️ [chest_opener] templates/chestfear.png 파일이 없어 상태이상 검사를 생략하고 1순위 따개를 선택합니다.")
            chosen_slot = chest_opener_slot
            
        # 2. 2순위: 지정 따개에 공포가 걸렸고 주인공 슬롯 검사
        if fear_on_primary:
            x1, y1, x2, y2 = SLOT_ROIS[masked_adventurer_slot]
            if check_color_template_present_in_roi(img_np_current, t_chestfear, x1, y1, x2, y2, 0.78):
                print(f"⚠️ [chest_opener] 2순위 주인공({masked_adventurer_slot}번) 역시 '상자 공포'가 검출되었습니다!")
                
                # 3. 3순위: 1~6번 슬롯 순차 스캔하여 공포가 없는 캐릭터 찾기
                for slot in [1, 2, 3, 4, 5, 6]:
                    sx1, sy1, sx2, sy2 = SLOT_ROIS[slot]
                    if not check_color_template_present_in_roi(img_np_current, t_chestfear, sx1, sy1, sx2, sy2, 0.78):
                        print(f"🔄 [chest_opener] 대체 슬롯 발견: {slot}번 캐릭터로 상자 개방을 결정합니다.")
                        chosen_slot = slot
                        break
                        
                # 만약 전원이 다 공포라면 최후의 수단으로 주인공 강제 선택
                if chosen_slot is None:
                    print("🚨 [chest_opener] 모든 캐릭터가 상자 공포 상태입니다! 최후의 보루로 주인공을 터치합니다.")
                    chosen_slot = masked_adventurer_slot
            else:
                print(f"🔄 [chest_opener] 대체 슬롯 발견: 주인공({masked_adventurer_slot}번)으로 상자를 개방합니다.")
                chosen_slot = masked_adventurer_slot
        
        # 최종 계산된 좌표 클릭
        if chosen_slot is not None:
            tx, ty = get_slot_center(chosen_slot)
            print(f"👉 [chest_opener] 최종 결정: {chosen_slot}번 카드 슬롯 ({tx}, {ty}) 터치를 주입합니다.")
            device.shell(f"input tap {tx} {ty}")
            time.sleep(1.5)
            return True
            
        time.sleep(0.1)
        
    print("⚠️ [chest_opener] 캐릭터 선택창 진입 또는 판정에 실패했습니다.")
    return False