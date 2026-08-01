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

# 💡 [v1.13.18 신설] 통합 힐링 필요 플래그 및 상자 복귀 감시 전역 변수
need_heal = False
came_from_chest = False

# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.16.0
# - 최근 수정일: 2026-07-29 08:05
# - 수정 기록:
#   1.16.0: 상자 대화창 우하단 화살표(dialogue_indicator.png) 감지 터치 개편, 공포 상태이상 캐릭 선택 시 "열 수 없다" 대화 팝업 복구 루프 추가, templates/chestopening/ 하위로 상자 관련 템플릿 폴더 정돈에 따른 버전 동기화
#   1.15.0: 지정 슬롯 따개 터치 개편, 상자공포 자동 감지 및 주인공/타 슬롯 우회 회피 시퀀스 추가, whowillopenit 템플릿 의존성 제거 및 '열다' 버튼 소멸 기반 진입 판정 최적화에 따른 버전 동기화
#   1.14.1-hotfix10: 전투 중 배속/자동 8초 가드 단일 블록 통합(상하단 동일 타이머 충돌로 인한 자동전투 8초 감지 영구 스킵 결함 완치), 정비 즉시 재사격 및 상자 없음 인지 시 터치 쿨타임(last_click_time = 0) 파쇄(정비 직후 7초 지연 및 출구 탭 3초 지연 제거)에 따른 버전 동기화
#   1.14.1-hotfix9: 상자깡 완료 연출 마진 sleep(1.0초) 탈거, 전투 중 배속/자동 켜기 가드 8초 쿨타임 주기 검사 도입, 화면 과도기 대기 한계 상향(5회 ➔ 10회)에 따른 버전 동기화
#   1.14.1-hotfix8: 전투 중 딸피 피장막 상황 앵커 소실 버그 해결(배속 앵커 판정을 그레이스케일로 전향하여 피장막 노이즈 우회), 백아 던전 층수 분기 제어(DUNGEON_FLOOR 추가 및 지하 2층 버튼 존재 유무에 따른 고정 좌표 분기 터치 적용)에 따른 버전 동기화
#   1.14.1-hotfix7: 고비용 독 감지 모니터링(HSV 변환 및 6개 슬롯 픽셀 감지) 함수 및 분기 완전 삭제 (CPU 사용량 대폭 경감 및 프레임 렉 근절 최적화)
#   1.14.1-hotfix6: 전투/상자 종료 후 필드 복귀 시 힐링 조건 플래그(came_from_combat/came_from_chest) 누수 버그 패치 및 이진화 매칭/메모리 캐싱 동기화
#   1.14.1-hotfix5: 여관 루프 정체 방지 45초 Watchdog 가드 탑재 및 1:1 이진화 매치 적용에 따른 버전 동기화
#   1.14.1-hotfix4: OpenCV 픽셀 번짐 방지를 위해 동적 리사이저 배제 및 원본 1:1 그레이스케일 매칭 롤백, dungeon_bot 내 load_grayscale_template 정의 유실 NameError 수정 완료
#   1.14.1-hotfix3: 템플릿 크기 및 ROI 정밀 분석 대조를 통한 여백 마진 보강, 그레이스케일 매칭 및 동적 템플릿 축소 스케일러 적용
#   1.14.0-hotfix4: 최초 탈출 정체 시점 타이머 보존 및 5분 절대 Watchdog 가드 구축
#   1.14.0-hotfix3: 바탕화면 튕김/가로 화면 30초 정체 시 예외 격발 및 에뮬레이터 자동 2단계 리부팅 복구 가드 탑재 (동기화)
#   1.14.0-hotfix2: 탈출 5분 리셋 누적 버그/출구 클릭 건너뜀 수정 및 정체 1~2회 시점 예비 연타 기능 이식
#   1.14.0-hotfix1: README 안내 보강에 따른 핫픽스 빌드 반영
#   1.14.0: 빈사/딸피 화면 렉 60초 정체 시 이미지 임계값 0.45 하향 완화 및 힐링 시퀀스 강제 격발 복원 로직 추가 (정식 기능 이식)
#   1.13.20-hotfix1: 탈출 정지 감지 5회 상향 및 백스텝 후 출구 이동 단추 0.1초 간격 2회 탭핑 복구 시퀀스 도입
#   1.13.20: 자동전투 켜기 씹힘 방지(auto_combat_paused_for_skill 가드 우회) 보완
#   1.13.19-hotfix2: 최상단 전투 가드 변수 리셋, 렉 보호 가드 주입, 탈출 앵커 임계치 상향 및 안전지대(700, 150) 터치 조율
#   1.13.19-hotfix1: 던전 최초 탈출 시 출구 이동 버튼 0.2초 간격 2회 터치(더블 탭) 보완
#   1.13.19: WVD 기반 사망/부활(InCombat_dead, btn_resurrect) 흐름 및 기동 복구(recover_app_startup) 연동 고도화
#   1.13.18: 통합 힐링 플래그 need_heal 도입, 상자 완료 필드 앵커 2차 검증 가드 주입, 임의 빈사 힐링 제거 및 임계치 완화
#   1.13.17: 버전 동기화
#   1.13.16: 버전 동기화
#   1.13.7: 버전 동기화
#   1.13.6: 에뮬레이터 콜드 리부트(Emulator Reboot) 기능 및 디스크 파일 연동 연속 오류 방지 가드 도입
#   1.13.5: 일반 필드 상태 정체 시간 리셋 버그 수정 및 5분 필드 정체 시 앱 리셋 재시작 가드 장착
#   1.13.4: 버전 동기화
#   1.13.3: 5분 타임아웃 세이프티 가드 도입 및 백스텝-전진/2번단추 사격 무한 교대식 복구 시퀀스 개편
#   1.13.2: 범용 탈출 물리 백스텝-전진 복구 도입, 최후의 5회차 앱 리셋 가드 탑재, 최초 탈출 시간 누적 보존 패치
#   1.13.1: 버전 동기화
#   1.13.0-hotfix4: 핫픽스 적용 - 글로벌 힐 주기에 따른 치료 정비 처리 및 상자 조우 시 치료 유예 가드 장착
#   1.13.0-hotfix3: 핫픽스 버전 동기화
#   1.12.6: 여관 정비 시 멀티 레벨업 '다음' 팝업 처리 구현 및 실시간 타임스탬프 로깅 래퍼 함수 도입
#   1.12.5: 탈출 정체 복구 카운트 리셋 오류 패치, 블랙박스 및 탈출 정지 최초 정체 시각 표기 추가 및 버전업
#   1.12.4: 힐러방 딸피 암전 시 블라인드 고정좌표 힐 시퀀스 핫픽스 적용 및 버전 동기화
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

def load_grayscale_template(file_path):
    if not os.path.exists(file_path): return None
    try:
        return cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
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

def check_dialogue_indicator_present(img_np, template, threshold=0.75):
    if img_np is None or template is None:
        return False
    h, w = img_np.shape[:2]
    if h < 2433 or w < 1377:
        return False
    roi = img_np[2349:2433, 1293:1377]
    return check_template_present(roi, template, threshold)

def check_gray_template_present_specific(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None or img_np is None: return False
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_gray_coords_specific(img_np, gray_temp, threshold_val=0.65):
    if gray_temp is None or img_np is None: return None
    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    result = cv2.matchTemplate(gray_img, gray_temp, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        h, w = gray_temp.shape[:2]
        return max_loc[0] + int(w / 2), max_loc[1] + int(h / 2)
    return None

def check_combat_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    # 피장막 상태를 우회하기 위해 그레이스케일 매치 구제 적용
    return check_gray_template_present_specific(crop, template, threshold_val)

def find_and_click_combat_template(device, img_np, template, threshold_val=0.65):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(0 * scale_x), int(200 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    # 피장막 상태를 우회하기 위해 그레이스케일 좌표 탐색 구제 적용
    coords = find_gray_coords_specific(crop, template, threshold_val)
    if coords:
        cx, cy = coords
        real_x = x1 + cx
        real_y = y1 + cy
        print(f"⚡ [전투 배속 단추 클릭] 그레이스케일 검출 좌표 ({real_x}, {real_y})")
        safe_device_shell(device, f"input tap {real_x} {real_y}")
        return True
    return False
def is_combat_speed_orange(img_np):
    if img_np is None: return False
    h, w = img_np.shape[:2]
    try:
        scale_x, scale_y = w / 1440.0, h / 2560.0
        cx, cy = int(70 * scale_x), int(1706 * scale_y)
        cx = max(0, min(cx, w - 1))
        cy = max(0, min(cy, h - 1))
        
        x1, x2 = max(0, cx - 15), min(w, cx + 15)
        y1, y2 = max(0, cy - 15), min(h, cy + 15)
        crop = img_np[y1:y2, x1:x2]
        
        # img_np는 RGB(Pillow 변환) 포맷이므로, crop[:, :, 0]이 Red, crop[:, :, 2]가 Blue임
        avg_r = np.mean(crop[:, :, 0])
        avg_b = np.mean(crop[:, :, 2])
        
        # 주황색 성분 판정 (Red가 Blue보다 60.0 이상 강하게 튀면 주황색으로 확정)
        is_orange = (avg_r - avg_b) > 60.0
        if is_orange:
            print(f"📊 [배속 색상 분석] 주황색(고속) 확정 검출 (Avg R: {avg_r:.1f}, B: {avg_b:.1f}, 차이: {avg_r - avg_b:.1f})")
        return is_orange
    except Exception as e:
        print(f"⚠️ [배속 색상 분석 오류] {e}")
        return False

def is_auto_combat_yellow(img_np):
    if img_np is None: return False
    h, w = img_np.shape[:2]
    try:
        scale_x, scale_y = w / 1440.0, h / 2560.0
        cx, cy = int(1380 * scale_x), int(1720 * scale_y)
        cx = max(0, min(cx, w - 1))
        cy = max(0, min(cy, h - 1))
        
        x1, x2 = max(0, cx - 15), min(w, cx + 15)
        y1, y2 = max(0, cy - 15), min(h, cy + 15)
        crop = img_np[y1:y2, x1:x2]
        
        # img_np는 RGB 포맷
        avg_r = np.mean(crop[:, :, 0])
        avg_b = np.mean(crop[:, :, 2])
        
        # 노란색 성분 판정 (Red와 Blue 편차가 50.0 이상이면 활성화 노란색으로 확정)
        is_yellow = (avg_r - avg_b) > 50.0
        if is_yellow:
            print(f"📊 [자동 색상 분석] 노란색(자동온) 확정 검출 (Avg R: {avg_r:.1f}, B: {avg_b:.1f}, 차이: {avg_r - avg_b:.1f})")
        return is_yellow
    except Exception as e:
        print(f"⚠️ [자동 색상 분석 오류] {e}")
        return False

def check_auto_btn_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    return check_gray_template_present_specific(crop, template, threshold_val)

def find_and_get_auto_btn_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1440 * scale_x)
    y1, y2 = int(1600 * scale_y), int(1800 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    coords = find_gray_coords_specific(crop, template, threshold_val)
    if coords:
        cx, cy = coords
        return x1 + cx, y1 + cy
    return None

def check_field_anchor_present(img_np, template, threshold_val=0.65):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1250 * scale_x), int(1420 * scale_x)
    y1, y2 = int(380 * scale_y), int(530 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_open_minimap_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1130 * scale_x), int(1290 * scale_x)
    y1, y2 = int(510 * scale_y), int(590 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        return x1 + max_loc[0] + int(w_temp / 2), y1 + max_loc[1] + int(h_temp / 2)
    return None

def check_field_btn_template_present(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return False
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1100 * scale_x), int(1440 * scale_x)
    y1, y2 = int(350 * scale_y), int(750 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return False
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return False
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val > threshold_val

def find_and_get_field_btn_coords(img_np, template, threshold_val=0.70):
    if template is None or img_np is None: return None
    h, w = img_np.shape[:2]
    scale_x, scale_y = w / 1440.0, h / 2560.0
    x1, x2 = int(1100 * scale_x), int(1440 * scale_x)
    y1, y2 = int(350 * scale_y), int(750 * scale_y)
    if x2 <= x1 or y2 <= y1 or x2 > w or y2 > h: return None
    crop = img_np[y1:y2, x1:x2]
    
    h_crop, w_crop = crop.shape[:2]
    h_temp, w_temp = template.shape[:2]
    if h_crop < h_temp or w_crop < w_temp: return None
    
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    result = cv2.matchTemplate(gray_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > threshold_val:
        return x1 + max_loc[0] + int(w_temp / 2), y1 + max_loc[1] + int(h_temp / 2)
    return None

def find_chest_btn_coords(img_np, t_act, t_deact, threshold_val=0.70):
    coords = find_and_get_field_btn_coords(img_np, t_act, threshold_val)
    if coords: return coords
    return find_and_get_field_btn_coords(img_np, t_deact, threshold_val)

def find_checkpoint_btn_coords(img_np, t_act, t_deact, threshold_val=0.70):
    coords = find_and_get_field_btn_coords(img_np, t_act, threshold_val)
    if coords: return coords
    return find_and_get_field_btn_coords(img_np, t_deact, threshold_val)

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

# [독 감지 모니터링 기능은 1.14.1-hotfix7에서 렉 최적화를 위해 탈거되었습니다]

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



def start_main_macro(device, run_skill_logic=False, healing_loops=1, heal_after_chest=True, healer_slot=5, masked_adventurer_slot=5, chest_opener_slot=6):
    if not device: return False, False

    print("\n=======================================")
    print("🎨 [dungeon_bot] 코어 마스크 도장을 로드합니다...")
    # 🗺️ [1.14.1 버전 신규 필드 UI 템플릿 연동부]
    # - field_anchor.png: 우측 상단 미니맵 내의 '던전 나가기(깃발)' 버튼. 현재 필드 인식을 검출하는 앵커로 전용함.
    t_field = load_grayscale_template("templates/Field/field_anchor.png") 
    
    # - open_minimap.png: 미니맵 좌하단에 위치한 삼각형 모양의 '미니맵 접기/펼치기' 토글 단추 앵커.
    #   (필드 앵커는 검출되나 상자 단추가 보이지 않을 때 미니맵 접힘 상태로 간주, (1223, 551) 부근을 터치해 펼치기 위해 감지)
    t_open_minimap = load_grayscale_template("templates/Field/open_minimap.png")
    
    # - exit_dungeon.png: 2번 버튼. 던전 출구 자동 이동 (깃발 모양 단추)
    t_move_exit = load_grayscale_template("templates/Field/exit_dungeon.png")
    
    # - chest_act/deact.png: 4번 버튼. 미니맵 상자 자동 이동 (활성화 / 눈보라 등으로 인한 비활성화(딤) 상태 멀티 스캔용)
    t_move_chest_act = load_grayscale_template("templates/Field/chest_act.png")
    t_move_chest_deact = load_grayscale_template("templates/Field/chest_deact.png")
    
    # - check_act/deact.png: 3번 버튼. 체크포인트 자동 회군 (활성화 / 눈보라 등으로 인한 비활성화(딤) 상태 멀티 스캔용)
    t_move_check_act = load_grayscale_template("templates/Field/check_act.png")
    t_move_check_deact = load_grayscale_template("templates/Field/check_deact.png")
    
    # - resume_act/deact.png: 1번 버튼. 이전 주행 경로 이동 재개 (Resume / Re-move 단추)
    #   (대설지대 눈보라 지역 진입 시 상자 버튼 비활성화 대응용으로 사전 매핑 로드 완료)
    t_move_resume_act = load_grayscale_template("templates/Field/resume_act.png")
    t_move_resume_deact = load_grayscale_template("templates/Field/resume_deact.png")
    t_no_chest = load_template("templates/no_chest.png") 
    t_yeolda = load_template("templates/chestopening/yeolda_clean.png")
    t_dialogue_indicator = load_template("templates/chestopening/dialogue_indicator.png")
    
    t_heal_auto = load_template("templates/healer_auto_btn.png")
    t_heal_confirm = load_template("templates/confirm_recover.png")
    t_heal_close = load_template("templates/close_panel.png")

    t_combat_in = load_grayscale_template("templates/combat_in.png")   
    t_combat_slow = load_grayscale_template("templates/combat_slow.png") 
    t_auto_off = load_grayscale_template("templates/auto_off.png")     
    t_auto_on = load_grayscale_template("templates/auto_on.png")       
    t_exit_mag = load_template("templates/exit_mag_icon.png")
    t_dungeon_sel = load_template("templates/WolfCave/dungeon_select.png")
    
    t_anchor_dead = load_dead_template("templates/anchor_dead_screen.png")
    t_btn_resurrect = load_dead_template("templates/btn_resurrect.png")
    t_incombat_dead = load_template("templates/InCombat_dead.png")
    t_net_error = load_template("templates/anchor_network_error.png")
    t_net_retry = load_template("templates/btn_network_retry.png")
    t_err_retry = load_template("templates/Error_retry.png")
    t_err_to_title = load_template("templates/Error_to_title.png")
    
    t_sc_cheonja = load_template("templates/shortcut_cheonja_core.png") 
    t_btn_lvl_ok = load_template("templates/btn_level_confirm.png")      
    t_btn_lvl1 = load_template("templates/btn_level_1.png")         
    t_btn_lvl1_atv = load_template("templates/btn_level_1_atv.png") 
    
    t_sc_jeongmil = load_template("templates/shortcut_jeongmil.png")    
    t_sc_ttang = load_template("templates/shortcut_ttang.png")          
    
    t_next = load_template("templates/indicator_next.png")              
    t_arrow = load_template("templates/indicator_arrow.png")

    print("=======================================")

    transition_delay_count = 0
    state = "FIELD_WAIT"
    last_click_time = 0 
    came_from_combat = False 
    event_counter = 0
    
    last_state_changed_time = time.time()
    previous_state = "FIELD_WAIT"
    exit_start_time = 0
    prev_minimap_zone = None
    
    global need_heal, came_from_chest
    need_heal = False
    came_from_chest = False
    low_threshold_active_until = 0.0
    low_threshold_reset_count = 0
    
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
    last_combat_color_check_time = 0
    
    last_empty_shortcut_detected_time = 0
    continuous_heal_retry_count = 0
    yeolda_stuck_retry_count = 0
    exit_clicked_once = False
    exit_first_start_time = None
    exit_recovery_retry_count = 0
    minimap_expanded = False

    cap_fail_counter = 0
    resolution_fail_counter = 0  # 🚨 [v1.14.0-hotfix3] 해상도 미달 가드 연속 카운터 추가
    while True:
        current_time = time.time()
        if current_time < low_threshold_active_until:
            field_threshold = 0.45
            combat_threshold = 0.50
            yeolda_threshold = 0.45
        else:
            field_threshold = 0.65
            combat_threshold = 0.80
            yeolda_threshold = 0.65

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
            resolution_fail_counter += 1
            print(f"⚠️ [dungeon_bot 해상도 미달 가드] 현재 화면 크기({width}x{height})가 기준 해상도(1440x2560) 미만입니다. 1.0초 대기합니다. ({resolution_fail_counter}/30)")
            if resolution_fail_counter >= 30:
                raise RuntimeError(f"dungeon_bot 내 해상도 미달 상태 30초 지속 감지 (화면 크기: {width}x{height})")
            time.sleep(1.0)
            continue
        else:
            resolution_fail_counter = 0  # 정상 해상도 검출 시 카운터 리셋

        mean_brightness = np.mean(img_np)
        if mean_brightness < 5.0:
            print("⏳ [dungeon_bot 로딩 가드] 화면 전환/로딩 중(암전) 포착! 0.5초 대기 후 재스캔합니다.")
            time.sleep(0.5)
            continue
        is_poisoned = False

        if check_template_present(img_np, t_dungeon_sel, 0.70):
            print("🚪 [dungeon_bot] 현실 화면이 '던전 선택창'으로 식별되었습니다! 사령탑으로 즉시 퇴장합니다.")
            return False, skill_mission_success_this_combat

        # 🌐 [통합 네트워크 에러 감시 가드]
        if check_template_present(img_np, t_err_retry, 0.70):
            print("🌐⚠️ [네트워크 가드] 'Error_retry.png' 포착! 즉시 재시도 터치를 주입합니다.")
            if find_and_click_template_in_bot(device, img_np, t_err_retry, 0.70):
                time.sleep(3.0)
                last_state_changed_time = time.time()
                continue
                
        if check_template_present(img_np, t_err_to_title, 0.70):
            raise RuntimeError("Error_to_title.png 검출로 인한 강제 앱 리부트 요구")

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
            stuck_limit = 180.0 if state == "IN_COMBAT" else 30.0
            
            # 🚨 [v1.13.20-hotfix4] 60초 이상 앵커 미인식 정체 시 임계값 하향 완화 검증
            if stuck_duration >= 60.0 and current_time >= low_threshold_active_until:
                temp_thresh_f = 0.45
                temp_thresh_c = 0.50
                temp_thresh_y = 0.45
                
                field_matched_low = check_field_anchor_present(img_np, t_field, temp_thresh_f)
                combat_matched_low = check_combat_template_present(img_np, t_combat_in, temp_thresh_c) or check_combat_template_present(img_np, t_combat_slow, temp_thresh_c)
                yeolda_matched_low = check_template_present_dynamic(img_np, t_yeolda, temp_thresh_y, 160)
                
                if field_matched_low or combat_matched_low or yeolda_matched_low:
                    print(f"🚨 [정체 탈출 가드] 임계값 0.45 완화 시 앵커 매칭 성공! (필드:{field_matched_low}, 전투:{combat_matched_low}, 상자:{yeolda_matched_low})")
                    need_heal = True
                    low_threshold_active_until = current_time + 60.0
                    if low_threshold_reset_count < 3:
                        last_state_changed_time = current_time  # 정체 타이머 리셋
                        low_threshold_reset_count += 1
                        print(f"🔴 빈사(딸피) 장막 간섭 판정: 완화 모드 리셋 적용 ({low_threshold_reset_count}/3)")
                    else:
                        print("🔴 빈사(딸피) 완화 리셋 한계(3회) 도달! 진성 정체 상태일 가능성이 있으므로 타이머 리셋을 건너뜁니다.")
                    
            if stuck_duration > stuck_limit:
                if state == "TRIGGER_EXIT":
                    last_state_changed_time = time.time()
                    continue
                stuck_time_str = datetime.datetime.fromtimestamp(last_state_changed_time).strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n⚠️ [🚨 블랙박스 경고] 현재 던전봇이 '{state}' 상태로 정체 중... (정체 시작: {stuck_time_str}, 경과: {int(stuck_duration)}초)")
                
                # 🛑 [v1.13.5 추가] 일반 상태 5분 이상 정체 시 자동 재부팅 세이프티 가드
                if stuck_duration >= 300.0:
                    raise RuntimeError(f"던전 필드 정체 한계 초과: '{state}' 상태로 {int(stuck_duration)}초간 정체되어 강제 앱 재시작을 수행합니다.")
                
                if state == "TRIGGER_EXIT":
                    print("🚪🚨 [탈출 정체 복구 시스템 작동] 던전 출구에서 30초간 정체 감지! 회군을 시작합니다.")
                    chk_coords = find_checkpoint_btn_coords(img_np, t_move_check_act, t_move_check_deact, 0.70)
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
                
                # [독 치료 복구 가드는 1.14.1-hotfix7에서 탈거되었습니다]

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

                # 🚨 [v1.14.0-hotfix5] 일반 정체 30초 지속 시 비상 뒤로가기(KEYCODE_BACK)를 날려 팝업 갇힘을 극복
                print("⏰ [일반 정체 복구] 30초간 정체 지속되어 비상 뒤로가기(KEYCODE_BACK)를 1회 주입합니다.")
                safe_device_shell(device, "input keyevent 4")
                time.sleep(1.0)
                last_state_changed_time = time.time()
                continue

            # 💀 [주인공 사망 부활 가드] 전멸 또는 부활 대기 화면 감지 시
            if get_dead_match_score(img_np, t_anchor_dead) > 0.65 or check_template_present(img_np, t_btn_resurrect, 0.60):
                print("💀 [주인공 사망 감지] 전멸/주인공 사망 화면이 식별되었습니다. 부활을 집도합니다.")
                if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    safe_device_shell(device, "input tap 720 1200")
                time.sleep(1.0)
                safe_device_shell(device, "input tap 705 1241")
                print("⏳ 부활 암전 연출 대기... 무조건 10초간 제어를 홀딩합니다.")
                time.sleep(10.0)
                need_heal = True  # 부활 즉시 정비 플래그 강제 작동
                state = "IN_COMBAT"
                last_state_changed_time = time.time()
                transition_delay_count = 0
                continue

            # 💀 [아군 사망 부활 가드] 아군 사망 앵커 감지 시
            if check_template_present(img_np, t_incombat_dead, 0.75):
                print("💀 [아군 사망 감지] 아군 사망 앵커가 포착되었습니다. 1초 간격 5회 부활 연타를 주입합니다.")
                state = "IN_COMBAT"
                last_state_changed_time = time.time()
                time.sleep(1.0) # 첫 진입 연출 대기
                import random
                for i in range(5):
                    rx = 640 + random.randint(0, 160)
                    ry = 1200 + random.randint(0, 160)
                    print(f"  👉 부활 시도 ({i+1}/5) - 터치 좌표: ({rx}, {ry})")
                    safe_device_shell(device, f"input tap {rx} {ry}")
                    time.sleep(1.0) # 매 클릭 간격 1초
                need_heal = True  # 부활 후 즉각 파티 힐링 정비 강제 작동
                transition_delay_count = 0
                continue

            combat_active = False
            if check_combat_template_present(img_np, t_combat_in, combat_threshold) or check_combat_template_present(img_np, t_combat_slow, combat_threshold):
                combat_active = True
                transition_delay_count = 0
                if state != "IN_COMBAT":
                    print("⚔️ [메인 가드] 배속 고정 UI 포착, 적 인카운터 확정! 전투 대기(`IN_COMBAT`) 진입.")
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time()
                    last_empty_shortcut_detected_time = 0
                    last_state_changed_time = time.time()
                    continue

            if not combat_active:
                if check_template_present_dynamic(img_np, t_yeolda, yeolda_threshold, 160):
                    transition_delay_count = 0
                    if yeolda_stuck_retry_count < 3:
                        yeolda_stuck_retry_count += 1
                        print(f"⚠️ [블랙박스 상자 해제 갇힘 복구] '열다'가 보이나 진입 실패 상태입니다. 상자 오프닝을 재시도합니다. ({yeolda_stuck_retry_count}/3)")
                        if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                            state = "BRANCH_CHECK"
                        last_state_changed_time = time.time()
                    else:
                        print("⚠️ [블랙박스 상자 해제 갇힘 복구] '열다' 재시도 3회 초과! '아무것도 안 한다' 강제 터치로 상자창을 확실히 탈출합니다.")
                        safe_device_shell(device, f"input tap {int(width * 0.5)} {int(height * 0.855)}")
                        time.sleep(1.0)
                        yeolda_stuck_retry_count = 0
                        state = "FIELD_WAIT"
                elif chest_opener.is_minigame_screen(img_np, height, width):
                    transition_delay_count = 0
                    state = "PLAY_MINIGAME"
                elif check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75):
                    transition_delay_count = 0
                    state = "CLEAR_CHECK"
                elif check_field_anchor_present(img_np, t_field, field_threshold):
                    transition_delay_count = 0
                    if state != "TRIGGER_EXIT":
                        if state == "IN_COMBAT":
                            print("🎉 [전투 종료 감지] 배속 마크 소멸 및 필드 안착 확인! (came_from_combat = True)")
                            came_from_combat = True
                            state = "FIELD_WAIT"
                            time.sleep(2.0)  # 전투 종료 안착 연출 마진
                            continue
                        elif state in ["BRANCH_CHECK", "PLAY_MINIGAME", "CLEAR_CHECK"]:
                            print("✨ [상자깡 완료 감지] 상자 처리 후 필드 안착 확인! (came_from_chest = True)")
                            came_from_chest = True
                            state = "FIELD_WAIT"
                            continue
                        state = "FIELD_WAIT"
                else:
                    if transition_delay_count < 10:
                        transition_delay_count += 1
                        print(f"⏳ [화면 과도기 감지] 필드/전투 앵커 일시 소실. 화면 안착 대기 중... ({transition_delay_count}/10)")
                        time.sleep(1.0)
                        continue
                    else:
                        transition_delay_count = 0
                        print("🔍 [길 잃음 복구] 10초간 앵커 연속 미검출로 stuck 판정, 안전지대(700, 150) 터치 및 뒤로가기(ESC) 입력을 주입합니다.")
                        safe_device_shell(device, "input tap 700 150")
                        time.sleep(0.5)
                        safe_device_shell(device, "input keyevent 4")
                        time.sleep(1.0)
                        state = "FIELD_WAIT"
            
        else:
            previous_state = state
            last_state_changed_time = time.time()
            yeolda_stuck_retry_count = 0
            low_threshold_reset_count = 0
        # 🎮 [미니게임 즉각 돌입 가드] 화면이 미니게임 해제 창인 경우 30초 정체 대기 없이 즉시 전이
        if state in ["FIELD_WAIT", "AUTO_MOVING"] and chest_opener.is_minigame_screen(img_np, height, width):
            print("🎮 [dungeon_bot] 미니게임 화면 포착! 즉각 PLAY_MINIGAME 상태로 진입합니다.")
            state = "PLAY_MINIGAME"
            last_state_changed_time = time.time()
            continue



        # [메인 루프 독 치료 가드는 1.14.1-hotfix7에서 탈거되었습니다]

        if state in ["FIELD_WAIT", "AUTO_MOVING"] and not minimap_expanded:
            # 🗺️ [미니맵 오토-오픈 가드] 매크로 가동 후 미니맵이 펼쳐질 때까지만 감지 작동 (ROI: 1287-1387, 415-500)
            field_present = check_field_anchor_present(img_np, t_field, field_threshold)
            if field_present:
                open_minimap_coords = find_open_minimap_coords(img_np, t_open_minimap, 0.70)
                if open_minimap_coords:
                    ox, oy = open_minimap_coords
                    print(f"🗺️ [미니맵 제어] 미니맵 접힘 상태(삼각형 마크) 감지! 펼침 시퀀스를 시작합니다. (좌표: {ox}, {oy})")
                    
                    for attempt in range(3):
                        print(f"🗺️ [미니맵 제어] 펼침 단추 터치 시도 ({attempt+1}/3)...")
                        safe_device_shell(device, f"input tap {ox} {oy}")
                        time.sleep(1.2) # 펼침 애니메이션 대기
                        
                        # 화면 갱신 후 상자 버튼 활성화 확인
                        try:
                            raw_cap = device.screencap()
                            img_np_check = cv2.imdecode(np.frombuffer(raw_cap, np.uint8), cv2.IMREAD_COLOR)
                            img_np_check = cv2.cvtColor(img_np_check, cv2.COLOR_BGR2RGB)
                        except:
                            continue
                            
                        chest_found = (check_field_btn_template_present(img_np_check, t_move_chest_act, 0.70) or 
                                       check_field_btn_template_present(img_np_check, t_move_chest_deact, 0.70))
                        if chest_found:
                            print("🗺️ [미니맵 제어] 미니맵이 성공적으로 펼쳐졌습니다!")
                            minimap_expanded = True
                            break
                    
                    if not minimap_expanded:
                        print("🗺️ [미니맵 제어] 3회 터치 시도 후에도 펼침 감지 실패. 고정 좌표(1215, 557) 물리 예비 사격을 가합니다.")
                        scale_x, scale_y = width / 1440.0, height / 2560.0
                        safe_device_shell(device, f"input tap {int(1215 * scale_x)} {int(557 * scale_y)}")
                        time.sleep(1.2)
                        minimap_expanded = True  # 중복 루프 방지를 위해 플래그 설정
                    continue

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if check_template_present_dynamic(img_np, t_yeolda, 0.65, 160):
                print("📦 [메인] '열다' 감지! 상자 해제 시퀀스로 진입.")
                if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                    state = "BRANCH_CHECK"
                continue

        if state in ["FIELD_WAIT", "AUTO_MOVING"]:
            if not check_field_anchor_present(img_np, t_field, 0.62):
                if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                    print("⚔️ [메인] 배속 고정 UI 포착,적 인카운터 확정! 전투 대기(`IN_COMBAT`) 진입.")
                    state = "IN_COMBAT"
                    yuzuna_done = False
                    milana_done = False
                    guksu_done = False
                    auto_combat_paused_for_skill = False
                    combat_entry_start_time = time.time() 
                    last_empty_shortcut_detected_time = 0 
                    last_combat_color_check_time = 0 
                    continue

        if state == "FIELD_WAIT":
            if check_field_anchor_present(img_np, t_field, 0.65):
                # 1. 전투 종료 복귀 검증 및 카운팅
                was_from_combat = False
                if came_from_combat:
                    came_from_combat = False
                    was_from_combat = True
                    event_counter += 1
                    print(f"⚔️ [전투 종료 복구] 필드 복귀 안착 확인! (전투 카운트: {event_counter}/{healing_loops})")
                    if healing_loops > 0 and event_counter >= healing_loops:
                        print(f"💊 [정비 도달] 전투 누적 횟수가 설정 주기({healing_loops}회)에 달해 need_heal = True로 전환합니다.")
                        need_heal = True

                # 2. 상자 정산 완료 후 복귀 검증
                if came_from_chest:
                    came_from_chest = False
                    if heal_after_chest:
                        print("📦 [상자 정산 완료 필드 안착] need_heal = True로 전환합니다.")
                        need_heal = True

                # 3. 통합 힐링 기동: 안전 필드 안착 및 힐링 플래그 감지 시 작동
                if need_heal:
                    if check_template_present(img_np, t_yeolda, 0.65):
                        print("📦 [상자 발견 가드] 화면에 '열다' 버튼이 노출되어 있어 상자 해제를 우선 처리하고 힐링을 다음 루프로 유예합니다.")
                    else:
                        print("💊 [통합 힐링 기동] 안전 필드 안착 확인. 정비 시퀀스를 시작합니다.")
                        heal_success = party_manager.run_party_healing_sequence(device, t_heal_auto, t_heal_close, healer_slot=healer_slot, masked_adventurer_slot=masked_adventurer_slot)
                        if heal_success:
                            low_threshold_active_until = 0.0
                            event_counter = 0
                            need_heal = False
                            if last_target_coords:
                                print(f"⏭️ [즉각 이동 재개] 정비 직후 딜레이 파쇄! 이전 타겟 좌표 ({last_target_coords[0]}, {last_target_coords[1]}) 즉시 재사격")
                                safe_device_shell(device, f"input tap {last_target_coords[0]} {last_target_coords[1]}")
                                last_click_time = 0.0
                            continue
                        else:
                            print("⚠️ [통합 힐링 실패] 기습 또는 인터럽트로 인해 치료 미완료. 힐링 플래그(need_heal = True)를 유지합니다.")

                # 4. 힐링 미작동 시 전투 종료 직후 첫 루프 가드
                if was_from_combat:
                    continue
                
                if time.time() - last_click_time > 4.0:
                    if check_field_anchor_present(img_np, t_field, 0.65):
                        coords = find_chest_btn_coords(img_np, t_move_chest_act, t_move_chest_deact, 0.70)
                    if coords:
                        cx, cy = coords
                        print(f"📦 [상자 이동 시도] '상자 자동 이동' ({cx}, {cy}) 2회 정밀 연사 터치(더블 탭)합니다.")
                        safe_device_shell(device, f"input tap {cx} {cy}")
                        time.sleep(0.25)
                        safe_device_shell(device, f"input tap {cx} {cy}")
                        last_click_time = time.time()
                        last_target_coords = (cx, cy)
                        
                        action_success = False
                        opened = False
                        toast_detected = False
                        
                        for retry_cnt in range(2): # 최초 1회 + 씹힘 시 재시도 1회
                            if retry_cnt > 0:
                                print(f"🔄 [상자 터치 재시도] 터치 씹힘 감지되어 2회 다시 연사 누릅니다. ({cx}, {cy})")
                                safe_device_shell(device, f"input tap {cx} {cy}")
                                time.sleep(0.25)
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
                                
                                if check_template_present_dynamic(img_np_sub, t_yeolda, 0.65, 160):
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
                            if chest_opener.open_and_disarm_chest(device, img_np, t_yeolda, chest_opener_slot=chest_opener_slot, masked_adventurer_slot=masked_adventurer_slot):
                                state = "BRANCH_CHECK"
                            else:
                                state = "FIELD_WAIT"
                        elif toast_detected:
                            print("🎉 [상자 없음] 토스트 메시지를 확인하여 탈출 시퀀스로 이행합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            # 🚨 [v1.14.0-hotfix4] 진입 시 타이머 강제 초기화 제거
                            # 최초 스턱(정체) 발생 시점에만 타이머를 시작하도록 하여, 백스텝 동작 시 오리셋되는 루프 락을 원천 차단합니다.
                            # exit_first_start_time = time.time() <-- 제거됨
                            exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 출구 클릭 플래그 리셋
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                            last_click_time = 0.0                 # 🚀 [v1.14.1-hotfix10] 탈출 탭 3초 쿨타임 파쇄
                        elif moved:
                            print("🏃 [이동 시작 확인] 미니맵이 움직이기 시작했습니다. AUTO_MOVING으로 이행.")
                            state = "AUTO_MOVING"
                        else:
                            print("📦🚫 [상자 없음 판정] 재시도 결과 미니맵 움직임과 '열다'가 모두 미검출되었습니다. 상자가 없는 것으로 논리적 판정하여 탈출로 전환합니다.")
                            state = "TRIGGER_EXIT"
                            exit_start_time = time.time()
                            # 🚨 [v1.14.0-hotfix4] 진입 시 타이머 강제 초기화 제거
                            # 최초 스턱(정체) 발생 시점에만 타이머를 시작하도록 하여, 백스텝 동작 시 오리셋되는 루프 락을 원천 차단합니다.
                            # exit_first_start_time = time.time() <-- 제거됨
                            exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 출구 클릭 플래그 리셋
                            exit_stuck_count = 0
                            exit_prev_minimap = None
                            last_click_time = 0.0                 # 🚀 [v1.14.1-hotfix10] 탈출 탭 3초 쿨타임 파쇄

        elif state == "AUTO_MOVING":
            toast_detected = False
            for scan_step in range(5):
                if check_template_present_dynamic(img_np, t_yeolda, 0.65, 160): break
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
            # 🚨 [v1.14.0-hotfix4] 독립형 5분 절대 Watchdog 가드 이식:
            # 백스텝 복구 드래그 동작 등으로 인해 미니맵이 강제로 움직여 exit_stuck_count가 0으로 도중에 초기화되더라도, 
            # 최초 정체 발생 시점(exit_first_start_time) 기준으로 5분(300초) 동안 필드를 벗어나지 못했다면 무조건 강제 앱 리셋 복구 프로세스를 작동시킵니다.
            if exit_first_start_time is not None:
                elapsed_exit_time = int(time.time() - exit_first_start_time)
                if elapsed_exit_time >= 300:
                    raise RuntimeError(f"탈출 5분 초과 앱 강제 재시작: {elapsed_exit_time}초 동안 탈출하지 못하여 프로세스 강제 리셋을 수행합니다.")

            # 💡 [기습 방어 인터럽트] 탈출 중 전투 발생 즉시 0.1초 만에 전투 태세 전환
            if check_combat_template_present(img_np, t_combat_in, 0.80) or check_combat_template_present(img_np, t_combat_slow, 0.80):
                print("⚔️ [TRIGGER_EXIT 인터럽트] 탈출 행군 중 기습 포착! 즉시 전투 모드로 스위칭합니다.")
                # 🚨 [v1.14.0-hotfix4] 전투 돌입 시에는 탈출 정체 누적 타이머를 초기화하여, 전투 시간으로 인한 억울한 타임아웃 격발을 방지합니다.
                exit_first_start_time = None
                state = "IN_COMBAT"
                yuzuna_done = False
                milana_done = False
                guksu_done = False
                auto_combat_paused_for_skill = False
                combat_entry_start_time = time.time() 
                last_empty_shortcut_detected_time = 0 
                continue

            exit_touched_this_loop = False
            # 출구 버튼 터치 (최초 1회 터치)
            if not exit_clicked_once:
                if time.time() - last_click_time > 3.0:
                    coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                    if coords_exit:
                        ex, ey = coords_exit
                        print(f"⏭️ [던전 탈출 시도] '출구 이동' 단추를 0.2초 간격으로 2회 연속 터치합니다. ({ex}, {ey})")
                        safe_device_shell(device, f"input tap {ex} {ey}")
                        time.sleep(0.2)
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

            is_real_field = check_field_anchor_present(img_np, t_field, 0.62)
            if exit_prev_minimap is not None and is_real_field:
                diff = cv2.absdiff(current_mini, exit_prev_minimap)
                mean_diff = np.mean(diff) / 255.0
                print(f"📊 [탈출 스턱 분석기] 미니맵 미세 움직임 변동 값: {mean_diff:.4f}")
                
                if mean_diff < 0.05:
                    exit_stuck_count += 1
                    
                    # 🚨 [v1.14.0-hotfix4] 최초 정체(스턱 1회차 이상)가 감지된 바로 그 시점에만 탈출 타이머를 개시합니다.
                    # 이후 백스텝 복구 드래그 등으로 인해 캐릭터가 움직여 exit_stuck_count가 0으로 리셋되어도,
                    # 이 최초 정체 발생 타임스탬프는 덮어쓰지 않고 엄격히 보존되어 절대적 5분 watchdog 카운트가 유효하게 유지됩니다.
                    if exit_first_start_time is None:
                        exit_first_start_time = time.time()
                        
                    exit_first_str = datetime.datetime.fromtimestamp(exit_first_start_time).strftime('%Y-%m-%d %H:%M:%S')
                    elapsed_exit_time = int(time.time() - exit_first_start_time)
                    print(f"⚠️ [탈출 정체 스택] 미니맵 정지 감지 ({exit_stuck_count}/5 회) (최초 탈출 시작: {exit_first_str}, 누적 경과: {elapsed_exit_time}초)")
                    
                    # 🚨 [v1.14.0-hotfix2] 정지 스택 1~2회차 신속 예비 연타 복구 작동
                    if exit_stuck_count == 1:
                        # 1회차: '상자 이동' 단추 5회 연타 주입
                        coords_chest = find_chest_btn_coords(img_np, t_move_chest_act, t_move_chest_deact, 0.70)
                        if coords_chest:
                            cx, cy = coords_chest
                            print(f"👉 [정체 1단계 복구] '상자 자동 이동' 단추 연타 5회 주입 ({cx}, {cy})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {cx} {cy}")
                                time.sleep(0.1)
                        else:
                            cx_fixed, cy_fixed = int(1338 * scale_x), int(577 * scale_y)
                            print(f"👉 [정체 1단계 복구] 상자 단추 미검출로 고정 좌표 연타 5회 주입 ({cx_fixed}, {cy_fixed})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {cx_fixed} {cy_fixed}")
                                time.sleep(0.1)
                                
                    elif exit_stuck_count == 2:
                        # 2회차: '출구 이동' 단추 5회 연타 주입
                        coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                        if coords_exit:
                            ex, ey = coords_exit
                            print(f"👉 [정체 2단계 복구] '출구 이동' 단추 연타 5회 주입 ({ex}, {ey})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {ex} {ey}")
                                time.sleep(0.1)
                        else:
                            ex_fixed, ey_fixed = int(1338 * scale_x), int(462 * scale_y)
                            print(f"👉 [정체 2단계 복구] 출구 단추 미검출로 고정 좌표 연타 5회 주입 ({ex_fixed}, {ey_fixed})")
                            for _ in range(5):
                                safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                                time.sleep(0.1)
                else:
                    exit_stuck_count = 0
                
                if exit_stuck_count >= 5:
                    elapsed_exit_time = int(time.time() - exit_first_start_time)
                    if elapsed_exit_time >= 300:
                        raise RuntimeError(f"탈출 5분 초과 앱 강제 재시작: {elapsed_exit_time}초 동안 탈출하지 못하여 프로세스 강제 리셋을 수행합니다.")
                    
                    exit_recovery_retry_count += 1
                    print(f"🚪🚨 [탈출 정체 복구 작동] 정지 감지로 백스텝 후 출구단추 0.1초 연사 터치를 단행합니다. (누적 경과: {elapsed_exit_time}초, 복구 시도 {exit_recovery_retry_count}회)")
                    
                    # 1. 백스텝 드래그 (뒤로 후진)
                    sx = int(720 * scale_x)
                    sy1 = int(1200 * scale_y)
                    sy2 = int(1600 * scale_y)
                    safe_device_shell(device, f"input swipe {sx} {sy1} {sx} {sy2} 300")
                    time.sleep(1.0)
                    
                    # 2. 출구 이동 단추 0.1초 간격 2회 탭핑
                    coords_exit = find_and_get_field_btn_coords(img_np, t_move_exit, 0.70)
                    if coords_exit:
                        ex, ey = coords_exit
                        print(f"⏭️ [던전 탈출 복구] '출구 이동' 단추를 0.1초 텀 재클릭합니다. ({ex}, {ey})")
                        safe_device_shell(device, f"input tap {ex} {ey}")
                        time.sleep(0.1)
                        safe_device_shell(device, f"input tap {ex} {ey}")
                    else:
                        ex_fixed, ey_fixed = int(1338 * scale_x), int(462 * scale_y)
                        print(f"⏭️ [던전 탈출 복구] 출구 단추 미검출로 고정 좌표를 0.1초 텀 재클릭합니다. ({ex_fixed}, {ey_fixed})")
                        safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                        time.sleep(0.1)
                        safe_device_shell(device, f"input tap {ex_fixed} {ey_fixed}")
                    time.sleep(2.0)
                    
                    exit_clicked_once = False
                    exit_stuck_count = 0
                    exit_prev_minimap = None
                    state = "FIELD_WAIT"
                    last_click_time = time.time()
                    continue
            
            exit_prev_minimap = current_mini
            
            if not check_field_anchor_present(img_np, t_field, 0.62):
                if check_template_present_dynamic(img_np, t_yeolda, 0.65, 160) or chest_opener.is_minigame_screen(img_np, height, width):
                    print("⚠️ [탈출 감시] 필드가 미검출되었으나, 상자 선택창('열다') 또는 미니게임 화면이 감지되었습니다. 탈출 복귀를 취소하고 상자 해제로 이행합니다.")
                else:
                    print("🎉 [탈출 무결점 성공] 던전 필드 화면이 완전히 소멸되었습니다! 사령탑 무대로 복귀합니다.")
                    exit_clicked_once = False             # 🚨 [v1.14.0-hotfix2] 다음 판을 위한 변수 초기화
                    exit_first_start_time = None          # 🚨 [v1.14.0-hotfix2] 다음 판을 위한 변수 초기화
                    return True, skill_mission_success_this_combat
            
            if exit_touched_this_loop or exit_clicked_once:
                time.sleep(3.0)
            else:
                time.sleep(0.3)
            continue

        elif state == "IN_COMBAT":
            if get_dead_match_score(img_np, t_anchor_dead) > 0.65 or check_template_present(img_np, t_btn_resurrect, 0.60):
                print("💀 [전투 중 주인공 사망] 전멸/주인공 사망 화면이 식별되었습니다. 부활을 집도합니다.")
                if not click_dead_template(device, img_np, t_btn_resurrect, 0.60):
                    safe_device_shell(device, "input tap 720 1200")
                time.sleep(1.0)
                safe_device_shell(device, "input tap 705 1241")
                print("⏳ 부활 암전 연출 대기... 무조건 10초간 제어를 홀딩합니다.")
                time.sleep(10.0)
                need_heal = True  # 부활 즉시 정비 플래그 작동
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

            # 💡 [v1.14.1-hotfix9] 배속 및 자동 켜기 가드는 8.0초 간격으로 수행하여 자원 절약 및 로그 도배 방지
            now = time.time()
            if now - last_combat_color_check_time >= 8.0:
                last_combat_color_check_time = now
                if (not is_combat_speed_orange(img_np)) and check_combat_template_present(img_np, t_combat_slow, 0.70):
                    print("⚡ [속도 혁명] 전투 진입 확인! 배속이 회색(1배속)이므로 주황색 고속 기어로 먼저 올립니다.")
                    if find_and_click_combat_template(device, img_np, t_combat_slow, 0.65):
                        time.sleep(0.4) 
                        continue

                if run_skill_logic and skill_mission_success_this_combat:
                    if is_auto_combat_yellow(img_np):
                        print("🏆🛡️ [자동 감지] 자동전투가 이미 활성화되어 있으므로 수동 제어(수정)를 완료 처리합니다.")
                        run_skill_logic = False
                        continue
                    
                    print("🏆🛡️ [전술 이행망 작동] 핵심 광역기 가드 완수 상태 확인. 수동 모드를 즉시 해제하고 자동전투를 활성화합니다.")
                    auto_off_coords = find_and_get_auto_btn_coords(img_np, t_auto_off, 0.65)
                    if auto_off_coords: 
                        safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}")
                    else:
                        safe_device_shell(device, "input tap 1380 1720")
                    run_skill_logic = False 
                    time.sleep(1.5) 
                    continue

                if not is_auto_combat_yellow(img_np):
                    auto_off_coords = find_and_get_auto_btn_coords(img_np, t_auto_off, 0.65)
                    if (not run_skill_logic) or (not auto_combat_paused_for_skill):
                        if auto_off_coords:
                            print("⚔️🛡️ [자동전투 비활성화 감지] 자동전투를 활성화하기 위해 터치합니다.")
                            safe_device_shell(device, f"input tap {auto_off_coords[0]} {auto_off_coords[1]}") 
                            time.sleep(1.0)
                            continue

            if run_skill_logic and (not skill_mission_success_this_combat):
                if time.time() - combat_entry_start_time > 35.0:
                    print("⚠️⏰ [비상 밸브 개방] 스킬 주입 제한시간 초과! 즉시 극하단 안전 좌표로 고속 자동전투 전환합니다.")
                    safe_device_shell(device, "input tap 1380 1720") 
                    run_skill_logic = False
                    continue

                if not auto_combat_paused_for_skill:
                    # 노란색(자동 온) 상태인지 컬러 판정!
                    # 만약 이미 꺼져 있다면(회색) 추가 클릭 없이 바로 auto_combat_paused_for_skill = True로 넘어감
                    if not is_auto_combat_yellow(img_np):
                        print("⚔️🛡️ [자동 감지] 자동 전투가 이미 꺼져(회색) 있습니다. 일시 중단을 확정합니다.")
                        auto_combat_paused_for_skill = True
                        continue
                        
                    auto_on_coords = find_and_get_auto_btn_coords(img_np, t_auto_on, 0.65)
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



            if not check_combat_template_present(img_np, t_combat_in, 0.65) and not check_combat_template_present(img_np, t_combat_slow, 0.65):
                print("🎉 배속마크 소멸! 필드로 주도권 복구 수순 가동. (연출 마진 확보를 위해 3.0초 슬로우 브레이크 가동)")
                came_from_combat = True 
                state = "FIELD_WAIT"
                time.sleep(3.0) 
            else: time.sleep(0.3)

        elif state == "BRANCH_CHECK":
            if chest_opener.is_minigame_screen(img_np, height, width): state = "PLAY_MINIGAME"
            elif check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75): state = "CLEAR_CHECK"
            else: time.sleep(0.2)

        elif state == "PLAY_MINIGAME":
            chest_opener.solve_trap_game(device, img_np)
            try: img_np_post = np.array(Image.open(io.BytesIO(device.screencap())))
            except: continue
            if chest_opener.is_minigame_screen(img_np_post, height, width): state = "PLAY_MINIGAME"
            else: state = "CLEAR_CHECK"
            continue

        elif state == "CLEAR_CHECK":
            if check_dialogue_indicator_present(img_np, t_dialogue_indicator, 0.75):
                safe_device_shell(device, "input tap 701 333")
                time.sleep(0.8)
            else:
                if check_field_anchor_present(img_np, t_field, 0.65):
                    print("✨ [상자깡 완료 및 필드 안착] 다음 탐색으로 정상 복귀합니다.")
                    state = "FIELD_WAIT"
                    came_from_chest = True
                    time.sleep(1.0)
                else:
                    time.sleep(0.3)

        time.sleep(0.001)