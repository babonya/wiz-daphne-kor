# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.12.3
# - 최근 수정일: 2026-06-27 00:25
# - 수정 기록:
#   1.12.3: 버전 동기화
#   1.12.2: 템플릿 로딩 자연 정렬(Natural Sort) 도입 및 버전 동기화
#   1.12.1: 마이너 버전 동기화
#   1.11.16: 미니게임 앵커 국소 크롭 스캔 범위 지정 및 임계값 0.70 상향 (동기화)
#   v18.03: trap_minigame_anchor.png 및 해제 Y좌표 보정 적용 (최초 버전 주석 도입)
#   v18.07: 따개 멀티 템플릿(disarmer_*.png) 자동 스왑 및 다이내믹 좌표 터치 시스템 도입
#   v18.09: 힐러/따개 템플릿 로딩 시 sorted() 정렬 적용 (알파벳 정렬 우선순위 제공)
#   v18.10: 힐러 시스템 예약 파일 차단 필터 적용 대응 (동기화)
#   18.11.0: 던전 탈출 정체 시 3번 체크포인트 복구 대응 및 SemVer 시맨틱 버전 표기 도입
#   18.11.1: '열다' 터치 씹힘 재시도 및 따개 오탐 방지 소멸 가드 장착
#   18.11.2: 캐릭터 선택창('누가 열 거야?') 정체 복구 가드 탑재 (동기화)
#   18.11.3: 여관 정비 시퀀스 중 ADB 통신 장애 크래시 자가 복구 가드 추가 (동기화)
#   18.11.4: 미니게임 화면 중 재시작 시 30초 정체 대기 없이 즉각 전이 복구 가드 추가 (동기화)
#   18.11.5: 탈출 완료 판정 오판 방지 가드에 맞춰 버전 동기화
#   18.11.6: 여권 만료 팝업 이중 앵커 가드에 맞춰 버전 동기화
#   1.11.7: 로딩 암전 가드, 해상도 크래시 가드, 예외 트레이스백 실시간 로깅 및 Dimension Guard 탑재 (동기화)
#   1.11.8: 4일 경과 로그 파일 자동 청소기 장착, 메인 루프 전체 이중 감시 예외 처리 보강 및 리드미 설명 개정 (동기화)
#   1.11.9: 최초 기동/재시작 자동 스샷 촬영, 스샷 동기화 스레드, 다중 사용자 경로 탐색 가드 탑재 (동기화)
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

def is_minigame_screen(img_np, height, width):
    """ 미니게임 상단 붉은상자+해골마크 앵커 존재 여부 감지 (v1.11.16) """
    # 1. 템플릿 매칭 검출 (제보받은 X: 57~187, Y: 227~317에 20px 마진을 더해 크롭 매칭)
    t_trap_anchor = load_grayscale_template("templates/trap_minigame_anchor.png")
    if t_trap_anchor is not None and img_np is not None:
        h_img, w_img = img_np.shape[:2]
        
        # 1440x2560 해상도 비례 스케일링 계산
        scale_x = w_img / 1440.0
        scale_y = h_img / 2560.0
        
        # X: 57~187 => 37~207, Y: 227~317 => 207~337 (마진 20px 적용)
        x1, x2 = int(37 * scale_x), int(207 * scale_x)
        y1, y2 = int(207 * scale_y), int(337 * scale_y)
        
        # 경계 처리
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w_img, x2)
        y2 = min(h_img, y2)
        
        if x1 < x2 and y1 < y2:
            crop_img = img_np[y1:y2, x1:x2]
            h_crop, w_crop = crop_img.shape[:2]
            h_temp, w_temp = t_trap_anchor.shape[:2]
            
            if h_crop >= h_temp and w_crop >= w_temp:
                gray_crop = cv2.cvtColor(crop_img, cv2.COLOR_RGB2GRAY)
                result = cv2.matchTemplate(gray_crop, t_trap_anchor, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                # 매칭 점수가 0.50을 초과하는 진성 매칭이거나 성공 판정 시에만 디버그 출력
                if max_val > 0.50:
                    print(f"🔍 [디버그] 미니게임 앵커 로드 완료. 현재 매칭 신뢰도(score): {max_val:.4f} (기준치: 0.70)")
                    
                if max_val > 0.70:
                    return True
                
    # 2. RGB 색상 감지 멀티스팟 이중 가드 (11.4 방식 + 3중 스팟 교차 검증)
    # 주황색 게이지바가 상단 Y: 7% 근처에 위치하므로, X축 23%, 50%, 77% 총 3지점을 교차 스캔
    orange_y = int(height * 0.07)
    orange_spots = [int(width * 0.23), int(width * 0.50), int(width * 0.77)]
    orange_count = 0
    for ox in orange_spots:
        if orange_y < height and ox < width:
            r, g, b = img_np[orange_y, ox][:3]
            # 주황/노란색 계열 게이지 바 색상 판정
            if r > 160 and g > 75 and b < 60:
                orange_count += 1
                
    if orange_count >= 2:
        print(f"🎮 [디버그] 미니게임 앵커 미검출 되었으나, RGB 게이지 색상 3중 가드 감지 성공! (포착 수: {orange_count}/3)")
        return True
        
    return False


def natural_sort_key(s):
    import re
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def load_multiple_templates(directory, prefix):
    import glob
    import os
    templates = []
    pattern = os.path.join(directory, f"{prefix}*.png")
    for file_path in sorted(glob.glob(pattern), key=natural_sort_key):
        temp = load_template(file_path)
        if temp is not None:
            templates.append((os.path.basename(file_path), temp))
    return templates

def find_template_coords(img_np, thresh_temp, threshold_val=0.75):
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

def open_and_disarm_chest(device, img_np, thresh_yeolda):
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
    disarmer_templates = load_multiple_templates("templates/!!Character", "disarmer_")
    
    # 선택창이 뜰 때까지 최대 5초간 화면 갱신하며 따개 추적
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
        
    print("⏳ 15연타 난사 완료. 정산창 연출 진입을 위해 1.0초간 충분히 대기합니다...")
    time.sleep(1.0)
    return True