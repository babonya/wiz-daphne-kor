# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.12.3
# - 최근 수정일: 2026-06-27 00:25
# - 수정 기록:
#   1.12.3: 버전 동기화
#   1.12.2: 버전 동기화
#   1.12.1: 마이너 버전업 - 템플릿 디렉토리 구조 다각화(Worldmap, WolfCave, Vill_Isbelg, inn_sleep) 분리 및 동적 파일명 최적화
#   1.11.16-hotfix1: 핫픽스 버전 동기화
#   v18.11.3: 여관 숙박 및 탭 동작 중 ADB 연결 장애 크래시 예외 전파 가드 탑재
#   v18.11.4: 미니게임 화면 중 재시작 시 30초 정체 대기 없이 즉각 전이 복구 가드 추가 (동기화)
#   v18.11.5: 탈출 완료 판정 오판 방지 가드에 맞춰 버전 동기화
#   v18.11.6: 여권 만료 팝업 이중 앵커 가드에 맞춰 버전 동기화
#   v1.11.7: 로딩 암전 가드, 해상도 크래시 가드, 예외 트레이스백 실시간 로깅 및 Dimension Guard 탑재 (동기화)
#   1.11.8: 4일 경과 로그 파일 자동 청소기 장착, 메인 루프 전체 이중 감시 예외 처리 보강 및 리드미 설명 개정 (동기화)
#   1.11.9: 최초 기동/재시작 자동 스샷 촬영, 스샷 동기화 스레드, 다중 사용자 경로 탐색 가드 탑재 (동기화)
#   1.11.16: 미니게임 앵커 국소 크롭 스캔 범위(X: 57~187, Y: 227~317 마진 적용) 지정 및 임계값 0.70 상향 (동기화)
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image

def safe_device_shell(device, command):
    try:
        return device.shell(command)
    except Exception as e:
        print(f"\n🌐⚠️ [inn_manager 소켓 단절] 윈도우 ADB 통신 장애 감지: {e}")
        raise e

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

def find_and_click_template(device, img_np, thresh_temp, threshold_val=0.70):
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
            click_x = max_loc[0] + int(w / 2)
            click_y = max_loc[1] + int(h / 2)
            safe_device_shell(device, f"input tap {click_x} {click_y}")
            return True
        return False
    except: return False

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

def run_inn_sleep_sequence(device):
    """
    [여관 독립 정비 모듈 - 레벨업 좌하단 닫기 픽스 사양]
    로비 진입 상태에서 호출되어 숙박/기상/레벨업 스킵 후 퇴장까지 전담합니다.
    """
    print("\n💤 [inn_manager] 여관 자동 숙박 시퀀스를 가동합니다.")
    
    # 도장 로드
    t_inn_title = load_template("templates/inn_sleep/inn_title.png")
    t_menu_stay = load_template("templates/inn_sleep/menu_stay.png")
    t_menu_leave = load_template("templates/inn_sleep/menu_leave.png")
    t_menu_standard = load_template("templates/inn_sleep/menu_standard.png")
    t_inn_confirm = load_template("templates/inn_sleep/inn_confirm_btn.png")
    t_inn_inv = load_template("templates/inn_sleep/inn_inventory_popup.png")
    t_arrow = load_template("templates/inn_sleep/arrow_clean.png")
    t_village = load_template("templates/Vill_Isbelg/village_anchor.png")

    # - 레벨업 및 스킬 팝업 관련 도장
    t_pop_levelup = load_template("templates/inn_sleep/popup_levelup_title.png")
    t_pop_skill = load_template("templates/inn_sleep/popup_skill_title.png")
    t_btn_skill = load_template("templates/inn_sleep/skill_close_btn.png")
    
    # 💡 [구조 교정] Daphne 팩트체크: 레벨업 창은 우하단 '다음'이 아니라 좌하단 '닫기' 버튼이 주범!
    t_btn_levelup_close = load_template("templates/inn_sleep/levelup_close_btn.png")

    is_fully_healed = False
    fail_safe_counter = 0

    while True:
        try:
            import sys
            if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'update_heartbeat'):
                sys.modules['__main__'].update_heartbeat()
        except:
            pass

        try:
            raw_cap = device.screencap()
            img_np = np.array(Image.open(io.BytesIO(raw_cap)))
        except:
            time.sleep(0.3)
            continue
            
        height, width = img_np.shape[:2]

        # -------------------------------------------------------------
        # 0순위. 레벨업 및 스킬 습득 조건부 무한 루프 스킵 제어
        # -------------------------------------------------------------
        if check_template_present(img_np, t_pop_levelup, 0.75):
            # 💡 [버그 소멸] 새로 제작하신 levelup_close_btn을 찾아 좌하단을 정교하게 타격합니다.
            print("📈 [inn_manager] 캐릭터 '레벨 업!' 창 포착 -> 좌하단 'X 닫기' 버튼을 정밀 조준 사격합니다.")
            if find_and_click_template(device, img_np, t_btn_levelup_close, 0.70):
                time.sleep(0.8)
            continue

        elif check_template_present(img_np, t_pop_skill, 0.75):
            print("✨ [inn_manager] 새로운 '능력 획득!' 창 포착 -> 중앙 하단 '탭하여 닫기' 버튼 타격")
            if find_and_click_template(device, img_np, t_btn_skill, 0.70):
                time.sleep(0.8)
            continue

        # -------------------------------------------------------------
        # 1순위. 고정 숙박 연쇄 팝업 처리 구간
        # -------------------------------------------------------------
        if check_template_present(img_np, t_inn_confirm, 0.70):
            print("🛑 [inn_manager] 숙박 최종 확인 창 -> '확인' 클릭")
            if find_and_click_template(device, img_np, t_inn_confirm, 0.70):
                print("⏳ 취침 연출 암전 진입... 5.5초 안전 대기 주입")
                time.sleep(5.5)
            continue

        elif check_template_present(img_np, t_inn_inv, 0.70):
            print("📦 [inn_manager] 소지품 정리 팝업 -> 화면 정중앙 터치 스킵")
            safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.5)}")
            time.sleep(1.0)
            continue

        elif check_template_present(img_np, t_arrow, 0.72):
            if not check_template_present(img_np, t_inn_title, 0.80):
                print("📐 [inn_manager] 기상 대화창 황금 화살표 -> 스킵 터치 주입")
                find_and_click_template(device, img_np, t_arrow, 0.72)
                is_fully_healed = True  
                time.sleep(0.8)
                continue

        # -------------------------------------------------------------
        # 2순위. 여관 기본 로비 및 메뉴 제어 구간 (무한 숙박 차단)
        # -------------------------------------------------------------
        elif check_template_present(img_np, t_inn_title, 0.83):
            if check_template_present(img_np, t_menu_stay, 0.70) and not is_fully_healed:
                print("🧾 [inn_manager] 로비 진입 -> '묵는다' 터치")
                find_and_click_template(device, img_np, t_menu_stay, 0.70)
                time.sleep(1.0)
            
            elif check_template_present(img_np, t_menu_standard, 0.70):
                print("🛏️ [inn_manager] 방 선택 메뉴 -> '스탠다드 룸' 터치")
                find_and_click_template(device, img_np, t_menu_standard, 0.70)
                time.sleep(1.0)

            elif check_template_present(img_np, t_menu_leave, 0.70) and is_fully_healed:
                print("🚪 [inn_manager] 로비 복귀 완료! '밖으로 나간다' 터치하여 여관을 나갑니다.")
                if find_and_click_template(device, img_np, t_menu_leave, 0.70):
                    time.sleep(2.0)
            continue

        # -------------------------------------------------------------
        # 3순위. 최종 탈출 조건 (마을 광장 복귀 성공 시 모듈 파기)
        # -------------------------------------------------------------
        elif check_template_present(img_np, t_village, 0.83):
            print("✨ [inn_manager] 마을 광장 복귀 성공! 여관 모듈을 안전하게 종료합니다.\n")
            break

        # 예외 가드 카운터
        fail_safe_counter += 1
        if fail_safe_counter > 150:
            print("⚠️ [inn_manager] 예외 정체 발생으로 강제 이탈합니다.")
            break
            
        time.sleep(0.3)