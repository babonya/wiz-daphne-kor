# -*- coding: utf-8 -*-
# ==============================================================================
# 📋 [공용] 화면 캡처 - 원시(raw) 방식 우선, PNG 방식은 실패 시 폴백으로만 사용 (v1.21.0)
# ==============================================================================
# 🚨 [2026-09-09 실측 확정] 지금까지 전 파일이 `screencap -p`(PNG 인코딩)로 화면을 받아 PIL로 다시
# 디코드하고 있었는데, 실측 결과 이 방식이 평균 1.60초가 걸렸다. 원시(비압축) 방식으로 받으면
# 0.63초 - 약 2.54배 빠르다(WVD도 이 방식을 씀 - wvd-master/src/script.py:606). 에뮬레이터가
# PNG로 압축하는 CPU 비용이, 압축 안 한 원본을 더 크게 보내는 것보다 훨씬 비쌌다.
#
# 검증한 것들(전부 실측/결정적 테스트로 확인, 추측 없음):
#   - 픽셀 포맷은 fmt=1(RGBA_8888) - PNG 경로도 항상 4채널 RGBA였으므로(np.array(Image.open(...))가
#     .convert('RGB') 없이 그대로 쓰이고 있었음) shape/dtype이 기존과 완전히 동일하다.
#   - 알파 채널 값은 PNG(항상 255)와 원시(0/255 혼재)가 다르지만, 코드 전체에서 알파를 실제로
#     읽는 곳이 한 곳도 없다(전부 [:,:,:3]으로 잘라내거나 COLOR_RGB2GRAY로 변환 - 이 변환이
#     4채널 입력에서 알파를 완전히 무시함을 결정적 테스트로 확인).
#   - chest_opener.py만 cv2.imdecode(IMREAD_COLOR)+COLOR_BGR2RGB로 3채널을 직접 만드는 별도 경로를
#     쓰는데, 합성 이미지(R=100/G=150/B=200)로 PIL 디코드와 완전히 동일한 채널 순서임을 확인했다.
#
# 설계: capture_screen_bytes()가 "바이트를 가져오는" 역할만 하고(device.screencap()의 완전한
# 대체품 - 원시 실패 시 자동으로 기존 PNG 경로로 폴백), decode_screen_bytes()가 "그 바이트를
# numpy 배열로 바꾸는" 역할만 한다. 이렇게 둘로 나누면 기존 호출부의 `raw = device.screencap()` /
# `if raw:` / `if not raw:` 같은 주변 로직을 하나도 안 건드리고 두 함수만 갈아끼울 수 있다.
# capture_screen()은 둘을 합친 편의 함수 - 기존 `np.array(Image.open(io.BytesIO(device.screencap())))`
# 한 줄짜리 자리를 그대로 대체한다.
# ==============================================================================
import io
import struct

import numpy as np
from PIL import Image

_RAW_HEADER = struct.Struct("<III")  # width, height, format - 전부 4바이트 부호없는 정수, 리틀엔디안
_RAW_FORMAT_RGBA_8888 = 1  # 안드로이드 screencap 원시 출력의 표준 포맷 코드(실측 확인)
# 💡 PNG 바이트를 원시 헤더로 잘못 해석해도 안전하다 - PNG 시그니처 앞 4바이트(0x89 'P' 'N' 'G')를
# 리틀엔디안 uint32로 읽으면 약 12억이 나와 아래 width<=4096 검사에 자연히 걸러진다. 그래서 별도
# PNG 시그니처 검사가 필요 없다.


def capture_screen_bytes(device):
    """디바이스 화면을 캡처해 바이트로 반환한다 - device.screencap()의 완전한 대체품.

    원시(raw) 방식을 우선 시도하고, 예외가 나면(연결 문제 등) 조용히 기존 PNG 방식으로 폴백한다.
    반환값의 형식(원시/PNG)은 decode_screen_bytes()가 헤더를 보고 알아서 구분하므로, 호출부는
    이 함수를 device.screencap()과 완전히 동일하게(같은 None/빈바이트 가능성 포함) 다루면 된다.
    """
    try:
        conn = device.create_connection()
        with conn:
            conn.send("exec:/system/bin/screencap")
            raw = bytes(conn.read_all())
        if len(raw) >= 12:
            return raw
    except Exception:
        pass
    return device.screencap()


def decode_screen_bytes(raw):
    """capture_screen_bytes()(또는 device.screencap())가 반환한 바이트를 numpy 배열로 디코드한다.

    반환 shape/dtype은 기존 np.array(Image.open(io.BytesIO(raw)))와 완전히 동일하다
    (H, W, 4) uint8 RGBA - 호출부 코드를 하나도 안 바꿔도 된다.
    raw가 None이거나 손상됐으면 기존과 마찬가지로 예외를 던진다(호출부의 기존 try/except가 그대로
    잡아내도록 - 조용히 다른 값으로 대체하지 않는다).
    """
    if raw is None:
        raise ValueError("캡처 데이터가 없습니다(None)")
    if len(raw) >= 12:
        width, height, fmt = _RAW_HEADER.unpack_from(raw, 0)
        if fmt == _RAW_FORMAT_RGBA_8888 and 0 < width <= 4096 and 0 < height <= 4096:
            expected = width * height * 4
            pixels = raw[12:12 + expected]
            if len(pixels) == expected:
                return np.frombuffer(pixels, dtype=np.uint8).reshape((height, width, 4)).copy()
    # 원시 헤더가 아니거나(폴백으로 받은 PNG) 픽셀 길이가 안 맞으면 PNG로 간주해 기존 방식으로 디코드.
    # 그래도 실패하면(진짜 손상된 데이터) 여기서 예외가 그대로 전파된다 - 기존 동작과 동일.
    return np.array(Image.open(io.BytesIO(raw)))


def capture_screen(device):
    """캡처+디코드를 한 번에 - 기존 `np.array(Image.open(io.BytesIO(device.screencap())))` 자리를
    그대로 대체한다."""
    return decode_screen_bytes(capture_screen_bytes(device))
