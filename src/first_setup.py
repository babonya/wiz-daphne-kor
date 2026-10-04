# -*- coding: utf-8 -*-
"""
🛠️ 처음설정 (처음설정.bat 이 파이썬 확인 뒤 실행) - 2026-09-28

처음 쓸 때, 그리고 업데이트(새 zip 덮어쓰기) 뒤에는 꼭 한 번 실행한다. 각 단계를 자동으로 검사하고, 안 된 부분만
단계별로 안내한다. 끝나면 setup_done.json 에 현재 버전을 기록해 매크로가 시작될 수 있게 한다.
  [1] 파이썬 (배치파일이 이미 확인) + 필수 라이브러리
  [2] ffmpeg (상자 조준용 - 없으면 매크로가 예전 연타 방식으로 자동 전환)
  [3] 내 설정 파일 my_settings.py (없으면 만들기 - 이전 버전 폴더에서 옮겨오기 가능 / 있으면 새 설정만 추가)
  [2026-10-01] ffmpeg 탐색 강화(winget Packages glob·레지스트리 PATH·-version 실행 확인), winget 없음/실패 처리, 무한반복 수정
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


def _ffmpeg_candidates():
    """shutil.which 실패 시 뒤져볼 후보 경로(순서대로). winget 은 PATH 에 Links 가 아니라 Packages/.../bin 을 등록하기도 하고,
    설치 직후엔 이 콘솔의 PATH 가 갱신되지 않는다(2026-10-01)."""
    import glob
    la = os.environ.get("LOCALAPPDATA", "")
    yield WINGET_FFMPEG
    pk = os.path.join(la, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*")
    for pat in (os.path.join(pk, "**", "bin", "ffmpeg.exe"), os.path.join(la, "Microsoft", "WinGet", "Links", "ffmpeg.exe")):
        for hit in glob.glob(pat, recursive=True):
            yield hit
    try:  # 레지스트리의 (갱신된) PATH - 이 콘솔이 설치 전에 떠 있었어도 최신 값을 읽는다
        import winreg
        for root, sub in ((winreg.HKEY_CURRENT_USER, "Environment"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                with winreg.OpenKey(root, sub) as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
            except OSError:
                continue
            for d in os.path.expandvars(val).split(os.pathsep):
                if d.strip():
                    yield os.path.join(d.strip().strip('"'), "ffmpeg.exe")
    except Exception:
        pass


def _ffmpeg_runs(path):
    try:
        r = subprocess.run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def find_ffmpeg():
    """실행되는 ffmpeg 경로 또는 None. 파일이 있어도 -version 이 실패하면 안내 후 못 찾은 것으로 취급."""
    cands = []
    w = shutil.which("ffmpeg")
    if w:
        cands.append(w)
    cands.extend(c for c in _ffmpeg_candidates() if os.path.isfile(c))
    seen = set()
    for c in cands:
        key = os.path.normcase(os.path.abspath(c))
        if key in seen:
            continue
        seen.add(key)
        if _ffmpeg_runs(c):
            d = os.path.dirname(os.path.abspath(c))
            if d.lower() not in os.environ.get("PATH", "").lower().split(os.pathsep):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return c
        print(f"  ⚠️ ffmpeg 파일은 있으나 실행에 실패했습니다: {c}")
    return None


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
            try:
                rc = subprocess.call(["winget", "install", "--id", "Gyan.FFmpeg", "-e"])
            except FileNotFoundError:
                print("  ❌ 이 PC에 winget이 없습니다. https://www.gyan.dev/ffmpeg/builds/ 에서 직접 설치 후 처음설정을 다시 실행하세요.")
                rc = None
            else:
                if rc != 0:
                    print(f"  ⚠️ winget 이 종료 코드 {rc} 로 끝났습니다(이미 설치돼 있거나 실패일 수 있음).")
                ff = find_ffmpeg()
                if ff:
                    print(f"  ✅ ffmpeg 확인: {ff}")
                    return True
                print("  ⚠️ 설치는 됐을 수 있으나 이 창에서는 못 찾았습니다 - 이 창을 닫고 처음설정을 다시 실행하세요.")
            if ask_yes("  ffmpeg 없이 진행할까요? (상자는 예전 연타 방식으로 엽니다)"):
                print("  ⚠️ ffmpeg 없이 진행합니다.")
                return True
            if not wait_key():
                return False
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
