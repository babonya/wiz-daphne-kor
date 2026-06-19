# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 18.11.1 (Stable)
# - 최근 수정일: 2026-06-17 10:15
# - 수정 기록:
#   v18.03: trap_minigame_anchor.png 및 해제 Y좌표 보정 적용 (최초 버전 주석 도입)
#   v18.07: 따개 멀티 템플릿(disarmer_*.png) 자동 스왑 및 다이내믹 좌표 터치 시스템 도입
#   v18.09: 힐러/따개 템플릿 로딩 시 sorted() 정렬 적용 (알파벳 정렬 우선순위 제공)
#   v18.10: 힐러 시스템 예약 파일 차단 필터 적용 대응 (동기화)
#   18.11.0: 던전 탈출 정체 시 3번 체크포인트 복구 대응 및 SemVer 시맨틱 버전 표기 도입
#   18.11.1: '열다' 터치 씹힘 재시도 및 따개 오탐 방지 소멸 가드 장착
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image

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

def check_text_by_user_template(img_np, thresh_temp, threshold_val=0.68):
    """ 도장 뼈대 대조 공통 함수 """
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def check_gray_template_present(img_np, gray_temp, threshold_val=0.70):
    if gray_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def is_minigame_screen(img_np, height, width):
    """ 미니게임 상단 붉은상자+해골마크 앵커 존재 여부 감지 """
    t_trap_anchor = load_grayscale_template("templates/trap_minigame_anchor.png")
    if t_trap_anchor is None:
        # 안전 가드: 앵커 이미지 분실 시 기존 1픽셀 RGB 판정 차선책 가동
        orange_y = int(height * 0.07)
        orange_x = int(width * 0.23)
        orange_r, orange_g, _ = img_np[orange_y, orange_x][:3]
        return orange_r > 170 and orange_g > 85
        
    return check_gray_template_present(img_np, t_trap_anchor, 0.70)


def load_multiple_templates(directory, prefix):
    import glob
    import os
    templates = []
    pattern = os.path.join(directory, f"{prefix}*.png")
    for file_path in sorted(glob.glob(pattern)):
        temp = load_template(file_path)
        if temp is not None:
            templates.append((os.path.basename(file_path), temp))
    return templates

def find_template_coords(img_np, thresh_temp, threshold_val=0.75):
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def open_and_disarm_chest(device, img_np, thresh_yeolda, thresh_milana):
    """
    [dungeon_bot 연동용 핵심 함수]
    '열다' 터치부터 따개 선택까지 한 번에 관통합니다.
    """
    height, width = img_np.shape[:2]
    
    # [1단계] '열다' 버튼을 발견 즉시 터치
    print("🔥 [chest_opener] '열다' 버튼 포착! 상자 오픈을 시도합니다.")
    open_x = int(width * 0.5)
    open_y = int(height * 0.795) 
    device.shell(f"input tap {open_x} {open_y}")
    time.sleep(1.2) # 캐릭터 선택창 애니메이션 대기
    
    # 디렉토리 내 모든 disarmer_*.png 템플릿 로드
    disarmer_templates = load_multiple_templates("templates", "disarmer_")
    
    # 선택창이 뜰 때까지 최대 5초간 화면 갱신하며 따개 추적
    start_time = time.time()
    last_click_yeolda_time = time.time()
    while time.time() - start_time < 5.0:
        try:
            raw_cap = device.screencap()
            img_np_current = cv2.imdecode(np.frombuffer(raw_cap, np.uint8), cv2.IMREAD_COLOR)
            img_np_current = cv2.cvtColor(img_np_current, cv2.COLOR_BGR2RGB)
        except:
            time.sleep(0.1)
            continue
            
        # [가드] 화면에 '열다' 버튼이 아직 보인다면 캐릭터 선택창에 못 들어온 상태임
        if check_text_by_user_template(img_np_current, thresh_yeolda, 0.70):
            # 1.5초 이상 화면이 머무르면 터치가 씹힌 것이므로 재시도 주입
            if time.time() - last_click_yeolda_time > 1.5:
                print("⚠️ [chest_opener] '열다' 터치 씹힘 감지! 재클릭을 주입합니다.")
                device.shell(f"input tap {open_x} {open_y}")
                last_click_yeolda_time = time.time()
            time.sleep(0.1)
            continue
            
        # [2단계] 등록된 따개 이름 도장 매칭 및 다이내믹 클릭
        if len(disarmer_templates) > 0:
            for file_name, thresh_disarmer in disarmer_templates:
                coords = find_template_coords(img_np_current, thresh_disarmer, 0.75)
                if coords:
                    dx, dy = coords
                    print(f"👤 [chest_opener] '{file_name}' 도장 검출 완료! 좌표 ({dx}, {dy}) 터치합니다.")
                    device.shell(f"input tap {dx} {dy}")
                    time.sleep(1.5) # 미니게임 혹은 정산창 전환 대기
                    return True
        else:
            # 하방 호환용 폴백 (기존 6번 슬롯 강제 터치)
            if check_text_by_user_template(img_np_current, thresh_milana, 0.75):
                print("👤 [chest_opener] '밀라나' 도장 검출 완료! 카드를 터치합니다.")
                milana_x = int(width * 0.76)
                milana_y = int(height * 0.855)
                device.shell(f"input tap {milana_x} {milana_y}")
                time.sleep(1.5) # 미니게임 혹은 정산창 전환 대기
                return True
            
        time.sleep(0.1)
        
    print("⚠️ [chest_opener] 따개 선택창 진입에 실패했습니다.")
    return False


def solve_trap_game(device, img_np):
    """ 
    [에러 1 완벽 정복 - 무지성 고속 연타 사양]
    타이밍 게이트 분석을 생략하고, 화면 하단 정중앙 '해제' 구역을
    0.1초 간격으로 15연타 무지성 폭격한 뒤 안전 연출 시간을 벌어줍니다.
    """
    print("🔮 [chest_opener] 미니게임 인카운터! 게이트 스캔을 스킵하고 0.1초 간격 15연타 초고속 폭격을 주입합니다.")
    height, width = img_np.shape[:2]
    
    # 해제/터치 버튼이 위치한 화면 정중앙 하단 고정 좌표 (실해상도 725/1440, 1565/2560 반영)
    release_x = int(width * 0.503)
    release_y = int(height * 0.611)
    
    # 0.1초 간격으로 무지성 15연타 난사
    for _ in range(15):
        device.shell(f"input tap {release_x} {release_y}")
        time.sleep(0.1)
        
    print("⏳ 15연타 난사 완료. 정산창 연출 진입을 위해 5.0초간 충분히 대기합니다...")
    time.sleep(5.0)
    return True