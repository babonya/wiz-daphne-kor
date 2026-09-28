# -*- coding: utf-8 -*-
"""
🛠️ 처음설정 (처음설정.bat 이 파이썬 확인 뒤 실행) - 2026-09-28

처음 쓸 때, 그리고 업데이트(새 zip 덮어쓰기) 뒤에는 꼭 한 번 실행한다. 각 단계를 자동으로 검사하고, 안 된 부분만
단계별로 안내한다. 끝나면 setup_done.json 에 현재 버전을 기록해 매크로가 시작될 수 있게 한다.
  [1] 파이썬 (배치파일이 이미 확인) + 필수 라이브러리
  [2] ffmpeg (상자 조준용 - 없으면 매크로가 예전 연타 방식으로 자동 전환)
  [3] 내 설정 파일 my_settings.py (없으면 만들기 - 이전 버전 폴더에서 옮겨오기 가능 / 있으면 새 설정만 추가)
"""
import os
import sys
import shutil
import subprocess
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
import user_settings as us

REQUIRED_LIBS = [("cv2", "opencv-python"), ("PIL", "pillow"), ("numpy", "numpy"), ("ppadb", "pure-python-adb")]
WINGET_FFMPEG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ffmpeg.exe")


def line(ch="="):
    print(ch * 64)


def ask_yes(prompt):
    try:
        return input(f"{prompt} (y/n): ").strip().lower() in ("y", "yes", "ㅛ")
    except EOFError:
        return False


def wait_key(prompt="해결했으면 엔터를 눌러 다시 검사합니다 (그만두려면 q + 엔터)"):
    try:
        return input(prompt + ": ").strip().lower() != "q"
    except EOFError:
        return False


def missing_libs():
    miss = []
    for mod, pkg in REQUIRED_LIBS:
        try:
            importlib.invalidate_caches()
            importlib.import_module(mod)
        except Exception:
            miss.append(pkg)
    return miss


def step_libs():
    line()
    print("[1단계] 파이썬 %d.%d 확인 완료 - 필수 라이브러리를 검사합니다." % sys.version_info[:2])
    while True:
        miss = missing_libs()
        if not miss:
            print("  ✅ 필수 라이브러리 4종(opencv / pillow / numpy / pure-python-adb) 모두 설치되어 있습니다.")
            return True
        print(f"  ❌ 설치되지 않은 라이브러리: {', '.join(miss)}")
        print(f"     해결 방법: 아래 명령을 실행하면 됩니다.")
        print(f"       python -m pip install {' '.join(miss)}")
        if ask_yes("  지금 자동으로 설치할까요?"):
            subprocess.call([sys.executable, "-m", "pip", "install"] + miss)
            continue
        if not wait_key():
            return False


def find_ffmpeg():
    return shutil.which("ffmpeg") or (WINGET_FFMPEG if os.path.exists(WINGET_FFMPEG) else None)


def step_ffmpeg():
    line()
    print("[2단계] ffmpeg(상자 미니게임 조준용)를 검사합니다.")
    while True:
        ff = find_ffmpeg()
        if ff:
            print(f"  ✅ ffmpeg 확인: {ff}")
            return True
        print("  ❌ ffmpeg 가 없습니다. 없으면 상자 조준이 거의 동작하지 않아서, 매크로가 예전 '연타' 방식으로 자동 전환됩니다.")
        print("     해결 방법: 아래 명령을 실행하면 됩니다(설치 중 동의 질문이 나오면 직접 확인 후 Y).")
        print("       winget install ffmpeg")
        if ask_yes("  지금 winget 으로 설치할까요?"):
            subprocess.call(["winget", "install", "--id", "Gyan.FFmpeg", "-e"])
            continue
        if ask_yes("  ffmpeg 없이 진행할까요? (상자는 예전 연타 방식으로 엽니다)"):
            print("  ⚠️ ffmpeg 없이 진행합니다.")
            return True
        if not wait_key():
            return False


def step_settings(version):
    line()
    print("[3단계] 내 설정 파일(my_settings.py)을 준비합니다.")
    if os.path.exists(us.MY_SETTINGS):
        try:
            us.load_settings_file(us.MY_SETTINGS)
        except Exception as e:
            print(f"  ❌ my_settings.py 에 문법 오류가 있어 읽을 수 없습니다: {e}")
            print("     해결 방법: 노트패드++ 로 열어 오류 줄을 고치거나, 파일 이름을 바꿔 두고 처음설정을 다시 실행하면 새로 만듭니다.")
            return False, []
        added = us.append_missing_settings(us.MY_SETTINGS, version)
        if added:
            print(f"  🆕 이번 버전에서 새로 생긴 설정 {len(added)}개를 my_settings.py 끝에 기본값으로 추가했습니다:")
            for n in added:
                print(f"       - {n}")
            print("     필요하면 my_settings.py 를 열어 값을 바꾸세요(각 항목 옆 주석에 설명이 있습니다).")
        else:
            print("  ✅ my_settings.py 가 이미 있고, 새로 생긴 설정은 없습니다. 기존 개인 설정을 그대로 씁니다.")
        return True, added

    print("  my_settings.py 가 없어서 새로 만듭니다.")
    print("  이전 버전을 '다른 폴더'에 쓰고 있었다면 그 폴더 경로를 넣어 주세요 - 옛 설정값을 그대로 옮겨 옵니다.")
    print("  (같은 폴더에 덮어썼거나 처음 쓰는 경우는 그냥 엔터 -> 기본값으로 만듭니다)")
    overrides = {}
    while True:
        try:
            old = input("  이전 버전 폴더 경로: ").strip().strip('"')
        except EOFError:
            old = ""
        if not old:
            break
        old_my = os.path.join(old, "my_settings.py")
        old_main = os.path.join(old, "src", "main.py")
        try:
            if os.path.exists(old_my):
                overrides = us.load_settings_file(old_my)
                print(f"  ✅ 이전 폴더의 my_settings.py 에서 {len(overrides)}개 값을 옮깁니다.")
                break
            if os.path.exists(old_main):
                overrides = us.extract_values_from_main(old_main)
                print(f"  ✅ 이전 폴더의 src/main.py 에서 설정 {len(overrides)}개 값을 옮깁니다.")
                break
            print("  ❌ 그 폴더에서 my_settings.py 나 src/main.py 를 찾지 못했습니다. 경로를 다시 확인해 주세요(그만두려면 엔터).")
        except Exception as e:
            print(f"  ❌ 옛 설정을 읽지 못했습니다({e}). 다른 경로를 넣거나 엔터로 기본값을 쓰세요.")
    defaults = us.default_setting_entries()
    us.write_new_my_settings({k: v for k, v in overrides.items() if k in defaults})
    changed = [k for k, v in overrides.items() if k in defaults and defaults[k]["value"] != v]
    print(f"  ✅ my_settings.py 를 만들었습니다(기본값과 다른 옮긴 값 {len(changed)}개).")
    for k in changed:
        print(f"       - {k} = {overrides[k]!r}")
    new_keys = [k for k in defaults if overrides and k not in overrides]
    if new_keys:
        print(f"  🆕 이전 버전에 없던 새 설정 {len(new_keys)}개는 기본값으로 넣었습니다: {', '.join(new_keys)}")
    return True, new_keys


def main():
    version = us.read_current_version()
    line()
    print(f"  위저드리 다프네 매크로 v{version} - 처음설정")
    print("  처음 쓸 때, 그리고 업데이트(새 버전 덮어쓰기) 뒤에는 꼭 한 번 실행해 주세요.")
    line()
    ok_libs = step_libs()
    if not ok_libs:
        print("\n❌ 필수 라이브러리가 없어서 여기서 멈춥니다. 해결한 뒤 처음설정.bat 을 다시 실행해 주세요.")
        return 1
    ok_ff = step_ffmpeg()
    if not ok_ff:
        print("\n❌ ffmpeg 단계를 끝내지 못했습니다. 해결한 뒤 처음설정.bat 을 다시 실행해 주세요.")
        return 1
    ok_set, new_keys = step_settings(version)
    if not ok_set:
        print("\n❌ 내 설정 파일 단계를 끝내지 못했습니다. 해결한 뒤 처음설정.bat 을 다시 실행해 주세요.")
        return 1
    us.write_setup_done(version)
    line()
    print("  🎉 처음설정 완료! 요약")
    print(f"   ✅ 파이썬 / 필수 라이브러리")
    print(f"   {'✅' if find_ffmpeg() else '⚠️'} ffmpeg {'(상자 조준 사용)' if find_ffmpeg() else '없음 - 상자는 예전 연타 방식'}")
    print(f"   ✅ 내 설정 파일: {us.MY_SETTINGS}" + (f"  (새 설정 {len(new_keys)}개 추가됨)" if new_keys else ""))
    print("  이제 원하는 던전 배치파일(예: 대설지대6층 상자파밍.bat)을 실행하세요.")
    print("  개인 설정은 my_settings.py 에서 고치면 되고, 업데이트해도 그대로 유지됩니다.")
    line()
    return 0


if __name__ == "__main__":
    sys.exit(main())
