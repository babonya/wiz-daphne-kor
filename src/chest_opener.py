# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.16.0
# - 최근 수정일: 2026-07-29 08:05
# - 수정 기록:
#   [미릴리즈] (2026-09-25): '누가 열 거야?'(who_open.png)가 실제로 보인 프레임에서만 슬롯 선택(예전엔 '열다'
#     소멸 첫 프레임에 블라인드 탭), 슬롯 선택을 select_opener_slot()으로 분리, '열다' 판정 ROI(YEOLDA_ROI).
#   1.16.0: 상자 대화창 우하단 화살표 감지 터치 개편, 공포 팝업 연계 자가 복구, templates/chestopening/ 하위로 리소스 이동에 따른 버전 동기화
#   1.15.0: 지정 슬롯 따개 선택 도입, 상자공포(chestfear) 그레이스케일/컬러 감지 및 우회 알고리즘 추가
#           (whowillopenit 템플릿 의존성 제거 및 '열다' 버튼 소멸 기반 진입 판정 전격 전환)
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image
from screen_capture import capture_screen_bytes, decode_screen_bytes

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

# 🩸 [2026-08-16 피장막 관통] dungeon_bot.check_template_present_multipass와 동일한 취지.
# 주인공 빈사 시 붉은 피안개가 씌워지면 흰 글씨의 그레이스케일 밝기가 통째로 내려앉아
# 고정 이진화 문턱 160에서는 글씨가 지워진 채 매칭된다(실측: 안개 화면 텍스트 영역 최대 밝기 165).
# 여러 문턱으로 시도해 하나라도 판정선을 넘으면 인정한다(판정 신뢰도는 그대로 유지).
FOG_BIN_PASSES = (160, 100, 85)

def check_text_by_user_template(img_np, thresh_temp, threshold_val=0.68, bin_passes=FOG_BIN_PASSES):
    """ 도장 뼈대 대조 공통 함수 (피장막 대응 다중 이진화 패스) """
    if thresh_temp is None or img_np is None: return False
    h_img, w_img = img_np.shape[:2]
    h_temp, w_temp = thresh_temp.shape[:2]
    if h_img < h_temp or w_img < w_temp: return False

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    for bin_th in bin_passes:
        _, thresh_img = cv2.threshold(gray_img, bin_th, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > threshold_val:
            return True
    return False

# 📦 [2026-09-25 ROI] 상자 선택지 "열다" 버튼 자리. 실측(dev/ROI_check/상자1_열다 (1).png, 피안개 3장, logs 실전
# 스샷 4장 - 전부 도장 좌상단 (664,1990), 도장 114x56)에 여백을 둔 영역. 전체화면으로 찾던 시절엔 행상인 대화
# 화면의 다른 글자가 0.689로 판정선(0.65)을 넘었다(ROADMAP 17). ROI 안 최고 오탐은 캠핑 "쉰다" 0.604.
YEOLDA_ROI = (550, 1850, 900, 2150)  # (x1, y1, x2, y2)

def check_yeolda_in_roi(img_np, thresh_temp, threshold_val=0.70, bin_passes=FOG_BIN_PASSES):
    """ '열다' 버튼 자리(YEOLDA_ROI)만 잘라 피장막 대응 다중 이진화로 대조 """
    if thresh_temp is None or img_np is None: return False
    x1, y1, x2, y2 = YEOLDA_ROI
    if img_np.shape[0] < y2 or img_np.shape[1] < x2: return False
    return check_text_by_user_template(img_np[y1:y2, x1:x2], thresh_temp, threshold_val, bin_passes)

# 👤 [2026-09-25] "누가 열 거야?" 캐릭터 선택창 제목(사용자 제작 도장 who_open.png, 원본 상자1_열다 (2).png).
# 실측: 이 화면 8장(피안개 3장 포함) 그레이스케일 0.999~1.000 @ (512,1493) 고정 / 다른 화면 최고 0.487.
# 도장(396x81) 둘레에 여백 50~60px을 둔 ROI만 본다.
WHO_OPEN_ROI = (450, 1440, 970, 1630)  # (x1, y1, x2, y2)
_t_who_open = None

def is_who_open_screen(img_np, threshold_val=0.80):
    """ 지금 화면이 '열다' 다음의 캐릭터 선택창("누가 열 거야?")인지 판별 """
    global _t_who_open
    if _t_who_open is None:
        _t_who_open = load_grayscale_template("templates/chestopening/who_open.png")
    if _t_who_open is None or img_np is None: return False
    x1, y1, x2, y2 = WHO_OPEN_ROI
    if img_np.shape[0] < y2 or img_np.shape[1] < x2: return False
    crop = img_np[y1:y2, x1:x2]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if len(crop.shape) == 3 else crop
    result = cv2.matchTemplate(gray_crop, _t_who_open, cv2.TM_CCOEFF_NORMED)
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
    t_trap_anchor = load_grayscale_template("templates/chestopening/trap_minigame_anchor.png")
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
        
    print("⏳ 15연타 난사 완료. 정산창 연출 진입을 위해 0.3초 대기합니다...")
    time.sleep(0.3)
    return True

def select_opener_slot(device, img_np, chest_opener_slot=6, masked_adventurer_slot=4):
    """
    캐릭터 선택창("누가 열 거야?")이 떠 있는 화면(img_np)에서 상자공포를 피해 따개 슬롯을 골라 터치한다.
    우선순위: 지정 따개 -> 주인공 -> 공포 없는 아무나(1~6번 순) -> 전원 공포면 주인공.
    (open_and_disarm_chest 안에 있던 로직을 그대로 옮김 - 매크로가 이 화면에서 시작한 경우에도 재사용하려고 분리)
    """
    # dungeon_bot 메인 루프의 화면은 4채널(RGBA)이라 3채널 상자공포 컬러 도장과 matchTemplate 타입이 안 맞는다
    # (cv2.error). 예전엔 이 로직이 자기가 다시 찍은 3채널 화면만 썼기 때문에 드러나지 않았음.
    if img_np is not None and len(img_np.shape) == 3 and img_np.shape[2] == 4:
        img_np = img_np[:, :, :3]
    t_chestfear = load_color_template("templates/chestfear.png")
    chosen_slot = None
    fear_on_primary = False

    # 1. 1순위: 지정 따개 슬롯에 상자공포 상태이상 검사
    if t_chestfear is not None:
        x1, y1, x2, y2 = SLOT_ROIS[chest_opener_slot]
        if check_color_template_present_in_roi(img_np, t_chestfear, x1, y1, x2, y2, 0.78):
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
        if check_color_template_present_in_roi(img_np, t_chestfear, x1, y1, x2, y2, 0.78):
            print(f"⚠️ [chest_opener] 2순위 주인공({masked_adventurer_slot}번) 역시 '상자 공포'가 검출되었습니다!")

            # 3. 3순위: 1~6번 슬롯 순차 스캔하여 공포가 없는 캐릭터 찾기
            for slot in [1, 2, 3, 4, 5, 6]:
                sx1, sy1, sx2, sy2 = SLOT_ROIS[slot]
                if not check_color_template_present_in_roi(img_np, t_chestfear, sx1, sy1, sx2, sy2, 0.78):
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

    tx, ty = get_slot_center(chosen_slot)
    print(f"👉 [chest_opener] 최종 결정: {chosen_slot}번 카드 슬롯 ({tx}, {ty}) 터치를 주입합니다.")
    device.shell(f"input tap {tx} {ty}")
    time.sleep(1.5)
    return True

def open_and_disarm_chest(device, img_np, thresh_yeolda, chest_opener_slot=6, masked_adventurer_slot=4):
    """
    [dungeon_bot 연동용 핵심 함수]
    '열다' 터치부터 상자공포 상태이상 회피 및 지정 슬롯 클릭까지 진행합니다.
    """
    height, width = img_np.shape[:2]

    # 매크로가 이미 캐릭터 선택창 위에서 호출된 경우('열다'는 이미 눌린 상태) 바로 슬롯만 고른다.
    if is_who_open_screen(img_np):
        print("👤 [chest_opener] 이미 캐릭터 선택창('누가 열 거야?')입니다 - '열다' 없이 슬롯 선택으로 바로 진행합니다.")
        return select_opener_slot(device, img_np, chest_opener_slot, masked_adventurer_slot)

    # [1단계] '열다' 버튼을 발견 즉시 터치
    print("🔥 [chest_opener] '열다' 버튼 포착! 상자 오픈을 시도합니다.")
    open_x = int(width * 0.5)
    open_y = int(height * 0.795)
    device.shell(f"input tap {open_x} {open_y}")
    time.sleep(1.0) # 캐릭터 선택창 애니메이션 대기

    # 🚨 [2026-09-25] 예전엔 "'열다'가 사라진 첫 프레임"을 곧바로 캐릭터 선택창으로 간주하고 슬롯을 눌렀다 -
    # 창이 뜨는 도중의 과도기 프레임이거나 다른 화면이어도 슬롯 좌표를 블라인드로 탭하고, 상자공포 검사도 그
    # 프레임으로 했다. 이제 "누가 열 거야?" 제목(who_open.png)이 실제로 보인 프레임에서만 슬롯을 고른다.
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
            # 🚨 [2026-09-09] 이 자리만 다른 파일과 달리 cv2.imdecode(IMREAD_COLOR)+BGR2RGB로 3채널을
            # 직접 만들던 특수 경로였다(다른 곳은 전부 4채널 RGBA). decode_screen_bytes()가 주는 4채널
            # 배열에서 알파를 잘라내면 완전히 동일한 3채널 RGB가 된다(합성 이미지 R/G/B 단색으로 두 경로의
            # 채널 순서가 정확히 일치함을 결정적 테스트로 확인 - screen_capture.py 상단 주석 참고).
            raw_cap = capture_screen_bytes(device)
            img_np_current = decode_screen_bytes(raw_cap)[:, :, :3]
        except Exception as cap_err:
            print(f"⚠️ [chest_opener] Screencap 버퍼 렉 감지: {cap_err}")
            time.sleep(0.1)
            continue

        # [2단계] 캐릭터 선택창 제목이 보이면 이 프레임으로 슬롯 선택
        if is_who_open_screen(img_np_current):
            print("👤 [chest_opener] 캐릭터 선택창('누가 열 거야?') 진입 확인! 따개 슬롯을 고릅니다.")
            return select_opener_slot(device, img_np_current, chest_opener_slot, masked_adventurer_slot)

        # 여전히 '열다' 버튼이 보인다면 터치 씹힘 재시도
        if check_yeolda_in_roi(img_np_current, thresh_yeolda, 0.70):
            if time.time() - last_click_yeolda_time > 1.5:
                print("⚠️ [chest_opener] '열다' 터치 씹힘 감지! 재클릭을 주입합니다.")
                device.shell(f"input tap {open_x} {open_y}")
                last_click_yeolda_time = time.time()

        time.sleep(0.1)

    print("⚠️ [chest_opener] 5초 안에 캐릭터 선택창('누가 열 거야?')이 확인되지 않아 슬롯 선택을 보류합니다.")
    return False
