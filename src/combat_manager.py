# ==============================================================================
# 📋 [버전 정보 및 히스토리]
# - 현재 버전: 1.14.1
# - 최근 수정일: 2026-07-03 23:55
# - 수정 기록:
#   1.14.1: 신규 스마트 룰 엔진 기반 전투 제어 엔진(combat_manager.py) 탑재
# ==============================================================================
import os
import time
import json
import io
import random
import cv2
import numpy as np
from PIL import Image

# 🖥️ 1440x2560 해상도 기반 매크로 고정 좌표계 및 관심구역 (ROI)
COORDS_SKILL_SLOTS = {
    1: (426, 1544),  # 좌상
    2: (1024, 1544), # 우상
    3: (426, 1686),  # 좌하
    4: (1024, 1686)  # 우하
}

COORDS_PARTY_GRID = {
    "전열좌": (320, 1920),
    "전열중": (720, 1920),
    "전열우": (1120, 1920),
    "후열좌": (320, 2240),
    "후열중": (720, 2240),
    "후열우": (1120, 2240)
}

# ROI 900x1600 -> 1440x2560 스케일 업 (1.6 배수) 적용
ROI_ACTIVE_CHAR = (139, 88, 117, 82)          # 활성화 캐릭터 portrait ROI
ROI_SUPPORT_CHECK = (1083, 2360, 302, 128)     # 아군 대상 지정 UI ROI

COORDS_AUTO_BATTLE = (1360, 1760)               # 자동전투 버튼 위치

# 🇰🇷 한국어 캐릭터 이름 -> 영문 도장 파일명 매핑 사전 (wizardry_txt_filenames_v3.xlsx 기준 및 한글 별칭 보강)
CHARACTER_NAME_MAP = {
    "아베니우스": "Abenius",
    "아베니스": "Abenius",
    "아담": "Adam",
    "아이닛키": "Ainikki",
    "올드릭": "Aldric",
    "알렉스": "Alex",
    "앨리스": "Alice",
    "엘리스": "Alice",
    "아멜리아": "Amelia",
    "아네모네": "Anemone",
    "아르보리스": "Arboris",
    "아샤": "Asha",
    "바케쉬": "Bakesh",
    "바르바라": "Barbara",
    "무명수인도적": "Beast-Thi",
    "벤자민": "Benjamin",
    "벨카난": "Berkanan",
    "베카남": "Berkanan",
    "부겐": "Bugen",
    "카밀": "Camille",
    "클로에": "Chloe",
    "클라리사": "Clarissa",
    "다니엘": "Daniel",
    "데보라": "Debra",
    "데브라": "Debra",
    "디노": "Dino",
    "무명드워프기사": "Dwarf-Kni",
    "에카르트": "Eckart",
    "엘더": "Elda",
    "엘도라도": "Eldorado",
    "무명엘프법사": "Elf-Mag",
    "무명엘프승려": "Elf-Pri",
    "엘리제": "Elise",
    "에밀": "Emil",
    "엘빈": "Erwin",
    "에우라리아": "Eulalia",
    "플루트": "Flut",
    "포르테": "Flut",
    "갈바두스": "Galbadus",
    "갈리나": "Galina",
    "간돌프": "Gandolfo",
    "개스턴": "Gaston",
    "가스통": "Gaston",
    "제라드": "Gerard",
    "게를루프": "Gerulf",
    "기리온": "Gillion",
    "하인리크": "Heinrico",
    "하인리히": "Heinrico",
    "무명인간전사": "Human-Fig",
    "무명인간닌자": "Human-Nin",
    "무명인간승려": "Human-Pri",
    "무명인간사무라이": "Human-Sam",
    "이알마스": "Iarumas",
    "야마스": "Iarumas",
    "쟝": "Jean",
    "장": "Jean",
    "카케로우": "Kagero",
    "카게로우": "Kagero",
    "키리하": "Kiriha",
    "라나뷔유": "Lanavaille",
    "라나": "Lanavaille",
    "리나리아": "Livana",
    "리바나": "Livana",
    "마리안느": "Marianne",
    "밀라나": "Milana",
    "올리브": "Olive",
    "오펠리아": "Ophelia",
    "필립": "Philip",
    "라파엘로": "Raffaello",
    "붉은수염": "Red Beard",
    "린네": "Rinne",
    "사비아": "Savia",
    "셰리리냐": "Shelirionach",
    "시오우": "Shiou",
    "발도르": "Valdor",
    "비비아나": "Viviana",
    "예카테리나": "Yekaterina",
    "에카테리나": "Yekaterina",
    "요이조": "Yoizou",
    "유르사": "Yrsa",
    "유즈나미키": "Yuzunamiki",
    "유즈나": "Yuzunamiki"
}

# 런타임 활성 전투 전략 큐
active_strategy_queue = []

# 이미지 템플릿 보관소
portrait_templates = {}
level_templates = {}
t_skill_detail = None
t_support_check = None
t_not_enough_mp = None
t_not_enough_sp = None
t_ok_btn = None
t_next_btn = None

def load_grayscale_image(path):
    if not os.path.exists(path):
        return None
    try:
        pil_img = Image.open(path).convert('RGB')
        img_np = np.array(pil_img)
        return cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    except:
        return None

def initialize_templates(workspace_dir):
    """
    포트레이트 및 레벨 템플릿 이미지를 일괄 캐싱 로드합니다.
    공식 templates/skill 디렉토리를 참조합니다.
    """
    global portrait_templates, level_templates, t_skill_detail, t_support_check, t_not_enough_mp, t_not_enough_sp, t_ok_btn, t_next_btn
    
    print("🔍 [combat_manager] templates/skill 디렉토리를 템플릿 탐색 경로로 설정합니다.")
    templates_path = os.path.join(workspace_dir, "templates")
    skill_path = os.path.join(templates_path, "skill")
    char_path = os.path.join(skill_path, "char")
    lvl_path = os.path.join(skill_path, "skillLvl")
    base_path = skill_path
    parent_templates_path = templates_path
    
    # 1. 포트레이트 템플릿 로드
    portrait_templates.clear()
    if os.path.exists(char_path):
        for file in os.listdir(char_path):
            if file.endswith(".png") and not file.endswith("_red.png"):  # 빨간색 꼬리표 제외
                base_name = os.path.splitext(file)[0]
                img = load_grayscale_image(os.path.join(char_path, file))
                if img is not None:
                    portrait_templates[base_name] = img
        print(f"🔮 [combat_manager] 캐릭터 얼굴 도장 로드 성공: {len(portrait_templates)}개 로드 완료.")
    else:
        print(f"⚠️ [combat_manager] 포트레이트 경로를 찾을 수 없습니다: {char_path}")

    # 2. 레벨 템플릿 로드
    level_templates.clear()
    if os.path.exists(lvl_path):
        for file in os.listdir(lvl_path):
            if file.endswith(".png"):
                base_name = os.path.splitext(file)[0]
                img = load_grayscale_image(os.path.join(lvl_path, file))
                if img is not None:
                    level_templates[base_name] = img
        print(f"🔮 [combat_manager] 스킬 레벨 도장 로드 성공: {len(level_templates)}개 로드 완료.")
    else:
        print(f"⚠️ [combat_manager] 레벨 경로를 찾을 수 없습니다: {lvl_path}")

    # 3. 기타 유틸리티 템플릿 로드
    t_skill_detail = load_grayscale_image(os.path.join(base_path, "skillDetail.png"))
    # 만약 작업 디렉토리에 없으면 부모 templates/ 에서 폴백 로드
    t_support_check = load_grayscale_image(os.path.join(base_path, "supportSkillCheck.png")) or load_grayscale_image(os.path.join(parent_templates_path, "supportSkillCheck.png"))
    t_not_enough_mp = load_grayscale_image(os.path.join(base_path, "notenoughmp.png")) or load_grayscale_image(os.path.join(parent_templates_path, "notenoughmp.png"))
    t_not_enough_sp = load_grayscale_image(os.path.join(base_path, "notenoughsp.png")) or load_grayscale_image(os.path.join(parent_templates_path, "notenoughsp.png"))
    t_ok_btn = load_grayscale_image(os.path.join(base_path, "OK.png")) or load_grayscale_image(os.path.join(parent_templates_path, "OK.png"))
    t_next_btn = load_grayscale_image(os.path.join(base_path, "next.png")) or load_grayscale_image(os.path.join(parent_templates_path, "next.png"))

def load_combat_strategy(workspace_dir):
    """
    combat_strategy.json 파일을 파싱하여 활성 전략 큐를 구성합니다.
    """
    global active_strategy_queue
    active_strategy_queue.clear()

    json_path = os.path.join(workspace_dir, "combat_strategy.json")
    if not os.path.exists(json_path):
        print("⚠️ [combat_manager] combat_strategy.json 전략 파일을 찾을 수 없습니다. 기본 자동 전투로 대체됩니다.")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        overall = data.get("overall_strategy", "")
        strategies = data.get("strategies", {})
        selected_strategy = strategies.get(overall, [])

        for step in selected_strategy:
            char_name = step.get("character", "").strip()
            skill_slot = int(step.get("skill_slot", 1))
            skill_lvl = int(step.get("level", 1))
            target = step.get("target", "enemy").strip()

            # 한글/영문 닉네임을 영문 도장 포트레이트 파일명 기준으로 번역
            char_base = CHARACTER_NAME_MAP.get(char_name, char_name)
            
            active_strategy_queue.append({
                "char_base": char_base,
                "skill_slot": skill_slot,
                "level": skill_lvl,
                "target": target
            })
            
        print(f"⚔️ [combat_manager] 활성 전략 '{overall}' 장착 완료. 총 {len(active_strategy_queue)}개 스킬 체인 대기 중.")
    except Exception as e:
        print(f"❌ [combat_manager] 전략 파싱 오류 발생: {e}")

def template_match_score(search_gray, template_gray, roi=None):
    """
    그레이스케일 템플릿 매칭을 일반 수행하여 최대 일치율과 중심 좌표를 반환합니다.
    """
    if search_gray is None or template_gray is None:
        return 0.0, None

    if roi:
        x, y, w, h = roi
        search_area = search_gray[y:y+h, x:x+w]
    else:
        search_area = search_gray

    h_s, w_s = search_area.shape[:2]
    h_t, w_t = template_gray.shape[:2]
    if h_s < h_t or w_s < w_t:
        return 0.0, None

    res = cv2.matchTemplate(search_area, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    match_coords = None
    if max_loc:
        cx = max_loc[0] + int(w_t / 2)
        cy = max_loc[1] + int(h_t / 2)
        if roi:
            match_coords = (cx + roi[0], cy + roi[1])
        else:
            match_coords = (cx, cy)

    return max_val, match_coords

def detect_active_character(img_np):
    """
    현재 스크린샷에서 활성화된 아군의 얼굴 템플릿을 식별하여 반환합니다.
    """
    if not portrait_templates:
        return None

    gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    highest_score = 0.0
    matched_name = None

    for name, temp in portrait_templates.items():
        score, _ = template_match_score(gray_img, temp, ROI_ACTIVE_CHAR)
        if score > highest_score:
            highest_score = score
            matched_name = name

    # 매칭률 80% 이상인 경우에만 감지 확정
    if highest_score >= 0.80:
        print(f"🧙‍♂️ [combat_manager] 활성 캐릭터 도장 검출: '{matched_name}' (일치율: {highest_score * 100:.1f}%)")
        return matched_name
    return None

def fallback_auto_combat(device):
    """
    지정된 행위가 없거나 부족할 때, 자동전투 버튼을 더블 타격하여 자율 동작하게 합니다.
    """
    print("🛡️ [combat_manager] 행동 룰이 없으므로 자동 전투(Auto) 자율 행동으로 원상 복귀합니다.")
    device.shell(f"input tap {COORDS_AUTO_BATTLE[0]} {COORDS_AUTO_BATTLE[1]}")
    time.sleep(0.5)
    device.shell(f"input tap {COORDS_AUTO_BATTLE[0]} {COORDS_AUTO_BATTLE[1]}")
    time.sleep(1.5)

def execute_char_turn(device, img_np, active_char_filename):
    """
    식별된 활성 캐릭터의 전략을 조회하고 격발 동작을 수행합니다.
    active_char_filename: 예 'Yuzunamiki_Ninja' 등 검출된 영문 파일명
    """
    global active_strategy_queue

    # 1. 큐에서 해당 캐릭터를 대상으로 하는 첫 번째 설정 탐색 (대소문자 구분 없이 부분 일치로 매칭)
    target_action = None
    for action in active_strategy_queue:
        char_base = action["char_base"].lower()
        if char_base in active_char_filename.lower():
            target_action = action
            break

    if not target_action:
        print(f"🔍 [combat_manager] 캐릭터 '{active_char_filename}'에 매칭되는 설정된 전략이 없습니다.")
        fallback_auto_combat(device)
        return False

    skill_slot = target_action["skill_slot"]
    skill_lvl = target_action["level"]
    target = target_action["target"]

    print(f"🔥 [combat_manager] 스킬 격발 실행: {active_char_filename} -> 단축 슬롯 {skill_slot} (레벨 {skill_lvl}, 대상: {target})")

    # 2. 숏컷 탭 시도 (최대 3회 스크린 피드백 대기)
    slot_coords = COORDS_SKILL_SLOTS.get(skill_slot, COORDS_SKILL_SLOTS[1])
    into_detail = False
    
    for _ in range(3):
        device.shell(f"input tap {slot_coords[0]} {slot_coords[1]}")
        time.sleep(1.0)
        
        try:
            curr_cap = device.screencap()
            curr_np = np.array(Image.open(io.BytesIO(curr_cap)))
            curr_gray = cv2.cvtColor(curr_np, cv2.COLOR_RGB2GRAY)
        except:
            continue
            
        score, _ = template_match_score(curr_gray, t_skill_detail)
        if score >= 0.75:
            into_detail = True
            break

    if not into_detail:
        print("⚠️ [combat_manager] 스킬 설명 패널 검출 실패! 자원이 부족한 것으로 판단하고 자율 행동(Auto) 처리합니다.")
        for _ in range(3):
            device.shell("input keyevent KEYCODE_BACK")
            time.sleep(0.2)
        fallback_auto_combat(device)
        return False

    # 3. 스킬 레벨(Lvl) 터치
    level_found = False
    for lvl_prefix in [f"lv{skill_lvl}", f"s_lv{skill_lvl}"]:
        temp_img = level_templates.get(lvl_prefix)
        if temp_img is not None:
            score, coords = template_match_score(curr_gray, temp_img)
            if score >= 0.70 and coords:
                device.shell(f"input tap {coords[0]} {coords[1]}")
                print(f"🎯 [combat_manager] 레벨 {skill_lvl} 구역 매칭 타격 성공! (좌표: {coords})")
                level_found = True
                break

    if not level_found and skill_lvl > 1:
        print(f"⚠️ [combat_manager] 목표 레벨 {skill_lvl} 매칭 실패. 기본 1단계 레벨로 우회 격타 시도.")
        for lvl_prefix in ["lv1", "s_lv1"]:
            temp_img = level_templates.get(lvl_prefix)
            if temp_img is not None:
                score, coords = template_match_score(curr_gray, temp_img)
                if score >= 0.70 and coords:
                    device.shell(f"input tap {coords[0]} {coords[1]}")
                    break
        time.sleep(0.5)

    # 4. 아군 타겟팅 여부 감지 및 타겟팅
    time.sleep(0.5)
    try:
        curr_cap = device.screencap()
        curr_np = np.array(Image.open(io.BytesIO(curr_cap)))
        curr_gray = cv2.cvtColor(curr_np, cv2.COLOR_RGB2GRAY)
    except:
        pass
        
    score_support, _ = template_match_score(curr_gray, t_support_check, ROI_SUPPORT_CHECK)
    if score_support >= 0.70:
        target_coords = COORDS_PARTY_GRID.get(target)
        if target_coords:
            device.shell(f"input tap {target_coords[0]} {target_coords[1]}")
            print(f"💚 [combat_manager] 아군 타겟 지정 터치 주입: '{target}' ({target_coords})")
        else:
            device.shell(f"input tap {COORDS_PARTY_GRID['전열중'][0]} {COORDS_PARTY_GRID['전열중'][1]}")
            print("💚 [combat_manager] 대상 미지정으로 기본 대상(전열중) 터치 주입.")
        time.sleep(0.5)

    # 5. 최종 확인 (OK / Next / 적 랜덤 타격)
    try:
        curr_cap = device.screencap()
        curr_np = np.array(Image.open(io.BytesIO(curr_cap)))
        curr_gray = cv2.cvtColor(curr_np, cv2.COLOR_RGB2GRAY)
    except:
        pass

    score_ok, coords_ok = template_match_score(curr_gray, t_ok_btn)
    score_next, coords_next = template_match_score(curr_gray, t_next_btn)

    if score_ok >= 0.75 and coords_ok:
        device.shell(f"input tap {coords_ok[0]} {coords_ok[1]}")
        print("✅ [combat_manager] 전체 스킬 확인(OK) 단추 격타 완료.")
    elif score_next >= 0.70 and coords_next:
        tx = coords_next[0] - 24 + random.randint(0, 48)
        ty = coords_next[1] + 240 + random.randint(0, 48)
        device.shell(f"input tap {tx} {ty}")
        print(f"✅ [combat_manager] 단체 스킬 조준 사격 완료. Target Next 보정 좌표: ({tx}, {ty})")
    else:
        rx = random.randint(120, 1400)
        ry = random.randint(480, 1400)
        device.shell(f"input tap {rx} {ry}")
        print(f"✅ [combat_manager] 확인 단추 미검출. 적 전열 영역 랜덤 사격: ({rx}, {ry})")

    # 6. 마나/SP 부족 팝업 체크 복구 가드
    time.sleep(1.0)
    try:
        curr_cap = device.screencap()
        curr_np = np.array(Image.open(io.BytesIO(curr_cap)))
        curr_gray = cv2.cvtColor(curr_np, cv2.COLOR_RGB2GRAY)
    except:
        return True

    score_nmp, _ = template_match_score(curr_gray, t_not_enough_mp)
    score_nsp, _ = template_match_score(curr_gray, t_not_enough_sp)

    if score_nmp >= 0.70 or score_nsp >= 0.70:
        print("⚠️ [combat_manager] 마력/SP 부족 경고 팝업 검출! 백스텝 후 1단계 스킬로 강제 하향 재시도합니다.")
        for _ in range(3):
            device.shell("input keyevent KEYCODE_BACK")
            time.sleep(0.2)
        target_action["level"] = 1
        return execute_char_turn(device, img_np, active_char_filename)

    # 7. 행동 성공 완료 후 큐에서 제거
    if target_action in active_strategy_queue:
        active_strategy_queue.remove(target_action)
        print(f"🏆 [combat_manager] 스킬 격발 체인 완수. 전략 큐 잔량: {len(active_strategy_queue)}개.")

    return True
