# -*- coding: utf-8 -*-
# 매크로 단일 실행 보장(윈도우 이름 있는 뮤텍스).
# 🚨 [2026-09-25 실전 확인] 재시작 주체가 둘(main.py의 os.execv 자체재시작 + .bat 슈퍼바이저)인데 서로
# 조율 없이 macro.pid 파일로 생존을 추측하다 보니, 추측이 틀릴 때마다 매크로가 하나씩 더 떠서 최대 5개가
# 동시에 같은 화면을 두드렸다(logs 2026-09-24 20:54~22:59). 이 잠금으로 "하나만 실행"을 확률이 아니라
# 보장으로 만든다 - 두 번째 인스턴스는 잠금을 못 잡으면 스스로 종료한다.
# - 프로세스가 어떤 식으로 죽든(크래시/강제종료) 윈도우가 잠금을 자동으로 풀어준다(WAIT_ABANDONED).
# - os.execv 자체재시작의 새 프로세스는 부모가 끝나며 잠금을 놓을 때까지 잠깐 기다렸다가 넘겨받는다.
import os
import sys

MUTEX_NAME = "Local\\WizDaphneMacroSingleInstance"
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102

_mutex_handle = None  # 프로세스가 살아 있는 동안 계속 쥐고 있어야 하므로 전역으로 보관


def acquire_single_instance_lock(wait_seconds=15.0):
    """잠금을 잡으면 True, 다른 매크로가 이미 실행 중이라 못 잡으면 False."""
    global _mutex_handle
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        # 잠금 자체를 못 만드는 예외 상황에선 매크로를 막지 않는다(예전과 동일하게 동작).
        return True
    result = kernel32.WaitForSingleObject(handle, int(wait_seconds * 1000))
    if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
        _mutex_handle = handle
        return True
    return False


def enforce_single_instance_or_exit(wait_seconds=15.0):
    if not acquire_single_instance_lock(wait_seconds):
        # 로그 엔진(DoubleWriter) 가동 전이라 cp949 콘솔에 그대로 찍힌다 - 이모지 금지, 출력 실패도 무시.
        try:
            print(f"[단일 실행 가드] 다른 매크로가 이미 실행 중이라 이 인스턴스(PID {os.getpid()})는 종료합니다. "
                  f"({wait_seconds:.0f}초 기다려도 잠금이 풀리지 않음)")
        except Exception:
            pass
        sys.exit(0)
