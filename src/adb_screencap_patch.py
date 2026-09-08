# -*- coding: utf-8 -*-
# =====================================================================================
#  ADB 화면 캡처 패치 / 뮤뮤 디스플레이 구성 점검 (v1.20.0)
# =====================================================================================
#  🚨 [2026-09-08 실측 확정] 뮤뮤의 "앱 상주" 기능(설정: 디바이스 설정 - 기타 - "애플리케이션이
#  실행 중입니다", 중국어 원문 应用保活)이 켜져 있으면, 뮤뮤가 앱마다 별도의 안드로이드 디스플레이를
#  만든다. 이 상태에서는 두 가지가 동시에 깨진다:
#
#   (1) 캡처: 디스플레이가 2개 이상이면 안드15의 screencap이 PNG 데이터 앞에 347바이트짜리 경고문을
#       평문으로 먼저 뱉는다("[Warning] Multiple displays were found, but no display id was
#       specified! ..."). 앞머리가 5b 57 61 72 6e 69 6e 67 = ASCII "[Warning" 이라 PIL의
#       Image.open()이 첫 바이트부터 실패한다("cannot identify image file"). 실측상 이 상태에서는
#       연속 10회 캡처가 100% 전부 깨졌다.
#   (2) 입력: 게임이 별도 디스플레이(예: 논리 2번)로 밀려나는데, `input tap`은 지정이 없으면 기본
#       디스플레이(0번 = 안드로이드 홈 런처)로 간다. 실측 확인: 탭 한 번에 뮤뮤 스토어 검색창이 열렸다.
#
#  ⚠️ 그래서 "캡처만 게임 화면으로 돌려서 우회"하면 절대 안 된다 - 화면은 제대로 읽으면서 클릭은
#  전부 홈 화면으로 나가는, 매크로가 정상이라 착각한 채 안드로이드 홈을 마구 누르는 최악의 상태가
#  된다. 우회 대신 "앱 상주를 끄라"고 정확히 안내하고 멈추는 게 옳다(같은 게임의 다른 매크로인 WVD도
#  이 경고문을 감지하면 우회하지 않고 스크립트를 정지시킨다 - wvd-master/src/script.py:639,691).
#
#  이 모듈이 하는 일은 두 가지뿐이다:
#   - install_screencap_patch(): 만에 하나 경고문이 섞여 들어와도 이미지가 디코딩은 되도록,
#     PNG 시그니처 앞의 쓰레기를 잘라내는 안전망. ppadb의 Transport.screencap을 한 번 래핑한다
#     (device.screencap() 호출부가 6개 파일 44곳이라, 개별 치환은 CLAUDE.md가 경고한 "한 곳만
#     빠뜨려도 조용히 터지는" 패턴에 해당해서 메서드 래핑으로 전역 적용).
#   - check_display_configuration(): 디스플레이가 2개 이상이면 원인과 해결법을 정확히 찍고 False.
# =====================================================================================

import re

# PNG 파일 시그니처. 이 앞에 붙은 쓰레기(경고문 등)를 잘라내는 기준점.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# "Display 4619827820427265280 (HWC display 0): ..." 형태를 파싱
_DISPLAY_LINE_RE = re.compile(r"Display\s+(\d+)\s*\(HWC display\s+(\d+)\)")

_patch_installed = False
_original_screencap = None


def _strip_leading_garbage(raw):
    """PNG 시그니처 앞에 붙은 경고문 등을 잘라낸다.

    시그니처를 못 찾으면 원본 바이트를 그대로 돌려준다 - 호출부의 기존 예외 처리
    흐름(디코딩 실패 → 재시도/재부팅)이 그대로 동작하게 두기 위함.
    """
    if not raw:
        return raw
    data = bytes(raw)
    idx = data.find(PNG_SIGNATURE)
    if idx > 0:
        return data[idx:]
    return data


def _patched_screencap(self):
    return _strip_leading_garbage(_original_screencap(self))


def install_screencap_patch():
    """ppadb의 screencap을 래핑한다. 여러 번 호출해도 안전(idempotent)."""
    global _patch_installed, _original_screencap
    if _patch_installed:
        return
    try:
        from ppadb.command.transport import Transport
        _original_screencap = Transport.screencap
        Transport.screencap = _patched_screencap
        _patch_installed = True
    except Exception as patch_err:
        print(f"❌ [ADB 캡처 패치 실패] {patch_err} - 기존 캡처 방식으로 동작합니다.")


def check_display_configuration(device):
    """안드로이드 디스플레이가 1개인지 점검한다. 2개 이상이면 원인/해결법을 찍고 False.

    조회 자체가 실패하면(권한/명령 부재 등) True를 돌려준다 - 점검을 못 했다는 이유로 매크로를
    막지는 않는다.
    """
    try:
        out = device.shell("dumpsys SurfaceFlinger --display-id") or ""
    except Exception as query_err:
        print(f"⚠️ [디스플레이 점검 생략] 조회 실패({query_err}) - 점검 없이 진행합니다.")
        return True

    displays = _DISPLAY_LINE_RE.findall(out)
    if len(displays) <= 1:
        return True

    print("")
    print("=" * 78)
    print(f"🚨 [뮤뮤 설정 오류] 안드로이드 디스플레이가 {len(displays)}개 감지되었습니다. 매크로를 시작할 수 없습니다.")
    print("")
    print("   원인: 뮤뮤의 '앱 상주' 기능이 켜져 있으면 앱마다 별도의 화면을 만듭니다.")
    print("         이 상태에서는 매크로가 읽는 화면과 클릭이 나가는 화면이 서로 달라져,")
    print("         게임 대신 안드로이드 홈 화면을 마구 누르게 됩니다.")
    print("")
    print("   해결: 뮤뮤 [디바이스 설정] → [기타] → 맨 위 '애플리케이션이 실행 중입니다'를 끄세요.")
    print("         (설명이 '여러 애플리케이션이 유휴 상태일 때 동시에 백그라운드에서 실행'인 항목)")
    print("         끄신 뒤 뮤뮤를 완전히 종료했다가 다시 켜주세요.")
    print("=" * 78)
    print("")
    return False
