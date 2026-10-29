"""윤곽선 글자 줄(글꼴 없이 도형으로 그린 발문)을 Tesseract로 읽는다.

- Tesseract 실행 파일: 환경 변수 PDF2HWPX_TESSERACT, PATH, Windows 기본 설치 위치 순서.
- 언어 모델(kor, 번호·[A] 표시를 다시 읽는 eng): 환경 변수 PDF2HWPX_TESSDATA, %LOCALAPPDATA%\\pdf2hwpx\\tessdata,
  없으면 Tesseract 기본 위치(Ubuntu: apt install tesseract-ocr tesseract-ocr-kor, eng는 기본 포함).
- 여러 줄을 세로로 이어 붙인 그림 한 장으로 한 번에 읽고(실행 횟수를 줄임), 글자 상자 좌표를 원래 줄로 되돌린다.
- 없거나 실패하면 None: 호출하는 쪽은 그 줄을 그림으로 둔다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import pymupdf as fitz

ZOOM = 4.0  # 줄 그림 배율(약 290dpi)
GAP_PX = 40  # 이어 붙인 줄 사이 빈칸(px)
LOW_CONF = 60.0  # 이보다 낮은 확신도의 글자는 '확인 필요'


@dataclass
class OcrChar:
    c: str
    x0: float  # 원문 좌표(pt)
    y0: float
    x1: float
    y1: float
    conf: float
    word: int = 0  # 같은 OCR 단어(글자 상자는 단어 상자를 나눈 것)


def _exe() -> Optional[str]:
    for cand in (os.environ.get("PDF2HWPX_TESSERACT"), shutil.which("tesseract"),
                 r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
        if cand and os.path.isfile(cand):
            return cand
    return None


def _tessdata() -> Optional[str]:
    for cand in (os.environ.get("PDF2HWPX_TESSDATA"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "pdf2hwpx", "tessdata")):
        if cand and os.path.isfile(os.path.join(cand, "kor.traineddata")):
            return cand
    return None


def _cmd() -> list[str]:
    exe = _exe()
    cmd = [exe] if exe else []
    data = _tessdata()
    return cmd + (["--tessdata-dir", data] if data and cmd else [])


@lru_cache(maxsize=1)
def _langs() -> frozenset:
    cmd = _cmd()
    if not cmd or os.environ.get("PDF2HWPX_NO_OCR"):
        return frozenset()
    try:
        r = subprocess.run(cmd + ["--list-langs"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(r.stdout.decode("utf-8", "replace").split())


def available() -> bool:
    """Tesseract와 한국어 모델이 있는지(한 번만 확인)."""
    return "kor" in _langs()


def read_rows(page: fitz.Page, rects: list[tuple[float, float, float, float]],
              masks: list[list[tuple[float, float, float, float]]], allow: str = "") -> Optional[list[list[OcrChar]]]:
    """쪽의 줄 영역들을 읽어 줄마다 글자 목록(원문 좌표). masks: 줄마다 흰색으로 지울 영역(진짜 글자가 이미 있는 곳,
    원문자는 잉크가 글자 상자보다 조금 커서 1.5pt 넓게). allow: 이 글자들만(문제 번호·[A] 표시를 다시 읽을 때)."""
    lang = "eng" if allow else "kor"  # 한국어 모델은 글자를 좁혀 주면 영문 대문자를 내지 못한다
    if not rects or lang not in _langs():
        return None
    pixes = []
    for r, ms in zip(rects, masks):
        pix = page.get_pixmap(clip=fitz.Rect(r), matrix=fitz.Matrix(ZOOM, ZOOM), colorspace=fitz.csGRAY, alpha=False)
        for m in ms:
            ir = fitz.IRect(int((m[0] - 1.5 - r[0]) * ZOOM), int((m[1] - 1.5 - r[1]) * ZOOM),
                            int((m[2] + 1.5 - r[0]) * ZOOM), int((m[3] + 1.5 - r[1]) * ZOOM)) & pix.irect
            if not ir.is_empty:
                pix.set_rect(ir, (255,))
        pixes.append(pix)
    # 세로로 이어 붙인 한 장
    width = max(p.width for p in pixes) + 2 * GAP_PX
    offsets, y = [], GAP_PX
    for p in pixes:
        offsets.append(y)
        y += p.height + GAP_PX
    sheet = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, width, y), False)
    sheet.set_rect(sheet.irect, (255,))
    for p, oy in zip(pixes, offsets):
        p.set_origin(GAP_PX, oy)
        sheet.copy(p, p.irect)
    try:
        opts = ["-l", lang] + (["-c", f"tessedit_char_whitelist={allow}"] if allow else [])
        r = subprocess.run(_cmd() + ["stdin", "stdout", *opts, "--psm", "6", "-c", "tessedit_create_tsv=1"],
                           input=sheet.tobytes("png"), capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    # 줄마다 Tesseract 글줄별로 모은다(큰 번호 때문에 한 줄을 위아래 두 글줄로 겹쳐 읽기도 한다: 가장 잘 읽힌 것만)
    found: list[dict] = [{} for _ in rects]
    for word, line in enumerate(r.stdout.decode("utf-8", "replace").splitlines()[1:]):
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        key = (f[2], f[3], f[4])  # block, par, line
        left, top, w, h, conf, text = int(f[6]), int(f[7]), int(f[8]), int(f[9]), float(f[10]), f[11].strip()
        cy = top + h / 2
        k = next((k for k, (p, oy) in enumerate(zip(pixes, offsets)) if oy - GAP_PX / 2 <= cy <= oy + p.height + GAP_PX / 2), None)
        if k is None:
            continue
        rx0, ry0 = rects[k][0], rects[k][1]
        x0 = rx0 + (left - GAP_PX) / ZOOM
        y0 = ry0 + (top - offsets[k]) / ZOOM
        cw = w / ZOOM / len(text)
        for i, c in enumerate(text):  # 글자 상자는 단어 상자를 글자 수로 나눈다(한글은 대부분 한 글자씩 나온다)
            found[k].setdefault(key, []).append(OcrChar(c, x0 + i * cw, y0, x0 + (i + 1) * cw, y0 + h / ZOOM, conf, word))
    out = []
    for lines in found:
        # 잘 읽힌 글줄부터, 이미 고른 글줄과 가로로 겹치지 않는 것만(좌우로 나뉜 글줄은 합치고, 겹쳐 읽은 것은 버린다)
        got: list[OcrChar] = []
        spans: list[tuple[float, float]] = []
        for cs in sorted(lines.values(), key=lambda cs: -sum(max(0.0, ch.conf) for ch in cs)):
            a, b = min(ch.x0 for ch in cs), max(ch.x1 for ch in cs)
            if all(min(b, y) - max(a, x) <= 0.3 * min(b - a, y - x) for x, y in spans):
                got += cs
                spans.append((a, b))
        out.append(sorted(got, key=lambda ch: ch.x0))
    return out


# 시험 발문에서 자주 틀리게 읽는 것: 맨 앞 '윗글'(받침 ㅅ이 작아 '워글'·'원글'로)
_WITGEUL = re.compile(r"^(\d{1,2}\.)[워원윈왼웟웠윘](?=글)")


def fix_chars(chars: list[OcrChar]) -> list[OcrChar]:
    """줄 하나의 글자 교정. 번호 뒤 군더더기 점("3.。", "1..")은 빼고, 따옴표는 한국어 시험지의 홑따옴표 ‘ ’로."""
    chars = [ch for k, ch in enumerate(chars) if not (ch.c in "。,·." and k > 0 and chars[k - 1].c == "." and k <= 3)]
    text = "".join(ch.c for ch in chars)
    m = _WITGEUL.match(text)
    if m:
        chars[m.end(1)].c = "윗"
    for k, ch in enumerate(chars):  # 단어 앞에 띄어 붙은 ':'는 여는 따옴표를 잘못 읽은 것("：음악 해석’")
        nxt = chars[k + 1] if k + 1 < len(chars) else None
        if ch.c in ":：" and nxt is not None and "가" <= nxt.c <= "힣"                 and (k == 0 or ch.x0 - chars[k - 1].x1 > 0.25 * (ch.y1 - ch.y0)):
            ch.c = "'"
    for k, ch in enumerate(chars):  # '<보기>'의 '<'를 따옴표로 읽은 것
        if ch.c in "“\"'‘`" and "".join(c.c for c in chars[k + 1:k + 4]).startswith("보기")                 and any(c.c == ">" for c in chars[k + 3:k + 6]):
            ch.c = "<"
    opening = True  # 줄 안의 따옴표는 여는 것과 닫는 것이 번갈아 나온다
    for k, ch in enumerate(chars):
        nxt = chars[k + 1] if k + 1 < len(chars) else None
        if ch.c in ":：" and not opening and nxt is not None and "가" <= nxt.c <= "힣":
            ch.c = "'"  # 닫는 따옴표를 ':'로 읽은 것("‘아리스토텔레스:의")
        if ch.c in "“\"'‘’”`":
            ch.c = "‘" if opening else "’"
            opening = not opening
    return chars
