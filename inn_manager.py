import time
import io
import cv2
import numpy as np
from PIL import Image

def check_template_present(img_np, thresh_temp, threshold_val=0.70):
    if thresh_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_and_click_template(device, img_np, thresh_temp, threshold_val=0.70):
    if thresh_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh_img = cv2.threshold(gray_img, 160, 255, cv2.THRESH_BINARY)
    result = cv2.matchTemplate(thresh_img, thresh_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    
    if max_val > threshold_val:
        h, w = thresh_temp.shape[:2]
        click_x = max_loc[0] + int(w / 2)
        click_y = max_loc[1] + int(h / 2)
        device.shell(f"input tap {click_x} {click_y}")
        return True
    return False

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
    t_inn_title = load_template("templates/inn_title.png")
    t_menu_stay = load_template("templates/menu_stay.png")
    t_menu_leave = load_template("templates/menu_leave.png")
    t_menu_standard = load_template("templates/menu_standard.png")
    t_inn_confirm = load_template("templates/inn_confirm_btn.png")
    t_inn_inv = load_template("templates/inn_inventory_popup.png")
    t_arrow = load_template("templates/arrow_clean.png")
    t_village = load_template("templates/village_anchor.png")

    # 레벨업 및 스킬 팝업 관련 도장
    t_pop_levelup = load_template("templates/popup_levelup_title.png")
    t_pop_skill = load_template("templates/popup_skill_title.png")
    t_btn_skill = load_template("templates/skill_close_btn.png")
    
    # 💡 [구조 교정] Daphne 팩트체크: 레벨업 창은 우하단 '다음'이 아니라 좌하단 '닫기' 버튼이 주범!
    t_btn_levelup_close = load_template("templates/levelup_close_btn.png")

    is_fully_healed = False
    fail_safe_counter = 0

    while True:
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
            device.shell(f"input tap {int(width * 0.5)} {int(height * 0.5)}")
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
            if check_template_present(img_np, t_menu_stay, 0.75) and not is_fully_healed:
                print("🧾 [inn_manager] 로비 진입 -> '묵는다' 터치")
                find_and_click_template(device, img_np, t_menu_stay, 0.75)
                time.sleep(1.0)
            
            elif check_template_present(img_np, t_menu_standard, 0.75):
                print("🛏️ [inn_manager] 방 선택 메뉴 -> '스탠다드 룸' 터치")
                find_and_click_template(device, img_np, t_menu_standard, 0.75)
                time.sleep(1.0)

            elif check_template_present(img_np, t_menu_leave, 0.75) and is_fully_healed:
                print("🚪 [inn_manager] 로비 복귀 완료! '밖으로 나간다' 터치하여 여관을 나갑니다.")
                if find_and_click_template(device, img_np, t_menu_leave, 0.75):
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