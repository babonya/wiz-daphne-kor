# -*- coding: utf-8 -*-
# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.14.1-hotfix10
# - 최근 수정일: 2026-07-26 22:45
# - 수정 기록:
#   1.14.1-hotfix10: 버전 동기화
#   1.14.1-hotfix9: 버전 동기화
#   1.14.1-hotfix8: 버전 동기화
#   1.14.1-hotfix7: 독 감지 기능 탈거에 따른 버전 동기화
#   1.14.1-hotfix6: 힐러 도장 이진화 매칭/캐싱 적용, 정지 지연 단축(0.1초), 하단 캐릭터 ROI 적용, 정상 스캔 선제 처리 및 1차 실패 시 2차 red 도장(임계값 60) 예외 탐색 분리 적용, red 감지 시 진입 대기(1.5초) 주입
#   1.13.20-hotfix1: 버전 동기화
#   1.13.20: 버전 동기화
#   1.13.19-hotfix2: 버전 동기화
#   1.13.19-hotfix1: 버전 동기화
#   1.13.19: 버전 동기화
#   1.13.18: 버전 동기화
#   1.13.17: 버전 동기화
#   1.13.16: 버전 동기화
#   1.13.7: 버전 동기화
#   1.13.6: 버전 동기화
#   1.13.5: 버전 동기화
#   1.13.4: 버전 동기화
#   1.13.3: 버전 동기화
#   1.13.2: 버전 동기화
#   1.13.1: 버전 동기화
#   1.13.0-hotfix4: 핫픽스 버전 동기화
#   1.13.0-hotfix3: 핫픽스 버전 동기화
#   1.13.0-hotfix2: 핫픽스 버전 동기화
#   1.13.0-hotfix1: 핫픽스 버전 동기화
#   1.13.0: 마이너 버전 동기화
#   1.12.6: 여관 정비 시 멀티 레벨업 '다음' 팝업 처리 구현 및 실시간 타임스탬프 로깅 래퍼 함수 도입
#   1.12.5: 탈출 정체 복구 카운트 리셋 오류 패치, 블랙박스 및 탈출 정지 최초 정체 시각 표기 추가 및 버전업
#   1.12.4: 힐러방 딸피 암전 시 블라인드 고정좌표 힐 시퀀스 핫픽스 적용 및 버전 동기화
#   1.12.3: 버전 동기화
#   1.12.2: 힐러 로딩 자연 정렬(Natural Sort) 도입, 일괄 회복 예비 좌표 대응 및 버전 동기화
#   1.12.1: 마이너 버전 동기화
#   v18.07: 힐러 멀티 템플릿(healer_*.png) 자동 스왑 검출 시스템 도입
#   v18.09: 힐러/따개 템플릿 로딩 시 sorted() 정렬 적용 (알파벳 정렬 우선순위 제공)
#   v18.10: 힐러 도장 로드 시 healer_auto_btn.png 등 시스템 예약 파일 자동 제외 필터링 추가
#   18.11.0: 던전 탈출 정체 시 3번 체크포인트 복구 대응 및 SemVer 시맨틱 버전 표기 도입
#   18.11.1: '열다' 터치 씹힘 재시도 및 갇힘 복구 대응 (동기화)
#   18.11.2: 캐릭터 선택창('누가 열 거야?') 정체 복구 가드 탑재 (동기화)
#   18.11.3: 여관 정비 시퀀스 중 ADB 통신 장애 크래시 자가 복구 가드 추가 (동기화)
#   18.11.4: 미니게임 화면 중 재시작 시 30초 정체 대기 없이 즉각 전이 복구 가드 추가 (동기화)
#   18.11.5: 여권 만료 팝업 이중 앵커 가드에 맞춰 버전 동기화
#   18.11.6: 여권 만료 팝업 이중 앵커 가드에 맞춰 버전 동기화
#   1.11.7: 로딩 암전 가드, 해상도 크래시 가드, 예외 트레이스백 실시간 로깅 및 Dimension Guard 탑재 (동기화)
#   1.11.8: 4일 경과 로그 파일 자동 청소기 장착, 메인 루프 전체 이중 감시 예외 처리 보강 및 리드미 설명 개정 (동기화)
#   1.11.9: 최초 기동/재시작 자동 스샷 촬영, 스샷 동기화 스레드, 다중 사용자 경로 탐색 가드 탑재 (동기화)
#   1.11.12: 힐러창 진입 전 안전지대 터치 및 대기 로직 추가
#   1.11.16: 미니게임 앵커 국소 크롭 스캔 범위(X: 57~187, Y: 227~317 마진 적용) 지정 및 임계값 0.70 상향 (동기화)
#   1.11.16-hotfix1: 핫픽스 버전 동기화
# ==============================================================================
import time
import io
import cv2
import numpy as np
from PIL import Image
import datetime

def print_log(msg):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if msg.startswith("\n"):
        print(f"\n[{now_str}] {msg[1:]}")
    elif msg.endswith("\n"):
        print(f"[{now_str}] {msg[:-1]}\n")
    else:
        print(f"[{now_str}] {msg}")

def load_grayscale_template(file_path):
    import os
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        return gray
    except: return None

def load_binarized_template(file_path, threshold_val=160):
    import os
    if not os.path.exists(file_path): return None
    try:
        pil_img = Image.open(file_path).convert('RGB')
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY)
        return thresh
    except: return None

def natural_sort_key(s):
    import re
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_multiple_grayscale_templates(directory, prefix):
    import glob
    import os
    templates = []
    pattern = os.path.join(directory, f"{prefix}*.png")
    for file_path in sorted(glob.glob(pattern), key=natural_sort_key):
        filename = os.path.basename(file_path)
        temp = load_grayscale_template(file_path)
        if temp is not None:
            templates.append((filename, temp))
    return templates

def load_multiple_binarized_templates(directory, prefix, default_threshold=160, red_threshold=60):
    import glob
    import os
    templates = []
    pattern = os.path.join(directory, f"{prefix}*.png")
    for file_path in sorted(glob.glob(pattern), key=natural_sort_key):
        filename = os.path.basename(file_path)
        thresh = red_threshold if "_red" in filename else default_threshold
        temp = load_binarized_template(file_path, thresh)
        if temp is not None:
            templates.append((filename, temp))
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

def find_binarized_coords_with_score(img_np, bin_temp, bin_threshold=160, roi=None):
    if bin_temp is None: return None, 0.0
    h_orig, w_orig = img_np.shape[:2]
    
    if roi:
        x_min, y_min, x_max, y_max = roi
        scale_x, scale_y = w_orig / 1440.0, h_orig / 2560.0
        rx1, ry1 = int(x_min * scale_x), int(y_min * scale_y)
        rx2, ry2 = int(x_max * scale_x), int(y_max * scale_y)
        
        # 안전한 슬라이싱을 위한 바운더리 클램핑
        rx1 = max(0, min(rx1, w_orig - 1))
        ry1 = max(0, min(ry1, h_orig - 1))
        rx2 = max(rx1 + 1, min(rx2, w_orig))
        ry2 = max(ry1 + 1, min(ry2, h_orig))
        
        cropped_img = img_np[ry1:ry2, rx1:rx2]
        gray_img = cv2.cvtColor(cropped_img, cv2.COLOR_RGB2GRAY) if len(cropped_img.shape) == 3 else cropped_img
        _, thresh_img = cv2.threshold(gray_img, bin_threshold, 255, cv2.THRESH_BINARY)
        
        result = cv2.matchTemplate(thresh_img, bin_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        h_temp, w_temp = bin_temp.shape[:2]
        coords = (rx1 + max_loc[0] + int(w_temp / 2), ry1 + max_loc[1] + int(h_temp / 2))
        return coords, max_val
    else:
        gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
        _, thresh_img = cv2.threshold(gray_img, bin_threshold, 255, cv2.THRESH_BINARY)
        result = cv2.matchTemplate(thresh_img, bin_temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        h_temp, w_temp = bin_temp.shape[:2]
        coords = (max_loc[0] + int(w_temp / 2), max_loc[1] + int(h_temp / 2))
        return coords, max_val

# ------------------------------------------------------------------------------
# 🎨 [모듈 레벨 캐싱] 정비 시퀀스 전용 템플릿 메모리 캐싱 (디스크 I/O 완전 제거)
# ------------------------------------------------------------------------------
# 정비창 고정 그레이스케일 템플릿
G_AUTO_BTN = load_grayscale_template("templates/healer_auto_btn.png")
G_CONFIRM_BTN = load_grayscale_template("templates/confirm_recover.png")
G_CLOSE_BTN = load_grayscale_template("templates/close_panel.png")
G_YEOLDA = load_grayscale_template("templates/yeolda_clean.png")
G_AUTO_ON = load_grayscale_template("templates/auto_on.png")
G_SPEED_ON = load_grayscale_template("templates/speed_on.png")
G_FIELD = load_grayscale_template("templates/field_anchor.png")

# 🏥 [캐릭터 슬롯 중심 좌표 매핑 정의]
def get_slot_coords(slot_idx):
    # 1~6번 슬롯의 물리적 정밀 중심 터치 좌표 (1440x2560 기준 실측)
    mapping = {
        1: (265, 2110),
        2: (733, 2110),
        3: (1199, 2110),
        4: (265, 2390),
        5: (733, 2390),
        6: (1199, 2390)
    }
    return mapping.get(slot_idx, (733, 2390)) # 기본값 5번 주인공/힐러 슬롯


def run_party_healing_sequence(device, t_auto_btn, t_close_btn, healer_slot=5, masked_adventurer_slot=5):
    print_log("💊 [party_manager] 정비 레이더 가동... 주변 상황 교차 검증을 시작합니다.")

    # 💡 [안전지대 강제 정지 가드] 이동 중 캐릭터 터치 씹힘 차단을 위해 선제적으로 멈춤
    print_log("💊 [party_manager] 안전지대 선제 터치(701, 333)로 캐릭터 정지를 유도합니다.")
    try:
        device.shell("input tap 701 333")
        time.sleep(0.1)
    except Exception as e:
        print_log(f"⚠️ [party_manager] 안전지대 정지 터치 실패 (무시): {e}")

    # 중복 없는 슬롯 순회 우선순위 리스트 빌드
    slot_sequence = []
    if healer_slot and healer_slot in range(1, 7):
        slot_sequence.append(healer_slot)
    if masked_adventurer_slot and masked_adventurer_slot in range(1, 7):
        if masked_adventurer_slot not in slot_sequence:
            slot_sequence.append(masked_adventurer_slot)
    for slot in [1, 2, 3, 4, 5, 6]:
        if slot not in slot_sequence:
            slot_sequence.append(slot)
            
    print_log(f"🔮 [party_manager] 힐러방 순회 스마트 탭핑 순서 결정: {slot_sequence}")

    enter_success = False
    
    for idx, slot_idx in enumerate(slot_sequence, 1):
        try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
        except:
            time.sleep(0.3)
            continue

        # 💡 [데드락 완파 핵심 가드 블록]
        # 정비창 진입 시도 도중 몬스터 기습이나 상자가 열려 인터럽트가 발생했다면,
        # 그냥 탈출하지 않고 확실하게 "치료 실패했다(False)"고 보고서를 반환합니다!
        if check_gray_template_present(img_np, G_YEOLDA, 0.65) or check_gray_template_present(img_np, G_AUTO_ON, 0.75) or check_gray_template_present(img_np, G_SPEED_ON, 0.75):
            print_log("🚨 [party_manager 인터럽트] 상자 또는 전투 기습 포착!! 시퀀스를 긴급 폐쇄합니다.")
            return False

        # 진입 완료 확인
        is_auto_btn_visible = check_gray_template_present(img_np, G_AUTO_BTN, 0.81)
        is_close_btn_visible = check_gray_template_present(img_np, G_CLOSE_BTN, 0.81)

        if is_auto_btn_visible or is_close_btn_visible:
            print_log("✅ [party_manager] 힐러방 내부 안착 검증 성공!")
            enter_success = True
            break
            
        # 순회 탭핑 주입
        hx, hy = get_slot_coords(slot_idx)
        print_log(f"🎯 [party_manager] {slot_idx}번 슬롯 ({hx}, {hy}) 터치 진입 시도... ({idx}/{len(slot_sequence)})")
        device.shell(f"input tap {hx} {hy}")
        time.sleep(1.5) # 화면 로딩/안착 대기 1.5초
        
    # 만약 모든 순회 시도 끝에 힐러방 안착 확인에 실패했다면
    # 이를 딸피 피장막 렉 또는 로딩 지연 상황으로 간주하고, 무매칭 블라인드 예외 복구(Fallback)를 전개합니다.
    if not enter_success:
        print_log("⚠️ [party_manager] 모든 슬롯 순회 터치 후 힐러방 안착 미검출. 렉/딸피 장막으로 간주해 블라인드 Fallback 복구 힐을 집도합니다.")
        print_log("⚡ [party_manager] [블라인드] 힐링버튼 고정 좌표(1333, 1357) 사격.")
        device.shell("input tap 1333 1357")
        time.sleep(3.0)

        print_log("🔥 [party_manager] [블라인드] '회복한다' 버튼 고정 좌표(963, 1898) 사격.")
        device.shell("input tap 963 1898")
        print_log("⏳ [블라인드] 힐 연출 및 화면 암전 대기... 무조건 6초간 정지합니다.")
        time.sleep(6.0)

        print_log("🚪 [party_manager] [블라인드] 힐러방 나가기 버튼 고정 좌표(85, 2389) 사격.")
        device.shell("input tap 85 2389")
        time.sleep(3.0)

        print_log("✨ [party_manager] 블라인드 파티 정비 시퀀스 종료. 메인으로 복귀합니다.\n")
        return True

    if not enter_success:
        print_log("⚠️ [party_manager 안전 가드] 힐러방 내부 안착 실패 판정. 필드 오인 사격을 차단하기 위해 복귀합니다.\n")
        return False

    # [단계] 자동힐 터치
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return False

    auto_coords = find_gray_coords(img_np, G_AUTO_BTN, 0.75) 
    if auto_coords:
        ax, ay = auto_coords
        device.shell(f"input tap {ax} {ay}")
        print_log(f"⚡ [party_manager] 별 모양 '자동힐' 버튼 ({ax}, {ay}) 타격 성공!")
        time.sleep(0.7)
    else:
        print_log("⚡ [party_manager] 별 마크 미검출. 엘리스 기본 고정 좌표(1344, 1351) 사격.")
        device.shell("input tap 1344 1351")
        time.sleep(0.7)

    # [단계] 일괄회복 최종 승인 터치
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return False

    h, w = img_np.shape[:2]
    confirm_coords = find_gray_coords(img_np, G_CONFIRM_BTN, 0.75)
    
    if confirm_coords:
        cx, cy = confirm_coords
        device.shell(f"input tap {cx} {cy}")
        print_log("🔥 [party_manager] '회복한다' 팝업 승인 완료!")
        print_log("⏳ 힐 연출 및 화면 암전 대기... 무조건 6초간 정지합니다.")
        time.sleep(6.0)
    else:
        print_log("🔍 [party_manager 검증] '회복한다' 버튼 미포착. 예비 고정 좌표(975, 1891)로 승인을 강제 감행합니다.")
        device.shell("input tap 975 1891")
        print_log("⏳ 힐 연출 및 화면 암전 대기... 무조건 6초간 정지합니다.")
        time.sleep(6.0)

    # [단계] 캐릭터 창 "닫기" 필드 복귀
    try: img_np = np.array(Image.open(io.BytesIO(device.screencap())))
    except: return True

    close_coords = find_gray_coords(img_np, G_CLOSE_BTN, 0.75)
    if close_coords:
        lx, ly = close_coords
        device.shell(f"input tap {lx} {ly}")
        print_log("🚪 [party_manager] '닫기' 버튼 터치 완료.")
        time.sleep(1.0)
    else:
        if not check_gray_template_present(img_np, G_FIELD, 0.65):
            print_log("⚠️ [party_manager] '닫기' 버튼 미포착 및 힐러방 상태 유지 확인. 좌측 X 닫기 강제 좌표 사격.")
            device.shell("input tap 75 1940")
            time.sleep(1.0)

    print_log("✨ [party_manager] 파티 정비 시퀀스 종료. 메인으로 복귀합니다.\n")
    # 💡 모든 힐 관문을 온전하게 완수했으므로 완벽한 치료 증명서(True) 발행!
    return True
