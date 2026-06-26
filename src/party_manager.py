# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.11.9 (Stable)
# - 최근 수정일: 2026-06-24 18:20
# - 수정 기록:
#   v18.07: 힐러 멀티 템플릿(healer_*.png) 자동 스왑 검출 시스템 도입
#   v18.09: 힐러/따개 템플릿 로딩 시 sorted() 정렬 적용 (알파벳 정렬 우선순위 제공)
#   v18.10: 힐러 도장 로드 시 healer_auto_btn.png 등 시스템 예약 파일 자동 제외 필터링 추가
#   18.11.0: 던전 탈출 정체 시 3번 체크포인트 복구 대응 및 SemVer 시맨틱 버전 표기 도입
#   18.11.1: '열다' 터치 씹힘 재시도 및 갇힘 복구 대응 (동기화)
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

def load_grayscale_template(file_path):
    import os
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        return gray
    except: return None

def load_multiple_grayscale_templates(directory, prefix):
    import glob
    import os
    templates = []
    pattern = os.path.join(directory, f"{prefix}*.png")
    # healer_auto_btn.png와 healer_name.png는 시스템 예약 파일이므로 캐릭터 목록에서 제외
    excluded_files = {"healer_auto_btn.png", "healer_name.png"}
    for file_path in sorted(glob.glob(pattern)):
        filename = os.path.basename(file_path)
        if filename in excluded_files:
            continue
        temp = load_grayscale_template(file_path)
        if temp is not None:
            templates.append((filename, temp))
            
    # 하방 호환성
    legacy_path = os.path.join(directory, "healer_name.png")
    if os.path.exists(legacy_path) and not any(t[0] == "healer_name.png" for t in templates):
        temp = load_grayscale_template(legacy_path)
        if temp is not None:
            templates.append(("healer_name.png", temp))
    return templates


def check_gray_template_present(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_gray_coords(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None: return None
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = gray_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def run_party_healing_sequence(device, t_healer_name, t_auto_btn, t_close_btn, dummy_var=None):
    print("💊 [party_manager] 정비 레이더 가동... 주변 상황 교차 검증을 시작합니다.")

    g_healer_name = load_grayscale_template("templates/healer_name.png")
    g_auto_btn = load_grayscale_template("templates/healer_auto_btn.png")
    g_confirm_btn = load_grayscale_template("templates/confirm_recover.png")
    g_close_btn = load_grayscale_template("templates/close_panel.png")

    g_yeolda = load_grayscale_template("templates/yeolda_clean.png")
    g_auto_on = load_grayscale_template("templates/auto_on.png")
    g_speed_on = load_grayscale_template("templates/speed_on.png")
    g_field = load_grayscale_template("templates/field_anchor.png")

    enter_success = False
    
    for retry in range(1, 6):
        try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
        except:
            time.sleep(0.3)
            continue

        # 💡 [데드락 완파 핵심 가드 블록 1]
        # 정비창 진입 시도 도중 몬스터 기습이나 상자가 열려 인터럽트가 발생했다면,
        # 그냥 탈출하지 않고 확실하게 "치료 실패했다(False)"고 보고서를 반환합니다!
        if check_gray_template_present(img_np, g_yeolda, 0.65) or check_gray_template_present(img_np, g_auto_on, 0.75) or check_gray_template_present(img_np, g_speed_on, 0.75):
            print("🚨 [party_manager 인터럽트] 상자 또는 전투 기습 포착!! 시퀀스를 긴급 폐쇄합니다.")
            return False

        is_auto_btn_visible = check_gray_template_present(img_np, g_auto_btn, 0.81)
        is_close_btn_visible = check_gray_template_present(img_np, g_close_btn, 0.81)

        if is_auto_btn_visible or is_close_btn_visible:
            print(f"✅ [party_manager] 리얼 힐러 창 내부 진입 무결점 검증 성공!")
            enter_success = True
            break
            
        # 등록된 힐러 도장 목록 중 하나라도 화면에 매칭되는지 동적 탐색
        healer_templates = load_multiple_grayscale_templates("templates", "healer_")
        coords = None
        for file_name, g_healer in healer_templates:
            coords = find_gray_coords(img_np, g_healer, 0.72)
            if coords:
                print(f"🎯 [party_manager] 힐러 '{file_name}' 도장 검출 성공! 좌표: {coords}")
                break
                
        if coords:
            hx, hy = coords
            print(f"🎯 [party_manager] 힐러 캐릭터 관리 마크 포착 ({hx}, {hy}) 터치 주입... ({retry}/5)")
            device.shell(f"input tap {hx} {hy}")
            time.sleep(0.8) 
        else:
            time.sleep(0.3)

    if not enter_success:
        print("⚠️ [party_manager 안전 가드] 힐러방 내부 안착 실패 판정. 필드 오인 사격을 차단하기 위해 복귀합니다.\n")
        return False

    # [단계] 자동힐 터치
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return False

    auto_coords = find_gray_coords(img_np, g_auto_btn, 0.75) 
    if auto_coords:
        ax, ay = auto_coords
        device.shell(f"input tap {ax} {ay}")
        print(f"⚡ [party_manager] 별 모양 '자동힐' 버튼 ({ax}, {ay}) 타격 성공!")
        time.sleep(0.7)
    else:
        print("⚡ [party_manager] 별 마크 미검출. 엘리스 기본 고정 좌표(1344, 1351) 사격.")
        device.shell("input tap 1344 1351")
        time.sleep(0.7)

    # [단계] 일괄회복 최종 승인 터치
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return False

    h, w = img_np.shape[:2]
    confirm_coords = find_gray_coords(img_np, g_confirm_btn, 0.75)
    
    if confirm_coords:
        cx, cy = confirm_coords
        device.shell(f"input tap {cx} {cy}")
        print("🔥 [party_manager] '회복한다' 팝업 승인 완료!")
        print("⏳ 힐 연출 및 화면 암전 대기... 무조건 6초간 정지합니다.")
        time.sleep(6.0)
    else:
        print("🔍 [party_manager 검증] '회복한다' 버튼 미포착. 실제 필드 복귀 유무 및 만피 상태를 재검증합니다...")
        if check_gray_template_present(img_np, g_field, 0.65):
            print("   ➔ ✨ 확인 결과: 이미 정상 필드입니다. 정비 시퀀스를 즉시 안전 종료합니다.")
            return True

    # [단계] 캐릭터 창 "닫기" 필드 복귀
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return True

    close_coords = find_gray_coords(img_np, g_close_btn, 0.75)
    if close_coords:
        lx, ly = close_coords
        device.shell(f"input tap {lx} {ly}")
        print("🚪 [party_manager] '닫기' 버튼 터치 완료.")
        time.sleep(1.0)
    else:
        if not check_gray_template_present(img_np, g_field, 0.65):
            print("⚠️ [party_manager] '닫기' 버튼 미포착 및 힐러방 상태 유지 확인. 좌측 X 닫기 강제 좌표 사격.")
            device.shell("input tap 75 1940")
            time.sleep(1.0)

    print("✨ [party_manager] 파티 정비 시퀀스 종료. 메인으로 복귀합니다.\n")
    # 💡 모든 힐 관문을 온전하게 완수했으므로 완벽한 치료 증명서(True) 발행!
    return True