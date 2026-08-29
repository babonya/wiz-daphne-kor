# ==============================================================================
# 📋 [원격 매크로 시작/정지 수신 서버]
# - 목적: 팀뷰어 로그인 없이, 테일스케일 사설망을 통해 폰 브라우저 북마크 탭 한 번으로
#         PC의 매크로를 시작/정지/상태확인 하기 위한 개인용 도구입니다.
# - 표준 라이브러리만 사용합니다 (pip install 추가 불필요).
# - 이 폴더(remote_control/)를 통째로 지워도 매크로 본체(src/main.py) 동작에는 전혀 지장이 없습니다.
# - 현재 버전: 1.19.0
# - 수정 기록:
#   1.19.0: 1.18.0에서 고친 "원격 정지 시 콘솔창 종료"가 매크로 자가 재시작(os.execv) 이후엔 다시
#     무력화되는 결함 완치 - find_parent_cmd_pid()는 그 순간의 직계 부모만 조회하는데, os.execv는 윈도우
#     에서 매번 새 PID를 만들어서 재시작 이후엔 직계 부모가 진짜 cmd.exe가 아니라 이미 죽은 이전
#     python.exe가 됨(윈도우는 죽은 프로세스의 부모 기록을 보존 안 해서 더 거슬러 올라갈 방법이 없음).
#     main.py가 최초 부팅 시점에만 캡처해 재시작에도 안 끊기게 저장해두는 macro_cmd.pid 파일을 우선
#     사용하도록 전환(구버전 호환용으로 기존 라이브 조회는 폴백 유지). 상세는 main.py 참고.
#   1.18.0: 원격 정지(/stop) 시 python.exe만 죽이고 그 부모 cmd.exe 콘솔창(빈 검은 화면)은 남아있던
#     결함을 완치 - 죽이기 전에 WMI로 부모 PID를 조회해두고, 실제로 cmd.exe일 때만 같이 종료한다.
#     상세는 CLAUDE.md/history.log 참고.
#   1.17.1-hotfix10: (이 파일 자체는 변경 없음, 버전 동기화용) 유령성 던전선택 '2nd' 층 버튼 미인식 결함 완치.
#     상세는 main.py 참고.
#   1.17.1-hotfix9: (이 파일 자체는 변경 없음, 버전 동기화용) 목요일 대용량 다운로드 타임아웃, FIELD_WAIT 무한
#     정체 5분 하드 리밋 미작동, 기동 복구 하켄 메뉴 미인식 결함 완치. 상세는 main.py/dungeon_bot.py 참고.
#   1.17.1-hotfix8: (이 파일 자체는 변경 없음, 버전 동기화용) 피장막 관통 인식, 하켄 메뉴 시작 인식, 하켄 가호
#     이름 우선순위 완치. 상세는 main.py/dungeon_bot.py 참고.
#   1.17.1-hotfix7: 대시보드 로그창 높이 축소(20→15줄, 고정 260px) 및 상단에 "N시간 M분째 실행 중" 표시 추가.
#     이 파일 자체 외 나머지는 main.py/dungeon_bot.py의 재시작 카운터/하켄 탈출 복구 결함 완치. 상세는 main.py 참고.
#   1.17.1-hotfix6: (이 파일 자체는 변경 없음, 버전 동기화용) main.py의 뮤뮤 완전 동결 시 자가복구 결함 완치. 상세는 main.py 참고.
#   1.17.1-hotfix5: (이 파일 자체는 변경 없음, 버전 동기화용) dungeon_bot.py의 하켄의 가호 오탐지 완치. 상세는 dungeon_bot.py 참고.
#   1.17.1-hotfix4: (이 파일 자체는 변경 없음, 버전 동기화용) dungeon_bot.py에 하켄의 가호 대응 신설. 상세는 dungeon_bot.py 참고.
#   1.17.1-hotfix3: 백그라운드(pythonw) 실행 지원(시작/종료 배치파일, PID 자기기록), 대시보드 URL 줄바꿈으로
#     토큰에 공백이 섞이던 403 결함 완치, pythonw 하에서 5초마다 콘솔 창이 깜빡이던 결함(CREATE_NO_WINDOW) 완치
#   1.17.1-hotfix2: 실시간 로그+버튼식 대시보드 웹페이지(/dashboard, /api/state) 신설, 마지막 실행 배치 기억 기능 추가
#   1.17.1: 최초 도입
# ==============================================================================
import glob
import http.server
import io
import json
import os
import re
import secrets
import subprocess
import sys
from urllib.parse import urlparse, parse_qs, quote

# 💡 [pythonw.exe/백그라운드 실행 대응] 콘솔이 없는 pythonw.exe로 실행되면 sys.stdout/stderr가 None이거나
# (또는 존재해도) 시스템 로케일(한글 Windows는 cp949)로 인코딩을 시도하다 print()의 이모지에서 그대로 죽어버립니다.
# None이면 버려지는 더미 스트림으로, 존재하면 UTF-8로 강제 재설정해 어떤 실행 방식에서도 죽지 않게 합니다.
if sys.stdout is None:
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
if sys.stderr is None:
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.local.json")
PID_FILE = os.path.join(PROJECT_ROOT, "macro.pid")
CMD_PID_FILE = os.path.join(PROJECT_ROOT, "macro_cmd.pid")
GUIDE_PATH = os.path.join(SCRIPT_DIR, "설정안내.txt")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
LAST_TARGET_PATH = os.path.join(SCRIPT_DIR, "last_target.txt")
SERVER_PID_PATH = os.path.join(SCRIPT_DIR, "remote_server.pid")

# 💡 [pythonw.exe/백그라운드 실행 대응] 콘솔 없는 pythonw.exe 밑에서 tasklist/tailscale 같은 콘솔 유틸리티를
# subprocess로 호출하면, 붙을 콘솔이 없어 Windows가 매번 새 콘솔 창을 잠깐 띄웠다 닫습니다(5초마다 폴링되는
# /api/state가 tasklist를 호출할 때마다 화면이 깜빡이는 원인이었음). CREATE_NO_WINDOW로 이를 원천 차단합니다.
# (실제 매크로를 띄우는 /start의 "start"는 사용자가 봐야 하는 창이라 의도적으로 이 플래그를 안 씁니다.)
NO_WINDOW = subprocess.CREATE_NO_WINDOW

DEFAULT_CONFIG = {
    "port": 8765,
    "token": None,
}

CONFIG = {}


def load_or_create_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        cfg["token"] = secrets.token_urlsafe(24)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"🆕 [최초 실행] 설정 파일을 새로 만들었습니다: {CONFIG_PATH}")
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def discover_targets():
    # 💡 프로젝트 루트(remote_control/의 부모 폴더)에 있는 모든 .bat 파일을 자동으로 원격 시작 대상으로 등록합니다.
    # 새 프리셋 조합용 배치파일(예: 백아2.bat, 유령성2층채굴.bat)을 그냥 루트 폴더에 추가하기만 하면,
    # config.local.json을 손댈 필요 없이 다음 /start 요청부터 바로 인식됩니다. (요청마다 매번 새로 스캔)
    targets = {}
    for bat_path in glob.glob(os.path.join(PROJECT_ROOT, "*.bat")):
        name = os.path.splitext(os.path.basename(bat_path))[0]
        targets[name] = bat_path
    return targets


def read_last_target():
    # 💡 대시보드 접속 시 드롭다운에 "마지막으로 시작한 배치"가 미리 선택되어 있도록 기록해두는 용도입니다.
    try:
        with open(LAST_TARGET_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def write_last_target(name):
    try:
        with open(LAST_TARGET_PATH, "w", encoding="utf-8") as f:
            f.write(name)
    except Exception:
        pass


def get_tailscale_ip():
    # 테일스케일 CLI가 PATH에 없는 환경도 있어서, 실패해도 조용히 None 반환 (0.0.0.0 폴백)
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
        out = result.stdout.strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


def get_tailscale_dns_name():
    # 💡 URL에 실제 IP 숫자 대신, 테일스케일 MagicDNS가 이 PC에 부여한 고유 호스트네임(예: konuri.tail007636.ts.net)을
    # 표시하기 위한 함수입니다. 서버 자체는 여전히 IP로 바인딩하며, 이건 안내 URL 표시용으로만 씁니다.
    try:
        # 💡 --json 출력에 한글 기기명(예: "한샘의 S25 Ultra")이 UTF-8로 섞여 나올 수 있어,
        # text=True만 쓰면 시스템 로케일(한글 Windows는 cp949)로 디코딩을 시도하다 깨짐 → encoding 명시 필수.
        result = subprocess.run(
            ["tailscale", "status", "--self", "--json"],
            capture_output=True, encoding="utf-8", timeout=5, creationflags=NO_WINDOW
        )
        data = json.loads(result.stdout)
        dns_name = data.get("Self", {}).get("DNSName", "")
        return dns_name.rstrip(".") if dns_name else None
    except Exception:
        return None


def print_and_save_guide(cfg, bind_ip, dns_name=None):
    host = dns_name or bind_ip or "<PC의 테일스케일 IP를 admin.tailscale.com에서 확인하세요>"
    port = cfg.get("port", 8765)
    token = cfg.get("token", "")
    lines = []
    lines.append("=" * 70)
    lines.append("📱 스마트폰의 웹 브라우저에서 '홈 화면에 추가'로 아래 대시보드 URL을 등록하세요")
    lines.append("   (실시간 로그 확인 + 시작/정지 버튼이 모두 있는 페이지입니다)")
    lines.append("=" * 70)
    # ⚠️ 이 줄은 짧게 유지하세요! 라벨이 길어지면 콘솔 창 너비를 넘어가 줄바꿈이 발생하고,
    # 그 줄바꿈 지점을 복사할 때 토큰 중간에 공백이 끼어드는 문제가 실사용 중 발견됨(대시보드 접속 403 원인).
    lines.append(f"🕹️ 대시보드 : http://{host}:{port}/dashboard?token={token}")
    lines.append("=" * 70)
    lines.append("(참고) 대시보드 없이 개별 URL만 쓰고 싶다면 아래도 그대로 동작합니다:")
    targets = discover_targets()
    if not targets:
        lines.append(f"⚠️ {PROJECT_ROOT} 에서 .bat 파일을 찾지 못했습니다. 시작 URL을 만들 수 없습니다.")
    for name in targets.keys():
        lines.append(f"▶ 시작 ({name}): http://{host}:{port}/start?target={quote(name)}&token={token}")
    lines.append(f"■ 정지        : http://{host}:{port}/stop?token={token}")
    lines.append(f"❔ 상태확인   : http://{host}:{port}/status?token={token}")
    lines.append("=" * 70)
    lines.append("💡 URL을 북마크에 등록하고 정상 접속까지 확인하셨다면, 다음부터는 이 창(Start Remote")
    lines.append('   Control.bat) 대신 "Start Remote Control (Background).bat"를 사용하시는 걸 권장합니다.')
    lines.append("   창이 아예 뜨지 않아 실수로 닫아버릴 걱정이 없습니다. 끌 때는")
    lines.append('   "Stop Remote Control (Background).bat"를 실행하시면 됩니다.')
    lines.append("=" * 70)
    text = "\n".join(lines)
    print(text)
    try:
        with open(GUIDE_PATH, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\n📄 위 내용을 {GUIDE_PATH} 에도 저장했습니다. 나중에 다시 열어보셔도 됩니다.")
    except Exception as e:
        print(f"⚠️ 안내 파일 저장 실패 (URL은 위에서 복사하시면 됩니다): {e}")


def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def read_cmd_pid_file():
    # 💡 [2026-08-29] main.py의 capture_root_cmd_pid()가 최초 부팅 시점에 저장해둔, 재시작에도 안 끊기는
    # 콘솔창(cmd.exe) PID. find_parent_cmd_pid()는 os.execv 자기재시작을 한 번이라도 거치면 직계 부모가
    # 이미 죽은 이전 python.exe가 되어 cmd.exe를 못 찾는 결함이 있었음(실전에서 "랜덤"하게 콘솔창이 안
    # 닫히는 증상으로 확인) - 파일에 미리 저장된 값을 우선 사용해 이 문제를 우회한다.
    if not os.path.exists(CMD_PID_FILE):
        return None
    try:
        with open(CMD_PID_FILE, "r", encoding="utf-8") as f:
            val = f.read().strip()
        return int(val) if val.isdigit() else None
    except Exception:
        return None


def is_our_python_process(pid, valid_images=("python.exe",)):
    # taskkill 대상이 정말 python.exe(또는 지정한 이미지명)가 맞는지 한 번 더 확인 (PID 재활용으로 엉뚱한 프로세스를 죽이는 사고 방지)
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW
        )
        out = result.stdout.strip()
        if not out or out.upper().startswith("INFO:"):
            return False
        image_name = out.split(",")[0].strip('"').lower()
        return image_name in valid_images
    except Exception:
        return False


def find_parent_cmd_pid(pid):
    # 💡 [2026-08-28] /start가 `start "" "bat"`로 새 cmd.exe 창을 띄우고 그 안에서 python.exe를 구동하는데,
    # /stop이 python.exe PID만 taskkill하면 이 창을 띄운 부모 cmd.exe는 빈 채로(검은 화면) 남아있었음
    # (사용자 실전 확인). python.exe PID를 죽이기 전에 미리 부모 PID를 조회해두고, 그 부모가 실제로
    # cmd.exe일 때만(다른 방식으로 기동됐을 경우 엉뚱한 창을 건드리지 않도록) 반환한다.
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f'(Get-CimInstance Win32_Process -Filter "ProcessId={pid}").ParentProcessId'],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW
        )
        ppid_str = result.stdout.strip()
        if not ppid_str.isdigit():
            return None
        ppid = int(ppid_str)
        if is_our_python_process(ppid, valid_images=("cmd.exe",)):
            return ppid
        return None
    except Exception:
        return None


def is_macro_running():
    pid = read_pid()
    if pid is None:
        return False, None
    if is_our_python_process(pid):
        return True, pid
    return False, None


def write_own_pid():
    # 💡 이 서버 자신의 PID를 기록해둡니다. python.exe(창 있음)/pythonw.exe(창 없음, 백그라운드) 어느 쪽으로
    # 실행되든 항상 기록되므로, "Stop Remote Control (Background).bat"가 창이 없는 상태에서도 정확히 이 프로세스만
    # 골라서 종료할 수 있습니다.
    try:
        with open(SERVER_PID_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def stop_background_server():
    # 💡 "Stop Remote Control (Background).bat"에서 `python -c "import server; server.stop_background_server()"`로 호출합니다.
    if not os.path.exists(SERVER_PID_PATH):
        print("⚠️ 실행 중인 원격 제어 서버를 찾지 못했습니다 (remote_server.pid 없음).")
        return
    try:
        with open(SERVER_PID_PATH, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except Exception:
        print("⚠️ remote_server.pid 파일을 읽지 못했습니다.")
        return

    if not is_our_python_process(pid, valid_images=("python.exe", "pythonw.exe")):
        print(f"⚠️ PID {pid}가 이미 종료된 것 같습니다. (오래된 pid 파일 정리)")
        try:
            os.remove(SERVER_PID_PATH)
        except Exception:
            pass
        return

    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5, creationflags=NO_WINDOW)
        os.remove(SERVER_PID_PATH)
        print(f"✅ 백그라운드 원격 제어 서버(PID {pid})를 종료했습니다.")
    except Exception as e:
        print(f"⚠️ 종료 실패: {e}")


def get_recent_log_lines(n=15):
    # 💡 logs/ 안의 파일명은 "YYYY-MM-DD-HHMM-0SS_접미사.txt" 형태라, 문자열 정렬 = 시간순 정렬이 그대로 성립함.
    try:
        files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".txt")]
    except Exception:
        return None, [], None
    if not files:
        return None, [], None
    latest = sorted(files)[-1]
    path = os.path.join(LOGS_DIR, latest)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # 💡 [실행 시작 시각] init_main_logger()가 매 로그 파일 3번째 줄에 남기는
        # "Log Created: YYYY-MM-DD HH:MM:SS"를 그대로 파싱해, 대시보드에서 "몇 시간째 실행 중"을 계산하는 기준으로 씁니다.
        started_at = None
        for line in lines[:5]:
            m = re.search(r"Log Created:\s*([\d-]{10} [\d:]{8})", line)
            if m:
                started_at = m.group(1)
                break
        tail = [line.rstrip("\n") for line in lines[-n:] if line.strip()]
        return latest, tail, started_at
    except Exception:
        return latest, [], None


def render_dashboard_html(token):
    targets = discover_targets()
    last_target = read_last_target()
    options_html = "\n".join(
        f'<option value="{name}"{" selected" if name == last_target else ""}>{name}</option>'
        for name in targets.keys()
    ) or '<option value="">(루트 폴더에 .bat 파일 없음)</option>'

    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Daphne 원격 제어</title>
<style>
  :root {
    --bg: #14121a; --bg-raised: #1c1926; --line: #322d40;
    --ink: #ece7f2; --ink-dim: #a49bb8; --ink-faint: #6f6683;
    --amber: #e0a94f; --good: #5fb896; --bad: #d97a6c;
    --danger: #c15a4e; --radius: 10px;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg: #f3efe6; --bg-raised: #ffffff; --line: #ddd4c2;
      --ink: #241f2e; --ink-dim: #5a5268; --ink-faint: #948aa3;
      --amber: #a8752a; --good: #2f8a68; --bad: #b8493a; --danger: #b8493a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
    display: flex; justify-content: center; min-height: 100vh; }
  .phone { width: 100%; max-width: 420px; min-height: 100vh; display: flex;
    flex-direction: column; padding: 18px 16px calc(18px + env(safe-area-inset-bottom, 0px)); gap: 14px; }
  .header { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
  .title { font-family: Georgia, "Noto Serif KR", serif; font-size: 1.28rem; font-weight: 700; margin: 0; }
  .title small { display: block; font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 0.72rem; font-weight: 500; color: var(--ink-faint); letter-spacing: 0.04em; margin-top: 2px; }
  .status-pill { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px 6px 10px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--bg-raised);
    font-size: 0.78rem; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--good) 25%, transparent); }
  .status-pill.off .dot { background: var(--ink-faint); box-shadow: none; }
  .status-pill span.label { color: var(--good); }
  .status-pill.off span.label { color: var(--ink-dim); }
  .uptime { font-size: 0.76rem; color: var(--ink-dim); text-align: center; min-height: 1.1em; }
  .log-card { background: var(--bg-raised); border: 1px solid var(--line); border-radius: var(--radius);
    display: flex; flex-direction: column; overflow: hidden; flex: 0 0 auto; height: 260px; }
  .log-card-head { display: flex; align-items: center; justify-content: space-between;
    padding: 9px 12px; border-bottom: 1px solid var(--line); }
  .log-card-head .eyebrow { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--ink-faint); }
  .live-tag { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.06em; color: var(--good);
    display: flex; align-items: center; gap: 5px; }
  .live-tag .dot { width: 6px; height: 6px; }
  .live-tag.paused { color: var(--ink-faint); }
  .live-tag.paused .dot { background: var(--ink-faint); box-shadow: none; }
  .log-body { flex: 1; overflow-y: auto; padding: 10px 12px 12px;
    font-family: ui-monospace, "Cascadia Mono", Consolas, "D2Coding", monospace;
    font-size: 0.71rem; line-height: 1.62; -webkit-overflow-scrolling: touch; }
  .log-line { white-space: pre-wrap; word-break: break-all; }
  .log-line .ts { color: var(--ink-faint); }
  .tag-village { color: var(--amber); }
  .tag-harken { color: #8ba3d9; }
  .tag-warn { color: var(--bad); }
  .tag-ok { color: var(--good); }
  .log-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 6px; color: var(--ink-faint); text-align: center; padding: 20px; }
  .log-empty .msg { font-size: 0.86rem; color: var(--ink-dim); font-weight: 600; }
  .log-empty .sub { font-size: 0.74rem; }
  .controls { background: var(--bg-raised); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .target-row { display: flex; align-items: center; gap: 8px; }
  .target-row label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink-faint); flex-shrink: 0; }
  select { flex: 1; background: var(--bg); color: var(--ink); border: 1px solid var(--line);
    border-radius: 7px; padding: 9px 10px; font-size: 0.86rem; font-family: inherit; }
  .btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  button { font-family: inherit; font-size: 0.92rem; font-weight: 700; border-radius: 8px;
    border: 1px solid transparent; padding: 13px 10px; cursor: pointer;
    transition: filter 0.15s ease, transform 0.05s ease; }
  button:active { transform: scale(0.98); }
  button:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }
  .btn-start { background: var(--amber); color: #1c1305; }
  .btn-start:hover { filter: brightness(1.08); }
  .btn-start:disabled { background: var(--line); color: var(--ink-faint); cursor: default; }
  .btn-stop { background: transparent; color: var(--danger); border-color: var(--danger); }
  .btn-stop:hover { background: color-mix(in srgb, var(--danger) 12%, transparent); }
  .btn-stop:disabled { color: var(--ink-faint); border-color: var(--line); cursor: default; }
  .toast { font-size: 0.74rem; color: var(--ink-dim); text-align: center; min-height: 1em; }
  .footer-note { font-size: 0.66rem; color: var(--ink-faint); text-align: center; letter-spacing: 0.02em; }
</style>
</head>
<body>
<div class="phone">
  <div class="header">
    <h1 class="title">Daphne 원격 제어<small>WIZ_DAPHNE_KOR · REMOTE</small></h1>
    <div class="status-pill off" id="statusPill"><span class="dot"></span><span class="label">확인 중…</span></div>
  </div>

  <div class="uptime" id="uptimeInfo">&nbsp;</div>

  <div class="log-card">
    <div class="log-card-head">
      <span class="eyebrow" id="logEyebrow">최근 로그</span>
      <span class="live-tag" id="liveTag"><span class="dot"></span>LIVE</span>
    </div>
    <div class="log-body" id="logBody"><div class="log-empty"><div class="msg">불러오는 중…</div></div></div>
  </div>

  <div class="controls">
    <div class="target-row">
      <label for="targetSelect">시작</label>
      <select id="targetSelect">__TARGET_OPTIONS__</select>
    </div>
    <div class="btn-row">
      <button class="btn-start" id="btnStart">시작</button>
      <button class="btn-stop" id="btnStop">정지</button>
    </div>
    <div class="toast" id="toast">&nbsp;</div>
  </div>

  <div class="footer-note">5초마다 자동 갱신 · 화면을 벗어나면 일시정지</div>
</div>

<script>
  const TOKEN = "__TOKEN__";
  const pill = document.getElementById('statusPill');
  const btnStart = document.getElementById('btnStart');
  const btnStop = document.getElementById('btnStop');
  const toast = document.getElementById('toast');
  const logBody = document.getElementById('logBody');
  const logEyebrow = document.getElementById('logEyebrow');
  const liveTag = document.getElementById('liveTag');
  const targetSelect = document.getElementById('targetSelect');
  const uptimeInfo = document.getElementById('uptimeInfo');
  let polling = null;

  function renderUptime(data) {
    if (!data.running || !data.log_started_at) { uptimeInfo.innerHTML = '&nbsp;'; return; }
    const started = new Date(data.log_started_at.replace(' ', 'T'));
    if (isNaN(started.getTime())) { uptimeInfo.innerHTML = '&nbsp;'; return; }
    const diffMin = Math.floor((Date.now() - started.getTime()) / 60000);
    if (diffMin < 0) { uptimeInfo.innerHTML = '&nbsp;'; return; }
    const h = Math.floor(diffMin / 60);
    const m = diffMin % 60;
    const durText = h > 0 ? `${h}시간 ${m}분째` : `${m}분째`;
    const hh = String(started.getHours()).padStart(2, '0');
    const mm = String(started.getMinutes()).padStart(2, '0');
    uptimeInfo.textContent = `⏱️ ${durText} 실행 중 (${hh}:${mm} 시작)`;
  }

  function tagFor(line) {
    if (line.includes('⚠️') || line.includes('🚨')) return 'tag-warn';
    if (line.includes('🏠')) return 'tag-village';
    if (line.includes('🚪') || line.includes('하켄')) return 'tag-harken';
    if (line.includes('✅') || line.includes('🚀') || line.includes('👉')) return 'tag-ok';
    return '';
  }

  function renderLogs(filename, lines) {
    if (!lines || lines.length === 0) {
      logBody.innerHTML = '<div class="log-empty"><div class="msg">로그가 없습니다</div><div class="sub">매크로가 아직 한 번도 실행되지 않았을 수 있습니다</div></div>';
      logEyebrow.textContent = '최근 로그';
      return;
    }
    logEyebrow.textContent = `최근 로그 · ${filename}`;
    logBody.innerHTML = '';
    for (const line of lines) {
      const m = line.match(/^(\\[[^\\]]+\\])\\s*(.*)$/);
      const div = document.createElement('div');
      div.className = 'log-line';
      if (m) {
        const ts = document.createElement('span');
        ts.className = 'ts';
        ts.textContent = m[1] + ' ';
        div.appendChild(ts);
        const rest = document.createElement('span');
        rest.className = tagFor(m[2]);
        rest.textContent = m[2];
        div.appendChild(rest);
      } else {
        div.textContent = line;
      }
      logBody.appendChild(div);
    }
    logBody.scrollTop = logBody.scrollHeight;
  }

  function setRunning(running, pid) {
    if (running) {
      pill.classList.remove('off');
      pill.querySelector('.label').textContent = `실행 중 · PID ${pid}`;
      btnStart.disabled = true;
      btnStop.disabled = false;
    } else {
      pill.classList.add('off');
      pill.querySelector('.label').textContent = '정지 상태';
      btnStart.disabled = false;
      btnStop.disabled = true;
    }
  }

  async function refresh() {
    try {
      const res = await fetch(`/api/state?token=${encodeURIComponent(TOKEN)}`);
      if (!res.ok) { toast.textContent = '상태 조회 실패 (토큰 확인 필요)'; return; }
      const data = await res.json();
      setRunning(data.running, data.pid);
      renderLogs(data.log_file, data.log_lines);
      renderUptime(data);
    } catch (e) {
      toast.textContent = '서버에 연결할 수 없습니다.';
    }
  }

  btnStart.addEventListener('click', async () => {
    const target = targetSelect.value;
    if (!target) { toast.textContent = '시작할 배치파일이 없습니다.'; return; }
    btnStart.disabled = true;
    toast.textContent = '시작 요청을 보냈습니다…';
    try {
      const res = await fetch(`/start?target=${encodeURIComponent(target)}&token=${encodeURIComponent(TOKEN)}`);
      toast.textContent = await res.text();
    } catch (e) {
      toast.textContent = '요청 실패';
    }
    setTimeout(refresh, 1000);
  });

  btnStop.addEventListener('click', async () => {
    btnStop.disabled = true;
    toast.textContent = '정지 요청을 보냈습니다…';
    try {
      const res = await fetch(`/stop?token=${encodeURIComponent(TOKEN)}`);
      toast.textContent = await res.text();
    } catch (e) {
      toast.textContent = '요청 실패';
    }
    setTimeout(refresh, 1000);
  });

  function startPolling() {
    if (polling) return;
    liveTag.classList.remove('paused');
    refresh();
    polling = setInterval(refresh, 5000);
  }
  function stopPolling() {
    if (!polling) return;
    clearInterval(polling);
    polling = null;
    liveTag.classList.add('paused');
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPolling(); else startPolling();
  });
  startPolling();
</script>
</body>
</html>""".replace("__TOKEN__", token).replace("__TARGET_OPTIONS__", options_html)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 기본 접속 로그는 생략 (필요시 여기서 print로 바꾸면 됨)

    def _respond(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def _respond_html(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _respond_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        token_given = qs.get("token", [""])[0]

        if not CONFIG.get("token") or token_given != CONFIG["token"]:
            self._respond(403, "forbidden")
            return

        if parsed.path == "/start":
            target = qs.get("target", [None])[0]
            targets = discover_targets()
            if not target or target not in targets:
                self._respond(400, f"알 수 없는 target입니다. 사용 가능: {list(targets.keys())}")
                return

            running, pid = is_macro_running()
            if running:
                self._respond(200, f"이미 실행 중입니다 (PID {pid}).")
                return

            bat_path = targets[target]
            if not os.path.exists(bat_path):
                self._respond(500, f"배치파일을 찾을 수 없습니다: {bat_path}")
                return
            try:
                subprocess.Popen(
                    f'start "" "{bat_path}"',
                    cwd=os.path.dirname(bat_path),
                    shell=True
                )
                write_last_target(target)
                self._respond(200, f"'{target}' 매크로 시작 요청을 보냈습니다.")
                print(f"▶ [원격 시작] target={target}")
            except Exception as e:
                self._respond(500, f"실행 실패: {e}")

        elif parsed.path == "/stop":
            running, pid = is_macro_running()
            if not running:
                self._respond(200, "이미 정지 상태입니다.")
                return
            try:
                # 💡 부모 cmd.exe 창(있다면)까지 같이 닫기 위해, python.exe를 죽이기 전에 미리 부모 PID를
                # 조회해둔다(죽인 뒤엔 프로세스가 사라져 WMI 조회가 안 됨). 재시작에도 안 끊기는 저장값을
                # 우선 쓰고(실제로 아직 cmd.exe로 살아있는지 재확인), 없으면 구버전 호환용 라이브 조회로 폴백.
                parent_cmd_pid = read_cmd_pid_file()
                if parent_cmd_pid and not is_our_python_process(parent_cmd_pid, valid_images=("cmd.exe",)):
                    parent_cmd_pid = None
                if not parent_cmd_pid:
                    parent_cmd_pid = find_parent_cmd_pid(pid)
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5, creationflags=NO_WINDOW)
                if parent_cmd_pid:
                    subprocess.run(["taskkill", "/PID", str(parent_cmd_pid), "/F"], capture_output=True, timeout=5, creationflags=NO_WINDOW)
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
                if os.path.exists(CMD_PID_FILE):
                    os.remove(CMD_PID_FILE)
                self._respond(200, f"매크로(PID {pid})를 정지했습니다.")
                print(f"■ [원격 정지] PID={pid}" + (f" (콘솔창 PID={parent_cmd_pid}도 함께 종료)" if parent_cmd_pid else ""))
            except Exception as e:
                self._respond(500, f"정지 실패: {e}")

        elif parsed.path == "/status":
            running, pid = is_macro_running()
            self._respond(200, f"실행 중 (PID {pid})" if running else "정지 상태")

        elif parsed.path == "/dashboard":
            self._respond_html(200, render_dashboard_html(CONFIG["token"]))

        elif parsed.path == "/api/state":
            running, pid = is_macro_running()
            log_file, log_lines, log_started_at = get_recent_log_lines(15)
            self._respond_json(200, {
                "running": running,
                "pid": pid,
                "log_file": log_file,
                "log_lines": log_lines,
                "log_started_at": log_started_at,
            })

        else:
            self._respond(404, "not found")


def main():
    global CONFIG
    write_own_pid()
    CONFIG = load_or_create_config()

    if not discover_targets():
        print(f"⚠️ {PROJECT_ROOT} 에서 .bat 파일을 하나도 찾지 못했습니다.")
        print("   원격으로 시작할 배치파일을 프로젝트 루트 폴더(remote_control/의 부모 폴더)에 두어야 합니다.")
        input("\n아무 키나 누르면 종료합니다...")
        return

    bind_ip = get_tailscale_ip()
    dns_name = get_tailscale_dns_name()
    print_and_save_guide(CONFIG, bind_ip, dns_name)

    port = CONFIG.get("port", 8765)
    # 테일스케일 IP를 찾았으면 그 주소에만 바인딩(로컬 LAN 노출 최소화), 못 찾으면 0.0.0.0으로 폴백
    host = bind_ip if bind_ip else "0.0.0.0"
    try:
        server = http.server.HTTPServer((host, port), Handler)
    except OSError as e:
        print(f"⚠️ {host}:{port} 바인딩 실패({e}), 0.0.0.0으로 재시도합니다.")
        server = http.server.HTTPServer(("0.0.0.0", port), Handler)

    print(f"\n🚀 원격 제어 서버가 {host}:{port} 에서 대기 중입니다.")
    print('   (창이 보이는 상태로 실행 중이라면 창을 닫거나 Ctrl+C로 종료 / 백그라운드 실행 중이라면 "Stop Remote Control (Background).bat" 사용)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        try:
            if os.path.exists(SERVER_PID_PATH):
                os.remove(SERVER_PID_PATH)
        except Exception:
            pass


if __name__ == "__main__":
    main()
