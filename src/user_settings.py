# -*- coding: utf-8 -*-
"""
🧩 사용자 설정(my_settings.py + 프리셋별 프로필) 로더/생성기 + 처음설정 완료 표시 - 2026-09-28

왜: 예전엔 글로벌 설정을 src/main.py 맨 위에서 직접 고쳤는데, 업데이트 zip을 덮어쓰면 main.py가 통째로 바뀌어
개인 설정이 날아갔다. 이제 main.py의 설정 구역은 "기본값"일 뿐이고, 사용자는 프로젝트 루트의 my_settings.py를 고친다.
  1) main.py 설정 구역(배포 기본값)  ->  2) my_settings.py(내 공통 설정)  ->  3) my_settings_<프로필>.py(그 프리셋에서만 다른 값)
  순서로 덮어쓴다. 2)·3)과 setup_done.json 은 git/릴리즈 zip 에서 빠지므로 업데이트로 절대 덮이지 않는다.
- 프로필은 presets.json 의 프리셋 항목에 "settings_profile": "이름" 을 넣으면 my_settings_이름.py 를 추가로 읽는다.
- setup_done.json 에는 "처음설정.bat 을 마지막으로 끝낸 버전"이 들어 있다. main.py 의 CURRENT_VERSION 보다 옛날이거나
  없으면(첫 실행·업데이트 직후) 매크로는 시작하지 않고 처음설정을 안내한다.
"""
import os
import re
import ast
import json
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "src", "main.py")
MY_SETTINGS = os.path.join(ROOT, "my_settings.py")
SETUP_DONE = os.path.join(ROOT, "setup_done.json")
BLOCK_START_MARK = "[Daphne 마스터 글로벌 제어 세팅 변수 구역"
BLOCK_END_MARK = "[프리셋 자동 로딩 엔진]"


def read_text(path):
    """utf-8(BOM 허용) -> cp949 순으로 읽는다(옛 버전 사용자가 ANSI로 저장했을 수도 있다)."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4])


def read_current_version(main_py=MAIN_PY):
    m = re.search(r'^CURRENT_VERSION\s*=\s*"([^"]+)"', read_text(main_py), re.M)
    return m.group(1) if m else "0"


def _settings_block(src):
    """main.py 소스에서 글로벌 설정 구역의 줄 목록을 돌려준다(없으면 빈 목록)."""
    lines = src.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if start is None and BLOCK_START_MARK in line:
            start = i
        elif start is not None and BLOCK_END_MARK in line:
            end = i
            break
    if start is None:
        return []
    if end is None:
        end = len(lines)
    # 끝 표시 줄 바로 위의 구분선(# ----)은 빼고 돌려준다
    while end > start and lines[end - 1].strip().startswith("# ---"):
        end -= 1
    return lines[start:end]


def default_setting_entries(main_py=MAIN_PY):
    """{이름: {"value": 기본값, "chunk": 주석 포함 원문}} (main.py 설정 구역 순서 유지)."""
    block = _settings_block(read_text(main_py))
    text = "\n".join(block)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    nodes = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()]
    entries = {}
    for i, node in enumerate(nodes):
        start = node.lineno - 1
        stop = nodes[i + 1].lineno - 1 if i + 1 < len(nodes) else len(block)
        chunk_lines = block[start:stop]
        # 다음 항목 앞의 "# 🏥 [..." 같은 소제목 줄은 다음 항목에 붙이기 위해, 끝쪽의 빈 줄/소제목을 떼어 낸다
        while chunk_lines and (not chunk_lines[-1].strip() or
                               (chunk_lines[-1].lstrip().startswith("#") and not chunk_lines[-1].startswith(" "))):
            chunk_lines.pop()
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        entries[node.targets[0].id] = {"value": value, "chunk": "\n".join(chunk_lines)}
    return entries


def load_settings_file(path):
    """설정 파일(파이썬 문법)을 실행해 대문자 이름만 돌려준다. 문법 오류면 예외."""
    ns = {}
    exec(compile(read_text(path), path, "exec"), {"__builtins__": {}}, ns)
    return {k: v for k, v in ns.items() if k.isupper()}


def extract_values_from_main(main_py):
    """옛 버전 main.py 의 설정 구역에서 현재 값만 뽑는다(마이그레이션용)."""
    return {k: e["value"] for k, e in default_setting_entries(main_py).items()}


def _replace_value_in_chunk(chunk, name, value):
    first, _, rest = chunk.partition("\n")
    m = re.match(r"^(\s*" + re.escape(name) + r"\s*=\s*)(.*?)(\s+#.*)?$", first)
    if not m:
        return chunk
    new_first = f"{m.group(1)}{value!r}{m.group(3) or ''}"
    return new_first + ("\n" + rest if rest else "")


HEADER = '''# -*- coding: utf-8 -*-
# ==============================================================================
# 🧩 [내 설정 파일] my_settings.py - 이 파일만 고치세요!
#    - 업데이트(새 zip 덮어쓰기)를 해도 이 파일은 바뀌지 않습니다. 개인 설정은 여기서 관리합니다.
#    - src/main.py 맨 위의 같은 이름 값은 "기본값"일 뿐이라, 거기를 고쳐도 이 파일 값이 우선합니다.
#    - 업데이트로 새 설정이 생기면 "처음설정.bat"이 이 파일 끝에 기본값으로 자동 추가합니다.
#    - 특정 던전에서만 값을 바꾸고 싶으면 my_settings_<이름>.py 를 만들고, presets.json 의 그 프리셋에
#      "settings_profile": "<이름>" 을 넣으세요(그 파일에는 다른 값만 적으면 됩니다). README 참고.
# ==============================================================================
'''


def write_new_my_settings(overrides=None, path=MY_SETTINGS):
    """main.py 기본값(주석 포함)으로 my_settings.py 를 만든다. overrides 에 있는 값은 그 값으로."""
    overrides = overrides or {}
    parts = [HEADER]
    for name, e in default_setting_entries().items():
        chunk = e["chunk"]
        if name in overrides and overrides[name] != e["value"]:
            chunk = _replace_value_in_chunk(chunk, name, overrides[name])
        parts.append(chunk)
    with open(path, "w", encoding="utf-8-sig") as f:   # BOM - 노트패드++ 가 ANSI 로 오인하지 않게
        f.write("\n".join(parts) + "\n")


def append_missing_settings(path=MY_SETTINGS, version=None):
    """my_settings.py 에 없는 설정만 기본값+주석으로 끝에 추가하고, 추가한 이름 목록을 돌려준다."""
    have = set(load_settings_file(path).keys())
    missing = [(n, e) for n, e in default_setting_entries().items() if n not in have]
    if missing:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n# ===== [업데이트로 추가된 설정 - v{version or '?'} · {stamp}] 기본값입니다. 필요하면 고치세요 =====\n")
            for _, e in missing:
                f.write(e["chunk"] + "\n")
    return [n for n, _ in missing]


def apply_user_settings(g, profile=None):
    """main.py 전역(g)에 my_settings.py -> my_settings_<profile>.py 순으로 덮어쓴다. 요약 문자열 목록을 돌려준다."""
    known = set(default_setting_entries().keys())
    msgs = []
    layers = [("my_settings.py", MY_SETTINGS)]
    if profile:
        layers.append((f"my_settings_{profile}.py", os.path.join(ROOT, f"my_settings_{profile}.py")))
    applied = ["main.py 기본값"]
    for label, path in layers:
        if not os.path.exists(path):
            if label != "my_settings.py":
                msgs.append(f"⚠️ [내 설정] 프로필 파일 {label} 이 없어 공통 설정만 씁니다.")
            continue
        try:
            vals = load_settings_file(path)
        except Exception as e:
            msgs.append(f"❌ [내 설정] {label} 을 읽지 못했습니다(문법 오류?) - 이 파일은 건너뜁니다: {e}")
            continue
        changed = [k for k in vals if k in known and g.get(k) != vals[k]]
        unknown = [k for k in vals if k not in known]
        for k in vals:
            if k in known:
                g[k] = vals[k]
        applied.append(f"{label}(바꾼 값 {len(changed)}개)")
        if unknown:
            msgs.append(f"⚠️ [내 설정] {label} 에 모르는 설정 이름이 있습니다(오타?): {', '.join(unknown)}")
    msgs.insert(0, "🧩 [내 설정] 적용 순서: " + " -> ".join(applied))
    return msgs


def setup_required(current_version):
    """(처음설정이 필요한가, 사유). setup_done.json 이 없거나 현재 버전보다 옛날이면 필요."""
    try:
        with open(SETUP_DONE, encoding="utf-8") as f:
            done = json.load(f).get("version", "0")
    except Exception:
        return True, "처음 실행(처음설정 기록 없음)"
    if version_tuple(done) < version_tuple(current_version):
        return True, f"업데이트 감지(처음설정 v{done} -> 현재 v{current_version})"
    return False, ""


def write_setup_done(version):
    with open(SETUP_DONE, "w", encoding="utf-8") as f:
        json.dump({"version": version, "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, f,
                  ensure_ascii=False, indent=1)


SETUP_REQUIRED_EXIT_CODE = 3


def block_if_setup_required(current_version, who="매크로"):
    """처음설정이 필요하면 안내를 찍고(로그 파일도 남김) 종료 코드 3으로 끝낸다. 배치파일은 3이면 pause 한다."""
    need, reason = setup_required(current_version)
    if not need:
        return
    lines = [
        "==========================================================",
        f"  {reason}",
        f"  {who}를 시작하기 전에 먼저 프로젝트 폴더의 \"처음설정.bat\"을 한 번 실행해 주세요.",
        "  (파이썬/라이브러리/ffmpeg 확인 + 내 설정 파일 준비. 업데이트 후에도 한 번씩 필요합니다)",
        "==========================================================",
    ]
    try:
        os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        with open(os.path.join(ROOT, "logs", f"{stamp}-000_setup_required.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    for line in lines:
        try:
            print(line)
        except Exception:
            pass
    raise SystemExit(SETUP_REQUIRED_EXIT_CODE)
