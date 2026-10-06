# -*- coding: utf-8 -*-
"""
💀🔀 파티바(던전선택/마을외곽 화면 아래 6명 카드) 사망자 판정 + 대열 원복 - 2026-10-06 (ROADMAP 0-B)

왜: 전열 캐릭터가 죽으면 게임이 후열 캐릭터를 자동으로 앞으로 당긴다(예: 3번 아베니우스 사망 -> 6번 밀라나가 3번으로).
대하켄이 열린 마을외곽 던전은 마을 복귀 때 부활하지만 대열은 섞인 채로 남아 HEALER_SLOT/MASKED_ADVENTURER_SLOT/
CHEST_OPENER_SLOT(슬롯 번호 설정)이 엉뚱한 캐릭터를 가리키게 된다. 그래서 여관 숙박 뒤 마을외곽 던전선택 화면에서
"순서변경" 버튼을 켜고 카드를 꾹 눌러 끌어 원래 슬롯으로 되돌린다(끌어 놓으면 두 카드가 자리를 바꾼다).

실측(1440x2560, dev/ROI_check/마을외곽-사망자배열변경 (1~3).png, 사망캐릭 순서변경 (1~4).png, 던전선택-백아/유령성/
루크나리아 마을외곽/이스벨크 마을외곽):
- 카드 격자: x = 45 / 499 / 954, y = 1971(윗줄 1~3번) / 2259(아랫줄 4~6번), 카드 크기 437x272. 필드 HUD도 같은 자리.
- 사망 판정 = 이름 줄의 주황빛 글자 픽셀 수: 사망 432~638개(글자 픽셀 대비 90%+) vs 생존 0개(11개 화면 전부).
  (카드 배경 R-B 값은 생존 최고 +12(루크나리아 배경) vs 사망 최저 +16으로 여유가 없어 쓰지 않는다)
- 캐릭터 식별 = 이름 줄 그레이스케일 대조: 같은 캐릭터 0.94~1.00 vs 다른 캐릭터 최고 0.38.
- 순서변경 버튼(파티바 위 오른쪽에서 두 번째 아이콘, 1200~1275 x 1835~1905): 켜짐 = 노랑 픽셀 1478~1799 vs 무채색 228~256,
  꺼짐 = 노랑 0 vs 무채색 819~1040, 루크나리아 모래 배경(꺼짐) 노랑 768 vs 무채색 1394.
✅ [2026-10-06 실기 확인] 백아 던전선택 화면(같은 버튼/카드 배치)에서 motionevent(DOWN -> 1초 -> MOVE 8단계 -> UP)가 첫 시도에 2<->3 교환 성공,
   restore_formation() 전체(버튼 켜기 -> 끌기 -> 검증 -> 버튼 끄기) 14초. draganddrop/swipe 는 예비로만 남겨 둔다.
"""
import os
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, "formation_ref")   # 기준 대열(슬롯별 이름 크롭). git/릴리즈 제외

CARD_X = (45, 499, 954)
CARD_Y = (1971, 2259)
CARD_W, CARD_H = 437, 272
NAME_ROI = (40, 52, 400, 108)          # 카드 기준 (x1, y1, x2, y2) - 이름 줄
DEAD_RED_MIN = 150                     # 이름 줄 주황 글자 픽셀 수 기준(사망 432+ / 생존 0)
DEAD_RED_RATIO = 0.5                   # 글자 픽셀 중 주황 비율 기준(사망 0.69~0.98)
REORDER_BTN_ROI = (1200, 1835, 1275, 1905)
REORDER_BTN_CENTER = (1237, 1870)
NAME_MATCH_TH = 0.80                   # 같은 캐릭터 판정(실측 0.94+ vs 최고 0.38)
NAME_UNIQUE_MAX = 0.70                 # 기준 저장 시 카드끼리 이 이상 닮으면(같은 이름 등) 저장하지 않는다


def card_origin(slot):
    i = slot - 1
    return CARD_X[i % 3], CARD_Y[i // 3]


def card_center(slot):
    x, y = card_origin(slot)
    return x + CARD_W // 2, y + CARD_H // 2


def _rgb(img_np):
    return img_np[:, :, :3]


def _name_crop(img_np, slot):
    x, y = card_origin(slot)
    x1, y1, x2, y2 = NAME_ROI
    return _rgb(img_np)[y + y1:y + y2, x + x1:x + x2]


def _name_gray(img_np, slot):
    return cv2.cvtColor(np.ascontiguousarray(_name_crop(img_np, slot)), cv2.COLOR_RGB2GRAY)


def has_party_bar(img_np):
    return img_np is not None and img_np.shape[0] >= 2560 and img_np.shape[1] >= 1440


def dead_slots(img_np):
    """이름이 주황빛(사망 표시)인 카드 슬롯 번호 목록. 입력은 매크로 캡처(RGB/RGBA)."""
    if not has_party_bar(img_np):
        return []
    out = []
    for slot in range(1, 7):
        c = _name_crop(img_np, slot).astype(np.int16)
        R, G, B = c[:, :, 0], c[:, :, 1], c[:, :, 2]
        txt = np.maximum(np.maximum(R, G), B) > 140
        red = txt & (R - B > 90) & (R - G > 50)
        n_red, n_txt = int(red.sum()), int(txt.sum())
        if n_red >= DEAD_RED_MIN and n_red >= n_txt * DEAD_RED_RATIO:
            out.append(slot)
    return out


def reorder_button_on(img_np):
    """아이콘 픽셀이 노랑(켜짐)이 무채색(꺼짐)보다 많으면 켜짐. 평균 색은 모래색 배경(루크나리아)에서 틀려 쓰지 않는다."""
    x1, y1, x2, y2 = REORDER_BTN_ROI
    c = _rgb(img_np)[y1:y2, x1:x2].astype(np.int16)
    R, G, B = c[:, :, 0], c[:, :, 1], c[:, :, 2]
    mx = np.maximum(np.maximum(R, G), B)
    mn = np.minimum(np.minimum(R, G), B)
    neutral = int(((mx > 120) & (mx - mn < 35)).sum())
    yellow = int(((mx > 110) & (R - B > 60) & (G - B > 35)).sum())
    return yellow > neutral


# ---------------------------------------------------------------- 기준 대열
def _ref_path(slot):
    return os.path.join(REF_DIR, f"slot{slot}.png")


def load_reference():
    refs = {}
    for slot in range(1, 7):
        p = _ref_path(slot)
        if not os.path.exists(p):
            return None
        g = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_GRAYSCALE)
        if g is None:
            return None
        refs[slot] = g
    return refs


def _score(cur_gray, ref_gray):
    t = ref_gray[4:-4, 10:-10]   # 위치가 몇 픽셀 흔들려도 맞도록 기준을 조금 깎아 슬라이드
    return float(cv2.matchTemplate(cur_gray, t, cv2.TM_CCOEFF_NORMED).max())


def names_distinct(img_np):
    g = {s: _name_gray(img_np, s) for s in range(1, 7)}
    for a in range(1, 7):
        for b in range(1, 7):
            if a != b and _score(g[a], g[b]) >= NAME_UNIQUE_MAX:
                return False
    return True


def save_reference(img_np):
    os.makedirs(REF_DIR, exist_ok=True)
    for slot in range(1, 7):
        cv2.imencode(".png", _name_gray(img_np, slot))[1].tofile(_ref_path(slot))


def current_positions(img_np, refs):
    """{기준 슬롯: 지금 그 캐릭터가 있는 슬롯}. 한 명이라도 못 찾거나 겹치면 None."""
    cur = {s: _name_gray(img_np, s) for s in range(1, 7)}
    pos = {}
    for rs in range(1, 7):
        scores = {cs: _score(cur[cs], refs[rs]) for cs in range(1, 7)}
        best = max(scores, key=scores.get)
        if scores[best] < NAME_MATCH_TH:
            return None
        pos[rs] = best
    if len(set(pos.values())) != 6:
        return None
    return pos


def check_reference(img_np, fresh_start, log=print):
    """마을외곽 화면에서 기준 대열을 준비한다. 사망자가 없을 때만 저장.
    기준이 없으면 저장하고, 매크로를 직접 켠 뒤 첫 확인에서 지금 대열이 기준과 다르면(사용자가 대열/멤버를 바꿈) 새로 저장.
    반환: 기준(dict) 또는 None."""
    refs = load_reference()
    if dead_slots(img_np):
        return refs
    if refs is not None and not fresh_start:
        return refs
    if refs is not None and current_positions(img_np, refs) == {s: s for s in range(1, 7)}:
        return refs
    if not names_distinct(img_np):
        log("⚠️ [대열 기준] 카드 이름끼리 너무 닮아(같은 이름?) 기준 대열을 저장하지 않습니다 - 대열 원복은 쉽니다.")
        return refs
    save_reference(img_np)
    log("🧬 [대열 기준] " + ("기준 대열이 없어" if refs is None else "직접 시작 후 첫 확인에서 대열이 기준과 달라")
        + " 지금 파티바를 기준 대열로 저장했습니다(formation_ref/).")
    return load_reference()


# ---------------------------------------------------------------- 드래그
def _drag(device, src_slot, dst_slot, method):
    x1, y1 = card_center(src_slot)
    x2, y2 = card_center(dst_slot)
    if method == "motionevent":
        steps = 8
        cmd = [f"input motionevent DOWN {x1} {y1}", "sleep 1.0"]
        for k in range(1, steps + 1):
            cmd.append(f"input motionevent MOVE {x1 + (x2 - x1) * k // steps} {y1 + (y2 - y1) * k // steps}")
        cmd += ["sleep 0.3", f"input motionevent UP {x2} {y2}"]
        device.shell("; ".join(cmd))
    elif method == "draganddrop":
        device.shell(f"input draganddrop {x1} {y1} {x2} {y2} 1500")
    else:
        device.shell(f"input swipe {x1} {y1} {x2} {y2} 2500")


DRAG_METHODS = ("motionevent", "draganddrop", "swipe")


def restore_formation(device, capture, refs, log=print):
    """순서변경 버튼을 켜고 카드를 끌어 기준 대열로 되돌린다. capture() -> 최신 화면(RGB).
    반환: "ok"(원복 완료/이미 같음) / "fail"(입력이 안 먹거나 판정 불가 - 그대로 진행)."""
    img = capture()
    pos = current_positions(img, refs)
    if pos is None:
        log("⚠️ [대열 원복] 지금 파티바에서 기준 캐릭터를 다 찾지 못했습니다(멤버 교체?) - 원복하지 않습니다.")
        return "fail"
    if all(pos[s] == s for s in pos):
        return "ok"
    log(f"🔀 [대열 원복] 대열이 기준과 다릅니다(기준 슬롯->지금 슬롯 {pos}). 순서변경으로 되돌립니다.")
    result = "fail"
    method_i = 0
    for _ in range(12):
        img = capture()
        if not reorder_button_on(img):
            device.shell(f"input tap {REORDER_BTN_CENTER[0]} {REORDER_BTN_CENTER[1]}")
            time.sleep(1.0)
            img = capture()
            if not reorder_button_on(img):
                log("⚠️ [대열 원복] 순서변경 버튼이 켜지지 않습니다 - 원복을 중단합니다.")
                break
        pos = current_positions(img, refs)
        if pos is None:
            log("⚠️ [대열 원복] 끌기 도중 캐릭터 판정 실패 - 원복을 중단합니다.")
            break
        wrong = [s for s in range(1, 7) if pos[s] != s]
        if not wrong:
            log("✅ [대열 원복] 기준 대열로 되돌렸습니다.")
            result = "ok"
            break
        dst = wrong[0]
        src = pos[dst]
        method = DRAG_METHODS[method_i]
        log(f"   👉 [대열 원복] {src}번 카드 -> {dst}번 자리로 끌기({method})")
        _drag(device, src, dst, method)
        time.sleep(1.2)
        after = current_positions(capture(), refs)
        if after == pos:   # 아무 변화 없음 -> 다음 입력 방식
            method_i += 1
            if method_i >= len(DRAG_METHODS):
                log("⚠️ [대열 원복] 세 가지 끌기 방식이 모두 먹히지 않았습니다 - 원복을 중단합니다(실기 확인 필요).")
                break
        else:
            log(f"   ✅ [대열 원복] 끌기 반영됨({method})")
    # 순서변경 버튼 끄기
    for _ in range(3):
        img = capture()
        if not reorder_button_on(img):
            break
        device.shell(f"input tap {REORDER_BTN_CENTER[0]} {REORDER_BTN_CENTER[1]}")
        time.sleep(1.0)
    return result
