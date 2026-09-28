# -*- coding: utf-8 -*-
"""
📦 상자만 자동 오픈 (손으로 플레이하면서 상자만 매크로에 맡기는 용도) - 2026-09-28

루트의 "상자 자동오픈(수동플레이용).bat"으로 실행한다. 던전 이동/전투는 전혀 하지 않고,
화면에 상자 관련 화면이 보일 때만 처리한다:
  '열다' 선택지 -> 열기 / '누가 열 거야?' -> 따개 슬롯 선택 / 함정 미니게임 -> 조준(매크로박스님 방식)
- 따개/주인공 슬롯과 조준 영점 보정 모드는 src/main.py 글로벌 설정 값을 그대로 읽는다(main.py를 import 하지는
  않는다 - import 하면 매크로 본체가 기동된다).
- 본 매크로와 같은 단일 실행 잠금을 잡아 둘이 동시에 돌지 않는다. macro.pid 를 써서 원격 대시보드에서 정지 가능.
- 로그: logs/<시각>_chestonly.txt
"""
import os
import sys
import ast
import time
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from single_instance import enforce_single_instance_or_exit
enforce_single_instance_or_exit()

from ppadb.client import Client as AdbClient
import chest_opener as co
from screen_capture import capture_screen_bytes, decode_screen_bytes

PORTS = ["16448", "5559", "16384", "16385", "5555", "16416", "5557"]


def read_main_settings():
    """src/main.py 최상단의 단순 대입(숫자/문자열)만 읽는다."""
    wanted = {"CHEST_OPENER_SLOT": 6, "MASKED_ADVENTURER_SLOT": 3, "CHEST_AIM_CALIBRATION": "auto",
              "CHEST_AIM_MANUAL_GLIDE_PX": None, "CHEST_AIM_MANUAL_LATENCY_MS": None,
              "CHEST_AIM_MANUAL_JITTER_MS": None, "CHEST_AIM_PRESERVE_MENTAL": 1}
    try:
        tree = ast.parse(open(os.path.join(ROOT, "src", "main.py"), encoding="utf-8-sig").read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in wanted:
                    try:
                        wanted[name] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    except Exception as e:
        print(f"⚠️ [상자 자동오픈] main.py 설정을 못 읽어 기본값을 씁니다: {e}")
    return wanted


class Tee:
    def __init__(self, path):
        self.term = sys.stdout
        self.f = open(path, "a", encoding="utf-8")
        self.at_line_start = True

    def write(self, s):
        out = []
        if self.at_line_start and s.lstrip(chr(10)).startswith("[20"):
            self.at_line_start = False            # chest_opener 가 이미 시각을 붙인 줄 - 중복 방지
        for ch in s:
            if self.at_line_start and ch != "\n":
                out.append(datetime.datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] ")
                self.at_line_start = False
            out.append(ch)
            if ch == "\n":
                self.at_line_start = True
        text = "".join(out)
        try:
            self.term.write(text)
        except Exception:
            pass
        self.f.write(text)
        self.f.flush()

    def flush(self):
        try:
            self.term.flush()
        except Exception:
            pass
        self.f.flush()


def connect():
    """매크로 본체와 같은 규칙: 마지막 연결 포트(mumu_last_port.txt)부터 먼저, 안 되면 전체 포트 스캔."""
    t0 = time.time()
    os.system("adb start-server > nul 2>&1")
    client = AdbClient(host="127.0.0.1", port=5037)
    last = None
    try:
        with open(os.path.join(ROOT, "mumu_last_port.txt"), encoding="utf-8") as f:
            last = f.read().strip() or None
    except Exception:
        pass
    if last:
        os.system(f"adb connect 127.0.0.1:{last} > nul 2>&1")
        try:
            d = client.device(f"127.0.0.1:{last}")
            if d is not None and d.get_state() == "device":
                print(f"✅ [상자 자동오픈] ADB 연결: 127.0.0.1:{last} (마지막 포트 바로 연결 · {time.time() - t0:.1f}초)")
                return d
        except Exception:
            pass
    for p in PORTS:
        os.system(f"adb connect 127.0.0.1:{p} > nul 2>&1")
    for p in PORTS:
        d = client.device(f"127.0.0.1:{p}")
        if d is not None:
            print(f"✅ [상자 자동오픈] ADB 연결: 127.0.0.1:{p} (전체 포트 스캔 · {time.time() - t0:.1f}초)")
            return d
    return None


def main():
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", datetime.datetime.now().strftime("%Y-%m-%d-%H%M") + "_chestonly.txt")
    sys.stdout = Tee(log_path)
    try:
        with open(os.path.join(ROOT, "macro.pid"), "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    cfg = read_main_settings()
    opener, hero = cfg["CHEST_OPENER_SLOT"], cfg["MASKED_ADVENTURER_SLOT"]
    print(f"📦 [상자 자동오픈] 시작 - 로그: {log_path} · 따개 {opener}번 · 주인공 {hero}번")
    co.set_aim_calibration(cfg["CHEST_AIM_CALIBRATION"], cfg["CHEST_AIM_MANUAL_GLIDE_PX"],
                           cfg["CHEST_AIM_MANUAL_LATENCY_MS"], cfg["CHEST_AIM_MANUAL_JITTER_MS"])
    co.set_chest_preserve_mental(cfg["CHEST_AIM_PRESERVE_MENTAL"])
    ff = co._MgStream._ffmpeg_path()
    print(f"   ffmpeg: {ff or '없음 - 조준이 사실상 동작하지 않습니다(README의 ffmpeg 설치 참고)'}")

    device = connect()
    if device is None:
        print("❌ [상자 자동오픈] ADB 연결 실패 - 종료합니다.")
        return
    t_yeolda = co.load_template("templates/chestopening/yeolda_clean.png")
    print("👀 [상자 자동오픈] 상자 화면을 기다립니다. (창을 닫거나 원격 정지로 끝냅니다)")

    while True:
        try:
            img = decode_screen_bytes(capture_screen_bytes(device))
        except Exception as e:
            print(f"⚠️ [상자 자동오픈] 캡처 실패: {e}")
            time.sleep(1.0)
            continue
        h, w = img.shape[:2]
        if h < 2560 or w < 1440:
            time.sleep(0.5)
            continue
        if co.is_minigame_screen(img, h, w):
            co.solve_trap_game(device, img)
        elif co.is_who_open_screen(img):
            co.select_opener_slot(device, img, opener, hero)
        elif co.check_yeolda_in_roi(img, t_yeolda, 0.65):
            co.open_and_disarm_chest(device, img, t_yeolda, chest_opener_slot=opener, masked_adventurer_slot=hero)
        else:
            time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("🛑 [상자 자동오픈] 사용자 중단")
