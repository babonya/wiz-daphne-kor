# ==============================================================================
# 📋 [원격 매크로 시작/정지 수신 서버]
# - 목적: 팀뷰어 로그인 없이, 테일스케일 사설망을 통해 폰 브라우저 북마크 탭 한 번으로
#         PC의 매크로를 시작/정지/상태확인 하기 위한 개인용 도구입니다.
# - 표준 라이브러리만 사용합니다 (pip install 추가 불필요).
# - 이 폴더(remote_control/)를 통째로 지워도 매크로 본체(src/main.py) 동작에는 전혀 지장이 없습니다.
# - 현재 버전: 1.17.1 (최초 도입)
# ==============================================================================
import glob
import http.server
import json
import os
import secrets
import subprocess
from urllib.parse import urlparse, parse_qs, quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.local.json")
PID_FILE = os.path.join(PROJECT_ROOT, "macro.pid")
GUIDE_PATH = os.path.join(SCRIPT_DIR, "설정안내.txt")

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


def get_tailscale_ip():
    # 테일스케일 CLI가 PATH에 없는 환경도 있어서, 실패해도 조용히 None 반환 (0.0.0.0 폴백)
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        out = result.stdout.strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


def print_and_save_guide(cfg, bind_ip):
    host = bind_ip or "<PC의 테일스케일 IP를 admin.tailscale.com에서 확인하세요>"
    port = cfg.get("port", 8765)
    token = cfg.get("token", "")
    lines = []
    lines.append("=" * 70)
    lines.append("📱 폰 크롬에서 '홈 화면에 추가'로 아래 URL을 그대로 등록하세요")
    lines.append("=" * 70)
    targets = discover_targets()
    if not targets:
        lines.append(f"⚠️ {PROJECT_ROOT} 에서 .bat 파일을 찾지 못했습니다. 시작 URL을 만들 수 없습니다.")
    for name in targets.keys():
        lines.append(f"▶ 시작 ({name}): http://{host}:{port}/start?target={quote(name)}&token={token}")
    lines.append(f"■ 정지        : http://{host}:{port}/stop?token={token}")
    lines.append(f"❔ 상태확인   : http://{host}:{port}/status?token={token}")
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


def is_our_python_process(pid):
    # taskkill 대상이 정말 python.exe가 맞는지 한 번 더 확인 (PID 재활용으로 엉뚱한 프로세스를 죽이는 사고 방지)
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        out = result.stdout.strip()
        if not out or out.upper().startswith("INFO:"):
            return False
        image_name = out.split(",")[0].strip('"')
        return image_name.lower() == "python.exe"
    except Exception:
        return False


def is_macro_running():
    pid = read_pid()
    if pid is None:
        return False, None
    if is_our_python_process(pid):
        return True, pid
    return False, None


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 기본 접속 로그는 생략 (필요시 여기서 print로 바꾸면 됨)

    def _respond(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

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
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5)
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
                self._respond(200, f"매크로(PID {pid})를 정지했습니다.")
                print(f"■ [원격 정지] PID={pid}")
            except Exception as e:
                self._respond(500, f"정지 실패: {e}")

        elif parsed.path == "/status":
            running, pid = is_macro_running()
            self._respond(200, f"실행 중 (PID {pid})" if running else "정지 상태")

        else:
            self._respond(404, "not found")


def main():
    global CONFIG
    CONFIG = load_or_create_config()

    if not discover_targets():
        print(f"⚠️ {PROJECT_ROOT} 에서 .bat 파일을 하나도 찾지 못했습니다.")
        print("   원격으로 시작할 배치파일을 프로젝트 루트 폴더(remote_control/의 부모 폴더)에 두어야 합니다.")
        input("\n아무 키나 누르면 종료합니다...")
        return

    bind_ip = get_tailscale_ip()
    print_and_save_guide(CONFIG, bind_ip)

    port = CONFIG.get("port", 8765)
    # 테일스케일 IP를 찾았으면 그 주소에만 바인딩(로컬 LAN 노출 최소화), 못 찾으면 0.0.0.0으로 폴백
    host = bind_ip if bind_ip else "0.0.0.0"
    try:
        server = http.server.HTTPServer((host, port), Handler)
    except OSError as e:
        print(f"⚠️ {host}:{port} 바인딩 실패({e}), 0.0.0.0으로 재시도합니다.")
        server = http.server.HTTPServer(("0.0.0.0", port), Handler)

    print(f"\n🚀 원격 제어 서버가 {host}:{port} 에서 대기 중입니다. (창을 닫거나 Ctrl+C로 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")


if __name__ == "__main__":
    main()
